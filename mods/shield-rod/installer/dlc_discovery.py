"""Find mounted Chapter 8 content without confusing it with source packages.

The recomp's dlc.cpp unpacks each enabled STFS package from <game>/dlc (or
<game_data_root parent>/dlc) into the SDK content folder below the user data
root. The installer must patch and extend that mounted copy, never the raw
source package, so this module locates it and explains every place it looked.
"""
from pathlib import Path
import os
import re

SUFFIX = Path('0000000000000000/58410A7A/00000002')
STAGE = Path('data/stage/stage00_03_set_hard.dat')
MARKER = re.compile(r'package0*2\.dat', re.I)


class DiscoveryError(ValueError):
    def __init__(self, message, details):
        super().__init__(message)
        self.details = details


XCONTENT_NAME_LENGTH = 42


def installed_name(name):
    """The folder name the recomp unpacks a package file into.

    XCONTENT file names hold at most 42 characters and the SDK cuts longer ones,
    so a renamed package file (official names are exactly 42) is unpacked under
    its first 42 characters. Every comparison with a folder name uses this.
    """
    return name.strip()[:XCONTENT_NAME_LENGTH].casefold()


def listed_packages(text):
    """dlc.cpp BuiltList: 'filename<TAB>id' lines, or the filename alone.

    Keys are installed folder names (installed_name), not file names.
    """
    result = {}
    for line in text.lstrip('﻿').splitlines():
        line = line.rstrip('\r\n ')
        if not line:
            continue
        name, sep, package_id = line.partition('\t')
        result[installed_name(name)] = package_id.strip().casefold() if sep else None
    return result


def safe(call, default, problems, what):
    try:
        return call()
    except OSError as error:
        problems.append(f'{what}: {error.strerror or error}')
        return default


def package_folder(path):
    """The extracted package folder containing a selected path, if any."""
    for parent in [path, *list(path.parents)[:3]]:
        if (parent / '000info').is_dir():
            return parent
    return None


def locations(path):
    path = Path(path).resolve()
    # Selecting the package itself, 000info, data or data/stage is also useful.
    folder = package_folder(path)
    if folder is not None:
        yield folder.parent
    for root in (path, path / '00000002', path / '58410A7A/00000002',
                 path / SUFFIX, path / 'content' / SUFFIX):
        yield root.resolve()


def has_mounted_packages(path):
    for root in locations(path):
        try:
            if any((child / '000info').is_dir() for child in root.iterdir() if child.is_dir()):
                return True
        except OSError:
            continue
    return False


def home_bases():
    # Overridden in tests so a fixture can never see the real user's content.
    bases = [Path.home() / 'Documents/harmonyrecomp']
    for variable, fallback in [('LOCALAPPDATA', Path.home() / 'AppData/Local'),
                               ('APPDATA', Path.home() / 'AppData/Roaming')]:
        bases.append(Path(os.environ.get(variable) or fallback) / 'harmonyrecomp')
    return bases


def logged_user_roots(game):
    """'User data: PATH' from the newest startup logs of this recomp."""
    logs = []
    try:
        logs = sorted((game / 'logs').glob('harmonyrecomp*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        pass
    for log in logs[:3]:
        try:
            with log.open('r', encoding='utf-8', errors='replace') as stream:
                match = re.search(r'\bUser data:\s*([^\r\n]+)', stream.read(16384))
        except OSError:
            continue
        if match:
            yield Path(match.group(1).strip())


def logged_packages(game):
    """Package names the newest startup log reports as installed by dlc.cpp."""
    names = set()
    try:
        logs = sorted((game / 'logs').glob('harmonyrecomp*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
        if logs:
            with logs[0].open('r', encoding='utf-8', errors='replace') as stream:
                text = stream.read(1 << 20)
            for match in re.finditer(r'\[dlc\] (?:installed (.+?)|(.+?) is installed)\s*$', text, re.M):
                names.add(installed_name(match.group(1) or match.group(2)))
    except OSError:
        pass
    return names


def user_roots(game, configured_content, settings, documents_path):
    # An explicit user_data_root is a scope boundary. Never fall through from a
    # missing DLC in one profile to somebody else's global/shared content.
    if settings.get('user_data_root'):
        yield configured_content
        # SDK releases have used both direct and content/ subdirectory layouts.
        yield configured_content.parents[2] / 'content' / SUFFIX
        return
    for root in logged_user_roots(game):
        yield from locations(root)
    yield configured_content
    bases = [documents_path / 'harmonyrecomp', *home_bases(),
             game / 'userdata', game / 'user_data', game]
    for base in bases:
        yield from locations(base)


def raw_packages(path):
    path = Path(path)
    try:
        files = [path] if path.is_file() else list(path.iterdir()) if path.is_dir() else []
    except OSError:
        return
    for item in files:
        try:
            if not item.is_file():
                continue
            with item.open('rb') as stream:
                header = stream.read(0x400)
        except OSError:
            continue
        if (header[:4] in (b'LIVE', b'PIRS', b'CON ') and len(header) == 0x400 and
                int.from_bytes(header[0x344:0x348], 'big') == 2 and
                int.from_bytes(header[0x360:0x364], 'big') == 0x58410A7A):
            yield item


def find(game, assets, configured_content, listing, override, settings, documents_path, validate_stage):
    game, assets = Path(game).resolve(), Path(assets).resolve()
    configured_content = Path(configured_content).resolve()
    listed = listed_packages(listing)
    enabled = set(listed) | logged_packages(game)
    chapter8_built = 'package02' in listed.values()
    sources = {(game / 'dlc').resolve(), (assets.parent / 'dlc').resolve(),
               (game / '.setup/package/src/assets/dlc').resolve()}
    hints, candidates, pinned = [], [], None
    if override and str(override).strip():
        selected = Path(os.path.expandvars(str(override).strip().strip('"'))).expanduser().resolve()
        if not selected.exists():
            raise DiscoveryError(f'The selected DLC location does not exist: {selected}',
                                 f'Selected DLC location: {selected} (missing)')
        packed = list(raw_packages(selected))
        known_source = selected in sources or any(selected.is_relative_to(p) for p in sources)
        # A folder can hold both unpacked package folders and loose STFS files;
        # prefer the mounted layout unless it is one of the recomp's source roots.
        if known_source or (packed and not has_mounted_packages(selected)):
            hints.append(f'Selected source-package location: {selected} ({len(packed)} HoD package files). '
                         'Searching the extracted content folder used by the recomp instead.')
            candidates += list(user_roots(game, configured_content, settings, documents_path))
        else:
            # An explicitly selected extracted location must not silently fall
            # through to a different copy/profile when it is wrong.
            hints.append(f'Selected extracted content location: {selected}')
            pinned = package_folder(selected)
            candidates += list(locations(selected))
    else:
        if settings.get('user_data_root'):
            hints.append(f'user_data_root in harmonyrecomp.toml: {settings["user_data_root"]}')
        candidates += list(user_roots(game, configured_content, settings, documents_path))
    seen, searched, unlisted, invalid, problems = set(), [], [], [], []
    for root in candidates:
        root = root.resolve()
        if root in seen or any(root == p or root.is_relative_to(p) for p in sources):
            continue
        seen.add(root)
        if not safe(root.is_dir, False, problems, str(root)):
            searched.append(f'{root} (not present)')
            continue
        searched.append(str(root))
        matches, others = [], []
        for folder in safe(lambda: sorted(root.iterdir()), [], problems, str(root)):
            if not safe(folder.is_dir, False, problems, str(folder)):
                continue
            if pinned is not None and folder != pinned:
                continue
            info = folder / '000info'
            markers = safe(lambda: [p for p in info.glob('package*.dat') if MARKER.fullmatch(p.name)],
                           [], problems, str(info))
            if not markers:
                continue
            stage = folder / STAGE
            try:
                valid = stage.is_file() and bool(validate_stage(stage))
                reason = 'stage file missing' if not stage.is_file() else 'stage is not the Legion Hard stage'
            except (OSError, ValueError) as error:
                valid, reason = False, str(error)
            if not valid:
                invalid.append(f'{folder} ({reason})')
                continue
            # Identity is the package02 marker plus its real Legion stage data.
            # The folder name usually equals a dlc_packages.txt entry, but real
            # installs exist where it does not and the game still plays it.
            (matches if installed_name(folder.name) in enabled else others).append(stage)
        if len(matches) == 1:
            found = matches[0].parents[2]
            return root, matches[0], '\n'.join(hints + [f'Chapter 8 mounted content: {found}'])
        if len(matches) > 1:
            raise DiscoveryError('Multiple enabled Chapter 8 copies were found. Select the extracted Chapter 8 folder you use.',
                                 '\n'.join(hints + ['Enabled Chapter 8 copies:'] + [str(p.parents[2]) for p in matches]))
        if len(others) == 1:
            found = others[0].parents[2]
            note = ('dlc_packages.txt enables Chapter 8 (package02) under a different file name'
                    if chapter8_built else 'its folder name is not listed in dlc_packages.txt')
            return root, others[0], '\n'.join(hints + [
                f'Chapter 8 mounted content: {found}',
                f'Note: {note}; using the only Chapter 8 copy in this content folder.'])
        unlisted += [str(p.parents[2]) for p in others]
    details = hints + ['Content locations checked:'] + searched
    if unlisted:
        details += ['Chapter 8 copies not named in dlc_packages.txt:'] + unlisted
    if invalid:
        details += ['Chapter 8 markers with missing/invalid Legion stage data:'] + invalid
    if problems:
        details += ['Locations that could not be read:'] + problems
    details = '\n'.join(details)
    if unlisted:
        message = ('Several Chapter 8 copies were found and none is named in this recomp\'s dlc_packages.txt. '
                   'Select the extracted Chapter 8 folder the game uses. See the log for details.')
    elif invalid:
        message = ('Chapter 8 was identified, but its extracted Hard stage data is missing or invalid. Launch the '
                   'game to extract the DLC again, or select its mounted content folder. See the log for details.')
    elif problems:
        message = ('Some DLC locations could not be read (permission denied or in use). Close other programs '
                   'using them and retry, or select the extracted Chapter 8 folder. See the log for details.')
    else:
        message = ('Chapter 8 mounted content was not found. The dlc folder holds the original packages; the game '
                   'unpacks them into its user data folder the first time it starts with them. Launch this recomp '
                   'once, close it, then retry with the location blank or select the extracted Chapter 8 folder '
                   '(it contains 000info and data). See the log for the paths checked.')
    raise DiscoveryError(message, details)
