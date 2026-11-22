"""Bundle the Music Pack Builder into one standalone .exe for sharing.

  python -m pip install pyinstaller numpy soundfile soxr
  python modding/tools/build_musicpack_exe.py

Output, ready to share (nothing to install for the person who runs it):
  modding/dist/HoD Music Pack Builder/
      HoD Music Pack Builder.exe
      README.txt                  how to use it
      THIRD-PARTY-NOTICES.txt     every bundled component, its license and source
      licenses/                   the full license texts
  modding/dist/HoD Music Pack Builder.zip   the same folder, zipped

The exe holds only this tool's code and its libraries; no game files and no
music. Run as the exe, the tool keeps packs and builds in
Documents/HoD Music Packs and asks once for the HarmonyRecomp folder
(remembered in %APPDATA%/HoD Music Pack Builder/settings.json).

The license texts are copied from the installed packages, so they always
match what was bundled. A missing file stops the build.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import importlib.metadata as md
import shutil
import subprocess
import sys
import tkinter
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
MODDING = hodpaths.WORK
NAME = 'HoD Music Pack Builder'

BSD_3 = """BSD 3-Clause License (the terms under which libFLAC, libogg, libvorbis
and libopus are distributed; copyright holders are listed in
soundfile-license_notes.md)

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

README = f"""{NAME}
{'=' * len(NAME)}

Makes music packs (BGM DLC) for Castlevania: Harmony of Despair on
HarmonyRecomp from your own music files. Nothing to install: run the exe.

1. Start "{NAME}.exe". The first time, Windows may say "Windows protected
   your PC": click "More info", then "Run anyway" (the exe is not signed).
2. Click Browse... next to "HarmonyRecomp folder" and choose the folder with
   harmonyrecomp.exe (your HarmonyRecomp must be set up with DLC).
3. Add songs (FLAC, WAV, OGG, MP3, or ready-made Xbox 360 .xwb banks) and type
   the title each one should have in the game's track list.
4. The loop is found automatically. Check it with "Hear the loop seam", or
   drag the green (start) and red (end) markers on the waveform.
5. Pick a DLC package number shown as "Free", close the game, and click
   "Install into the game". The songs appear in the game's track list.
   "Match the game's music volume" (on by default) makes every song as loud
   as the official music.

Sound quality: the game holds each song in its sound memory as uncompressed
audio, and a song bigger than about 5 MB is skipped (listed but silent).
48000 Hz stereo takes 11 MB per minute, so "Best that fits the size limit"
lowers the sample rate until the song fits: the panel under the loop points
shows the rate and size each song gets. Shorter is clearer: only the intro and
one pass of the loop are kept, and anything after the loop end is dropped.
"Mono" doubles the rate in the same size (good for songs with little stereo).
A fixed sample rate is also offered, but a song that ends up over the limit
may not play. (The official music uses Xbox XMA compression, which is about
ten times smaller, but no freely available XMA encoder exists.)

"Save DLC file..." makes the pack one file, like the official music packs, to
share. Whoever gets it installs it with "Install a DLC file...". Uninstall
removes a pack again. Other players in an online session need the same pack.

Your pack files are kept in the "Music Packs" folder next to this program
(or in Documents\\HoD Music Packs if that folder cannot be written to).

No game files or music are included in this program; it uses only the songs
you give it. Third-party components and their licenses: THIRD-PARTY-NOTICES.txt
and the licenses folder.
"""


def dist_file(dist, rel):
    """Path of a file shipped with an installed distribution (must exist)."""
    p = Path(md.distribution(dist).locate_file(rel))
    if not p.is_file():
        raise FileNotFoundError(f'{dist}: {rel} not found ({p})')
    return p


def ver(dist):
    return md.version(dist)


def write_licenses(out):
    lic = out / 'licenses'
    lic.mkdir()
    base = Path(sys.base_prefix)
    copies = [  # (file in licenses/, source)
        ('Python-LICENSE.txt', base / 'LICENSE.txt'),
        ('Tcl-Tk-license.terms.txt', base / 'tcl/tk8.6/license.terms'),
        ('numpy-LICENSE.txt', dist_file('numpy', f'numpy-{ver("numpy")}.dist-info/licenses/LICENSE.txt')),
        ('soundfile-LICENSE.txt', dist_file('soundfile', f'soundfile-{ver("soundfile")}.dist-info/LICENSE')),
        ('soundfile-license_notes.md', dist_file('soundfile', 'licensing/license_notes.md')),
        ('libsndfile-COPYING-LGPL-2.1.txt', dist_file('soundfile', '_soundfile_data/COPYING')),
        ('soxr-LICENSE.txt', dist_file('soxr', f'soxr-{ver("soxr")}.dist-info/licenses/LICENSE.txt')),
        ('soxr-COPYING.LGPL.txt', dist_file('soxr', f'soxr-{ver("soxr")}.dist-info/licenses/COPYING.LGPL')),
        ('libsoxr-LICENSE.txt', dist_file('soxr', f'soxr-{ver("soxr")}.dist-info/licenses/LICENSE-libsoxr.txt')),
        ('PFFFT-LICENSE.txt', dist_file('soxr', f'soxr-{ver("soxr")}.dist-info/licenses/LICENSE-PFFFT.txt')),
        ('cffi-LICENSE.txt', dist_file('cffi', f'cffi-{ver("cffi")}.dist-info/licenses/LICENSE')),
        ('PyInstaller-COPYING.txt', dist_file('pyinstaller', f'pyinstaller-{ver("pyinstaller")}.dist-info/licenses/COPYING.txt')),
    ]
    # numpy's other bundled-code licenses, flattened
    numpy_dir = f'numpy-{ver("numpy")}.dist-info/licenses/'
    for f in md.distribution('numpy').files:
        s = str(f).replace('\\', '/')
        if s.startswith(numpy_dir) and s != numpy_dir + 'LICENSE.txt':
            name = 'numpy-' + s[len(numpy_dir):].replace('/', '_')
            copies.append((name if '.' in Path(name).name else name + '.txt', Path(f.locate())))
    for name, src in copies:
        if not Path(src).is_file():
            raise FileNotFoundError(f'license source missing: {src}')
        shutil.copyfile(src, lic / name)
    (lic / 'BSD-3-Clause.txt').write_text(BSD_3, encoding='utf-8')

    py = sys.version.split()[0]
    tcl = tkinter.Tcl().eval('info patchlevel')
    rows = [
        (f'Python {py}', 'PSF License 2.0 (with notices for OpenSSL [Apache 2.0], libffi, zlib, bzip2)',
         'Python-LICENSE.txt', 'https://www.python.org/downloads/source/'),
        (f'Tcl/Tk {tcl} (window toolkit)', 'Tcl/Tk license (BSD-style; Tcl and Tk use the same text)',
         'Tcl-Tk-license.terms.txt', 'https://www.tcl-lang.org/software/tcltk/'),
        (f'NumPy {ver("numpy")} (includes OpenBLAS)', 'BSD-3-Clause and others listed in the file',
         'numpy-LICENSE.txt, numpy-*.txt', 'https://github.com/numpy/numpy'),
        (f'python-soundfile {ver("soundfile")}', 'BSD-3-Clause', 'soundfile-LICENSE.txt',
         'https://github.com/bastibe/python-soundfile'),
        ('libsndfile 1.2.2 (audio file reading)', 'LGPL-2.1-or-later', 'libsndfile-COPYING-LGPL-2.1.txt',
         'https://github.com/libsndfile/libsndfile'),
        ('  built into libsndfile: libFLAC 1.4.3, libogg, libvorbis 1.3.7, libopus 1.5.2',
         'BSD-3-Clause', 'BSD-3-Clause.txt, soundfile-license_notes.md (copyrights, sources)', ''),
        ('  built into libsndfile: mpg123, LAME (MP3)', 'LGPL-2.1-or-later / LGPL-2.0-or-later',
         'libsndfile-COPYING-LGPL-2.1.txt, soundfile-license_notes.md (copyrights, sources)', ''),
        (f'python-soxr {ver("soxr")} with libsoxr (resampling)', 'LGPL-2.1-or-later',
         'soxr-LICENSE.txt, soxr-COPYING.LGPL.txt, libsoxr-LICENSE.txt, PFFFT-LICENSE.txt',
         'https://github.com/dofuuz/python-soxr'),
        (f'cffi {ver("cffi")} (binary backend)', 'MIT-0', 'cffi-LICENSE.txt', 'https://github.com/python-cffi/cffi'),
        (f'PyInstaller {ver("pyinstaller")} bootloader', 'GPL-2.0-or-later with the bootloader exception '
         '(allows distributing bundled programs under any terms)', 'PyInstaller-COPYING.txt',
         'https://github.com/pyinstaller/pyinstaller'),
        ('Microsoft Visual C++ runtime (vcruntime140, msvcp140, ucrtbase)',
         'Microsoft redistributable runtime, shipped as part of Python', '-',
         'https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files'),
    ]
    lines = [f'{NAME}: third-party notices', '',
             'This program bundles the components below. Their full license texts are in',
             'the licenses folder. The LGPL libraries (libsndfile with mpg123 and LAME,',
             'and libsoxr) are unmodified; their source code is available at the links',
             'given, and they are loaded as separate DLLs that the bundle unpacks at start,',
             'so they can be replaced with compatible builds.', '']
    for comp, license_, files, src in rows:
        lines += [comp, f'    License: {license_}', f'    Text:    {files}']
        if src:
            lines.append(f'    Source:  {src}')
        lines.append('')
    (out / 'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(lines), encoding='utf-8')
    return len(copies) + 1


def main():
    work = MODDING / 'build' / 'pyinstaller'
    dist = MODDING / 'dist'
    out = dist / NAME
    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
           '--name', NAME, '--paths', str(TOOLS),
           '--hidden-import', 'hod_musicpack', '--hidden-import', 'txrc',
           '--collect-data', 'soundfile', '--collect-binaries', 'soundfile',
           # not used by the tool; keeps the exe smaller
           '--exclude-module', 'matplotlib', '--exclude-module', 'scipy', '--exclude-module', 'PIL',
           '--exclude-module', 'IPython', '--exclude-module', 'pytest',
           '--workpath', str(work), '--distpath', str(work / 'dist'), '--specpath', str(work),
           str(hodpaths.tool('hod_musicpack_gui.py'))]
    subprocess.run(cmd, check=True)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.move(str(work / 'dist' / f'{NAME}.exe'), out / f'{NAME}.exe')
    (out / 'README.txt').write_text(README, encoding='utf-8')
    n = write_licenses(out)
    shutil.rmtree(work, ignore_errors=True)
    archive = shutil.make_archive(str(dist / NAME), 'zip', dist, NAME)
    exe = out / f'{NAME}.exe'
    print(f'\nBuilt {exe} ({exe.stat().st_size / 2**20:.1f} MB), {n} license texts')
    print(f'Zip to share: {archive}')


if __name__ == '__main__':
    main()
