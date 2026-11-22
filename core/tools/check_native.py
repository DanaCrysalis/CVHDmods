"""Compile every hod-mods native source with the recomp build's own flags into a
scratch folder, without touching the recomp tree; optionally link the exe from
the existing build's other objects plus these.

  python core/tools/check_native.py [--link] [--only NAME] [--out DIR]
  HOD_UNITS=shield_rod,refectio python core/tools/check_native.py --link   link only these sections (+ hub)
  HOD_CLEAN_SRC=<dir>  a folder holding only the generated headers, to prove no
                       include resolves to an old in-place copy in .setup/package/src/src

Needs a configured recomp build (<game>/.setup/package/src/out/build/win-amd64-release)
for its compile flags; with --link, its objects. Catacombs module sources are
compiled only when that build has their module targets (a POISONWORM build).
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import concurrent.futures as cf, os, re, subprocess, sys
from pathlib import Path

GAME = hodpaths.GAME
REPO = hodpaths.REPO
SRC = GAME / ".setup/package/src"
BUILD = SRC / "out/build/win-amd64-release"
CLANG = GAME / ".setup/toolchain/llvm/bin/clang++.exe"
OUT = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else hodpaths.WORK / "build" / "check_native"
OUT.mkdir(parents=True, exist_ok=True)

ninja = (BUILD / "build.ninja").read_text(errors="replace")
def edge_vars(obj_suffix):
    i = ninja.index(obj_suffix)
    block = ninja[i:ninja.index("\n\n", i)]
    v = {}
    for line in block.splitlines()[1:]:
        k, _, val = line.strip().partition(" = ")
        v[k] = val
    return v

def words(s):  # split a ninja command-line fragment, keeping quoted paths
    return [w.replace('"', '') for w in re.findall(r'(?:[^\s"]+|"[^"]*")+', s)]

exe = edge_vars("CMakeFiles/harmonyrecomp.dir/src/shield_rod.cpp.obj:")
dll = edge_vars("CMakeFiles/harmonyrecomp_dllTest12.dir/src/nathan_dss.cpp.obj:")
defines = [d for d in words(exe["DEFINES"]) if not d.startswith("-DHARMONYRECOMP_POISONWORM")]
flags = [
    *[f"-DHODMOD_{n}=1" for n in ("SHIELD_ROD", "FAMILIARS", "GLYPHS", "NATHAN", "CATACOMBS")],
]
exe_inc = []
for d in ["core/runtime", "mods/shield-rod/src", "mods/familiars/src", "mods/glyphs/src", "mods/nathan/src"]:
    exe_inc += ["-I", str(REPO / d)]
# A clean recomp src/ folder holds only stock files and the generated headers;
# HOD_CLEAN_SRC names a folder with just those headers (the live tree may still
# hold old copies of mod sources that would hide a missing include). scripts/
# stands in for src/ so "../generated/<module>/..." still resolves.
CLEAN = Path(os.environ.get("HOD_CLEAN_SRC") or SRC / "src")
def no_src_src(ws):
    out, skip = [], False
    for w in ws:
        if skip: skip = False; continue
        if w.startswith("-I") and w.rstrip("/").replace("\\", "/").endswith("/src/src"): continue
        out.append(w)
    return out
generated_root = ["-I", str(CLEAN), "-I", str(SRC / "scripts")]
exe_cmd = [str(CLANG), *defines, *flags, *exe_inc, *no_src_src(words(exe["INCLUDES"])), *generated_root, *words(exe["FLAGS"])]

units = {
    "hod_hub": REPO / "core/runtime/hod_hub.cpp",
    "hod_mods": REPO / "core/runtime/hod_mods.cpp",
    "hod_overrides": REPO / "core/runtime/hod_overrides.cpp",
    "equip_card_icon": REPO / "core/runtime/equip_card_icon.cpp",
    "shield_rod": REPO / "mods/shield-rod/src/shield_rod.cpp",
    "alucard_familiar": REPO / "mods/familiars/src/alucard_familiar.cpp",
    "refectio": REPO / "mods/glyphs/src/refectio.cpp",
    "arma_custos": REPO / "mods/glyphs/src/arma_custos.cpp",
    "nathan_dss_damage": REPO / "mods/nathan/src/nathan_dss_damage.cpp",
}
def module_cmd(target, folder):
    v = edge_vars(f"CMakeFiles/{target}.dir/")
    return [str(CLANG), *words(v["DEFINES"]), "-I", str(REPO / folder), "-I", str(REPO / "core/runtime"),
            *no_src_src(words(v["INCLUDES"])), *generated_root, *words(v["FLAGS"])]
module_units = [
    ("nathan_dss", "harmonyrecomp_dllTest12", "mods/nathan/src", "nathan_dss.cpp"),
    ("poison_worm_module", "harmonyrecomp_DLL_Cm050", "mods/catacombs/src", "poison_worm_module.cpp"),
    ("poison_worm_shot_module", "harmonyrecomp_dllshotCm050w", "mods/catacombs/src", "poison_worm_shot_module.cpp"),
    ("poison_worm_soul_module", "harmonyrecomp_dllshotSoulCm050", "mods/catacombs/src", "poison_worm_soul_module.cpp"),
    ("cerberus_module", "harmonyrecomp_DLL_Cm068", "mods/catacombs/src", "cerberus_module.cpp"),
    ("cerberus_shot_module", "harmonyrecomp_dllshotCm068", "mods/catacombs/src", "cerberus_shot_module.cpp"),
    ("cerberus_soul_module", "harmonyrecomp_dllshotSoulCm068", "mods/catacombs/src", "cerberus_soul_module.cpp"),
    ("cerberus_spell_module", "harmonyrecomp_dllshotLearnCm068", "mods/catacombs/src", "cerberus_spell_module.cpp"),
    ("skeleton_bomber_module", "harmonyrecomp_DLL_Cm007", "mods/catacombs/src", "skeleton_bomber_module.cpp"),
    ("skeleton_bomber_shot_module", "harmonyrecomp_dllshotCm007", "mods/catacombs/src", "skeleton_bomber_shot_module.cpp"),
    ("skeleton_bomber_soul_module", "harmonyrecomp_dllshotSoulCm007", "mods/catacombs/src", "skeleton_bomber_soul_module.cpp"),
]
only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None

def compile_one(name, src, cmd):
    obj = OUT / f"{name}.obj"
    r = subprocess.run([*cmd, "-c", str(src), "-o", str(obj)], capture_output=True, text=True)
    return name, r.returncode, (r.stdout + r.stderr)[-6000:]

jobs = [(n, s, exe_cmd) for n, s in units.items()]
jobs += [(n, REPO / folder / f, module_cmd(t, folder)) for n, t, folder, f in module_units if f"CMakeFiles/{t}.dir/" in ninja]
if only:
    jobs = [j for j in jobs if j[0] == only]
failed = 0
with cf.ThreadPoolExecutor(6) as pool:
    for name, rc, log in pool.map(lambda j: compile_one(*j), jobs):
        print(f"{'OK  ' if rc == 0 else 'FAIL'} {name}")
        if rc:
            failed += 1
            print(log)
if failed:
    sys.exit(1)

if "--link" in sys.argv:
    # Link harmonyrecomp.exe from the build's other objects plus ours.
    i = ninja.index("build harmonyrecomp.exe:")
    line = ninja[i:ninja.index("\n", i)]
    inputs = line.split(":", 1)[1].split("||")[0].split("|")[0]
    objs = [o.replace("$ ", " ").replace("$:", ":") for o in re.findall(r"(?:\$ |\$:|[^ ])+", inputs.replace("CXX_EXECUTABLE_LINKER__harmonyrecomp_Release", ""))]
    objs = [o for o in objs if o.endswith(".obj")]
    mod_names = {"shield_rod", "refectio", "arma_custos", "equip_card_icon", "alucard_familiar", "nathan_dss_damage", "shield_rod_bridge"}
    keep = [str(BUILD / o) for o in objs if Path(o).stem.replace(".cpp", "") not in mod_names]
    chosen = os.environ.get("HOD_UNITS")
    ours = [str(OUT / f"{n}.obj") for n in units if not chosen or n in chosen.split(",") or n.startswith("hod_")]
    link = edge_vars("build harmonyrecomp.exe:")
    rsp = OUT / "link.rsp"
    rsp.write_text("\n".join('"' + p.replace("\\", "/") + '"' for p in keep + ours) + "\n" + link["LINK_LIBRARIES"] + "\n")
    cmd = [str(CLANG), "-nostartfiles", "-nostdlib", *words(link["FLAGS"]),
           *[w for w in words(link["LINK_FLAGS"]) if not w.startswith("/MAP")],
           "-Xlinker", f"/MAP:{OUT / 'harmonyrecomp.map'}",
           f"@{rsp}", "-o", str(OUT / "harmonyrecomp.exe"), "-Xlinker", f"/implib:{OUT / 'harmonyrecomp.lib'}",
           "-Xlinker", f"/pdb:{OUT / 'harmonyrecomp.pdb'}"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=BUILD)
    print("LINK", "OK" if r.returncode == 0 else "FAIL")
    if r.returncode:
        print((r.stdout + r.stderr)[-8000:])
        sys.exit(1)
