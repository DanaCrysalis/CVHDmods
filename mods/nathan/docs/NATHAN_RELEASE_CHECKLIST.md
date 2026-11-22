# Nathan Graves DLC: remaining work

Written November 10, 2026; refreshed November 12 (tester readiness). A tick means done; items that say "confirm in game" are ticked only after live play, not from the native harness.
State of the build and how things work: `README.md` and `docs/Nathan_DLC_Technical_Report.html`; history in `docs/HISTORY.md`. Rollout analysis: `docs/Nathan_TU3_Feasibility.html`.

## 1. Confirm in game what is installed but untested

- [ ] Pluto + Griffin doubles walking speed; Jupiter + Cockatrice halves it; boots interact as expected
- [ ] Green recovery numbers: Mercury + Unicorn, Jupiter + Mandragora, Uranus + Unicorn / Black Dog
- [ ] MP costs feel right on a 100 MP pool (`nathan_dss_balance.json`, `scale`)
- [ ] Whip ATK and whip level follow card copies (level 2 at 20 copies, level 3 at 180)
- [ ] Pair level raises damage, healing and stat bonuses as copies increase
- [ ] Projectiles, familiars and the Pluto shadow are drawn where they hit: facing left, jumping, every camera zoom
- [ ] Projectile damage is comparable with a whip hit and grows with INT
- [ ] Diana shots follow the CotM table: Salamander stops on the first enemy; Serpent, Golem, Griffin, Unicorn and Black Dog pass through
- [ ] Die-on-hit shots really vanish on the first enemy they touch

## 2. Check every DSS pair (100)

For each pair: activates on RB, costs the listed MP, right art and sound, lands where drawn, damages or heals as described, ends cleanly on RB / death / room change.

- [ ] Mercury x10 (elemental whips)
- [ ] Venus x10 (stat boosts)
- [ ] Jupiter x10 (shields)
- [ ] Mars x10 (weapons)
- [ ] Diana x10 (whip projectiles)
- [ ] Apollo x10 (thrown spells; now fire the way Nathan faces, confirmed November 12; each pair still to check)
- [ ] Neptune x10 (every pair is now a 50% resistance; card text confirmed November 12, effect still to play-test)
- [ ] Saturn x10 (familiars)
- [ ] Uranus x10 (summons)
- [ ] Pluto x10 (specials, Item Crash)
- [ ] Each pair also checked crouching, airborne and facing left
- [x] Diana pass-through and behavior confirmed from CotM testing (November 11)
- [ ] Confirm against CotM which shots pass through: Apollo Cockatrice / Unicorn, all Saturn shots

## 3. Known fidelity gaps to fix or accept

- [ ] Familiar behavior is a first pass (targeting, attack choreography, impact effects)
- [ ] Summons hit a fixed rectangle near Nathan instead of acting across the screen
- [x] Apollo + Serpent orb bursts into shards on its timer, on the first enemy it touches, or on terrain (confirm in game)
- [x] Diana + Manticore blob sticks to what it hits and keeps hitting (confirm in game)
- [ ] Jupiter + Black Dog self-poison is a plain HP loss with no status icon
- [ ] Pluto Bear Ring transformation is not implemented (no Bear Ring in HoD)
- [ ] Some CotM animation timing banks and the art-to-pair mapping were never verified
- [ ] Mars weapons and the shadow use physical attack; decide whether any should use INT
- [x] Pool's own query reviewed: it is the same hostile-group query native player shots make (hostile players, Survival opponents); enemies are detected by the overlap probe. Kept.

## 4. Card acquisition

- [x] Trace how HoD drop tables work (README, November 11): chests can be done with DLC data alone; enemy drops need one native hook
- [x] A card drops from its enemy as a pickup (user saw one from a Moldy Corpse, November 11)
- [x] Card icon: CotM's card-drop sprite, pulled from the ROM by `tools/nathan_card_icons.py` into cell 80 of Nathan's sub-weapon icon sheet (souls draw from that sheet, not the item sheet; fixed November 11)
- [x] Card icon in the menu and on the ground (confirmed in game November 12)
- [x] Whip spin no longer extends Nathan's hurt area (confirmed in game November 12)
- [x] Five cards in Hard boss chests, chosen by stage file: Saturn (ch 2 and 9), Unicorn (ch 3 and 7), Uranus (ch 4 and 8), Black Dog (ch 5 and 11), Pluto (ch 6 and 10); DLC chapters are the second source (table edit, `tools/nathan_card_drops.py`, November 12)
- [ ] Confirm in game that Hard boss chests (base and DLC) give those cards
- [ ] Uranus + Unicorn heals other players in range (needs a second player **with Nathan installed**; November 12 test with a player without the DLC: no heal, as expected: the heal is a negative-damage player attack, Charlotte's method, which each machine resolves for its own player, and a machine without the DLC never creates it)
- [x] Enemy card drops: card in a free item slot of the enemy's row (table edit, fifteen cards on sixteen enemies, 2.5% base; Mercury also from Hellmont in chapter 11; Cockatrice from Medusa Head at 0.5%)
- [ ] Confirm in game that a killed enemy drops its card as a pickup and that collecting it adds the card
- [x] No cards in ordinary chests (enemy drops and boss chests replace them)
- [x] Cards listed in the Monster Compendium natively, for every character (two-slot limit enforced by the tools); only Nathan can get the drop
- [x] Compendium lists the enemy card drops (confirmed in game November 12)
- [x] Placement revised to the user's table (November 12); tune rates after play
- [x] Copies 2 to 9 come from the same drops and boss chests (the game caps a card at 9)
- [x] Starting cards decided: one Mercury and one Salamander (November 12). Nathan's first update in a level makes sure the save owns one each, plus Card Swap and the Tackle; collected counts are never changed
- [ ] Card pickup presentation: icon, name popup, inventory count
- [x] Real acquisition is in place (enemy drops and boss chests). `nathan_cards.py --migrate-save` stays a developer tool; saves that used it keep their cards

## 5. Character completeness

- [ ] Whip level 2 and 3 art and hitboxes look right (first reachable now)
- [x] Armor / accessory / subweapon permissions stay as native table edits (decided November 11: table edits are preferred over hooks)
- [ ] HoD-only moves that use adapted animations: back dash, co-op moves, status poses, crouching throw
- [x] Dive kick uses the user's hand-made poses (`modding/art/dive_kick`, palette-matched at build time; confirmed in game November 12)
- [x] Tackle Martial Art replaces Simon's leftover VK shot: QCF + attack, dash through enemies, one hit per enemy, 15 MP (confirmed in game November 12)
- [x] Tackle direction follows Nathan's facing (fixed November 12; confirm left in game)
- [x] Card Swap cards draw above all terrain (own render list 6 instead of the body's list 3; confirmed in game November 12)
- [x] Martial Arts menu opens for Nathan and lists Tackle with its name, description and MP (confirmed in game November 12)
- [x] Martial Arts page shows the input row under Tackle (exe table only covers base arts; filled in by a wrapper of `823ED2E0`; confirmed in game November 12)
- [ ] Tackle feel: dash speed, length, damage (`tackle` in `nathan_dss_balance.json`)
- [ ] Dual Crush and other co-op interactions with Nathan as either partner
- [ ] All chapters, Normal and Hard, plus Survival mode
- [x] Pair descriptions updated to match current behavior (Diana, Uranus + Unicorn)
- [x] Card rule texts in all six languages (November 12; Japanese also uses katakana card names)
- [ ] Pair descriptions (100) and the Card Swap item text are still English in every language
- [ ] Records and ranking screens show Nathan correctly

## 6. Multiplayer

- [x] A remote Nathan no longer reads or writes the local save (grants, Card Swap, playtime, mastery, card counts); its pair level comes from its owner (November 17)
- [x] Online DSS: the local Nathan announces state, casts, swings, the attack button and the Serpent extra as native replicate-only spawn events; copies replay them without MP or self-heals (November 17; harness only)
- [ ] Two-player test of the online DSS (TESTING.md section F); whip ATK on copies still comes from the copy's own stats
- [x] Other players see the pool objects through the replay; hits are authoritative on the owner's machine only (native rule for remote attack owners)
- [ ] Lobby must reject or flag mismatched builds (version fingerprint plus DLC version)
- [ ] Behavior when another player does not have the DLC (seen November 12: they see an Axe Armor; Nathan's effects on them, such as the Unicorn heal, cannot reach them)
- [ ] Survival / PvP: pool hits against players

## 7. Robustness

- [ ] Room changes, death, revive and stage exit leave no stuck objects or state
- [ ] All 16 pool slots in use at once; rapid card swapping mid-attack
- [ ] Long session with no leak or slowdown
- [ ] Old saves load; a save made with the DLC loads without it

## 8. Packaging and distribution

- [ ] Choose the route: unofficial PC update bundle plus DLC, or hooks merged upstream by the recomp author, or both
- [ ] Ask the recomp author what they would accept: a hook / mod API, a 12th character slot, the lobby fingerprint
- [x] HarmonyRecomp version: stay on v0.6.0 for testing (user's decision, November 12); setup refuses other versions. Rebase when a new release matters
- [x] One-command build, verify and install: `tools/build_nathan.py [--install]`
- [x] Clean build from a fresh package (November 12): passes with the two patches in `modding/patches` (the CMake one had never been saved; now it is), the runtime sources and the mod package; recipe in README
- [x] Recipe builds Nathan's package from the user's own HoD install, Simon DLC and CotM ROM: `make_nathan_package.py` plus the regular build; checked against the installed package (November 12)
- [x] Distribution archive: `tools/make_nathan_release.py` (allowlist, refuses game files and local paths; November 12)
- [x] One-command first install for other people: `tools/setup_nathan.py` (checks, save backup, patches, CotM extraction, bootstrap, recompile, content install with header, build and install); steps 1-7 dry-run on this install, the build chain run end to end (November 12)
- [x] No machine-specific paths: the CotM extraction moved into the mod (`cotm_extract.py`, byte-identical output) and every tool finds it through `nathan_paths.py`
- [x] Nothing game-derived needed from `data/`: the two native checks use a hash-guarded record of their code reads; the XEX key is read from the recomp's own runtime
- [x] Equipment permissions are part of `build_nathan.py` (stage, `--install` and active)
- [ ] Test the archive on a clean install (first tester, or a copy of the game folder)
- [x] Shipped art decided: the two dive kick poses and the menu portrait ship in `modding/art` (November 12); everything else comes from the user's files
- [x] Base-table edits include `martialartsset.dat` and the six base `textres_*.txrc` (Tackle text); `nathan_card_drops.py --install` in `build_nathan.py --install` applies them with the others
- [x] Installer with backups and `--restore <backup>` to undo one install; installer also checks every override is linked
- [x] Installer registers the package in `dlc_packages.txt` (next to the exe and the build's generated copy) when the line is missing
- [x] Pruned `modding/backups` to the newest installs plus original-bearing ones; pristine originals in `modding/originals` (November 12)
- [ ] Test on a clean install and a second machine
- [x] Player-facing README (`PLAYER_README.md`) and tester plan (`TESTING.md`), November 12
- [ ] Credits and license (placeholder in `PLAYER_README.md`)

## 9. Housekeeping

- [x] Tools indexed and legacy ones marked in `tools/README.md` (`sheet2hod` is still in use)
- [x] Outdated handoff note, legacy test-character tools and scratch build output removed (November 12)
- [x] README folded into one current description; the dated notes are kept unchanged in `docs/HISTORY.md` (November 12)
- [x] Technical report regenerated November 12 (repeat after the last change)
