"""Rewrite the test character's name and bio (groups 6-8) in every language."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from txrc import decode, encode

TEXT = {
    'en': ('Nathan Graves', "Morris Baldwin's student,\na vampire hunter armed\nwith the Hunter Whip.", 'Nathan'),
    'de': ('Nathan Graves', 'Schüler von Morris Baldwin,\nein Vampirjäger mit\nder Jägerpeitsche.', 'Nathan'),
    'fr': ('Nathan Graves', 'Élève de Morris Baldwin,\nchasseur de vampires armé\ndu Fouet du chasseur.', 'Nathan'),
    'es': ('Nathan Graves', 'Discípulo de Morris Baldwin,\ncazavampiros armado con\nel Látigo del cazador.', 'Nathan'),
    'it': ('Nathan Graves', 'Allievo di Morris Baldwin,\ncacciatore di vampiri\ncon la Frusta del cacciatore.', 'Nathan'),
    'ja': ('ネイサン・グレーブス', 'モーリス・ボールドウィンの弟子。\nハンターウィップを操る\nヴァンパイアハンター。', 'ネイサン'),
}

for folder in sys.argv[1:]:
    for lang, (full, bio, short) in TEXT.items():
        f = Path(folder) / f'textres17_{lang}.txrc'
        doc = decode(f.read_bytes())
        groups = doc['sections'][0]
        assert all(len(groups[g]) == 1 for g in (6, 7, 8)), (f, [len(groups[g]) for g in (6, 7, 8)])
        old = groups[6][0]
        groups[6][0], groups[7][0], groups[8][0] = full, bio, short
        f.write_bytes(encode(doc))
        check = decode(f.read_bytes())['sections'][0]
        assert (check[6][0], check[7][0], check[8][0]) == (full, bio, short)
        print(f'{f.parent.parent.parent.name[:12]}… {lang}: {old!r} -> {full!r}')
