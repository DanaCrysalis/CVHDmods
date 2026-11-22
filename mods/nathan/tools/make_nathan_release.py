"""SUPERSEDED by the hod-mods repository (kept as the record of the old release
format). It packed a zip that was unpacked over <game>/modding; the repo's
layout (mods/nathan, core) replaces that archive, and core/tools/check_repo.py
replaces its asset and privacy checks.

Pack the Nathan Graves mod for other people: modding/dist/Nathan_Graves_<date>.zip.

The archive is unpacked into the HarmonyRecomp game folder; its paths mirror
that folder. It is an allowlist: only the mod's own tools, patches, runtime
sources, settings and the shipped art (dive kick poses, menu portrait). It
carries no game or CotM files: every sprite, sound and table is made on the
user's machine from their own HoD install and CotM ROM (setup_nathan.py).

After packing, the archive is checked: no game-format files, no file over
1 MB other than the shipped art, nothing from build/, originals/, backups/ or
data/ (other than the module patch list and the
code-read record), and no personal paths.

  python modding/tools/make_nathan_release.py
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import datetime, fnmatch, hashlib, json, re, zipfile
from pathlib import Path
ROOT = hodpaths.GAME
MOD = hodpaths.legacy('modding')
TOOLS = hodpaths.legacy('modding/tools')
OUT = hodpaths.legacy('modding/dist')

# Tools that belong to other projects (music packs) or are one-off research
# aids that read game files directly; neither is needed to build Nathan.
NOT_NATHAN = ['hod_musicpack*.py', 'build_musicpack_exe.py', '*Music Pack*',
              'build_nathan_technical_report.py']  # the report generator reads the developer's machine
TOOL_TYPES = ('.py', '.cpp', '.inc', '.ps1', '.md')
# data/ holds game-derived research files; only these two of the mod's own go:
# the module patch list (original bytes as hashes) and the record of the code
# words the native checks read (see nathan_paths.CodeImage).
DATA_OK = ('modding/data/nathan_module_patches.json', 'modding/data/nathan_game_reads.json')
GAME_FORMATS = ('.dds', '.opd', '.csr', '.col', '.dat', '.txrc', '.def', '.xwb', '.xsb', '.dll', '.exe', '.bin', '.gba', '.wav', '.xex')

def files():
    yield hodpaths.legacy('modding/README.md'), 'modding/README.md'
    yield hodpaths.legacy('modding/TESTING.md'), 'modding/TESTING.md'
    yield hodpaths.legacy('modding/PLAYER_README.md'), 'Nathan Graves - README.md'
    yield hodpaths.legacy('modding/nathan_dss_balance.json'), 'modding/nathan_dss_balance.json'
    yield hodpaths.legacy('modding/nathan_summon_visuals.json'), 'modding/nathan_summon_visuals.json'
    yield hodpaths.legacy('modding/data/nathan_module_patches.json'), 'modding/data/nathan_module_patches.json'
    yield hodpaths.legacy('modding/data/nathan_game_reads.json'), 'modding/data/nathan_game_reads.json'
    for folder in ('patches', 'art'):
        for p in sorted((MOD/folder).rglob('*')):
            if p.is_file(): yield p, p.relative_to(ROOT).as_posix()
    for p in sorted(TOOLS.glob('*'))+sorted((TOOLS/'legacy').glob('*')):
        if p.is_file() and p.suffix in TOOL_TYPES and not any(fnmatch.fnmatch(p.name, pat) for pat in NOT_NATHAN):
            yield p, p.relative_to(ROOT).as_posix()
    for p in sorted((ROOT/'.setup/package/src/src').glob('nathan_*')):
        yield p, p.relative_to(ROOT).as_posix()

def check(entries):
    old_source = 'Castle'+'rando'   # the developer's original extraction folder
    personal = [str(Path.home()), Path.home().name, str(ROOT), old_source]
    problems = []
    for src, arc in entries:
        data = src.read_bytes()
        if src.suffix.lower() in GAME_FORMATS: problems.append(f'{arc}: game file format')
        if len(data) > 1 << 20 and not arc.startswith('modding/art/'): problems.append(f'{arc}: {len(data)} bytes')
        if any(part in ('build', 'originals', 'backups', '__pycache__') for part in Path(arc).parts): problems.append(f'{arc}: excluded folder')
        if arc.startswith('modding/data/') and arc not in DATA_OK: problems.append(f'{arc}: data/')
        if src.suffix in ('.py', '.md', '.json', '.cpp', '.h', '.inc', '.ps1', '.patch'):
            text = data.decode('utf-8', errors='replace')
            for needle in personal:
                if needle and re.search(re.escape(needle), text, re.I): problems.append(f'{arc}: contains a local path or name ({needle})')
    return problems

def main():
    entries = list(files())
    missing = [arc for src, arc in entries if not src.is_file()]
    assert not missing, f'missing: {missing}'
    problems = check(entries)
    assert not problems, 'Not packed:\n  '+'\n  '.join(problems)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.date.today().strftime('%Y%m%d')
    archive = OUT/f'Nathan_Graves_{stamp}.zip'
    manifest = {arc: hashlib.sha256(src.read_bytes()).hexdigest() for src, arc in entries}
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for src, arc in entries: z.write(src, arc)
        z.writestr('modding/release_manifest.json', json.dumps({'date': stamp, 'recomp': 'v0.6.0', 'files': manifest}, indent=1)+'\n')
    print(f'{archive}: {len(entries)} files, {archive.stat().st_size//1024} KB')

if __name__ == '__main__':
    raise SystemExit('Superseded: share the hod-mods repository instead (see the docstring).')
