"""Shield Rod installer: validate, build in staging, then journal every write."""
from pathlib import Path
import ctypes
import datetime
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import tomllib
import zipfile
import dlc_discovery
import executable_patch
import extras
import local_build

CONTENT_ID = '000000000000000000000000000000535200001358'
NATHAN_ID = '000000000000000000000000000000000C00001758'
STAGE_NAME = 'stage00_03_set_hard.dat'
STATE_DIR = 'ShieldRodInstaller'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def stopped():
    if os.name != 'nt':
        return
    from ctypes import wintypes as w
    class Entry(ctypes.Structure):
        _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD),
                    ('heap', ctypes.c_size_t), ('module', w.DWORD), ('threads', w.DWORD),
                    ('parent', w.DWORD), ('priority', w.LONG), ('flags', w.DWORD), ('exe', w.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32FirstW.restype = kernel.Process32NextW.restype = w.BOOL
    kernel.CloseHandle.argtypes = [w.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = Entry();entry.size = ctypes.sizeof(entry)
        found = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        if not found and ctypes.get_last_error() != 18:
            raise ctypes.WinError(ctypes.get_last_error())
        while found:
            require(entry.exe.lower() != 'harmonyrecomp.exe', 'Close HarmonyRecomp before installing or uninstalling.')
            found = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)


def documents():
    if os.name == 'nt':
        buf = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
            return Path(buf.value)
    return Path.home() / 'Documents'


def settings(game):
    config = Path(game) / 'harmonyrecomp.toml'
    return tomllib.loads(config.read_text(encoding='utf-8-sig')) if config.exists() else {}


def paths(game):
    """Game, assets and the configured default mounted content root."""
    game = Path(game).resolve()
    require((game / 'harmonyrecomp.exe').is_file(), 'Choose the folder containing harmonyrecomp.exe.')
    config = settings(game)
    def absolute(value):
        p = Path(value).expanduser()
        return (p if p.is_absolute() else game / p).resolve()
    assets = absolute(config.get('game_data_root', 'assets'))
    user = absolute(config['user_data_root']) if config.get('user_data_root') else documents() / 'harmonyrecomp'
    # This SDK stores marketplace packages directly below the user data root.
    return game, assets.resolve(), (user / dlc_discovery.SUFFIX).resolve()


def chapter8_stage(path):
    """Read-only check that a file is the Legion Hard stage with its boss chest."""
    data = Path(path).read_bytes()
    ranks = [struct.unpack_from('>ii', data, pos + 40) for pos, _, length, name in stage_records(data)
             if name == b'treasureBox' and length >= 16 and struct.unpack_from('>I', data, pos + 32)[0] == 4]
    return ranks == [(0, 208)]


def chapter8(game, assets, content, listing, content_override=None):
    """Return (mounted content root, Chapter 8 Hard stage, diagnostics)."""
    return dlc_discovery.find(game, assets, content, listing, content_override, settings(game),
                              documents(), chapter8_stage)


# Mod packages this installer owns, and Nathan's (not part of this release).
# Official DLC uses packages 01-04, 07, 11-16, 28 and 29 (src/dlc.cpp).
MOD_PACKAGES = {CONTENT_ID: ('Shield Rod', 'package19'), extras.FAMILIAR_ID: ('Alucard familiar cards', 'package21'),
                extras.REFECTIO_ID: ('Refectio', 'package20'), NATHAN_ID: ('Nathan', 'package17')}


def stray_mods(game, content, listing):
    """Mod packages present without an installation record, usually copied into
    dlc/ with the official DLC (a fresh recomp refused, November 19). Returns
    (dlc_packages.txt lines, files, names). Install drops the lines and deletes
    the files inside its transaction, so Uninstall puts them back."""
    tags = {tag: cid for cid, (_, tag) in MOD_PACKAGES.items()}
    lines, folders, found = [], set(MOD_PACKAGES), set()
    for line in listing.splitlines():
        parts = [part.strip() for part in line.split('\t')]
        hit = next((p for p in parts if p.upper() in MOD_PACKAGES or p.casefold() in tags), None)
        if hit:
            lines.append(line)
            folders.add(parts[0])  # the file name, which may differ from the content id
            found.add(MOD_PACKAGES[hit.upper() if hit.upper() in MOD_PACKAGES else tags[hit.casefold()]][0])
    files = []
    headers = content.parent / 'Headers/00000002'
    for name in sorted(folders):
        for p in (game / 'dlc' / name, headers / (name + '.header')):
            if p.is_file():
                files.append(p)
        if (content / name).is_dir():
            files += sorted(p for p in (content / name).rglob('*') if p.is_file())
        if any(p.is_relative_to(game / 'dlc' / name) or p.is_relative_to(content / name) or p == headers / (name + '.header')
               for p in files):
            found.add(MOD_PACKAGES.get(name.upper(), (name, ''))[0])
    return lines, files, sorted(found)


def preflight(game, resources, content_override=None, log=None):
    game, assets, content = paths(game)
    require(not (game / STATE_DIR / 'installation.json').exists(),
            'A Shield Rod installation or interrupted installation is recorded here. Use Uninstall / Restore first.')
    require((game / 'dlc_packages.txt').is_file(),
            'dlc_packages.txt is missing next to harmonyrecomp.exe, so this recomp has no DLC enabled. Rerun official Setup with Chapter 8 in its dlc folder.')
    listing = (game / 'dlc_packages.txt').read_text(encoding='utf-8-sig')
    # Resolve the real mounted content before any Shield Rod checks or writes.
    content, chest, found = chapter8(game, assets, content, listing, content_override)
    if log:
        log(found)
    stray = stray_mods(game, content, listing)
    extras.IGNORED = {p.relative_to(content).parts[0].casefold() for p in stray[1] if p.is_relative_to(content)}
    if stray[1] or stray[0]:
        (log or (lambda text: None))('Found earlier mod packages with no installation record: ' + ', '.join(stray[2]) +
                                     f' ({len(stray[0])} dlc_packages.txt line(s), {len(stray[1])} file(s)). '
                                     'They will be removed and replaced; Uninstall puts them back.')
    for p in [game / 'harmonyrecomp.exe', assets / 'data/opd/weapon/ar/P_ARSH00.OPD']:
        require(p.is_file(), f'Missing required file: {p}')
    # Reject a combined runtime even if someone removed its DLC list entry.
    executable = (game / 'harmonyrecomp.exe').read_bytes()
    require(b'[shield rod]' not in executable and b'[nathan' not in executable.lower(),
            'This executable already contains Shield Rod or Nathan. Restore a clean recomp first.')
    manifest = json.loads((resources / 'payload.json').read_text())
    # A known baseline can use the compact delta. Other locally compiled 0.6.0
    # builds are rebuilt against their own retained SDK, objects and DLC registry.
    patch = manifest['executable_patch']
    actual = hashlib.sha256(executable_patch.canonical_pe(executable)).hexdigest()
    manifest['local_build_context'] = None if actual == patch['base_sha256'] else local_build.plan(game)
    for relative, expected in manifest['compatibility'].items():
        root, name = relative.split(':', 1)
        p = (game if root in ('game', 'game_pe') else assets) / name
        context = manifest.get('local_build_context')
        if context and relative == 'game:rexruntime.dll':
            # local_build.plan already verifies this against the user's SDK.
            continue
        if context and root == 'game_pe':
            cached = context['build'] / name
            require(p.is_file() and cached.is_file() and executable_patch.canonical_pe(p.read_bytes()) == executable_patch.canonical_pe(cached.read_bytes()),
                    f'The installed {name} does not match its setup cache. Rerun official 0.6.0 Setup, then retry.')
            continue
        require(p.is_file() and (hashlib.sha256(executable_patch.canonical_pe(p.read_bytes())).hexdigest() if root == 'game_pe' else sha(p)) == expected, f'Unsupported or modified recomp file: {p}. This installer supports Wrexxial HarmonyRecomp 0.6.0 with the matching ReXGlue SDK and HoD TU2 data.')
    for name, expected in manifest['original_shields'].items():
        p = assets / 'data/opd/weapon/ar' / name
        require(p.is_file() and sha(p) == expected, f'{name} is already modified or incompatible. Restore the original shield assets first.')
    # Familiar cards and Refectio: Chapters 7 and 11 and the original base files.
    chapter7, chapter11 = extras.preflight(game, assets, content, listing, chest, manifest, log or (lambda text: None))
    return game, assets, content, listing, chest, manifest, chapter7, chapter11, stray


def stage_records(data):
    require(data[:4] == b'SSD*' and len(data) >= 24, 'Invalid Chapter 8 stage file.')
    start, size = struct.unpack_from('>II', data, 16)
    end = start + size
    require(24 <= start <= end <= len(data) and not any(data[end:]), 'Invalid stage section.')
    pos = start
    while pos < end:
        require(pos + 32 <= end, 'Truncated stage object.')
        head = struct.unpack_from('>H', data, pos)[0]
        size = head & 0x3fff
        require(pos + 32 + size <= end, 'Truncated stage object data.')
        yield pos, head, size, data[pos+6:pos+32].split(b'\0')[0]
        pos += 32 + size
    require(pos == end, 'Invalid stage object layout.')


def patch_chest(data):
    start = struct.unpack_from('>I', data, 16)[0]
    out = bytearray(data[:start])
    bosses = 0
    for pos, head, length, name in stage_records(data):
        record = data[pos:pos+32+length]
        if name == b'treasureBox' and length >= 16 and struct.unpack_from('>I', record, 32)[0] == 4:
            require((length - 16) % 8 == 0, 'Malformed boss chest.')
            require(struct.unpack_from('>ii', record, 40) == (0, 208), 'Unexpected Chapter 8 boss chest ranks.')
            items = [struct.unpack_from('>HHI', record, i) for i in range(48, len(record), 8)]
            require(not any(it[:2] == (3, 160) for it in items), 'The Shield Rod drop is already installed.')
            payload = record[32:48] + b''.join(struct.pack('>HHI', *it) for it in items + [(3, 160, 50)])
            record = struct.pack('>H', (head & 0xc000) | len(payload)) + record[2:32] + payload
            bosses += 1
        out += record
    require(bosses == 1, 'Expected exactly one Chapter 8 Hard boss chest.')
    struct.pack_into('>I', out, 20, len(out) - start)
    out += bytes(-len(out) % 16)
    list(stage_records(out))
    return bytes(out)


def content_header(content_id=CONTENT_ID, title='Shield Rod DLC'):
    # SDK XCONTENT_AGGREGATE_DATA (0x148) followed by little-endian license mask.
    header = bytearray(332)
    struct.pack_into('>II', header, 0, 1, 2)
    title = title.encode('utf-16-be')
    header[8:8+len(title)] = title
    header[264:306] = content_id.encode('ascii')
    struct.pack_into('>I', header, 320, 0x58410A7A)
    struct.pack_into('<I', header, 328, 1)
    return bytes(header)


def build_payload(game, disc_path, resources, work, manifest, log):
    # Reusable converters resolve all outputs inside an isolated staging root.
    _, assets, _ = paths(game)
    os.environ['SHIELD_ROD_BUILD_ROOT'] = str(work)
    os.environ['SHIELD_ROD_SOTN_DISC'] = str(disc_path)
    (work / 'modding').mkdir(parents=True)
    shutil.copy2(resources / 'shield_rod.json', work / 'modding/shield_rod.json')
    (work / '.setup/package/src/src').mkdir(parents=True)
    with zipfile.ZipFile(resources / 'traces.zip') as archive:
        for name in archive.namelist():
            target = (work / name).resolve()
            require(target.is_relative_to(work.resolve()), 'Invalid trace archive path.')
        archive.extractall(work)
    # Import only after the private build root is configured. Imports are reset
    # so a second install in the same GUI cannot accidentally reuse old paths.
    import importlib
    import shield_rod
    sr = importlib.reload(shield_rod)
    log('Checking the USA SotN disc...')
    _, disc = sr.open_disc(disc_path)
    required = ['player/weaponset.dat'] + [f'text/textres_{lang}.txrc' for lang in sr.LANGS]
    ar = assets / 'data/opd/weapon/ar'
    required += ['opd/weapon/ar/' + p.name for p in ar.iterdir()
                 if p.name.startswith(('P_ARSH', 'C_ARSH', 'T_ARSH')) or p.name in (sr.MACE_SPRITE, sr.CLUB_PALETTE, sr.TEXTURE_HEADER_FROM)]
    for relative in required:
        target = work / '.setup/package/src/assets/data' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(assets / 'data' / relative, target)
    log('Extracting Shield Rod equipment and graphics...')
    import shield_stfs
    package = sr.build(disc, shield_stfs)
    disc.f.close()
    log('Building all thirteen shield spell assets...')
    import build_shield_sotn
    importlib.reload(build_shield_sotn).main()
    log('Rendering the original SotN spell sounds...')
    import build_shield_audio
    importlib.reload(build_shield_audio).main(resources / 'render_sotn_spu.exe')
    stage = work / 'modding/build/shield_sotn_assets'
    for name, expected in manifest['spell_assets'].items():
        require(sha(stage / name) == expected, f'Generated spell asset failed verification: {name}')
    for name, expected in manifest['sound_assets'].items():
        require(sha(work / 'modding/build/shield_audio/data/sound' / name) == expected, f'Generated sound failed verification: {name}')
    require(sha(work / '.setup/package/src/src/shield_rod_sotn_trace.h') == manifest['trace_header'], 'Animation geometry does not match the Shield Rod runtime.')
    context = manifest.get('local_build_context')
    if context:
        archive = resources / 'SOURCE_AND_LICENSES.zip'
        require(sha(archive) == manifest['source_archive_sha256'], 'Runtime source archive is damaged.')
        runtime, symbols = local_build.build(context, work, resources, log)
        shutil.copy2(runtime, work / 'harmonyrecomp.exe')
        shutil.copy2(symbols, work / 'harmonyrecomp.map')
        manifest['runtime'] = {'harmonyrecomp.exe': sha(runtime), 'harmonyrecomp.map': sha(symbols)}
    else:
        patch_info = manifest['executable_patch']
        patch_path = resources / patch_info['file']
        require(sha(patch_path) == patch_info['sha256'], 'Executable patch is damaged.')
        original = executable_patch.canonical_pe((game / 'harmonyrecomp.exe').read_bytes())
        require(hashlib.sha256(original).hexdigest() == patch_info['base_sha256'], 'Original executable changed during staging.')
        log('Applying and verifying the Shield Rod executable patch...')
        patched = executable_patch.apply(original, patch_path.read_bytes(), patch_info['target_size'], patch_info['target_sha256'])
        (work / 'harmonyrecomp.exe').write_bytes(patched)
        shutil.copy2(resources / 'harmonyrecomp.map', work / 'harmonyrecomp.map')
        for name, expected in manifest['runtime'].items():
            require(sha(work / name) == expected, f'Installer runtime payload is damaged: {name}')
    return package, stage


def safe_target(path, roots):
    path = Path(path)
    resolved = path.resolve()
    require(any(resolved.is_relative_to(root.resolve()) and resolved != root.resolve() for root in roots), f'Unsafe installation path: {path}')
    require(not path.is_symlink(), f'Symbolic link is not supported: {path}')
    return resolved


def transact(game, content, pairs, log, fail_after=None, assets=None):
    state = game / STATE_DIR
    journal = state / 'installation.json'
    require(not journal.exists(), 'An installation is already recorded.')
    backup = state / 'backups' / datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup.mkdir(parents=True)
    roots = [game.resolve(), content.resolve(), content.parent.resolve() / 'Headers/00000002']
    if assets is not None:
        roots.append(Path(assets).resolve())
    rows = []
    for index, (source, target) in enumerate(pairs):
        target = safe_target(target, roots)
        require(target not in [Path(row['target']) for row in rows], 'Duplicate installation target.')
        old = backup / f'{index:04}.bak'
        exists = target.is_file()
        require(not target.exists() or exists, f'Target is not a file: {target}')
        if exists:
            shutil.copy2(target, old)
        # A source of None deletes the target (a replaced stray mod file); its
        # backup brings it back on Uninstall.
        rows.append(dict(target=str(target), backup=str(old) if exists else None,
                         before_sha256=sha(old) if exists else None, sha256=sha(source) if source is not None else None))
    record = dict(format=1, game=str(game.resolve()), content=str(content.resolve()), status='installing',
                  backup=str(backup), assets=str(Path(assets).resolve()) if assets else None, files=rows)
    write_json(journal, record)  # durable recovery record before first mutation
    try:
        for index, ((source, _), row) in enumerate(zip(pairs, rows)):
            target = Path(row['target'])
            require((sha(target) if target.is_file() else None) == row['before_sha256'], f'File changed during staging: {target}')
            if source is None:
                target.unlink(missing_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.shieldrod-new')
            shutil.copy2(source, temporary)
            try:
                require(sha(temporary) == row['sha256'], f'Copy verification failed: {target}')
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            if fail_after is not None and index == fail_after:
                raise OSError('Injected installation failure')
        record['status'] = 'installed'
        write_json(journal, record)
    except Exception:
        log('Installation failed; restoring the original files...')
        restore(game, log, check_running=False, interrupted=True)
        raise
    log(f'Installed and verified {len(rows)} files. Backup: {backup}')
    return record


def install(game, disc, resources, log=print, content_override=None, ooe=None):
    stopped()
    # An earlier installation by this installer is uninstalled first (update).
    if (paths(game)[0] / STATE_DIR / 'installation.json').is_file():
        log('A previous Shield Rod installation is recorded here; uninstalling it first...')
        restore(game, log, check_running=False)
    game, assets, content, listing, chest, manifest, chapter7, chapter11, stray = preflight(game, resources, content_override, log)
    stray_lines, stray_files, _ = stray
    require(Path(disc).is_file(), 'Choose your USA SotN ISO, BIN, or CUE file.')
    # The Order of Ecclesia ROM is optional; check it before the long build.
    fx_art = extras.refectio_art(ooe, log)
    exe_before = sha(game / 'harmonyrecomp.exe')
    chest_before = chest.read_bytes()
    patched = patch_chest(chest_before)
    with tempfile.TemporaryDirectory(prefix='ShieldRod-') as tmp:
        work = Path(tmp)
        package, stage = build_payload(game, disc, resources, work, manifest, log)
        pairs = [(work / name, game / name) for name in manifest['runtime']]
        pairs += [(stage / name, assets / 'data/opd/weapon/ar' / name) for name in manifest['spell_assets']]
        sound = work / 'modding/build/shield_audio/data/sound'
        pairs += [(sound / name, assets / 'data/sound' / name) for name in manifest['sound_assets']]
        pairs.append((package, game / 'dlc' / CONTENT_ID))
        for p in (work / 'modding/build/shield_rod/contents').rglob('*'):
            if p.is_file():
                pairs.append((p, content / CONTENT_ID / p.relative_to(work / 'modding/build/shield_rod/contents')))
        header = work / 'content.header'
        header.write_bytes(content_header())
        pairs.append((header, content.parent / 'Headers/00000002' / (CONTENT_ID + '.header')))
        # Familiar cards and Refectio: packages, art, sounds, menus and drops.
        # The Chapter 8 Hard chest gets the Sword Card on top of Shield Rod's entry.
        chapter7_before = {p: p.read_bytes() for p in (chapter7 / 'data/stage' / n for n in extras.CHAPTER7[1:])}
        extra_pairs, patched, lines, headers = extras.build(
            game, assets, content, chapter7, chapter11, chest, patched, disc, resources, work, manifest, log, fx_art)
        pairs += extra_pairs
        for content_id, title in headers:
            path = work / (content_id + '.header')
            path.write_bytes(content_header(content_id, title))
            pairs.append((path, content.parent / 'Headers/00000002' / (content_id + '.header')))
        chest_stage = work / 'chapter8-hard.dat'
        chest_stage.write_bytes(patched)
        pairs.append((chest_stage, chest))
        listing_stage = work / 'dlc_packages.txt'
        kept = ''.join(line + '\n' for line in listing.splitlines() if line not in stray_lines)
        listing_stage.write_bytes((kept.rstrip('\r\n') + '\n' + CONTENT_ID + '\tpackage19\n' +
                                   ''.join(line + '\n' for line in lines)).encode('utf-8'))
        pairs.append((listing_stage, game / 'dlc_packages.txt'))
        # Stray mod files the new packages do not overwrite are deleted (backed up).
        targets = {Path(target).resolve() for _, target in pairs}
        pairs += [(None, p) for p in stray_files if p.resolve() not in targets]
        stopped()
        require(chest.read_bytes() == chest_before, 'Chapter 8 changed while assets were built. Run the installer again.')
        require(all(p.read_bytes() == data for p, data in chapter7_before.items()),
                'Chapter 7 changed while assets were built. Run the installer again.')
        require(sha(game / 'harmonyrecomp.exe') == exe_before, 'Original executable changed while assets were built. Run the installer again.')
        log('Backing up and installing Shield Rod...')
        return transact(game, content, pairs, log, assets=assets)


# dlc_packages.txt is shared with every other DLC. If it changed after
# installation (the player added DLC since; a friend's uninstall of 1.4 was
# refused for this, November 19), uninstall removes only this installer's own
# lines and keeps the rest, instead of refusing or restoring the old list.
MOD_IDS = {CONTENT_ID, extras.FAMILIAR_ID, extras.REFECTIO_ID}


def merged_dlc_list(current, original=None):
    """The DLC list without this installer's lines. With the pre-install list, that
    list is kept byte for byte (minus lines removed since) and lines added since
    are appended, so a list nobody else touched comes back exactly."""
    BOM = b'\xef\xbb\xbf'
    def lines(data):
        return data.decode('utf-8-sig').splitlines(keepends=True)
    def key(line):
        return line.strip()
    def ours(line):
        return line.split('\t')[0].strip().upper() in MOD_IDS
    now = [line for line in lines(current) if key(line) and not ours(line)]
    if original is None:
        return (BOM if current.startswith(BOM) else b'') + ''.join(now).encode('utf-8')
    present = {key(line) for line in now}
    before = lines(original)
    kept = [line for line in before if not key(line) or key(line) in present]
    known = {key(line) for line in before}
    newline = '\r\n' if '\r\n' in original.decode('utf-8-sig') else '\n'
    added = [key(line) + newline for line in now if key(line) not in known]
    if added and kept and not kept[-1].endswith(('\n', '\r')):
        kept[-1] += newline
    return (BOM if original.startswith(BOM) else b'') + ''.join(kept + added).encode('utf-8')


def restore(game, log=print, check_running=True, interrupted=False):
    if check_running:
        stopped()
    game = Path(game).resolve()
    journal = game / STATE_DIR / 'installation.json'
    require(journal.is_file(), 'No Shield Rod installation or recovery record found in this folder.')
    record = json.loads(journal.read_text(encoding='utf-8'))
    require(record['format'] == 1 and Path(record['game']).resolve() == game, 'This backup belongs to another recomp folder.')
    content = Path(record['content']).resolve()
    roots = [game, content, content.parent / 'Headers/00000002']
    if record.get('assets'):
        roots.append(Path(record['assets']).resolve())
    # Validate everything before restoring anything. Do not overwrite later mods.
    dlc_list = (game / 'dlc_packages.txt').resolve()
    merged = {}
    for row in record['files']:
        target = safe_target(row['target'], roots)
        current = sha(target) if target.is_file() else None
        if target == dlc_list and current is not None and current not in (row['sha256'], row['before_sha256']):
            merged[str(target)] = merged_dlc_list(target.read_bytes(),
                                                  Path(row['backup']).read_bytes() if row['backup'] else None)
            continue
        require(current in (row['sha256'], row['before_sha256']), f'File changed after installation: {target}. Restore your later changes first; original backups remain available at {record["backup"]}.')
        if row['backup']:
            backup = Path(row['backup']).resolve()
            require(backup.is_relative_to((game / STATE_DIR / 'backups').resolve()) and sha(backup) == row['before_sha256'], 'An original backup is missing or damaged.')
    for row in reversed(record['files']):
        target = Path(row['target'])
        if str(safe_target(target, roots)) in merged:
            data = merged[str(safe_target(target, roots))]
            temporary = target.with_name(target.name + '.shieldrod-new')
            temporary.write_bytes(data)
            os.replace(temporary, target)
            require(target.read_bytes() == data, f'Restore verification failed: {target}')
            log('dlc_packages.txt changed after installation (other DLC added since); '
                'removed only the Shield Rod, familiar card and Refectio entries and kept the rest.')
        elif row['backup']:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(row['backup'], target)
            require(sha(target) == row['before_sha256'], f'Restore verification failed: {target}')
        else:
            target.unlink(missing_ok=True)
            # Remove only empty directories created for this mod, never trees.
            parent = target.parent
            while parent not in roots and any(parent.is_relative_to(r) for r in roots):
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
    record['status'] = 'rolled_back' if interrupted else 'uninstalled'
    write_json(Path(record['backup']) / 'restoration.json', record)
    journal.unlink()
    log('Original files restored and verified. Shield Rod, familiar card and Refectio content removed. Backups retained.')
    return record
