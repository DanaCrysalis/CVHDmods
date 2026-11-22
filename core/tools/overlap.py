"""List files in a package that share a path (case-insensitive) with another package or the base game."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys
from pathlib import Path
pkg = Path(sys.argv[1]); others = [Path(p) for p in sys.argv[2:]]
mine = {p.relative_to(pkg).as_posix().lower() for p in pkg.rglob('*') if p.is_file()}
mine.discard('.extracted')
hits = {}
for o in others:
    roots = [d for d in o.iterdir() if d.is_dir()] if o.name == 'dlc' else [o]
    for r in roots:
        if r.resolve() == pkg.resolve():
            continue
        for p in r.rglob('*'):
            if p.is_file():
                rel = p.relative_to(r).as_posix().lower()
                if rel in mine:
                    hits.setdefault(rel, []).append(r.name[:8])
for k in sorted(hits):
    print(f'{k}  <- also in {sorted(set(hits[k]))}')
print(f'{len(hits)} shared of {len(mine)} files')
