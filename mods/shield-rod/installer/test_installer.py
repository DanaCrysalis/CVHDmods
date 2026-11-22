"""Installer transaction tests and an isolated, real-disc end-to-end fixture."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
from pathlib import Path
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import bz2
import struct
import executable_patch

HERE = Path(__file__).parent
ROOT = hodpaths.GAME  # the development machine's game folder
OUT = hodpaths.legacy('modding/build/shield_rod_universal')
sys.path.insert(0, str(OUT / 'converters'))
import installer_core as core
import dlc_discovery
import shield_stfs


class Transactions(unittest.TestCase):
    def test_ninja_paths_and_rules_are_data(self):
        import local_build
        self.assertEqual(local_build.ninja_words('D$:/a$ b/file.obj other.obj | sdk.lib'),
                         ['D:/a b/file.obj', 'other.obj', '|', 'sdk.lib'])
        with tempfile.TemporaryDirectory(dir=OUT) as tmp:
            ninja = Path(tmp) / 'build.ninja'
            ninja.write_text('build ignored: CUSTOM_COMMAND\n  COMMAND = DO_NOT_EXECUTE\n'
                             'build x.obj: CXX_COMPILER__harmonyrecomp_Release D$:/a$ b/x.cpp\n'
                             '  FLAGS = -O3\n')
            edges = local_build.read_edges(ninja)
            self.assertEqual(set(edges), {'x.obj'})
            self.assertEqual(edges['x.obj']['inputs'], ['D:/a b/x.cpp'])
        with self.assertRaises(ValueError):
            local_build.ninja_words('$unknown')

    def test_windows_compiler_arguments(self):
        import local_build
        args = local_build.windows_arguments('-I"D:/a b/include" -DVERSION=\\"v0.6.0\\"')
        self.assertEqual(args, ['-ID:/a b/include', '-DVERSION="v0.6.0"'])

    def test_missing_setup_explains_recovery(self):
        import local_build
        with tempfile.TemporaryDirectory(dir=OUT) as tmp:
            with self.assertRaisesRegex(ValueError, 'rerun official 0.6.0 Setup'):
                local_build.locate(Path(tmp))

    def test_wrong_setup_release_is_refused(self):
        import local_build
        with tempfile.TemporaryDirectory(dir=OUT) as tmp:
            setup = Path(tmp) / '.setup'
            (setup / 'package').mkdir(parents=True)
            (setup / 'package/release.txt').write_text('v0.5.0')
            with self.assertRaisesRegex(ValueError, 'v0.6.0'):
                local_build.plan(Path(tmp), setup=setup)

    def test_patch_application_and_integrity(self):
        def signed(value):
            return (abs(value) | (1 << 63 if value < 0 else 0)).to_bytes(8, 'little')
        controls = b''.join(signed(v) for v in [0, 0, 2, 2, 0, -4, 2, 0, 0])
        control, difference, extra = bz2.compress(controls), bz2.compress(bytes(4)), bz2.compress(b'')
        patch = b'BSDIFF40' + signed(len(control)) + signed(len(difference)) + signed(4) + control + difference + extra
        expected = b'cdab'
        self.assertEqual(executable_patch.apply(b'abcd', patch, 4, hashlib.sha256(expected).hexdigest()), expected)
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            executable_patch.apply(b'abXd', patch, 4, hashlib.sha256(expected).hexdigest())
        with self.assertRaises(ValueError):
            executable_patch.apply(b'abcd', patch, 5, hashlib.sha256(expected).hexdigest())

    def test_only_timestamp_and_checksum_are_normalized(self):
        original = bytearray(512)
        original[:2] = b'MZ'
        struct.pack_into('<I', original, 60, 64)
        original[64:68] = b'PE\0\0'
        canonical = executable_patch.canonical_pe(original)
        struct.pack_into('<I', original, 72, 123456)
        struct.pack_into('<I', original, 152, 654321)
        self.assertEqual(executable_patch.canonical_pe(original), canonical)
        original[256] = 1
        self.assertNotEqual(executable_patch.canonical_pe(original), canonical)

    def test_pcm_standard_library_conversion(self):
        from portable_pcm import finish_pcm
        import wave
        with tempfile.TemporaryDirectory(dir=OUT) as tmp:
            root = Path(tmp)
            samples = [0] * 400
            samples[8], samples[9] = 100, -200
            raw, wave_file = root / 'raw', root / 'sound.wav'
            raw.write_bytes(struct.pack('<400h', *samples))
            pcm, count, peak = finish_pcm(raw, wave_file, 0x641, 100)
            self.assertEqual((count, peak), (7, 200))
            self.assertEqual(pcm, struct.pack('>14h', *samples[:14]))
            with wave.open(str(wave_file), 'rb') as audio:
                self.assertEqual(audio.readframes(7), struct.pack('<14h', *samples[:14]))

    def test_raster_slices_and_pixel_order(self):
        import portable_raster as raster
        words = raster.frombuffer(struct.pack('<4H', 0x3210, 0x7654, 0xba98, 0xfedc), '<u2').reshape(2, 2)
        pixels = raster.nibbles(words)
        self.assertEqual(pixels.flatten().tolist(), list(range(16)))
        page = raster.zeros((2, 8))
        page[0:2, 0:8] = raster.repeat(pixels[0:2, 0:4], 2, axis=1)
        self.assertEqual(page.rows, [[0, 0, 1, 1, 2, 2, 3, 3], [8, 8, 9, 9, 10, 10, 11, 11]])

    def test_install_restore_and_interruption(self):
        for failure in [None, 0, 1]:
            with tempfile.TemporaryDirectory(dir=OUT) as tmp:
                root = Path(tmp)
                game = root / 'game'
                game.mkdir()
                content = root / 'content'
                content.mkdir()
                old, new, source = game / 'old', content / 'new', root / 'source'
                old.write_bytes(b'original')
                source.write_bytes(b'modified')
                pairs = [(source, old), (source, new)]
                if failure is not None:
                    with self.assertRaises(OSError):
                        core.transact(game, content, pairs, lambda _: None, fail_after=failure)
                else:
                    core.transact(game, content, pairs, lambda _: None)
                    self.assertEqual(new.read_bytes(), b'modified')
                    core.restore(game, lambda _: None, check_running=False)
                self.assertEqual(old.read_bytes(), b'original')
                self.assertFalse(new.exists())
                self.assertFalse((game / core.STATE_DIR / 'installation.json').exists())

    def test_modified_file_blocks_all_restore_writes(self):
        with tempfile.TemporaryDirectory(dir=OUT) as tmp:
            root = Path(tmp)
            source, game, content = root / 'source', root / 'game', root / 'content'
            game.mkdir(); content.mkdir(); source.write_bytes(b'mod')
            a, b = game / 'a', game / 'b'
            a.write_bytes(b'original a'); b.write_bytes(b'original b')
            core.transact(game, content, [(source, a), (source, b)], lambda _: None)
            b.write_bytes(b'later mod')
            with self.assertRaisesRegex(ValueError, 'changed after installation'):
                core.restore(game, lambda _: None, check_running=False)
            self.assertEqual(a.read_bytes(), b'mod')
            self.assertEqual(b.read_bytes(), b'later mod')

    def test_dlc_list_added_to_later_keeps_new_lines(self):
        with tempfile.TemporaryDirectory(dir=OUT) as tmp:
            root = Path(tmp)
            game, content, staged = root / 'game', root / 'content', root / 'staged'
            game.mkdir(); content.mkdir()
            listing = game / 'dlc_packages.txt'
            listing.write_bytes(b'CHAPTER8\tpackage02\r\n')
            staged.write_bytes(listing.read_bytes() + (core.CONTENT_ID + '\tpackage19\n' +
                               core.extras.FAMILIAR_ID + '\tpackage21\n').encode())
            other = game / 'other'
            other.write_bytes(b'original')
            changed = root / 'changed'
            changed.write_bytes(b'mod')
            core.transact(game, content, [(staged, listing), (changed, other)], lambda _: None)
            # The player installs another DLC afterwards.
            listing.write_bytes(listing.read_bytes() + b'NEWDLC\tpackage05\n')
            logs = []
            core.restore(game, logs.append, check_running=False)
            self.assertEqual(listing.read_bytes(), b'CHAPTER8\tpackage02\r\nNEWDLC\tpackage05\r\n')
            # A line removed since installation stays removed.
            self.assertEqual(core.merged_dlc_list(b'NEWDLC\tpackage05\n', b'A\tpackage02\r\nB\tpackage03\r\n'),
                             b'NEWDLC\tpackage05\r\n')
            self.assertEqual(other.read_bytes(), b'original')
            self.assertTrue(any('kept the rest' in line for line in logs))
            # Unchanged since installation: the original list comes back byte for byte.
            listing.write_bytes(b'CHAPTER8\tpackage02\r\n')
            core.transact(game, content, [(staged, listing)], lambda _: None)
            core.restore(game, lambda _: None, check_running=False)
            self.assertEqual(listing.read_bytes(), b'CHAPTER8\tpackage02\r\n')

    def test_deletion_is_restored(self):
        with tempfile.TemporaryDirectory(dir=OUT) as tmp:
            root = Path(tmp)
            game, content = root / 'game', root / 'content'
            game.mkdir(); content.mkdir()
            stray = content / 'old' / 'file.dat'
            stray.parent.mkdir()
            stray.write_bytes(b'stray mod file')
            core.transact(game, content, [(None, stray)], lambda _: None)
            self.assertFalse(stray.exists())
            core.restore(game, lambda _: None, check_running=False)
            self.assertEqual(stray.read_bytes(), b'stray mod file')

    def test_stray_mod_packages_are_found(self):
        with tempfile.TemporaryDirectory(dir=OUT) as tmp:
            root = Path(tmp)
            game, content = root / 'game', root / 'user/0000000000000000/58410A7A/00000002'
            (game / 'dlc').mkdir(parents=True); content.mkdir(parents=True)
            fam = core.extras.FAMILIAR_ID
            listing = (CHAPTER + '\tpackage02\n' + fam + '\tpackage21\n' + 'NATHAN COPY\tpackage17\n')
            (game / 'dlc' / fam).write_bytes(b'pkg')
            (game / 'dlc' / 'NATHAN COPY').write_bytes(b'pkg')
            (game / 'dlc' / CHAPTER).write_bytes(b'official')
            (content / fam / '000info').mkdir(parents=True)
            (content / fam / '000info/package21.dat').write_bytes(b'PackageInfo\r\n')
            headers = content.parent / 'Headers/00000002'
            headers.mkdir(parents=True)
            (headers / (fam + '.header')).write_bytes(b'h')
            lines, files, names = core.stray_mods(game, content, listing)
            self.assertEqual(lines, [fam + '\tpackage21', 'NATHAN COPY\tpackage17'])
            self.assertEqual({p.name for p in files}, {fam, 'NATHAN COPY', 'package21.dat', fam + '.header'})
            self.assertIn('Alucard familiar cards', names)
            self.assertIn('Nathan', names)
            self.assertNotIn(game / 'dlc' / CHAPTER, files)

    def test_path_escape(self):
        with tempfile.TemporaryDirectory(dir=OUT) as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                core.safe_target(root / 'allowed/../outside', [root / 'allowed'])

    def test_disc_sector_formats(self):
        import sotn_disc
        for stride, offset in [(2048, 0), (2352, 24), (2352, 16)]:
            with tempfile.TemporaryDirectory(dir=OUT) as tmp:
                image = bytearray(18 * stride)
                pvd = bytearray(2048)
                pvd[:7] = b'\x01CD001\x01'
                pvd[40:72] = b'SLUS_00067'.ljust(32, b' ')
                pvd[156] = 34
                pvd[188] = 1
                image[16*stride+offset:16*stride+offset+2048] = pvd
                path = Path(tmp) / 'disc.iso'
                path.write_bytes(image)
                disc = sotn_disc.Disc(path)
                self.assertEqual(disc.sector(16), pvd)
                with self.assertRaises(ValueError):
                    disc.sector(100)
                disc.f.close()



CHAPTER = '9CF520072EB8FA1F1BFFAE7F2C4CC375043CDA9658'
FIXTURE_STAGE = OUT / 'test_game/userdata' / dlc_discovery.SUFFIX / CHAPTER / 'data/stage' / core.STAGE_NAME


def stfs_header():
    header = bytearray(0x400)
    header[:4] = b'LIVE'
    header[0x344:0x348] = (2).to_bytes(4, 'big')
    header[0x360:0x364] = (0x58410A7A).to_bytes(4, 'big')
    return bytes(header)


class Discovery(unittest.TestCase):
    """Chapter 8 detection across the layouts users actually have."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=OUT)
        self.root = Path(self.tmp.name)
        self.game = self.root / 'game'
        (self.game / 'assets').mkdir(parents=True)
        self.docs = self.root / 'Documents'
        self.docs.mkdir()
        self.stage = FIXTURE_STAGE.read_bytes()
        # Never let a test see the real user's Documents/AppData content.
        self.saved = dlc_discovery.home_bases
        dlc_discovery.home_bases = lambda: []

    def tearDown(self):
        dlc_discovery.home_bases = self.saved
        self.tmp.cleanup()

    def mounted(self, content, name=CHAPTER, stage=None, marker='package02.dat'):
        folder = Path(content) / name
        (folder / '000info').mkdir(parents=True)
        (folder / '000info' / marker).write_bytes(b'PackageInfo\r\n')
        (folder / 'data/stage').mkdir(parents=True)
        (folder / 'data/stage' / core.STAGE_NAME).write_bytes(self.stage if stage is None else stage)
        return folder

    def find(self, listing=CHAPTER + '\n', override=None, settings=None, configured=None):
        configured = configured or self.docs / 'harmonyrecomp' / dlc_discovery.SUFFIX
        return dlc_discovery.find(self.game, self.game / 'assets', configured, listing, override,
                                  settings or {}, self.docs, core.chapter8_stage)

    def scoped(self):
        user = self.game / 'userdata'
        return dict(settings={'user_data_root': 'userdata'}, configured=user / dlc_discovery.SUFFIX), user

    def test_validator_reads_the_real_stage(self):
        self.assertTrue(core.chapter8_stage(FIXTURE_STAGE))
        bad = self.root / 'bad.dat'
        bad.write_bytes(b'SSD*' + bytes(60))
        with self.assertRaises(ValueError):
            core.chapter8_stage(bad)

    def test_filename_only_and_tagged_allowlists(self):
        args, user = self.scoped()
        folder = self.mounted(user / dlc_discovery.SUFFIX)
        for listing in [CHAPTER + '\n', '\ufeff' + CHAPTER + '\r\n', CHAPTER + '\tpackage02\n',
                        'OTHER\tpackage01\n' + CHAPTER.lower() + ' \n']:
            content, stage, _ = self.find(listing, **args)
            self.assertEqual(stage.parents[2], folder.resolve())
            self.assertEqual(content, (user / dlc_discovery.SUFFIX).resolve())

    def test_raw_dlc_override_resolves_to_mounted_profile(self):
        args, user = self.scoped()
        folder = self.mounted(user / dlc_discovery.SUFFIX)
        raw = self.game / 'dlc'
        raw.mkdir()
        (raw / CHAPTER).write_bytes(stfs_header())
        for override in [raw, raw / CHAPTER]:
            content, stage, text = self.find(override=override, **args)
            self.assertEqual(stage.parents[2], folder.resolve())
            self.assertIn('source-package', text)
            self.assertFalse(content.is_relative_to(raw.resolve()))

    def test_hybrid_folder_prefers_mounted_layout(self):
        args, _ = self.scoped()
        other = self.root / 'copied'
        folder = self.mounted(other)
        (other / 'loose_package').write_bytes(stfs_header())
        _, stage, _ = self.find(override=other, **args)
        self.assertEqual(stage.parents[2], folder.resolve())

    def test_direct_selection_variants(self):
        user = self.root / 'profile'
        folder = self.mounted(user / dlc_discovery.SUFFIX)
        for selected in [folder, folder / '000info', folder / 'data', folder / 'data/stage',
                         folder / 'data/stage' / core.STAGE_NAME, user / dlc_discovery.SUFFIX,
                         user / '0000000000000000/58410A7A', user]:
            _, stage, _ = self.find(override=selected)
            self.assertEqual(stage.parents[2], folder.resolve(), selected)

    def test_selected_package_disambiguates_duplicates(self):
        content = self.root / 'profile' / dlc_discovery.SUFFIX
        self.mounted(content)
        second = self.mounted(content, 'RENAMED_CHAPTER8')
        listing = CHAPTER + '\nRENAMED_CHAPTER8\n'
        with self.assertRaisesRegex(dlc_discovery.DiscoveryError, 'Multiple'):
            self.find(listing, override=content)
        _, stage, _ = self.find(listing, override=second)
        self.assertEqual(stage.parents[2], second.resolve())

    def test_content_subfolder_layout(self):
        args, user = self.scoped()
        folder = self.mounted(user / 'content' / dlc_discovery.SUFFIX)
        _, stage, _ = self.find(**args)
        self.assertEqual(stage.parents[2], folder.resolve())

    def test_redirected_and_literal_documents(self):
        redirected = self.mounted(self.docs / 'harmonyrecomp' / dlc_discovery.SUFFIX)
        _, stage, _ = self.find()
        self.assertEqual(stage.parents[2], redirected.resolve())
        shutil.rmtree(self.docs / 'harmonyrecomp')
        literal = self.root / 'home/Documents/harmonyrecomp'
        folder = self.mounted(literal / dlc_discovery.SUFFIX)
        dlc_discovery.home_bases = lambda: [literal]
        _, stage, _ = self.find()
        self.assertEqual(stage.parents[2], folder.resolve())

    def test_startup_log_user_data_root_wins(self):
        logged = self.root / 'Elsewhere/harmonyrecomp'
        folder = self.mounted(logged / dlc_discovery.SUFFIX)
        self.mounted(self.docs / 'harmonyrecomp' / dlc_discovery.SUFFIX, 'DOCUMENTS_COPY')
        (self.game / 'logs').mkdir()
        (self.game / 'logs/harmonyrecomp_7.log').write_text(
            '[2026-11-16 20:08:06.727] [info] [core] [t1]   User data:      ' + str(logged) + '\n')
        _, stage, _ = self.find(CHAPTER + '\nDOCUMENTS_COPY\n')
        self.assertEqual(stage.parents[2], folder.resolve())

    def test_folder_name_differing_from_list_is_used(self):
        # Seen on a real OneDrive install: the mounted folder lacked the
        # package file's last two characters, and Chapter 8 played in game.
        args, user = self.scoped()
        folder = self.mounted(user / dlc_discovery.SUFFIX, CHAPTER[:40])
        _, stage, text = self.find(CHAPTER + '\tpackage02\n', **args)
        self.assertEqual(stage.parents[2], folder.resolve())
        self.assertIn('different file name', text)
        _, stage, text = self.find('SOMETHING_ELSE\n', **args)
        self.assertEqual(stage.parents[2], folder.resolve())
        self.assertIn('not listed', text)

    def test_long_package_file_name_matches_its_installed_folder(self):
        # Tester's install, November 20: a renamed 44-character Chapter 8 file.
        # XCONTENT names hold 42 characters, so it unpacks under its first 42.
        long_name = '9CF5200072EB8FA1F1BFFAE7F22C4CC375043CDA9658'
        self.assertEqual(dlc_discovery.installed_name(long_name), long_name[:42].casefold())
        self.assertEqual(dlc_discovery.installed_name(CHAPTER), CHAPTER.casefold())
        args, user = self.scoped()
        folder = self.mounted(user / dlc_discovery.SUFFIX, long_name[:42])
        self.mounted(user / dlc_discovery.SUFFIX, 'STALE_COPY')
        _, stage, text = self.find(long_name + '\tpackage02\n', **args)
        self.assertEqual(stage.parents[2], folder.resolve())
        self.assertNotIn('Note:', text)
        # dlc.cpp logs the file name, not the folder name.
        (self.game / 'logs').mkdir()
        (self.game / 'logs/harmonyrecomp_4.log').write_text(f'[info] [core] [t1] [dlc] installed {long_name}\n')
        _, stage, text = self.find('SOMETHING_ELSE\n', **args)
        self.assertEqual(stage.parents[2], folder.resolve())
        self.assertNotIn('Note:', text)

    def test_extras_find_long_named_chapter(self):
        # extras.find_package (Chapters 7 and 11) must match installed folder names too.
        import extras
        content = self.root / 'content'
        long_name = '36DA9EF296B35F21C2470D71D9A21F5F8DFC6DDE5800'
        folder = content / long_name[:42]
        for copy in (folder, content / 'STALE_COPY'):  # two copies: only name matching can pick one
            (copy / '000info').mkdir(parents=True)
            (copy / '000info/package01.dat').write_bytes(b'PackageInfo\r\n')
        enabled = set(dlc_discovery.listed_packages(long_name + '\tpackage01\n'))
        self.assertEqual(extras.find_package(content, enabled, 'package01', lambda f: True, 'Chapter 7'), folder)

    def test_recomp_fix_applies_only_to_the_stock_source(self):
        import zipfile
        import local_build
        stock = zipfile.ZipFile(ROOT / '.setup/downloads/harmonyrecomp-package.zip').read('src/src/dlc.cpp')
        src = self.root / 'setup_src'
        (src / 'src').mkdir(parents=True)
        for text, expected in [(stock, ['dlc.cpp']), (stock.replace(b'\r\n', b'\n'), ['dlc.cpp']),
                               (stock + b'// changed\r\n', [])]:
            (src / 'src/dlc.cpp').write_bytes(text)
            self.assertEqual(local_build.recomp_fixes(src), expected)
        (src / 'src/dlc.cpp').unlink()
        self.assertEqual(local_build.recomp_fixes(src), [])
        # The shipped source (with the fix) must not count as the stock file.
        self.assertEqual(local_build.recomp_fixes(ROOT / '.setup/package/src'), [])

    def test_listed_copy_beats_unlisted_and_unlisted_duplicates_refused(self):
        args, user = self.scoped()
        listed = self.mounted(user / dlc_discovery.SUFFIX)
        self.mounted(user / dlc_discovery.SUFFIX, 'STALE_COPY')
        _, stage, text = self.find(CHAPTER + '\n', **args)
        self.assertEqual(stage.parents[2], listed.resolve())
        self.assertNotIn('Note:', text)
        with self.assertRaisesRegex(dlc_discovery.DiscoveryError, 'Several') as caught:
            self.find('SOMETHING_ELSE\n', **args)
        self.assertIn('STALE_COPY', caught.exception.details)

    def test_log_reported_package_counts_as_enabled(self):
        args, user = self.scoped()
        self.mounted(user / dlc_discovery.SUFFIX, 'STALE_COPY')
        logged = self.mounted(user / dlc_discovery.SUFFIX, 'LOGGED NAME')
        (self.game / 'logs').mkdir()
        (self.game / 'logs/harmonyrecomp_3.log').write_text(
            '[info] [core] [t1] [dlc] LOGGED NAME is installed\n[info] [core] [t1] [dlc] installed OTHER\n')
        _, stage, text = self.find('SOMETHING_ELSE\n', **args)
        self.assertEqual(stage.parents[2], logged.resolve())
        self.assertNotIn('Note:', text)

    def test_invalid_stage_is_explained(self):
        args, user = self.scoped()
        self.mounted(user / dlc_discovery.SUFFIX, stage=b'not a stage')
        with self.assertRaisesRegex(dlc_discovery.DiscoveryError, 'invalid'):
            self.find(**args)

    def test_missing_dlc_never_leaves_configured_profile(self):
        args, user = self.scoped()
        (user / dlc_discovery.SUFFIX).mkdir(parents=True)
        self.mounted(self.docs / 'harmonyrecomp' / dlc_discovery.SUFFIX)
        global_copy = self.root / 'home/harmonyrecomp'
        self.mounted(global_copy / dlc_discovery.SUFFIX)
        dlc_discovery.home_bases = lambda: [global_copy]
        with self.assertRaisesRegex(dlc_discovery.DiscoveryError, 'not found') as caught:
            self.find(**args)
        self.assertNotIn(str(self.docs), caught.exception.details)
        self.assertNotIn(str(global_copy), caught.exception.details)
        with self.assertRaisesRegex(dlc_discovery.DiscoveryError, 'does not exist'):
            self.find(override=self.root / 'nowhere', **args)

    def test_duplicate_enabled_copies_are_refused(self):
        args, user = self.scoped()
        self.mounted(user / dlc_discovery.SUFFIX)
        self.mounted(user / dlc_discovery.SUFFIX, 'RENAMED_CHAPTER8', marker='package2.dat')
        with self.assertRaisesRegex(dlc_discovery.DiscoveryError, 'Multiple'):
            self.find(CHAPTER + '\nRENAMED_CHAPTER8\n', **args)

    def test_preflight_accepts_legacy_list_before_compatibility_checks(self):
        (self.game / 'harmonyrecomp.exe').write_bytes(b'MZ')
        (self.game / 'harmonyrecomp.toml').write_text('user_data_root = "userdata"\n')
        folder = self.mounted(self.game / 'userdata' / dlc_discovery.SUFFIX)
        (self.game / 'dlc_packages.txt').write_text(CHAPTER + '\n')
        logs = []
        # Discovery passes; the empty fake recomp then fails on missing assets.
        with self.assertRaisesRegex(ValueError, 'Missing required file'):
            core.preflight(self.game, OUT / 'resources', log=logs.append)
        self.assertIn(str(folder.resolve()), '\n'.join(logs))
        # A stray Shield Rod line no longer stops the installer: it is replaced.
        (self.game / 'dlc_packages.txt').write_text(CHAPTER + '\n' + core.CONTENT_ID + '\tpackage19\n')
        logs = []
        with self.assertRaisesRegex(ValueError, 'Missing required file'):
            core.preflight(self.game, OUT / 'resources', log=logs.append)
        self.assertTrue(any('will be removed and replaced' in line for line in logs))
        (self.game / 'dlc_packages.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'dlc_packages.txt is missing'):
            core.preflight(self.game, OUT / 'resources')


def fixture():
    game = OUT / 'test_game'
    require_new = not game.exists()
    assert require_new, 'Keep the prior fixture for diagnosis; choose a fresh output before rerunning.'
    game.mkdir(parents=True)
    assets = game / 'assets'
    ar = assets / 'data/opd/weapon/ar'
    ar.mkdir(parents=True)
    shutil.copy2(hodpaths.legacy('modding/backups/nathan_dss_20261112_043946_source/runtime/harmonyrecomp.exe'), game / 'harmonyrecomp.exe')
    for name in ['rexruntime.dll', 'harmonyrecomp_dllAlucard.dll']:
        shutil.copy2(ROOT / name, game / name)
    for name in ['default.xex', 'default.xexp', 'data/player_dll/dllAlucard.dll']:
        (assets / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'assets' / name, assets / name)
    source = ROOT / 'assets/data/opd/weapon/ar'
    for p in source.iterdir():
        if p.name.startswith(('P_ARSH', 'C_ARSH', 'T_ARSH')) or p.name in ('P_ARSW04.OPD', 'C_ARSW03.COL', 'T_ARSW03.CSR'):
            original = hodpaths.legacy('modding/originals/shield_sotn') / p.name
            shutil.copy2(original if original.exists() else p, ar / p.name)
    for relative in ['player/weaponset.dat'] + [f'text/textres_{lang}.txrc' for lang in ['de', 'en', 'es', 'fr', 'it', 'ja']]:
        p = assets / 'data' / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'assets/data' / relative, p)
    chapter_id = '9CF520072EB8FA1F1BFFAE7F2C4CC375043CDA9658'
    content = game / 'userdata/0000000000000000/58410A7A/00000002'
    chapter = content / chapter_id
    (chapter / '000info').mkdir(parents=True)
    (chapter / '000info/package02.dat').write_bytes(b'PackageInfo\r\n')
    original = shield_stfs.read_stfs(ROOT / 'dlc' / chapter_id)
    stage = chapter / 'data/stage' / core.STAGE_NAME
    stage.parent.mkdir(parents=True)
    stage.write_bytes(original['data/stage/' + core.STAGE_NAME])
    # Familiar cards and Refectio: TU2 base files, the files they read, and
    # unmodified Chapters 7 and 11 unpacked from the raw official packages.
    import extras
    originals = hodpaths.legacy('modding/originals/game/assets')
    for name in extras.BASE_FILES:
        (assets / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(originals / name, assets / name)
    extra_files = ['data/player/soulset.dat'] + [f'data/gimmick/icon/icon00_{s}.dds' for s in extras.ICON_SHEETS]
    extra_files += [extras.FX_TEMPLATE + '/' + n for n in extras.FX_TEMPLATE_FILES]
    for name in extra_files:
        (assets / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'assets' / name, assets / name)
    listing = chapter_id + '\tpackage02\n'
    for package_id, marker, wanted in (('36DA9EF296B35F21C2470D71D9A21F5F8DFC6DDE58', 'package01', ('data/stage/stage00_04_set',)),
                                       ('E939382FFF0128B6E9FBA68C8F1BDB186EA8ABA758', 'package07', ('data/item/glyphset_dlc07', 'data/text/textres07_'))):
        files = shield_stfs.read_stfs(ROOT / 'dlc' / package_id)
        folder = content / package_id
        (folder / '000info').mkdir(parents=True)
        (folder / f'000info/{marker}.dat').write_bytes(b'PackageInfo\r\n')
        for name, data in files.items():
            if name.startswith(wanted):
                (folder / name).parent.mkdir(parents=True, exist_ok=True)
                (folder / name).write_bytes(data)
        listing += f'{package_id}\t{marker}\n'
    (game / 'dlc_packages.txt').write_text(listing)
    (game / 'harmonyrecomp.toml').write_text('user_data_root = "userdata"\n')
    # Missing Chapter 8 must fail before creating even an installer directory.
    before = snapshot(game)
    marker = chapter / '000info/package02.dat'
    data = marker.read_bytes(); marker.unlink()
    try:
        core.preflight(game, OUT / 'resources')
        raise AssertionError('Missing Chapter 8 was accepted')
    except ValueError as error:
        assert 'Chapter 8' in str(error)
    marker.write_bytes(data)
    assert snapshot(game) == before
    core.preflight(game, OUT / 'resources')
    (OUT / 'test_fixture_before.json').write_text(json.dumps(before, indent=2))
    print(game)
    return game


def snapshot(root):
    return {p.relative_to(root).as_posix(): core.sha(p) for p in root.rglob('*')
            if p.is_file() and not any(part in p.relative_to(root).parts for part in (core.STATE_DIR, '.setup'))}


if __name__ == '__main__':
    if '--fixture' in sys.argv:
        fixture()
    elif '--local-build' in sys.argv:
        # The path for installations whose executable differs from the patch
        # baseline: compile the shipped runtime sources against this machine's
        # retained setup (its build cache must be the Shield Rod-only, OFF one).
        import local_build
        context = local_build.plan(ROOT, setup=ROOT / '.setup', verify_executable=False)
        with tempfile.TemporaryDirectory(dir=OUT) as tmp:
            exe, _ = local_build.build(context, Path(tmp), OUT / 'resources')
            print('Local build linked:', exe.stat().st_size, 'bytes')
    elif '--verify-restored' in sys.argv:
        expected = json.loads((OUT / 'test_fixture_before.json').read_text())
        assert snapshot(OUT / 'test_game') == expected
        print('Every original fixture file restored byte-for-byte; all added mod files removed.')
    else:
        unittest.main()
