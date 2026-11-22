"""Prepare a HarmonyRecomp v0.6.0 source tree (<game>/.setup/package) for hod-mods.

  python core/tools/setup_recomp.py --check        report each patched file's state
  python core/tools/setup_recomp.py                apply core/recomp/harmonyrecomp-v0.6.0.patch
  python core/tools/setup_recomp.py --from-legacy  first put back the stock copy of any file the
                                                   older in-place mod builds changed (from the
                                                   setup's own download), then apply
  python core/tools/setup_recomp.py --tidy         also move the old in-place mod sources out of
                                                   .setup/package/src/src (they now live in this repo)
  python core/tools/setup_recomp.py --restore <backup folder>

The patch only hooks the recomp's CMakeLists.txt into core/cmake/hodmods.cmake
and carries three small fixes (build.py mods/ folder, dlc.cpp long package
names, test-install user data). Every file it replaces is backed up first under
<work>/backups/recomp_<time>/ with a manifest, and a file that is neither the
stock v0.6.0 copy nor already patched is left alone unless --from-legacy.
Then configure with -DHODMODS_ROOT=<this repo> (core/tools/rebuild_recomp.py does).
"""
import argparse
import datetime
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

import hodpaths

PACKAGE = hodpaths.GAME / ".setup" / "package"
PATCH = hodpaths.REPO / "core" / "recomp" / "harmonyrecomp-v0.6.0.patch"
DOWNLOAD = hodpaths.GAME / ".setup" / "downloads" / "harmonyrecomp-package.zip"
# LF-normalized SHA-256 of the stock v0.6.0 files the patch touches.
STOCK = {
    "src/CMakeLists.txt": "2a1ff7c3d8dd9e129717427b329154b70e998423d0d3414f6932fcff4dfb9682",
    "src/scripts/build.py": "0422c17d6ae107facfd16701d3977afaa9f79d24f3401c869f3406a134f86e31",
    "src/src/dlc.cpp": "0817cb18e5241452873ac0f68582dedd6393752eb2749991934f606af12b016b",
    "src/src/harmonyrecomp_app.h": "00fbc2dfe7950aba58a4a3fd91dd871d4f1de43d5b355379096d064de1beee94",
}
# Mod sources the older in-place builds kept in the recomp's src/ folder.
# Generated headers (*_balance.h, *_assets.h, ...) stay: the tools write them there.
LEGACY_SOURCES = [
    "alucard_familiar.cpp", "alucard_familiar.h", "arma_custos.cpp", "arma_custos.h", "cerberus_module.cpp",
    "cerberus_orb_spell.h", "cerberus_shot_module.cpp", "cerberus_soul_module.cpp", "cerberus_spell_module.cpp",
    "equip_card_icon.cpp", "hurt_record_guest.h", "nathan_audio_guest.h", "nathan_card_swap_guest.h",
    "nathan_dss.cpp", "nathan_dss_combinations.h", "nathan_dss_damage.cpp", "nathan_dss_guest.h",
    "nathan_dss_state.h", "nathan_progress_guest.h", "nathan_projectiles_guest.h", "nathan_tackle_guest.h",
    "nathan_tackle_state.h", "nathan_uranus_guest.h", "poison_worm_module.cpp", "poison_worm_shot_module.cpp",
    "poison_worm_soul_module.cpp", "refectio.cpp", "refectio.h", "shield_rod.cpp", "shield_rod.h",
    "shield_rod_bridge.cpp", "skeleton_bomber_module.cpp", "skeleton_bomber_shot_module.cpp",
    "skeleton_bomber_soul_module.cpp",
]


def lf_sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def parse_patch(text: str) -> dict:
    """{path: [(old_start, [(tag, line), ...]), ...]} from a unified diff."""
    files, current, hunk = {}, None, None
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith("+++ "):
            current = line[4:].split("\t")[0]
            current = current[2:] if current.startswith("b/") else current
            files[current] = []
        elif line.startswith("--- "):
            continue
        elif line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", line)
            hunk = (int(m.group(1)), [])
            files[current].append(hunk)
        elif hunk is not None and line[:1] in (" ", "+", "-"):
            hunk[1].append((line[0], line[1:]))
        elif hunk is not None and line == "":
            continue
    return files


def apply_hunks(data: bytes, hunks) -> bytes:
    crlf = b"\r\n" in data
    lines = data.decode("utf-8").replace("\r\n", "\n").split("\n")
    out, pos = [], 0
    for old_start, body in hunks:
        at = old_start - 1 if old_start else 0
        out += lines[pos:at]
        for tag, text in body:
            if tag in " -":
                if lines[at] != text:
                    raise ValueError(f"line {at + 1}: expected {text!r}, found {lines[at]!r}")
                at += 1
            if tag in " +":
                out.append(text)
        pos = at
    out += lines[pos:]
    result = "\n".join(out)
    return (result.replace("\n", "\r\n") if crlf else result).encode("utf-8")


def patched_hashes(patch) -> dict:
    stock = zipfile.ZipFile(DOWNLOAD) if DOWNLOAD.is_file() else None
    out = {}
    for rel, hunks in patch.items():
        if stock:
            out[rel] = lf_sha(apply_hunks(stock.read(rel), hunks))
    return out


def state(rel, data, patched) -> str:
    h = lf_sha(data)
    if h == STOCK[rel]:
        return "stock"
    if patched.get(rel) == h:
        return "patched"
    return "changed (not stock v0.6.0, not this patch)"


def backup_dir() -> Path:
    d = hodpaths.WORK / "backups" / ("recomp_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    d.mkdir(parents=True, exist_ok=False)
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--from-legacy", action="store_true")
    ap.add_argument("--tidy", action="store_true")
    ap.add_argument("--restore", type=Path)
    args = ap.parse_args()

    if args.restore:
        manifest = json.loads((args.restore / "manifest.json").read_text())
        for rel in manifest["files"]:
            src = args.restore / "files" / rel
            dst = PACKAGE / rel if not rel.startswith("moved/") else PACKAGE / "src/src" / Path(rel).name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print("restored", dst.relative_to(hodpaths.GAME))
        return 0

    patch = parse_patch(PATCH.read_text(encoding="utf-8"))
    assert set(patch) == set(STOCK), sorted(patch)
    patched = patched_hashes(patch)
    states = {rel: state(rel, (PACKAGE / rel).read_bytes(), patched) for rel in STOCK}
    for rel, s in states.items():
        print(f"{rel}: {s}")
    legacy_left = [n for n in LEGACY_SOURCES if (PACKAGE / "src/src" / n).is_file()]
    if legacy_left:
        print(f"src/src still holds {len(legacy_left)} old in-place mod sources (--tidy moves them out)")
    if args.check:
        return 0 if all(s == "patched" for s in states.values()) else 1

    todo = [rel for rel, s in states.items() if s != "patched"]
    blocked = [rel for rel in todo if states[rel] != "stock" and not args.from_legacy]
    if blocked:
        print("Refusing: " + ", ".join(blocked) + " differ from stock v0.6.0. Re-run with --from-legacy to put "
              "back the stock copy from " + str(DOWNLOAD.relative_to(hodpaths.GAME)) + " first (backed up).")
        return 1
    if not todo and not (args.tidy and legacy_left):
        print("Nothing to do.")
        return 0
    backup = backup_dir()
    saved = []
    stock_zip = zipfile.ZipFile(DOWNLOAD) if any(states[r] != "stock" for r in todo) else None
    for rel in todo:
        target = PACKAGE / rel
        (backup / "files" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup / "files" / rel)
        saved.append(rel)
        base = target.read_bytes() if states[rel] == "stock" else stock_zip.read(rel)
        if states[rel] != "stock" and lf_sha(base) != STOCK[rel]:
            raise SystemExit(f"{DOWNLOAD}: {rel} is not the stock v0.6.0 file")
        if b"\r\n" in target.read_bytes() and b"\r\n" not in base:
            base = base.replace(b"\n", b"\r\n")
        target.write_bytes(apply_hunks(base, patch[rel]))
        print("patched", rel)
    if args.tidy:
        for n in legacy_left:
            src = PACKAGE / "src/src" / n
            dst = backup / "files" / "moved" / n
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            saved.append(f"moved/{n}")
        print(f"moved {len(legacy_left)} old mod sources to {backup}")
    (backup / "manifest.json").write_text(json.dumps({"files": saved}, indent=1) + "\n")
    print(f"backup: {backup}  (undo: setup_recomp.py --restore \"{backup}\")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
