"""Check the repository before a commit or release: no game files, no large
binaries, no local paths or personal names.

  python core/tools/check_repo.py            every file git would commit
  python core/tools/check_repo.py --all      every file in the checkout

Rules (the project's own, see docs/LEGAL.md):
  * no game or ROM formats, whatever the extension's file came from;
  * no file over 1 MB, except the shipped hand-made art;
  * no absolute paths of the developer's machine, user names or e-mail
    addresses (extend PERSONAL in hodmods.local.json: "private_words": [...]).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import hodpaths

REPO = hodpaths.REPO
GAME_FORMATS = {".dds", ".opd", ".csr", ".col", ".dat", ".txrc", ".def", ".xwb", ".xsb", ".xgs", ".dll", ".exe",
                ".bin", ".gba", ".nds", ".iso", ".cue", ".wav", ".xex", ".xexp", ".arc", ".hodchapter", ".stfs",
                ".header", ".zip", ".pdb", ".lib", ".obj"}
ART_OK = ("mods/nathan/art/", "core/art/")
TEXT = {".py", ".md", ".json", ".cpp", ".h", ".inc", ".c", ".ps1", ".patch", ".txt", ".cmake", ".html", ".bat", ".toml"}
PATTERNS = [
    (r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\"'<>]+", "a Windows user folder"),
    (r"\bH:[\\/]", "a path on the developer's research drive"),
    (r"[\w.+-]+@[\w-]+\.[\w.]+", "an e-mail address"),
]
ALLOWED_EMAILS = {"noreply@anthropic.com"}


def files(all_files):
    if not all_files:
        r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=REPO,
                           capture_output=True, text=True)
        if r.returncode == 0:
            return [REPO / line for line in r.stdout.splitlines() if line]
    return [p for p in REPO.rglob("*") if p.is_file() and ".git" not in p.relative_to(REPO).parts]


def main():
    local = json.loads((REPO / "hodmods.local.json").read_text()) if (REPO / "hodmods.local.json").is_file() else {}
    words = [w for w in local.get("private_words", []) if w]
    words += [str(hodpaths.GAME), str(Path.home()), Path.home().name, "Castle" + "rando"]
    problems = []
    for p in files("--all" in sys.argv):
        rel = p.relative_to(REPO).as_posix()
        if rel == "hodmods.local.json":
            continue
        data = p.read_bytes()
        if p.suffix.lower() in GAME_FORMATS:
            problems.append(f"{rel}: game/binary file format")
        if len(data) > 1 << 20 and not rel.startswith(ART_OK):
            problems.append(f"{rel}: {len(data) // 1024} KB")
        if p.suffix.lower() in TEXT or p.name in (".gitignore", ".gitattributes"):
            text = data.decode("utf-8", errors="replace")
            for w in words:
                for variant in {w, w.replace("\\", "/")}:
                    if re.search(rf"(?<![A-Za-z]){re.escape(variant)}(?![A-Za-z])", text, re.I):
                        problems.append(f"{rel}: contains {variant!r}")
            for pattern, what in PATTERNS:
                for m in re.finditer(pattern, text):
                    if what == "an e-mail address" and (m.group(0).lower() in ALLOWED_EMAILS or "." not in m.group(0).split("@")[1]):
                        continue
                    problems.append(f"{rel}: {what}: {m.group(0)[:60]}")
    for line in sorted(set(problems)):
        print(line)
    print(f"{len(set(problems))} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
