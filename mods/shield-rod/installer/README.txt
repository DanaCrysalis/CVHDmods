Shield Rod DLC Installer 1.5.3

Installs, in one step:
  - Alucard's Shield Rod and its thirteen shield spells (Chapter 8 Hard Legion
    boss chest);
  - Alucard's five familiar cards in his Enchanted equipment row: Bat (drops
    from Bats), Ghost (Ghosts), Demon (Imps), Faerie (Chapter 7 Hard purple
    chests) and Sword (Chapter 8 Hard purple chests);
  - Shanoa's Refectio glyph, a heal over time (Chapter 7 purple and boss
    chests, Normal and Hard).

REQUIREMENTS
  - Wrexxial HarmonyRecomp 0.6.0 (Windows x64) with HoD title update 2.
  - The .setup folder (the setup files) from your HarmonyRecomp compile, still
    in the recomp folder. Do not delete it after Setup.
  - Official DLC Chapter 7, Chapter 8 and Chapter 11 installed, and the recomp
    launched once with them so it unpacks them. The installer refuses to run
    if any of the three is missing or disabled. (Chapter 7 holds the familiar
    and Refectio chests, Chapter 8 the Shield Rod and Sword Card chests, and
    Chapter 11's glyph table is the base for Refectio.)
  - Your USA Symphony of the Night disc (SLUS-00067), for the SotN graphics
    and sounds.
  - Optional: your USA Order of Ecclesia ROM (.nds). With it, Refectio's cast
    effect uses the original Order of Ecclesia sprites; without it, the
    installer draws its own version of the effect. Everything else is the same.
  - Close the game before installing or uninstalling.

Run ShieldRodInstaller.exe. No Python or compiler installation is needed.
Choose the folder containing harmonyrecomp.exe, then your USA Symphony of the
Night disc: SLUS-00067. ISO (2048-byte sectors), CUE/BIN (2352-byte sectors),
and the first data-track BIN are supported. Other regional releases and CHD
are not supported. The installer reads the disc and ROM without changing them.

1.5.3: fixes chest rewards vanishing when a DLC file in the recomp's dlc
folder has a name longer than 42 characters (for example a renamed Chapter 8
package). The recomp unpacked such a package again at every start, which threw
away the Shield Rod and Sword Card chest entries; the game now keeps the
unpacked copy. If you were affected, run Install once more after updating.
Other DLC is unaffected. (This is a fix to HarmonyRecomp's own DLC handling,
included until the recomp ships it.)
1.5.2: Install updates an earlier installation by itself (it runs
Uninstall / Restore first). Copies of the Shield Rod, familiar card, Refectio
or Nathan packages found without an installation record (for example copied
into the dlc folder with the DLC files) are removed and replaced; their files
are backed up and Uninstall puts them back. Other DLC and other mods are left
alone.
1.5.1: the Sword Card's description shows the Sword Brothers command with
arrows (↓↘→↗↑↓+X/Y) and its MP 30 cost; the arrows are added to the game's
text fonts (font.arc, restored on uninstall). Bat and Ghost Cards are rarer
(1% drop, was 2.5%) and show a rarity star. Familiars use cards picked up
during a run right away. Sword Brothers counts every sword's hit; the
installer now ships every runtime header (fixes the locally compiled build).
The Ghost's soul steal heals the HP each hit takes, at most 8.
1.5.0: adds the familiar cards and Refectio. Their art and sounds come from
your SotN disc (and, optionally, your Order of Ecclesia ROM); their drops are
edits to Chapters 7 and 8 and to the enemy table that keep every other reward.
Shield Rod hits now register on time (they used to miss some enemies), and
the empowered Alucard Shield hits at Valmanway's rate and drains 1 MP every 8
frames. Every player in an online session needs 1.5.0 to see the familiars.
Uninstall now works after other DLC was added (it used to stop with "File
changed after installation: ...dlc_packages.txt"). To update from an older
version, run 1.5.0, click Uninstall / Restore, then Install.

Install official Chapter 8 DLC and launch the recomp once before using this
installer, then close the game. Installation is refused if Chapter 8 is absent
or disabled. Leave the optional third field blank: the installer finds the
copy the game unpacked from its startup log, harmonyrecomp.toml settings
(user_data_root / game_data_root) and the usual Documents and AppData folders.
If detection fails, you may select either the recomp's dlc folder or the
unpacked Chapter 8 folder (it contains 000info and data), which is below
<user data>/0000000000000000/58410A7A/00000002. On failure the log lists every
location checked; use Copy log to share it.

1.3: Chapter 8 detection now accepts older dlc_packages.txt files that list
package file names only, a selected raw dlc folder, Documents folders moved by
OneDrive or Windows, and recomps installed anywhere (for example AppData).
1.3.1: an unpacked Chapter 8 folder whose name differs from its
dlc_packages.txt entry is used when it is the only copy (the log notes it).
1.4.0: online co-op. A Shield Rod cast is sent to the other players with the
game's own player events (no extra network traffic), so they see the spell,
its hits and damage numbers. Damage is still applied once, by the caster.
Every player in the session needs Shield Rod 1.4.0 or later to see spells;
players without it are not affected.
1.4.1: buff spells (ATK, DEF, INT, fire, thunder and dark resistance) now
reach other players within about a screen of the caster, online and local;
before, only the caster was buffed. Buffs also show on the buffed player's
status screen, whatever their character. Both players need 1.4.1.
1.4.2: the Shield Rod sound bank header now matches the game's own banks
(two unused header fields were swapped). No change in game; sounds identical.

This package supplies Shield Rod (all thirteen spells, original-disc spell
graphics and sound effects, green buff notices, and the Chapter 8 Hard Legion
boss-chest drop, weight 50, approximately 0.5% before luck), the familiar cards
and Refectio. It adds them using a verified patch or a build against the
retained setup.
The installer does not bundle the full executable. It contains no
Nathan DSS code and installs no Nathan character, cards, assets or drops.

Supported recomp: unmodified Windows x64 Wrexxial HarmonyRecomp 0.6.0 with
HoD title update 2 and the matching release SDK. ReXGlue SDK 0.8 is the SDK
version, not the HarmonyRecomp release number.

Different users' 0.6.0 executables need not have identical hashes. When the
compact prebuilt patch does not match, the installer uses that installation's
retained .setup folder to rebuild only the Shield Rod code and affected native
files, then links them with its existing game/DLC objects. This can take several
minutes. It does not edit the setup source or cache, replace character DLLs, or
add Nathan code. The original executable must match its own retained build output.

Keep .setup with the recomp folder. If it was deleted or does not match the
installed game, rerun official Wrexxial 0.6.0 Setup first, then retry. No per-user
patch or upload of executables is needed. The compiler/SDK already retained by
Setup are used; this installer downloads nothing. TU2 data, original shield
assets, installed Chapter 8 and SDK compatibility are still checked. Existing
Nathan/Shield Rod installs and other custom executable mods are not supported.
Other installed DLC and its module registry are preserved.

Spells/assets/sounds are built from your own HoD files, your selected SotN
disc and, if given, your Order of Ecclesia ROM in temporary staging. Output
hashes must match the tested runtime before installation begins. The chest
and enemy table edits preserve all other rewards. The installer does not
modify saves, your SotN disc or your ROM.

BACKUP / UNINSTALL
Every changed original file is backed up below the selected recomp folder:
ShieldRodInstaller/backups/<timestamp>/. The installation journal is written
before any game file changes. Failure triggers rollback. After a power loss,
run this installer, select the same recomp folder, and click Uninstall / Restore.

To uninstall, close the game, run the installer, select the recomp folder and
click Uninstall / Restore. No SotN disc or ROM is needed. Original executable,
assets, chests, enemy table and DLC list are restored byte-for-byte; the added
Shield Rod, familiar card and Refectio content and their content headers are
removed. Original backups remain available afterward.
If DLC was added after installing (dlc_packages.txt changed), uninstall removes
only this installer's own entries from the list and keeps the new ones.
If another mod changed any other installed file, uninstall stops before
overwriting it. Restore that later change first, or recover manually from the
saved backups.
Keep the recomp folder and its ShieldRodInstaller directory together.

Re-running HarmonyRecomp Setup can overwrite custom runtimes or clear DLC
content. Uninstall this mod before rebuilding/updating the recomp, then install
again only if the new build passes compatibility checks. Clearing the recomp's
installed DLC cache also removes the patched Chapter 8 chest: uninstall and
reinstall after the game has unpacked Chapter 8 again.

SOURCE / LICENSES
SOURCE_AND_LICENSES.zip includes the complete matching GPL SPU renderer source,
its build command/license, the installer/converters, Shield Rod runtime source,
and applicable runtime notices. The same archive is embedded in the installer.
SotN game files, generated texture pages and rendered audio are not bundled;
they are generated from the disc selected by each user. Captured spell geometry
and timing form the conversion recipes used by the runtime.

SIZE AND BUILD METHOD
The raster and PCM converters now use only the Python standard library.
NumPy/OpenBLAS, Pillow/image codecs, Unicorn, and OpenSSL are not bundled.
Cryptographic checks use Python's built-in SHA implementations. The diagnostic
symbol map, animation recipes, GUI runtime, and source/licenses remain included.
