# Nathan Graves for Harmony of Despair (test build)

Nathan Graves from *Castlevania: Circle of the Moon* as a playable character
in the HarmonyRecomp PC version of *Castlevania: Harmony of Despair*, with
Circle of the Moon's DSS card system: 10 action cards x 10 attribute cards =
100 combinations, collected from enemies and boss chests.

**This is a test build.** Back up your saves (setup does this too, see below),
and expect bugs: reporting them is the point (see `modding/TESTING.md`).

## What you need

This archive contains no game files. Everything is made on your own PC from
your own copies:

1. **HarmonyRecomp v0.6.0**, installed with `HarmonyRecomp-Setup.exe`
   using your own Harmony of Despair files and DLC. **The Simon (8-bit) DLC
   ("Add Character (Simon)") is required**: Nathan is built on top of his
   package. Start the game once after setup, then close it.
   Other HarmonyRecomp versions are not supported yet.
2. **Circle of the Moon (USA) ROM**, unmodified
   (SHA-1 `d661b01eb94186435723ac03344792c11c20c522`). Nathan's sprites,
   effects and card art are read from it.
3. **agbplay** (Windows release, https://github.com/ipatix/agbplay/releases):
   renders Nathan's sound effects from the ROM. Only `agbplay-cli.exe` is used.
4. **Python 3.11 or newer** (https://www.python.org), with two packages:
   `python -m pip install pillow numpy`

## Install

1. Close the game.
2. Unzip this archive **into your HarmonyRecomp game folder** (the folder with
   `harmonyrecomp.exe`), keeping its folders. Nothing of yours is replaced.
3. Open a terminal in that folder and run (with your own paths):

   ```
   python modding/tools/setup_nathan.py --rom "C:\path\to\Castlevania - Circle of the Moon (USA).gba" --agbplay "C:\path\to\agbplay-cli.exe"
   ```

4. Wait. The first run recompiles the game with Nathan's code, which takes
   about as long as the original HarmonyRecomp setup did. Every step checks
   its own result and the setup stops with a message saying what is wrong,
   so it is safe to run again after fixing it.
5. Start the game. Nathan is on Character Select.

## Your saves

Setup copies your saves to `modding/backups/saves/<date and time>/` before it
changes anything. To restore one, close the game and copy the folders inside
it back into `Documents\harmonyrecomp\`. Nathan only ever *adds* his starting
items to a save; nothing else in it is changed. It has not yet been tested
whether a save that has been played with Nathan still loads after he has been
removed, so keep that backup.

## Playing Nathan

- **Whip:** X; hold X to spin the whip.
- **DSS:** RB uses the current pair: depending on the Action Card it
  toggles an effect (costing MP while on) or casts it. Action Cards sit in
  the RB slot, Attribute Cards in the passive slot, equipped like souls.
- **Card Swap:** hold Y, then left/right picks the Action Card and up/down
  the Attribute Card (only cards you own).
- **Tackle (Martial Art):** down, down-forward, forward + X. A dash that
  passes through enemies and hits each one once (15 MP).
- He starts with one Mercury and one Salamander card. Other cards drop from
  enemies (the Monster Compendium shows which, once you have seen them) and
  from Hard mode boss chests. More copies of a card make its pairs stronger.

## Known issues

- **Online play:** everyone must use the same build of this archive.
  - With Nathan installed on every machine, Nathan's DSS cards, casts,
    familiars and summons are sent to the other players, so they see them,
    and the Uranus + Unicorn heal reaches them. This is new and not yet
    tested with two players.
  - Players without the mod see Nathan as an Axe Armor (the game's rule for
    missing DLC) and none of his effects; his Unicorn heal can't reach them.
- Familiars (Saturn) and summons (Uranus) are approximations of CotM's.
- The 100 pair descriptions are English in every language.
- No automated uninstall yet. Restoring the backups and rerunning
  `HarmonyRecomp-Setup.exe` should give you a clean game, but this has not
  been tested.

## Credits and license

<!-- TODO before sharing: author credits and the license for the mod's own code. -->
Nathan Graves, Circle of the Moon and Harmony of Despair are Konami's. This
mod contains none of their files. HarmonyRecomp is by its own authors; agbplay
by ipatix.
