"""Map the game's DLCnn mount slots to package numbers from a harmonyrecomp log."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import re, sys

pat = re.compile(r"'(DLC\d+):\\data\\item\\\w+?_dlc(\d+)")
seen = {}
for line in open(sys.argv[1], encoding='utf-8', errors='ignore'):
    m = pat.search(line)
    if m:
        seen.setdefault(m.group(1), set()).add(int(m.group(2)))
for k in sorted(seen):
    print(k, sorted(seen[k]))
