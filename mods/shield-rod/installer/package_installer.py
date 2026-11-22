"""Package the separately built Shield Rod-only runtime and asset converters."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
from pathlib import Path
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = hodpaths.GAME  # the development machine's game folder
HERE = Path(__file__).parent
OUT = hodpaths.legacy('modding/build/shield_rod_universal')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def familiar_payload(resources, icon):
    """Expected inputs and outputs of the familiar card / Refectio build (extras.py).

    Base-file inputs are the TU2 originals kept in modding/originals. Outputs that
    depend only on them (and the SotN disc) must come out byte-identical on the
    player's machine: the art and sounds are the ones built by the development
    tools; the menu icon, row mask and enemy drops are recomputed here."""
    import tempfile
    import extras
    originals = hodpaths.legacy('modding/originals/game/assets')
    base = {name: sha(originals / name) for name in extras.BASE_FILES}
    cfg = json.loads((resources / 'alucard_familiars.json').read_text(encoding='utf-8'))
    outputs = {}
    assets = ROOT / 'assets'
    for name in ['data/opd/player/aru/P_ARU_00.OPD', 'data/opd/player/aru/C_ARFM.COL'] +                 [f'data/opd/player/aru/T_ARFM0{i}.CSR' for i in range(1, 5)]:
        outputs[name] = sha(assets / name)
    for name in ['SE_FAMILIAR.xsb', 'SE_FAMILIAR.xwb']:
        outputs['data/sound/' + name] = sha(hodpaths.legacy('modding/build/familiar_audio/data/sound') / name)
        assert outputs['data/sound/' + name] == sha(assets / 'data/sound' / name), 'familiar sound bank not installed'
    with tempfile.TemporaryDirectory() as tmp:
        for name, path in extras.equip_icon(originals, icon, Path(tmp)).items():
            outputs[name] = sha(path)
            assert outputs[name] == sha(assets / name), f'{name} differs from the installed one'
    font = extras.font_with_arrows((originals / 'data/arc/font.arc').read_bytes())
    outputs['data/arc/font.arc'] = hashlib.sha256(font).hexdigest()
    assert font == (assets / 'data/arc/font.arc').read_bytes(), 'installed font.arc differs from a fresh build'
    def_bytes = extras.def_with_rows((originals / 'data/player/player_default.def').read_bytes())
    outputs['data/player/player_default.def'] = hashlib.sha256(def_bytes).hexdigest()
    assert def_bytes == (assets / 'data/player/player_default.def').read_bytes()
    outputs['data/enemy/EnemyParam.dat'] = hashlib.sha256(
        extras.enemy_drops((originals / 'data/enemy/EnemyParam.dat').read_bytes(), cfg)).hexdigest()
    return dict(base_files=base, outputs=outputs)


def runtime_files():
    """local_build.MOD_SOURCES and every local header they include, recursively.

    A fixed list missed refectio.h, so the local build (installations whose
    executable differs from the patch baseline) failed (friend's log, November 19)."""
    import re
    import local_build
    src = ROOT / '.setup/package/src/src'
    files, pending = [], list(local_build.MOD_SOURCES) + list(local_build.RECOMP_FIXES)
    while pending:
        name = pending.pop(0)
        if name in files:
            continue
        assert (src / name).is_file(), f'Runtime file missing: {name}'
        files.append(name)
        for include in re.findall(r'^\s*#\s*include\s+"([^"]+)"', (src / name).read_text(encoding='utf-8'), re.M):
            if '/' not in include:  # ../generated/... comes from the player's own setup
                pending.append(include)
    return files


def main():
    resources = OUT / 'resources'
    modules = OUT / 'converters'
    resources.mkdir(parents=True, exist_ok=True)
    modules.mkdir(exist_ok=True)
    build = hodpaths.legacy('modding/build/shield_rod_standalone/resources')
    # Prove the runtime being packaged actually omitted both DSS translation
    # units, rather than merely omitting Nathan's character DLC data.
    mapping = (build / 'harmonyrecomp.map').read_text(errors='replace')
    assert 'shield_rod_bridge.cpp.obj' in mapping
    assert 'nathan_dss_damage.cpp.obj' not in mapping
    assert 'harmony::nathan' not in mapping and '?Load@State@nathan' not in mapping
    runtime = ['harmonyrecomp.exe', 'harmonyrecomp.map']
    # The shipping resources contain a patch and diagnostics, not a full EXE.
    shutil.copy2(build / 'harmonyrecomp.map', resources / 'harmonyrecomp.map')
    import executable_patch
    base_path = hodpaths.legacy('modding/backups/nathan_dss_20261112_043946_source/runtime/harmonyrecomp.exe')
    base = executable_patch.canonical_pe(base_path.read_bytes())
    target = (build / 'harmonyrecomp.exe').read_bytes()
    patch_path = resources / 'harmonyrecomp.bsdiff'
    base_sha, target_sha = hashlib.sha256(base).hexdigest(), hashlib.sha256(target).hexdigest()
    cache = OUT / 'patch_cache.json'
    key = dict(base_sha256=base_sha, target_sha256=target_sha)
    if not patch_path.exists() or not cache.exists() or json.loads(cache.read_text()) != key:
        sys.path.insert(0, str(hodpaths.legacy('modding/build/patch_build_deps')))
        import bsdiff4
        patch_path.write_bytes(bsdiff4.diff(base, target))
        cache.write_text(json.dumps(key))
    assert executable_patch.apply(base, patch_path.read_bytes(), len(target), target_sha) == target
    patch_info = dict(file=patch_path.name, sha256=sha(patch_path), base_sha256=base_sha,
                      base_original_sha256=sha(base_path), base_size=len(base),
                      target_size=len(target), target_sha256=target_sha,
                      normalization='PE COFF timestamp and optional checksum only')
    print('Verified executable patch:', patch_path.stat().st_size, 'bytes', flush=True)

    shutil.copy2(hodpaths.legacy('modding/shield_rod.json'), resources / 'shield_rod.json')
    shutil.copy2(hodpaths.legacy('modding/build/shield_audio/render_sotn_spu.exe'), resources / 'render_sotn_spu.exe')
    with zipfile.ZipFile(resources / 'traces.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for folder in ['sotn_spell_traces', 'sotn_child_traces']:
            for p in sorted((hodpaths.legacy('modding/build') / folder).glob('*.json')):
                z.write(p, 'modding/build/' + folder + '/' + p.name)
    for name in ['build_shield_sotn.py', 'build_shield_audio.py', 'sotn_disc.py', 'txrc.py', 'hodsprite.py',
                 'familiar_art.py', 'build_familiar_audio.py', 'refectio_fx.py', 'ndsfs.py', 'font_arrows.py']:
        shutil.copy2(hodpaths.tool(name), modules / name)
    # Familiar cards and Refectio settings; the Enchanted-row card icon (the mod
    # author's own drawing) as palette indexes, so the installer needs no imaging library.
    shutil.copy2(hodpaths.legacy('modding/alucard_familiars.json'), resources / 'alucard_familiars.json')
    shutil.copy2(hodpaths.legacy('modding/refectio.json'), resources / 'refectio.json')
    import equip_card_icon
    from hodsprite import read_opd
    originals_menu = hodpaths.legacy('modding/originals/game/assets/data/opd/menu')
    # The palette file is never modified, so the live copy is its original.
    icon = equip_card_icon.card_indexes(read_opd(originals_menu / 'p_ui_equip0.opd'), ROOT / 'assets/data/opd/menu')
    (resources / 'card_slot_icon.json').write_text(json.dumps(icon))
    graphics = (modules / 'build_shield_sotn.py').read_text(encoding='utf-8')
    graphics = graphics.replace('import numpy as np', 'import portable_raster as np')
    old = 'np.stack([(vram[256:512,896:960]>>bit)&15 for bit in [0,4,8,12]],axis=2).reshape(256,256)'
    assert old in graphics
    graphics = graphics.replace(old, 'np.nibbles(vram[256:512,896:960])')
    (modules / 'build_shield_sotn.py').write_text(graphics, encoding='utf-8')
    sprite_tree = ast.parse(hodpaths.tool('hodsprite.py').read_text(encoding='utf-8'))
    sprite_tree.body = [n for n in sprite_tree.body if not isinstance(n, ast.FunctionDef) or n.name != 'render_frame']
    (modules / 'hodsprite.py').write_text(ast.unparse(sprite_tree), encoding='utf-8')

    # The original note-to-pitch routine has already been executed against this
    # exact USA executable. Package its finite input/output recipe instead of a
    # whole CPU emulator. ADPCM and envelopes still render from the user's disc.
    audio_manifest=json.loads((hodpaths.legacy('modding/build/shield_audio/manifest.json')).read_text())
    familiar_audio=json.loads((hodpaths.legacy('modding/build/familiar_audio/manifest.json')).read_text())
    pitch={}
    for effect in audio_manifest['effects']+familiar_audio['effects']:
        for voice in effect['voices']:
            t,e=voice['tone'],voice['event'];key=(t['center'],t['fine'],e['note'])
            assert key not in pitch or pitch[key]==voice['pitch']
            pitch[key]=voice['pitch']
    import sys as runtime_sys
    import shield_rod as development_sr
    _,disc=development_sr.open_disc()
    executable_sha=hashlib.sha256(disc.get('SLUS_000.67')).hexdigest();disc.f.close()
    audio_tree=ast.parse(hodpaths.tool('build_shield_audio.py').read_text())
    pitch_class=ast.parse('class OriginalPitch:\n    def __init__(self,exe):\n        assert hashlib.sha256(exe).hexdigest()=='+repr(executable_sha)+', "Unsupported SotN executable"\n    def __call__(self,tone,note):\n        return '+repr(pitch)+'[(tone["center"],tone["fine"],note)]\n').body[0]
    audio_tree.body=[pitch_class if isinstance(n,ast.ClassDef) and n.name=='OriginalPitch' else n
        for n in audio_tree.body if not (isinstance(n,ast.ImportFrom) and n.module.startswith('unicorn'))]
    audio_tree.body = [n for n in audio_tree.body if not (isinstance(n, ast.Import) and any(a.name == 'numpy' for a in n.names))]
    audio_tree.body.insert(0, ast.ImportFrom(module='portable_pcm', names=[ast.alias(name='finish_pcm')], level=0))
    render = next(n for n in audio_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'render')
    cut = next(i for i, n in enumerate(render.body) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'values' for t in n.targets))
    render.body = render.body[:cut] + ast.parse("""
path=OUT/f'sound_{sid:04x}.wav'
pcm,frames,peak=finish_pcm(raw,path,sid,RATE)
return pcm,frames,dict(id=sid,cue=f'SE_SR_{sid:04X}',sound_table_row=row,voices=voices,
    wav_sha256=sha(path.read_bytes()),frames=frames,seconds=frames/RATE,peak=peak,
    register_stream_sha256=sha(command_file.read_bytes()))
""").body
    audio_source=ast.unparse(audio_tree).replace("own-disc SLUS_000.67 _spu_note2pitch 8002B13C executed with Unicorn", "USA executable validated; exact original _spu_note2pitch input/output recipe")
    (modules/'build_shield_audio.py').write_text(audio_source,encoding='utf-8')
    # Ship only equipment/disc conversion functions from the development tool.
    # Its local installer and historical Nathan-aware chest editor are excluded.
    tree = ast.parse(hodpaths.tool('shield_rod.py').read_text())
    functions = {'disc_path', 'open_disc', 'convert', 'weapon_row', 'text_files', 'build', 'shield_items'}
    tree.body = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.Assign)) or
                 isinstance(n, ast.ClassDef) and n.name == 'WeaponSlot' or
                 isinstance(n, ast.FunctionDef) and n.name in functions]
    source = ast.unparse(tree)
    source = source.replace('import hod_musicpack as package_writer', "raise ValueError('A package writer is required')")
    assert 'nathan' not in source.lower() and 'import hod_musicpack' not in source
    (modules / 'shield_rod.py').write_text(source, encoding='utf-8')
    original = hodpaths.legacy('modding/originals/shield_sotn')
    extras_manifest = familiar_payload(resources, icon)
    manifest = dict(version='1.5.3', extras=extras_manifest, chapter7_required=True, chapter11_required=True, ooe_rom_optional=True, executable_patch=patch_info, runtime={n: sha(build / n) for n in runtime},
                    original_shields={p.name: sha(p) for p in original.iterdir() if p.suffix.upper() in ('.OPD', '.COL')},
                    spell_assets=json.loads((hodpaths.legacy('modding/build/shield_sotn_assets/verified_assets.json')).read_text())['assets'],
                    sound_assets=json.loads((hodpaths.legacy('modding/build/shield_audio/manifest.json')).read_text())['files'],
                    trace_header=sha(ROOT / '.setup/package/src/src/shield_rod_sotn_trace.h'),
                    compatibility={key: (hashlib.sha256(executable_patch.canonical_pe((ROOT / path).read_bytes())).hexdigest() if key.startswith('game_pe:') else sha(ROOT / path)) for key, path in {
                        'game:rexruntime.dll': 'rexruntime.dll',
                        'game_pe:harmonyrecomp_dllAlucard.dll': 'harmonyrecomp_dllAlucard.dll',
                        'assets:default.xex': 'assets/default.xex',
                        'assets:default.xexp': 'assets/default.xexp',
                        'assets:data/player_dll/dllAlucard.dll': 'assets/data/player_dll/dllAlucard.dll'}.items()},
                    nathan_code_included=False, chapter8_required=True)
    (resources / 'payload.json').write_text(json.dumps(manifest, indent=2))
    # Complete matching SPU renderer source accompanies its GPL executable.
    with zipfile.ZipFile(resources / 'SOURCE_AND_LICENSES.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for p in (hodpaths.legacy('modding/research/sotn_audio/dfsound')).iterdir():
            if p.is_file():
                z.write(p, 'spu-renderer/dfsound/' + p.name)
        z.write(hodpaths.tool('render_sotn_spu.c'), 'spu-renderer/render_sotn_spu.c')
        z.writestr('spu-renderer/BUILD.txt', 'Build on Windows with clang:\nclang -O2 -D_CRT_SECURE_NO_WARNINGS -DCALLBACK= -I dfsound render_sotn_spu.c dfsound/spu.c dfsound/registers.c dfsound/dma.c -o render_sotn_spu.exe\n')
        for p in HERE.glob('*.py'):
            z.write(p, 'installer/' + p.name)
        for p in modules.glob('*.py'):
            z.write(p, 'converters/' + p.name)
        for name in runtime_files():
            z.write(ROOT / '.setup/package/src/src' / name, 'runtime/' + name)
        z.write(ROOT / '.setup/package/src/LICENSE', 'licenses/HarmonyRecomp-BSD.txt')
        z.write(ROOT / '.setup/package/src/scripts/LICENSE-NocturneRecomp.txt', 'licenses/NocturneRecomp.txt')
        import importlib.metadata
        for dependency in ['pyinstaller']:
            distribution=importlib.metadata.distribution(dependency)
            for relative in distribution.files or []:
                if '/licenses/' in str(relative).replace('\\','/'):
                    z.write(distribution.locate_file(relative),'licenses/'+dependency+'/'+str(relative).split('licenses/',1)[-1])
        z.write(Path(sys.base_prefix)/'LICENSE.txt','licenses/Python.txt')
        for name in ['tk8.6']:
            z.write(Path(sys.base_prefix)/'tcl'/name/'license.terms','licenses/'+name+'.txt')

    manifest['source_archive_sha256'] = sha(resources / 'SOURCE_AND_LICENSES.zip')
    (resources / 'payload.json').write_text(json.dumps(manifest, indent=2))
    shutil.copy2(resources / 'SOURCE_AND_LICENSES.zip', OUT / 'SOURCE_AND_LICENSES.zip')
    shutil.copy2(HERE / 'README.txt', OUT / 'README.txt')
    (OUT / 'build_isolation.json').write_text(json.dumps(dict(nathan_objects_present=False,
        bridge_object_present=True, runtime=manifest['runtime'], installed_game_unchanged=True), indent=2))
    # Stage Tcl/Tk locally: this host's installed Tcl library fails its startup
    # search, although an identical copy in the build workspace initializes.
    gui_libs=OUT/'gui-libs'
    for name in ['tcl8.6','tk8.6','tcl8']:
        shutil.copytree(Path(sys.base_prefix)/'tcl'/name,gui_libs/name,dirs_exist_ok=True)
    env=os.environ.copy();env['TCL_LIBRARY']=str(gui_libs/'tcl8.6');env['TK_LIBRARY']=str(gui_libs/'tk8.6')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', '--onefile', '--windowed',
        '--name', 'ShieldRodInstaller', '--distpath', str(OUT / 'dist'), '--workpath', str(OUT / 'pyinstaller'),
        '--specpath', str(OUT), '--paths', str(modules), '--paths', str(HERE),
        '--exclude-module', 'hod_musicpack', '--exclude-module', 'nathan_card_drops',
        '--exclude-module', 'pytest', '--exclude-module', 'scipy',
        '--exclude-module', 'numpy', '--exclude-module', 'PIL', '--exclude-module', 'unicorn',
        '--exclude-module', '_hashlib', '--exclude-module', '_ssl', '--exclude-module', 'ssl',
        '--add-data', str(resources) + ';resources', str(HERE / 'app.py')], cwd=HERE, env=env, check=True)
    exe = OUT / 'dist/ShieldRodInstaller.exe'
    (OUT / 'SHA256.txt').write_text(sha(exe) + '  ShieldRodInstaller.exe\n')
    print('Standalone installer:', exe)


if __name__ == '__main__':
    main()
