"""Rebuild harmonyrecomp.exe with the hod-mods sections compiled in.

  python core/tools/rebuild_recomp.py [ON|OFF] [POISONWORM] [-<section> ...]

  ON / OFF     Nathan Graves in or out (default ON). OFF is the distributable
               runtime without Nathan (Shield Rod, familiars, glyphs).
  POISONWORM   adds the Chapter 14 Catacombs modules (mods/catacombs). That exe
               is for the test install only; every build without the word passes
               HARMONYRECOMP_POISONWORM=OFF, so the CMake cache never carries it
               into a normal build.
  -shield-rod, -familiars, -glyphs   leave that section out of this build.

The recomp tree must be prepared once with core/tools/setup_recomp.py.
Output: <game>/.setup/package/src/out/build/win-amd64-release/harmonyrecomp.exe
and .map. Installs nothing.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import os
import subprocess
import sys

ROOT = hodpaths.GAME
src = ROOT / '.setup/package/src'
tc = ROOT / '.setup/toolchain'
args = [a.upper() for a in sys.argv[1:]]
nathan = next((a for a in args if a in ('ON', 'OFF')), 'ON')
worm = 'ON' if 'POISONWORM' in args else 'OFF'
sections = {'SHIELD-ROD': 'HODMOD_SHIELD_ROD', 'FAMILIARS': 'HODMOD_FAMILIARS', 'GLYPHS': 'HODMOD_GLYPHS'}
options = [f'-D{flag}=' + ('OFF' if f'-{name}' in args else 'ON') for name, flag in sections.items()]
env = os.environ.copy()
env['PATH'] = os.pathsep.join([str(tc / 'cmake/bin'), str(tc / 'llvm/bin'), str(tc / 'ninja')] + env['PATH'].split(os.pathsep))


def run(*a):
    subprocess.run(list(map(str, a)), cwd=src, env=env, check=True)


check = subprocess.run([sys.executable, str(hodpaths.tool('setup_recomp.py')), '--check'], capture_output=True, text=True)
if check.returncode:
    sys.exit(check.stdout + '\nThe recomp tree is not prepared: run core/tools/setup_recomp.py first.')
run(tc / 'cmake/bin/cmake.exe', '--preset', 'win-amd64-release', f'-DCMAKE_PREFIX_PATH={ROOT / ".setup/package/sdk"}',
    '-DCMAKE_BUILD_TYPE=Release', '-DHARMONYRECOMP_VERSION=v0.6.0', f'-DHODMODS_ROOT={hodpaths.REPO.as_posix()}',
    '-DHARMONYRECOMP_NATHAN=' + nathan, '-DHARMONYRECOMP_POISONWORM=' + worm, *options)
run(tc / 'cmake/bin/cmake.exe', '--build', 'out/build/win-amd64-release', '--target', 'harmonyrecomp', '--parallel', '8')
print(f'BUILD OK (Nathan {nathan}, Catacombs {worm}, ' + ', '.join(o[2:] for o in options) + ')')
