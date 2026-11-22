# Poison Worm prototype: research notes

Nov 19, 2026. Status: research only. Nothing in the main game install has been changed.

## Test install

All Poison Worm work happens in `D:\Games\Emulators\Recomps\HoD Test - Poison Worm`. It was copied on 2026-11-19 from the main install, leaving out `.setup`, `logs` and `modding`.

- **Its own user data:** `userdata\` is a copy of `Documents\harmonyrecomp` without the old save backups. It holds saves, unpacked DLC and the shader cache.
- **Launch:** always use `Play Test.bat`. It passes `--user_data_root` on the command line, because the SDK reads that option before it loads the toml, so a toml value would be ignored. Starting the exe directly would use the main Documents folder.
- **Verified 2026-11-19:** the log shows `Game directory: …\HoD Test - Poison Worm\assets` and `User data: …\HoD Test - Poison Worm\userdata`. All DLC is installed, with no errors and the same warnings as the main install. `Documents\harmonyrecomp` was untouched.
- **Netplay:** turned off in the test copy's `harmonyrecomp.toml`, so it can't share a LAN lobby with the main install.

Rules for this work:

- **Exe builds:** `rebuild_recomp.py` builds from the main install's `.setup` source. Copy the built exe into the test folder only, never over the main exe. Keep Poison Worm source changes behind their own CMake option, so the main build is unaffected.
- **Data edits:** make them in the test copy's `assets\` and `dlc\` only. Don't copy test packages into `.setup/package/src/assets/dlc`, and don't run the other mods' install tools against the test copy. Those tools write to the main install.

## Own module pilot: DLL_Cm050 (2026-11-20, test exe `b548fa7b`)

`modding/tools/poison_worm_module.py` (`module`, `codegen`, `build`, `install`) makes the Poison Worm a DLC-style enemy. No exe hook is needed to load it.

- **How the game loads it:** spawn `8224C478` sees the `DLL_` prefix and builds `<package device>:\dll\enemy\<row name>.dll`. The generic DLL enemy object `82250B78` loads that module, so every `DLL_` name is its own module file.
- **Template:** the 8-bit DLC Bat `DLL_FCbat`, rebased with `xexrebase.py` to `0x89380000`, the next free 0x80000 slot after the 8-bit DLC enemies (`0x88080000`–`0x89380000`; the DLC bosses share `0x8BF00000`).
  - **Patched in place, same lengths:** `data/enemy/DLL_FCbat/p_FCbat.opd` → `data/enemy/DLL_Cm050/p_Cm050.opd`, and `DLL_FCbat` → `DLL_Cm050`.
  - **Still from the 8-bit DLC:** shared effects in `data/enemy/DLL_FCcommon/p_FCcommon.opd`.
- **Codegen:** listed in `harmonyrecomp_manifest.local.toml` (guest path `dll/enemy/dll_cm050.dll`). Then `rexglue codegen <manifest> --target DLL_Cm050` runs with `REX_XEX_APPLY_PATCHES=true`, like `build.py`; without it the main game fails validation with "unresolved call 0x826444A8". It takes about 42 s and also reprocesses `default.xex`; the shards come out identical apart from the CMake hook rewrites.
- **Codegen `--target` truncates two shared files to that one module:**
  - `generated/default/dll_targets.cmake`, the build targets;
  - `generated/default/module_registry.cpp`, the exe's list of recompiled modules.

  The tool backs both up and merges: earlier entries stay in place, and new ones go at the end. Keeping the order keeps every other module's function-table address. An exe built from the truncated registry would lose every character and DLC module.
- **The exe must be rebuilt after adding a module, because the registry is compiled into it.** First try: the game loaded the module and crashed with "function not in function table" at `0x893957D0` (`xstart`).
- **Package 22:**
  - row `DLL_Cm050` from the 8-bit Bat's row in `EnemyParam04`, with HP 58, drops 0 and Compendium 0/0;
  - `dll/enemy/DLL_Cm050.dll`;
  - the sprite in `data/enemy/DLL_Cm050/`, from `poison_worm_art.build_module`: all 20 CotM frames under their CotM numbers. Anims: 0 parent loop, 1 falling child, 2 crawling child, 3–6 debris.
- **Placement:** the Chapter 1 record `DLL_Cm050` at set (2560, 2224), replacing `pworm`. The Bat-hook test sprite was removed from the test copy's base assets.
- **Smoke test:** "Registered recompiled module … `harmonyrecomp_DLL_Cm050`", "registered 783 functions", sprite opened from the package device (only the optional `_idx`/`_uv` atlas reported missing), no crash in 45 s. Behavior is still the 8-bit Bat's.
- **In game (user, 2026-11-20):** works, no crash.
- **Main install:** unaffected. The `.setup` build tree now has the extra module target and registry entry, which is harmless there. `scripts/build.py` would drop both, because it rewrites the manifest.

## Stage 2b: parent behavior in the module (2026-11-20; built, not yet tested in game)

**Terrain file `stage00_00_hit.hit2`:**
- Layout: a 0x120-byte header, then 270 × 152 big-endian u16 cells of 16 × 16 world px.
- Cell value: high byte = room number; low byte = collision (`0x03` solid, `0x00` open, `0x45` seen at a slope). A cell of `0x0003` is outside every room.
- The start room 0x2F runs over world x 272–976, with its floor surface at y 2352 and its ceiling underside at y 2192 (160 px tall).

**How the module works** (the 8-bit Bat's code):
- **Creation:** the exe's generic DLL enemy `82250B78` calls export 1, the factory at `0x893913F0`. It allocates a 0x44EC-byte module object with vtable `0x89381D90`, then makes four vtable calls: `+0x2C` (resource name), `+0x6C`/`+0x70`/`+0x74` (exe callbacks) and `+0x78` (handle).
- **Slot 2 (`0x893915A0`), spawn setup:** registers boxes through `+0x220` (flags `0x40000009`, `0x40000029`) and queues commands through `+0x388`.
- **Slot 7 (`0x893917E8`), the per-frame update:** gets the frame time in f1 and dispatches on the state at `+0x44C0`:
  - 0 hang (`0x893918E8`): triggers when the player is below and close, using constants 96 and 160;
  - 1 fly; 2–3 later phases; 4 dying.
  - `+0x44D1`/`+0x44D2`/`+0x44D3` are hit flags; `+0x44D3` forces state 4.
- **Fields:** `+0x9C` player position, `+0xA4` own position, `+0xAC` velocity (the exe applies it), `+0xB4` probably acceleration, `+0x21F` requested animation (setter at vtable `+0xA4`), `+0x2B8` sprite object.
- **Calls into the exe:** guest indirect calls outside the module's code range fall back to `rex::runtime::ResolveIndirectFunction`, so module code can call exe functions such as spawn `8224C478` with `REX_CALL_INDIRECT_FUNC`.

**This build:**
- **Code:** `src/poison_worm_module.cpp`, compiled into `harmonyrecomp_DLL_Cm050` when `HARMONYRECOMP_POISONWORM` is ON. It overrides slot 7 and is reached through the exe's vtable call, so it needs no rewrite.
- **Behavior:** while alive in state 0, the worm keeps animation 0 and creeps toward the player's x within ±32 px of home, re-aiming every 2–4 s. It never flies. When hit or dying, the Bat's own update runs.
- **Tuning:** `poison_worm_tuning.txt` next to the exe (creep speed, range, re-aim times, `log_frames`). Velocity units are unconfirmed; the default assumes px/s.
- **Placement:** set (864, 2192) = world (432, 2192), the start-room ceiling above the start zombies, at the user's request.
- **Next:** small worms (gravity and floor handling, via the spawn routine plus a child flag) and poison on contact.

**Result (user, 2026-11-20): "looks right".** The log confirms velocity is in px/s: 7.5 px/s gave 7.5 px a second, with a frame time of about 0.0166 s.

## Stage 2c: small worms (2026-11-20; built, not yet tested in game)

- **Release:** the parent releases through the exe's spawn routine `8224C478` (r3 = the module's own `DLL_Cm050` string at `0x89381D84`, r4/r5 world x/y as integers, r6 facing 0, r7 = r8 = 1, as in the exe's summon call at `822E22EC`). It uses CotM's rule and rhythm: player below and near, bursts of 4, at most 12 alive.
- **Child flag:** a thread-local flag around the spawn call lets the factory override (`0x893913F0`) mark the new object as a small worm.
- **HP:** after the spawn, the exe object's HP (`+0x98`/`+0x9C`) is set to 1.
- **Gravity:** the setup override (slot 2, `0x893915A0`) gives small worms the 8-bit Skeleton's settings (`DLL_FCskl` slot 2 at `0x88511670`): `+0x229` = 1, bytes `+0x268`–`+0x26B` = 1, floats `+0x23C`–`+0x254` = 12, 0, −34, −8, −14, 8, −14, and sprite `+0x66` = 1. These are getters the exe reads, so the exe should apply the gravity and floor collision. Unconfirmed.
- **Movement:** the small worm falls with animation 1 and a sideways speed of ±30 px/s. It counts as landed once its y stops changing for 3 frames, then crawls with animation 2 at 9.375 px/s and turns when its x stops changing.
- **Not yet:** poison on contact, despawning off-screen, crawl facing, and the hit-debris spray.

**Test result (user, 2026-11-20):** the screenshot showed copies of the parent hanging lower in the air. The log shows what happened:
- the child flag worked: 12 releases became small worms that "fell", "landed" and "crawled";
- their y never changed from 2217, about 24 px below the parent, and the landing check took the stillness for a landing.

Two findings:
- **The exe adds no gravity.** The 8-bit Skeleton's own walk code (`0x885121C0`) sets velocity itself: walk 70 px/s, initial vy −220.
  - **Exe-written contact words:** `+0x258` (probably floor), `+0x25C` (ceiling), `+0x260`/`+0x264` (left and right walls; the Skeleton turns on these). They're set through setters at `0x89390140` and nearby.
  - **`+0x44A0`–`+0x44B4` are attribute masks** (`0x88514780` tests them), not collision.
- **Animation:** `+0x21F`–`+0x221` are exe-written state, not requests. The animation index is the u16 at `+0x222`: the Bat's setup writes it, the draw setup (slot 3) copies it to sprite `+0x5C`, and its setter is slot 162 (`+0x288`). The command queue `+0x388` is used only at setup.

**Fix (built 2026-11-20, untested):**
- the animation goes to both `+0x222` and sprite `+0x5C` every frame;
- small worms get their own gravity (600 px/s², capped at 240 px/s; tunable) and land on floor contact or when falling stalls, with a 400 px safety limit;
- they crawl with wall contacts or stalling to turn, and face the way they crawl via sprite `+0x30` (2 when moving right, as the Bat does).

**Test (user, 2026-11-20):** "behavior is right", so falling, landing and crawling work, but the small worms still drew as the parent mass. Writing `+0x222` and sprite `+0x5C` doesn't switch animations.

**The real switch,** read from the Bat starting its flight (`0x89391B04`–`0x89391B60`) on the sprite object at `+0x2B8`: `+0x00` = animation index (u32), `+0x28` = frame 0, `+0x10` and `+0x54` = 0.0, `+0x1C` = 1, `+0x2B` = 1. `SetAnimation` now writes exactly that, only when the index changes. Built and installed 2026-11-20; untested.

**Test (user, 2026-11-20):** the small worms now show the right frames, but they don't animate (one frame) and they float about 8 px above the floor.

- **Floating:** the log shows floor contact at y 2343–2345 against a floor surface of 2352, after which the exe allowed no further downward movement. The Skeleton's `+0x250` = 8 is a feet sensor 8 px below the position. The 8-bit floor walkers draw their feet at y 0, like ours.
- **Terrain mask:** `+0x44A0` = `0x24012` is set by every 8-bit floor walker (Skeleton, Zombie, Mummy) and 0 by every flyer (Bat, Medusa Head, Medusa, Ghost, Fishman). So it's a terrain mask, not an attack attribute.
- **Fix:** small worms get `+0x44A0` = `0x24012`, `+0x44A4` = 0 and `+0x250` = `floor_sensor` (tunable, default 0). Animation switches now go through the module command `+0x388` (`0x89393558`) with (animation, 1, 0), as spawn setup starts animation 0, sent once per change. Built and installed 2026-11-20; untested.
- **Test (user, 2026-11-20):** the small worms now rest on the floor, so the terrain mask and floor sensor fix worked. But they looked like the mass again: the command `+0x388` doesn't switch animations (its first argument isn't an animation; the Fishman sends `(1, 1, 0)` at setup).
  - **Animation:** the 8-bit Fishman switches with just sprite `+0x54` = 0.0 and then sprite `+0x00` = animation (e.g. `0x88911CA0`). The Bat's extra `+0x1C` = 1 is probably what froze the previous build on one frame. `SetAnimation` now copies the Fishman, once per change. Built and installed 2026-11-20; untested.
  - **Test (user):** the Fishman's two writes alone still showed the mass.
  - **Next build:** the Bat's switch without `+0x1C` (`+0x00`, `+0x54`, `+0x2B`, `+0x28`, `+0x10`), plus a diagnostic. For the first small worms, the sprite's first 0x60 bytes are logged after each switch and 30 frames later (`[pworm] sprite ...`). Built and installed 2026-11-20; untested.
  - **Diagnostic result** (`harmonyrecomp_021.log`, without `+0x1C`): nothing in the `+0x2B8` object changed over 30 frames. The animation stayed as written, and `+0x28` and `+0x10` stayed at 0. So it's a request the exe reads, and `+0x1C` is the "apply" trigger.
  - **The earlier freeze:** that build compared against sprite `+0x00` to decide whether to send the request. The exe probably rewrites that field after applying, so the request went out every frame and restarted the animation on frame 0.
  - **Fix:** the Bat's full request, `+0x1C` included, sent once per change as tracked in `Worm::anim`. The dump is still on. Built and installed 2026-11-20; untested.
  - **Test (user):** right small-worm frames now, but still one frame and floating.
  - **Log `harmonyrecomp_022`:** the exe consumes the request: it clears `+0x1C`, and sprite `+0x08` (the current frame, u32) becomes 4 for falling and 8 for crawling. But `+0x08` and `+0x10` never advance. `+0x54` = 0 is normal; the Fishman writes 0 too, from constant `0x88901D18`.
  - **Fix: the worm code drives frames itself.** It writes sprite `+0x08` every update from CotM's ticks: parent 0–3 at 8, falling 4-5-6-7-6-5 at 4, crawling 8–11 at 8.
  - **Floating:** every small worm comes to rest at y 2341–2344 against a floor at 2352, whatever `+0x250` is. The earlier "on the floor" look came from the taller mass frames. Fix: small-worm frames 4–11 are drawn 8 px lower in the sprite (`CHILD_DROP` in `poison_worm_art.py`).
  - Built and installed 2026-11-20; untested.
  - **Test (user):** still frozen and floating; the art shift made no visible difference.
  - **Live read-only probe** (user left the game running; scratch `wormprobe.py`): the module object is at exe object `+0xF3D8`. For DLL enemies the exe object's `+0x40`/`+0x44` stay 0; the position lives in the module. The request sprite (`+0x2B8`) of the parent, which animates natively, shows:
    - `+0x04`: tick counter, counting up;
    - `+0x08`: current frame, stepping 1 → 2 → 3;
    - `+0x10` = 1.0: **playback speed**.

    On the small worms `+0x10` = 0.0, because I copied the Bat's flight start, so they never advanced.
  - **Fix:** `+0x10` = 1.0 on every switch, and the game animates; the manual frame stepping was removed.
  - **Foot point:** module `+0x4410`/`+0x4414`, written by the exe through a setter, is always the position plus 8: 2200 for the parent hanging at 2192, and 2352.2 (the floor) for a small worm at 2344.2. That's why small worms rest with their position about 8 px above the floor.
  - **Art offset:** with frames shifted 8 px they still looked high in game, so `CHILD_DROP` is now 12. The request's frame-box list (`+0x70`) held (−10, 1, 18, 7), confirming that the shifted sprite file was loaded.
  - Built 2026-11-20; installed once the game is closed.
  - **Test (user, speed fix and 12 px offset):** "much better": they animate. With 12 px some look sunk into the floor and some don't, because the landing height varies by up to 4 px (4 px a frame at top fall speed, and the probe stops the fall early). The user wants them all exactly on the floor.
  - **Fix:**
    - On floor contact the small worm takes its foot point (`+0x4414`), finds the next 16 px tile boundary at or below it (flat floors), and eases its position to exactly that minus 8 using a small downward velocity. It's limited to `settle_max` (6 px), so slopes are left alone.
    - `CHILD_DROP` goes back to 8, so the art bottom lands on the floor surface.
    - The log line `[pworm] small worm … settled at y …` reports each result.
    - The module has a position setter (`0x893904C0`), which suggests the exe pushes the position every frame, so velocity is used rather than a direct position write.
  - **Result (user, 2026-11-20): "looks good".** Log `harmonyrecomp_026`: the small worms landed at y 2340–2344, and 11 settled at 2344.0 (±0.02). The 12th landed at exactly 2344, so the exe does allow the small downward correction after contact. **Parent and small worms now look and move right.**
- **Poison on contact (2026-11-20; built and installed, test exe `8f2dbce8`, untested):**
  - **The player's damage routine** is `0x8244BF10` (a player-class vtable method; pointer at `0x82202008`): f1 = damage, r7 = the attack's attribute mask, r9 = the attacker's handle. Status comes from r7 (Nathan's Jupiter + Cockatrice clears `0x8000` to block stone).
  - **The row and module don't carry the attack's status.** Stats-row setter `82240538`: row `+0x30`–`+0x3E` are weaknesses/resistances to slash `0x20`, strike `0x40`, pierce `0x80`, fire `0x100`, ice `0x200`, lightning `0x400`, holy `0x800`, dark `0x1000` (a positive value sets the bit at object `+0xDC`). `+0x40`/`+0x42`/`+0x44` are poison/curse/stone resistance. `+0x2C` is the soul rate (into object `+0xBC`).
  - **Module queries:** module vtable `+0x4B8` = `IsAttribute(kind, mask)`, with kinds 0–5 → masks `+0x44A4`/`+0x44A8`/`+0x44AC`/`+0x44B0`/`+0x44A0`/`+0x44B4`, and 9 → always yes. The exe calls it from `0x822548CC`–`0x82256A0C` with single bits `0x80`–`0x2000000` (trait queries), never `0x2000`. Vtable `+0x220` only stores the body flags at `+0x1DC`.
  - **Hook:** `harmony::poison_worm::IncomingHit` (`src/poison_worm.cpp`, declared in `src/poison_worm.h`) runs first in both `8244BF10` overrides (`nathan_dss_damage.cpp` and `shield_rod_bridge.cpp`) through `POISON_WORM_INCOMING_HIT`, which does nothing unless `HARMONYRECOMP_POISONWORM` is set. If the attacker's row (exe object `+0xC0`) is named `DLL_Cm050`, it adds `0x2000` to r7, and the game poisons natively. It logs `[pworm] hit from worm …` for the first 20 hits.
  - **Online co-op:** damage is applied only on the owner's machine (`8224E700`), so poison follows HoD's own sync. Unverified.
- **Test (user): it cursed instead of poisoning.** The log showed the attributes arriving as `0x40000029`, which is exactly the module's body flags at `+0x1DC`.
  - **So the module sets its own touch attributes natively,** and no exe hook is needed.
  - **The player side maps differently from Nathan's enemy-side table.** In `8244BF10`: bit `0x4000` → status 0 (poison), `0x2000` → status 1 (curse); a third bit → status 2 (stone). Each calls `8244DCA0(owner, status, 1, f1 = duration)`.
  - **Final form:** the module's spawn-setup override ORs `0x4000` into `+0x1DC`, for the mass and the small worms.
  - **Exe hooks removed (2026-11-20):** the poison hook, plus the stage 1/2a `pworm` registry, spawn and resource-name hooks. Their code (`poison_worm.cpp`/`.h`) is archived in `modding/backups/poison_worm_exe_hooks_20261120`. With `HARMONYRECOMP_POISONWORM` the exe now only adds the test-install user-data isolation; the worm is entirely its module plus data. `poison_worm.py install` is retired (it would install the old `pworm` setup); use `poison_worm_module.py install`.
  - Test exe `5e934216` and the module are installed. **Result (user, 2026-11-20): poison works.** Log `harmonyrecomp_028`: no errors, and release/settle ran normally.
- **Stage 2 state:** the Poison Worm behaves as in CotM — hangs and creeps, releases small worms that fall, animate, settle on the floor and crawl, and both poison on contact. All of it is in its own module plus data; the exe has no worm hooks.
- **Poison Worm soul design (user, 2026-11-20):** Soma throws small worms that poison and damage enemies on contact and behave like the small worms (crawl on the floor). Count by soul level: 1 at levels 1–3, 2 at 4–6, 3 at 7–9. Only the mass drops it; small worms never count for souls. Not built yet.
- **Small worms are not "real monsters"** (user, 2026-11-20: like the Man-eating Plant's seeds, but showing damage numbers). After each spawn, the module points the exe object's row (`+0xC0`) at one shared copy of the mass's row with HP 1 and everything else zeroed: soul, soul rate, items, item rates, `+0x18` (kill reward) and the Compendium fields. They're still hittable and still damage and poison. Built and installed 2026-11-20; untested.
- **Soul, first build (2026-11-20; installed, untested):** `modding/tools/poison_worm_soul.py` (`module`, `codegen`, `build`); the soul data goes into package 22 through `poison_worm_module.py install`. No hooks: everything is DLC data plus the module.
  - **How DLC souls work:** soul tables have rows at file `+20`. Base row fields: `+0x0C` type (1 = bullet), `+0x0E` effect selector (26 = DLC shot module for every 8-bit bullet soul), `+0x10` power (s16), `+0x12` attribute mask, `+0x2E` MP, `+0x30` icon cell (`0x15` = the bullet-soul icon). The shot module's info block (object vtable `+0x60`) gives category 0 and shot ID = global soul index.
  - **Template:** the 8-bit R. Zombie soul (73), `dllshotSoulFCzombi`, which summons a walking zombie. Its shot ID is `li r11,0x49` at `0x842119E0`.
  - **Our module:** `dllshotSoulCm050`, rebased to `0x85700000` (the next free shot slot). Its sprite path is patched to `data/enemy/DLL_Cm050/p_Cm050.opd` and its shot ID to `0x74` (116) at `0x857119E0`. Codegen and the merge leave 119 targets/modules, and the exe was rebuilt for the registry (test exe `4f49cc0f`).
  - **Package 22:**
    - `data/item/soulset_dlc22.dat`: one row, global index 116 (item `0x6E7`), copied from R. Zombie's — Soma only, type 1 / selector 26, power 100, MP 20, icon `0x15`, never in chests.
    - `data/text/textres22_{de,en,es,fr,it,ja}.txrc`: group 13 "Poison Worm", group 14 the description (English in every language for now).
    - `dll/shot/dllshotSoulCm050.dll`.
  - **Drop:** the mass row's `+0x24` = (6, 116), rate `+0x2C` = 1000, meant as 100% for testing. The units are inferred; raise it if it isn't 100%.
  - **Test (user, 2026-11-20):** the soul drops, and its name and description show.
    - **Text:** the description needed a line break. The game's own text uses a literal backslash-n (`\n` written as two characters, e.g. "Summon an 8-bit bat as a\nfamiliar."), so ours does too.
    - **MP:** the menu showed **MP 8**, which is the template's `+0x2A`, so `+0x2A` is the displayed cost (now 20). `+0x2E` isn't it, despite the familiar-tool note.
    - **Casting:** it put out "invisible-ish shadows" that moved along the ground and hit something, maybe, but not all of them connected. That's expected: it's the zombie code with our sprite's animation numbers.
  - **Soul module vtable** `0x85701D90` (356 slots, a different base class from the enemy modules). The template's own slots are 0, 1, 2, 4, 9, 16, 24 (info), 25, 26, 179 and 180. Next: find its update and replace it with the worm throw.
  - **Soul update (slot 9, `0x85711D38`, f1 = frame time):**
    - `+0x318` holds the state: 2 walk at a fixed speed (turning at the wall contacts `+0x23C`/`+0x240`), 3 → 4 wait for the animation to end (sprite `+0xAC`), 5 destroy (vtable `+0x158`).
    - Other fields: lifetime `+0x320` against limit `+0x32C`, direction `+0x324`, velocity `+0x64`/`+0x68`, sprite request `+0x258`.
    - Slot 16 runs once (flags `+0x328`/`+0x329`); slots 179/180 are the command queue (Zombie: `(0,1,0)`, `(2,0,1)`).
    - **So the Zombie soul already walks on the floor, turns at walls and expires.**
  - **Info block word +8 = the shot's attack attributes (enemy side):** Fishman fireball `0x4000010A` (fire `0x100`), Black Knight lance `0x80000082` (pierce `0x80`), Zombie `0x42` (strike `0x40`).
  - **Build 2 (2026-11-20; installed, untested), still no code:**
    - `li r8,0x42` at `0x857119EC` → `li r8,0x2042` (strike plus poison `0x2000`).
    - The soul draws its own sprite, `p_Cm050s.opd` (path patched; same page and palette files as the enemy). Every animation in it plays the crawl, which should fix the invisible shadows.
    - Description break moved after "that" (user).
    - Next: module code for the thrown arc and the 1/2/3 count by soul level.
  - **Test (user, 2026-11-20):** when cast in a jump, a worm fell straight down from Soma, hit the floor and vanished, and its "shadow" moved right.
    - **Requests:** actually throw it; handle terrain properly (cf. the Shield Rod Axe Knight); MP 8 ("not a powerful attack").
    - **Findings:** the Zombie soul's update already does terrain. In state 1 it adds 640 px/s² of gravity until the exe-written floor push `+0x234` says it's on a floor, then snaps onto it. In state 2 it walks at 60 px/s and turns at `+0x23C`/`+0x240`. Position is `+0x5C`/`+0x60` (getters at `0x85710250`/`0x85710268`).
    - **The vanish was the art:** the soul sprite had inherited the enemy's 8 px small-worm shift, while the shot's origin sits on the floor surface, so the worm was drawn inside the floor.
    - **The Axe Knight route, for reference:** exe terrain queries `823C2D80` (floor push) and `823C2468`/`823C2720` (walls). Module code can call them through `ResolveIndirectFunction`; not needed here.
  - **Build 3 (2026-11-20; installed, untested):**
    - The soul sprite `p_Cm050s.opd` is built unshifted, in a temporary folder so it can't overwrite the enemy's `p_Cm050.opd`.
    - `src/poison_worm_soul_module.cpp` (compiled into `harmonyrecomp_dllshotSoulCm050`) overrides slot 9. In state 0 it sets the velocity to (dir × 90, −210) px/s, so the Zombie's airborne state gives a throw arc. In state 2 the crawl is 24 px/s.
    - MP (`+0x2A`) is 8.
    - Still to do: the 1/2/3 worms by soul level.
  - **Test (user, 2026-11-20):** "looking good so far"; the throw started near his feet.
  - **Build 4 (2026-11-20; installed, untested):** on the first frame (state 0) the shot also moves to Soma's hand, 20 px forward (× direction) and 40 px up from its spawn point at his feet (`kHandForward`/`kHandUp`).
  - **Test (user, 2026-11-20):** "looks good"; the worms fade too fast.
  - **Build 5 (installed, untested):** lifetime. The template's slot 4 sets limit `+0x32C` = 3 + 0.25 × soul level (`+0x204`, byte) seconds (constants at `0x85701CFC`/`0x85701D00`); `+0x320` counts up by frame time and the worm fades once it passes. State 0 now sets the limit to 8 + 0.5 × level (8.5 s at level 1, 12.5 s at level 9).
  - **Behavior is still the R. Zombie soul's,** drawn with the worm sprite. Next: the module code for the worm throw (1/2/3 worms by soul level, crawl, poison and damage enemies).
- **Soul:** killing a worm gave an "R. Vampire Bat" soul. The row came from the 8-bit Bat's, whose soul is `+0x24` (category 6, index `0x3E`), with its rate at `+0x2C` (inferred: Skeleton 25, Zombie 20, 8-bit Bat 50). Both are now 0, so for now neither the mass nor the small worms drop a soul.
  - **User wants:** small worms never count for souls; the mass gets its own Poison Worm soul (not made yet).
  - **Plan:** once the mass has a soul, small worms point their exe object's row pointer (`+0xC0`) at a soul-less copy of the row.
- **Poison:** the attribute bits are known from Nathan's work (poison `0x2000`, stone `0x8000`; fire `0x100`, ice `0x200`, lightning `0x400`, holy `0x800`, dark `0x1000`). The stats rows and module masks don't carry contact status, though. Next: trace where an enemy's contact attack gets its attributes, starting from the box registration at `+0x220` (flags `0x40000029`).


## Catacombs chapter DLC: chapter + worm in one package (2026-11-20)

The stage designer delivered `Catacombs-mwld6cy6dcg6.hodchapter` ("The Moonlight Within", HoD Level Editor 0.3.1-ALPHA, level format 7) into the test copy's `stage\` folder. `modding/tools/catacombs_dlc.py` packs it with the worm into one official-style package: **package 23, content ID `...435400001758` (tag "CT"), chapter 14** (user's number). `poison_worm_module.py install` now goes through it, and worm package 22 is retired (moved to `poison_worm_originals/retired`).

- **.hodchapter** = zip: `manifest.json` (title, package 31, stage/map names, music), `package/...` (the game files), `package.header`, `editor/level.hodlevel.zip` (the editor's source, not game data).
- **Chapter number** = `stageNN_def.dat` `+0x20` (u32). Official: package 01 → 7, 02 → 8, 03 → 9, 04 → 10, 07 → 11. The editor writes 0 and its Mod Loader fills it at install; package 31 is the editor's Play slot ("chapter 32"). The base game has no def files. 12 is the first free number; 14 leaves a gap (the editor's Play uses 32, so gaps are presumably fine).
- **Package number appears in:** the file names (`stageNN_*`, `mapNN_*`, `bgmNN_def`, `bwall/ewallNN_*`, `textresNN_*`, `000info/packageNN.dat`), the dds paths inside both `.arc` files, the names in `stageNN_def.dat`, and the wall gimmicks' picture pack.
- **Set-file gimmick record:** u16 params size, u16 x, u16 y, char name[26], params. `attackBreakWall` (12 bytes) and `eraseWall` (8 bytes) params begin u32 picture pack (= package number; -1 in the editor means "own"), u32 picture index. The editor prefixes some names with `+` (`+eraseWall`, `+shutterV`). 9 walls per set file; Hard = Normal (identical file).
- **Text:** the chapter uses section 0 group 12 (stage name, music name); the soul's groups 13/14 merge in without a clash.
- **Host modules are matched by guest path** (`module_registry.cpp`: `dll/enemy/dll_cm050.dll`), not by package, so no exe change was needed to move the worm.
- **Enemies placed:** stock ones (armc02 ×34, YA_SK7 ×25, nirus, honeb, wdrag, matan0, thdm, axe_am, evil, dula00, final, troop, frank, plus `DLL_Region`, the Legion boss from official package 02). The Chapter 1 test worm stays and now loads from package 23.
- **Worm spots (user, 2026-11-20):** the designer marked them with Moldy Corpses (`matan0`). The build turns each into `DLL_Cm050` at the same x, with y = the ceiling underside straight above (searched in the `.hit2`, same room), in Normal and Hard: world (1429, 2016), (1249, 2240), (1438, 2240), (1568, 2240). Two low corridors, 96 px floor to ceiling. `.hit2` header: `*HT*`, u16 width, u16 height (cells), u32 data offset (`0xA0` here, `0x120` in Chapter 1).
- **Test (user, 2026-11-20):** worms hang on the ceilings in chapter 14 but release no small worms. Log `harmonyrecomp_035`: every release got handle 0, so spawn `8224C478` refused (Chapter 1 gets handles like `0x119`).
  - **Spawn's first check:** enemy manager `[0x8291D8F4]`, list `+0x14` begin / `+0x18` end (4-byte entries); more than 200 (`cmplwi 0xC8`) returns 0. The chapter places 108 enemies plus Legion (`DLL_Region`, many body objects), so the cap is the suspect. Not confirmed yet.
  - **Diagnostic (installed, untested):** on a refused spawn the module logs `[pworm] spawn refused: enemy manager ... list holds N (cap 200)`.
  - **If confirmed, options:** spawn the small worms outside the enemy list (as shots, like the Man-Eating Plant's seeds, which is how the user described them); raise the cap (an exe change); or the designer trims enemies.

## Small worms as enemy shots (2026-11-20; built, untested)

- **Confirmed cap (log `harmonyrecomp_036`):** all 24 releases refused while the enemy list held 223. Stage loading puts enemies past the cap; only spawns during play are checked.
- **User decision:** "make the small worms projectiles like the demon seeds".
- **How DLC enemies fire shots (Legion `DLL_Region` + `dllshotRegionHuman`):**
  - The enemy appends 60-byte requests to its own list at object `+0x1C8` (`+0x1CC` begin, `+0x1D0` end, `+0x1D4` capacity end), returned by vtable slot 21 (`addi r3,r3,0x1c8`). Legion's push is module code (`0x8BF16C48`); growth uses the game allocator/free pointers the game writes into module globals (Legion `0x8BF31564`/`0x8BF31568`, DLL_Cm050 `0x893B14A4`/`0x893B14A8`; r3 = size / pointer).
  - **Slot 1** queues one request per shot used (Legion `0x8BF11A18`; the 8-bit Bat's is an empty `blr` at `0x893917E0`). The game reads them when it builds the DLL enemy (`82250F78` → `8248A690(category, ID)`, a preload) and clears the list.
  - **Every frame** the generic DLL enemy update (`82252BB0`) fires each request: byte `+0x30` = 1 → skill factory `82487EF8(category, ID, owner handle, position, +0x18, +0x20)`; 0 → registry `82486AB0` + allocate `0x1CC` + `8248DB90` (Legion uses 0).
  - **Request:** `+0x00`/`+0x04` position, `+0x08`/`+0x0C` 0, `+0x10` category (11 = enemy shot), `+0x14` shot ID, `+0x18` facing (1 = left), `+0x20` 0, `+0x24` power (Legion: `[+0x1F0]` × 0.6), `+0x28` attack attributes (`0x40000042`), `+0x2C` `[+0x1E0]`, `+0x30` path byte, `+0x34` 65.536 × 18, `+0x38` `[[+0x2C8] +0x18]`. Initializer defaults (`0x8BF10000`): `+0x24` 1.0, `+0x2C` 5.0, `+0x30` 1, `+0x34` −1.0, `+0x38` −1.
  - The shot registry (`82486AB0`) is a linear list of (category, ID) pairs, 0x1A8-byte records; any 32-bit ID works.
- **Enemy shot IDs seen (category 11):** Fishhead shot 1, Legion fire `0x64`, Legion body `0x65`.
- **`dllshotRegionHuman` (Legion's falling body):** slot 4 setup `0x83891AB8`, slot 8 lifetime (`+0x31C` += dt; past 300 s → state 2), slot 9 update `0x83891D40` (state 0 airborne: vy += 588 px/s² up to 300; 1 on floor: vx = `+0x32C` × `+0x328`, floor push `+0x234` = 0 → falls; 2 start dying; 3 spray (two sub-shots via vtable `+0x4A0`); 4 destroy), slot 14 `0x83892120` terrain callback (landing → state 1, sound `0x128`). `+0x330` facing (1 = left), `+0x32C` speed (±30 px/s), sprites `+0x258` body (random animation `0x72`/`0x74`/`0x76`) and `+0x268` death (animation `0x71`); sprite `+0x30` = 2 when moving right. Info: category 11, ID `0x65`, attributes `0x4000004A`; sprite `data/enemy/DLL_region/p_region.opd`.
- **Built (`modding/tools/poison_worm_shot.py`):** `dllshotCm050w` = that module rebased to `0x85780000`, ID `li r7,0x65` → `0x4050` (`0x857919E0`), attributes `ori r8,r8,0x4a` → `0x404a` (+ player-side poison `0x4000`), sprite → `data/enemy/DLL_Cm050/p_Cm050w.opd` (`poison_worm_art.build_shot_sprite`: 128 animations, all the crawl except `0x71` = debris; unshifted frames).
  - `src/poison_worm_shot_module.cpp`: setup sets the crawl speed (9.375 px/s); the update turns at walls (`+0x23C`/`+0x240`, as the R. Zombie soul) and ends the worm after 20 s (state 2, its own spray).
  - `src/poison_worm_module.cpp`: slot 1 queues the preload request; releases now queue fire requests (random direction, attributes `0x40004042`) instead of spawning enemies; the cap of 12 counts this mass's shots within their 20 s. `shots = 0` in the tuning file brings back the enemy children.
- **Test 1 (user, 2026-11-20): Chapter 1 crashed** loading (`crash_20261120_103247`: DLL_Cm050 read guest `0x1CC`, object 0). `0x893917E0` is one shared empty `blr`: the Bat's vtable slots 1, 5, 6, 8, 9, 25, 81, 83, other vtables and the module startup table (`0x8938066C`/`0x89380670`, r3 = 0) all point at it, so the override ran with no object. **Fix (installed, untested):** the factory override records each new object; only the first call on such an object queues the preload (the game calls vtable `+4` right after the factory, `82250F54`). The shot module's overrides (`0x85791AB8`, `0x85791D40`) and the worm's other three are referenced once each (vtable + `.pdata`).
- **Test 2 (user, 2026-11-20):** Chapter 1 loads; preload queued (`harmonyrecomp_038`), every release queued and created a shot 25 px below the mass, but "they just immediately appear on the ground". Legion's body falls on its second sprite (`+0x268`, visible from setup) and shows the body sprite (`+0x258`, hidden at setup: `+0x29` = 0) only on landing (slot 14); the worm's second sprite showed nothing.
  - **Fix (installed, untested):** while state 0 the update shows the body sprite (`+0x29` = 1, second sprite 0) with animation `0x70` (the falling frames; `poison_worm_art.SHOT_FALL_ANIM`) through the body's own animation call (vtable `+0x2D0`: r4 animation, r5 0); on landing it switches to `0x72` (crawl) and logs where and after how long.
- **Test 3 (user, 2026-11-20, `harmonyrecomp_039`):** small worms fall, animate, land and crawl; they can be hit and killed, and they poison on contact (screenshot: Soma poisoned, damage 3). **No damage numbers** when hit; the user accepts that ("an acceptable compromise"). They floated above the floor: every landing rests at the floor surface − 16 (y 2336 over 2352 in Chapter 1; 2096 over 2112 in chapter 14), so Legion's body keeps its position 16 px above the floor. **Fix (installed, untested):** the shot sprite's worm frames move down 16 px (`poison_worm_art.SHOT_DROP`); sprite only, no code.
- **Test 4 (user, 2026-11-20):** small worms sit on the floor. The mass's death is "just a single worm flying away weirdly".
  - **The Bat's hit/death path:** the game calls module slot 31 (`0x89392268`, sets `+0x44D2`) on a hit and slot 32 (`0x89392278`, sets `+0x44D3`) on death (`82254578` calls `+0x80`). The Bat's dispatch (`0x893917E8`): `+0x44D1` skips the update; `+0x44D3` → state 4; `+0x44D2` while in state 0 → state 1 (fly, animation 1 = our small-worm falling frames). State 4 (`0x893921C0`): stops, hides the sprite (`+0x29` = 0), sets sprite `+0xAD` = 1 (the game's death effect, which seems to start from the current frame), clears `+0x229` (vtable `+0x28C`), waits for sprite `+0xAC`, then sets `+0x44D1`.
  - **Likely cause (not confirmed):** a non-lethal hit flew the mass as a Bat with the small-worm frames, and its death effect then started from that frame.
  - **Fix (installed, untested):** the update absorbs `+0x44D2` while the mass is alive and hanging, so it keeps its behavior and frame; it logs hits and the animation at death.
  - **Confirmed (user + `harmonyrecomp_041`, 2026-11-20):** no flying worm any more; the mass took 3 hits (absorbed, stayed hanging) and died in state 0 with animation 0 (the mass frame).
  - **Still not CotM:** CotM's mass sinks 0.5 px/frame, throws explosions and worm-chunk debris for 60 ticks, and throws debris for 3 frames when hit.
- **CotM death and hit debris (user: "Yes, build it"; 2026-11-20; installed, untested):**
  - **Mass (`poison_worm_module.cpp` slot 7):** on `+0x44D3` while hanging, it runs its own death for `death_time` (60 ticks): `+0x229` = 0 at once (as the Bat's death), velocity (0, `death_sink` 30 px/s), `death_debris_first` (4) chunks, then one every `death_debris_gap` (6 ticks); then the Bat's state 4 runs (hide + the game's death effect = the final puff). A non-lethal hit throws `hit_debris` (3) chunks. All are tuning keys.
  - **Chunks are worm shots marked in the request's facing word** (`+0x18`, which the shot copies to `+0x21C`): 0/1 = small worm, 2 = chunk left, 3 = chunk right; power 0, attributes `0x40000000`. `poison_worm_shot_module.cpp` setup turns a marked shot into a chunk (vx ±30–90, vy −90 to −180 px/s, gravity 420, life 0.35–0.6 s, animation `0x60`–`0x63` = CotM debris frames 12–19); its update skips the body's state machine and, at the end, sets state 4 so the body's code destroys it.
  - **Debris frames carry no hitboxes in `p_Cm050w.opd`**, so chunks should neither hurt nor be hittable, if this shot's boxes come from the sprite (the body's setup also passes a fixed (±8, 16) pair through vtable `+0xB8`; unverified).
  - **Not done:** CotM's explosions every 6 ticks (only HoD's final death effect plays).
- **Test 5 (user + `harmonyrecomp_042`, 2026-11-20):** the mass sank slowly but "didn't explode"; **no chunks**; small worms no longer show the falling frames (horizontal the whole fall). The log has the 3 hits, the death sink and its end, and small-worm markers 0/1 (so request `+0x18` does reach the shot's `+0x21C`), but no chunk ever logged its creation.
  - **Correction:** the body's vtable `+0x2D0` does not set an animation; it appends a 0x84-byte command (word 0 = animation, r5 at `+0x58`) to the sprite command queue at `+0x264` (`+0x268` begin, `+0x26C` end, `+0x270` capacity end). The "second sprite `+0x268`" in the earlier notes is the first queued command; `Show()` was writing `+0x29` into it. Now only the body sprite `+0x258` is touched.
  - **Diagnostics (installed):** the mass logs each chunk request with its list; the shot logs chunk creation, falls and landings with the queue size and the sprite's animation word.
- **Test 6 (user + `harmonyrecomp_043`, 2026-11-20):** "it does throw a bunch of worms out on death". The log shows every chunk queued and created (3 per hit, 4 at death, then one per 6 ticks), falls and landings, but the body sprite's animation word (`+0x258` → `+0x00`) stayed 0 (= crawl in `p_Cm050w.opd`) whatever vtable `+0x2D0` was asked for; the layer list grew from 2 to 3.
  - **Finding:** vtable `+0x2D0` appends a sprite layer (0x84 bytes, list at `+0x264`); the setup's first layer draws at Legion's body offset. Legion changes animations by writing the sprite's `+0x00` and setting `+0x1C` = 1, as our enemy module does with its own sprite.
  - **Fix (installed, untested):** the shot module draws only on `+0x258`: visible, animation written directly (`0x70` falling, `0x72` crawl, `0x71` debris when killed, `0x60`–`0x63` for chunks), and every layer hidden (`+0x29` = 0) each frame. No more `+0x2D0` calls. Logs each state change with the sprite's animation word.
- **Test 7 (user + `harmonyrecomp_044`, 2026-11-20):** "worms fall correctly". Log: falls show `0x70`, landings switch to `0x72`, 23 chunks created with `0x60`–`0x63`, all visible. Chunk looks, the mass's death puff and CotM's explosions not yet reviewed in game.
- **User check in CotM (2026-11-20):** the mass does **not** sink on death, it explodes in place; every hit launches a few fake worms that explode shortly after. `death_sink` is now 0 (installed). Our chunks use CotM frames 12–19 (the fake worms); the explosions are still missing.
- **CotM death routine, re-read (`0x08058344`, state table `0x0866E80C`):** each tick `tick % 6 == 1` → effect spawner `0x08014848(kind 1, count 1, x, y + 8 px, random spread 14 px / 8 px)`; `tick % 6 == 2` → a chunk (`0x08058D60`, random offsets); after 60 ticks → next state. (It also writes `+0x14` = `0x8000`, but the user sees no sinking.)
  - **Explosion actor:** `0x08014848` kind 1 → `0x0808DBF8` → actor type `0x202` (`0x201`–`0x203` share function `0x0808DCCD`). Sprite definition `0x081001FC` = {script `0x084545A8`, parts `0x08453FA0`}; animation **step** from the table at `0x08100208` by kind: 0 → 0, 1 → 5, 2 → 12, 3 → 20. Step 5 = frames 0, 1, 2, 4, 5, 6 at 4, 4, 6, 6, 6, 6 ticks.
  - **Common effects sheet:** parts `0x08453FA0` (125 frames, referenced by about a dozen effect definitions), tiles from VRAM tile 768 (`0x06016000`); the ROM tiles `0x084FECA8` (0x2000 bytes, uncompressed) are loaded there by records `0x080E5F2C`/`0x080E5F8C` (palette `0x084FEC68` → banks 4–5). The explosion's parts use palette bank 3; candidate colours = bank 3 of `0x456464` (the shared sprite palettes). Candidate render: `modding/build/cotm_explosion_candidate.png`. **Not yet confirmed** that these tiles and that palette are what CotM shows.
- **CotM explosion found (user captures, 2026-11-20):** orange/yellow flame puffs. The first candidate was wrong (records `0x080E5F2C`/`0x080E5F8C` load other tiles at that address). **The effects sheet's own loader is `0x0800D174`:** DMA `0x084548A4` → `0x06016000` (0xDE0 halfwords), palettes `0x08453F20` → bank 12, `0x08453F40` → bank 13. The explosion actor forces its palette (`+0x1C` = (`+0x6C` & 0xF) | `0x80000000`, `+0x6C` = 8 from the spawner). Rendered with palette `0x08453F00`, the frames match the captures (`0x08453F20`–`0x08453F80` give grey, blue, red and purple variants).
- **Explosions built (installed, untested):**
  - `poison_worm_art.explosion_frames()` composes effect frames 0, 1, 2, 4, 5, 6 (flips baked). `build_shot_sprite` now writes the shot's own page `f_Cw050.csr` and colours `c_Cw050.col` (palette 0 worm, palette 1 explosion), frames 20–25 = the explosion (part flags `1 << 8`, no hitboxes), animation `0x64` = 4, 4, 6, 6, 6, 6 ticks.
  - **Request marker 4 = explosion:** the shot stays still, plays `0x64` and is removed after 32 ticks. A chunk turns into an explosion when its flight (0.35–0.6 s) ends.
  - **Mass death:** in place (`death_sink` 0), no extra burst; every 6 ticks an explosion (phase 1, at x ± 7, y + 8 ± 4) and a chunk (phase 2), for 60 ticks; then the Bat's death.
- **Test 8 (user + `harmonyrecomp_045`, 2026-11-20):** explosions "may have gone off but it was hard to see them". The log has them created (animation `0x64`, visible). Per-part palettes are normal in HoD sprites (56 of 95 checked use palettes above 0; Legion uses palette 1), so the colours should be right. Likely cause: the explosion frames sit 3–19 px above their origin, so at CotM's +8 px below the hang point they drew inside the ceiling, under the foreground tiles. **Change (installed, untested):** origin 18 px below the hang point (`explosion_y`), x spread ±10, so the flames cover the mass body.
- **Unknown until tested:** whether the body shot is hittable and shows damage numbers, whether the preload is needed or works, the sprite's height on the floor, and whether the wall contacts are filled for this shot.

## Chapter name fix (2026-11-20; installed, untested)

- **User:** the chapter's in-game name was blank. Text ids are `(package × 4) << 24 | 0x0C << 16 | index` (group 12 of that package's text; the editor's notes say so too). `stageNN_def.dat` `+0x24` is the chapter-name id and each 0x24-byte `bgmNN_def.dat` record starts with a music-title id; both still pointed at package 31 (`0x7C0C0000`/`0x7C0C0001`). `catacombs_dlc.py` now renumbers them (`0x5C0C0000`/`0x5C0C0001`). Official: package 07 `0x1C0C0000`; package 01 uses bank 0 (base text) `0x000C006D`.

## Monster Compendium entry (2026-11-20; installed, untested)

- **Row fields:** `+0x4C` = 1 listed (0 for sub-rows such as `x1dr01`/`DRA3` and the 8-bit Dracula pet and Guillotine), `+0x4E` = the global entry number: base 1–51, package 01 52–53, 02 54–57, 03 58–61, 04 (8-bit) 62–82, 07 (Fuma) 83–92. `+0x2A` indexes the row's own package text: names group 9, descriptions group 10.
- **List builder `823F7178`:** walks numbers 0..`[manager +0x290]`, looks each up in the manager's map (`+0x2C`, `8224D008`) and lists rows with `+0x4C` ≠ 0. Entry = {row, number, unseen flag}; the flag is set when the save's u32 at `save +0x1018 +0x3700 + 4 × number` is 0, read only for numbers < 256 (`823F7228`). `+0x290` is raised at load to the highest number seen (`8224D4FC`), so new numbers need no exe change. The screen prints `+0x4E` (`823F8308`, formatting `827551C0`).
- **Poison Worm:** number **93** (`poison_worm_module.COMPENDIUM_NUMBER`), `+0x2A` = 0; package 23 text group 9 "Poison Worm", group 10 "A writhing mass of worms that / drops poisonous young below." The small-worm row copy keeps 0/0 (and small worms are shots now anyway). `cotm_enemies.json`: Poison Worm `enabled` and `compendium` on.
- **Not checked:** how the screen draws the enemy's picture (for DLL enemies it resolves the module through `8224BA18`), and that the soul shows as its drop.

- **Test (user + `harmonyrecomp_047`, 2026-11-20):** the entry appears at the end of the list as `???`, but killing a mass didn't unlock it.
  - **Cause: DLC enemy keys.** The DLC loader (`8224D464`) keys each listed row as **`0x38 + (package − 1) × 10 + row`**: map `+0x2C` key → row, map `+0x38` name → key, `+0x290` = the highest key. That key, not `+0x4E`, orders the list and indexes the save's counters: the kill (`82247BA8`: `8224B910(row +0x50)` → key; counter += 1, capped at 999999) and the list's unseen flag (`823F7228`) both use only keys below 256. Example: 8-bit R. Zombie, package 4 row 2 → key 88, shown as No. 62. Package 23 gave the worm key 276, so its kills were never counted.
  - **Rule:** a package with Compendium enemies must be numbered 20 or below, with at most 10 rows (`DLL_FuHbsr` is Fuma's 11th row and unlisted).
  - **Fix (installed, untested):** the Catacombs package is now **package 10** (content ID `…435400000A58`; free: 05, 06, 08–10), key 146; package 23 retired from the test copy. Name text id `0x280C0000`, music `0x280C0001`, walls 10, files `stage10_*` etc. Chapter 14 unchanged. Risk: the editor's Mod Loader may also hand out 05–10 on the user's main install.

- **Test (user, 2026-11-20):** the entry unlocks: "No. 93 Poison Worm", Kills 1, soul (3 of 9 levels), items `--------`, description shown. **Picture frame empty.** (The element icons are the 8-bit Bat's row values, not yet CotM's.)
  - **Correction to the 10-rows rule:** keys run on across packages. The 8-bit package (04) has 23 rows, keys 86–108, which covers the blocks packages 05 and 06 would use; it works because neither exists. Fuma's row 10 is key 126 = package 08's row 0. So **05, 06 and 08 are unsafe** for enemy packages; **09 and 10 are safe**, and package 10 can use keys 146–255 (about 110 rows) as long as packages 11–20 never carry enemies (they are characters and mods). All 21 Catacombs enemies fit in package 10.
  - **Picture:** `data/enemy/dictionary/enemy_<key>.dds` in the enemy's package (8-bit rows 2–22 = `enemy_088`–`108`, package 01 = `056`–`057`): 384 × 272 DXT1, Xbox byte order, the enemy's sprite at 1× on transparency. `poison_worm_art.build_dictionary_picture` composes the mass (frame 0) hanging, a falling (frame 5) and a crawling (frame 8) small worm from the ROM, encodes DXT1 (3-colour + transparent blocks where needed); packaged as `enemy_146.dds` (`catacombs_dlc.enemy_key(package, row)`). Installed, untested.

## Stats from CotM (2026-11-20; installed, untested)

- **User:** picture shows but is tiny next to the base game's; "fix the stats based on the cotm worm, account for the disparities".
- **Picture:** now 3× (`poison_worm_art.DICT_SCALE`), nearest-neighbour: mass hanging, falling worm, crawling worm.
- **HoD row layout (decoded against the Axe Knight / Peeping Eye pages):** `+0x00` the enemy key (8-bit rows: FCzombi 88, FCbat 93; base rows = their name index), `+0x04` HP, `+0x0C` attack, `+0x10` defense, `+0x18` score, `+0x1C`/`+0x20` items (category, index), `+0x24` soul, `+0x2A` name index, `+0x2C` soul rate, `+0x30` slash, `+0x32` strike, `+0x34` pierce, `+0x36` fire, `+0x38` ice, `+0x3A` lightning, `+0x3C` holy, `+0x3E` dark, `+0x40` poison, `+0x42` curse, `+0x44` stone (s16; negative = weak/red, positive = resists/blue), `+0x46`/`+0x48` item rates. Compendium icons left to right = `+0x32` strike, `+0x30` slash, `+0x34` pierce, `+0x36` fire, `+0x38` ice, `+0x3A` lightning, `+0x44` stone (the rock), `+0x3C` holy, `+0x3E` dark, `+0x40` poison (the eye), `+0x42` curse (the skull): confirmed when `+0x40` = +100 lit the eye blue (user screenshot, 2026-11-20).
- **Shared enemies (CotM → HoD):** Zombie HP 48 → 8, atk 70 → 8; Skeleton 25 → 12, 65 → 10; Bat 5 → 1, 50 → 6; Axe Armor 55 → 15, 120 → 10; Merman 60 → 13; Mummy 100 → 20; median HP ratio 0.18, attack 0.056 (HoD attack is compressed; CotM DEF ≤ 45 → HoD 0; EXP 2–30 → score 50–200).
- **Poison Worm (CotM HP 120, ATK 30, DEF 20, EXP 12):** HP **22**, attack **4** (below the Bat's 6, as CotM's 30 is below every shared enemy), defense **0**, score **100**, key **146** at `+0x00`. Elements neutral, poison status +100 (immune; its own element). CotM's weakness/resistance data is not in the stats row (`0x080CB2B8`, 20 bytes) nor the attack table (`0x080CBDD0`, 40 bytes: attack flags + power per attack) and is still unlocated.
- **Test (user, 2026-11-20):** picture full size; poison immunity shows (eye icon blue); soul rate shows 231.15% with the test 1000 and the soul did not drop on every kill (not pursued: test value). Logs `049`–`051` have no fights.
- **User decision (2026-11-20):** drops stay empty ("drops are not a problem (ignore them)"); the only known CotM weakness data is poison immunity, which the row already has, so the elements are final as built.
- **Drops (background):** CotM drops item `0x2E` (400/10000 = 4%) and `0x25` (50 = 0.5%). Its item names aren't found yet: the text is neither ASCII, a byte/word offset code, nor found by pattern (the `rmor` hits at `0x0FAFF0` were numeric data). Soul rate is still the test 1000.

## Enemy key budget (2026-11-20)

- **User concern:** don't let the Catacombs DLC use up other stage makers' room.
- **Budget:** key = 56 + 10 × (package − 1) + row, every row of an enemy package (listed or not); kill counters only below 256. Official: 56–57 (01), 66–69 (02), 76–79 (03), 86–108 (04, 23 rows: spills through 05 into 06), 116–126 (07, 11 rows: takes 08's first key). Clean free blocks: 09 (136–145), 10 (146–155). 11–16 = official character packs (no enemies), 17–22 our mods (no enemies; 21+ past 255).
- **The HoD Level Editor works in the same budget:** its Enemy Maker writes a custom enemy's row into the chapter's `EnemyParamNN.dat`, its portrait to `data/enemy/dictionary/enemy_<index>.dds`, its text into groups 9/10, and refuses "more than N custom enemies per level" (N not read out of its binary). Its notes say "a DLC package numbers its own portraits from the lowest file it ships".
- **Decision (user, 2026-11-20): option 1**, all Catacombs enemies in package 10 (rows 0–18, keys 146–164), spilling into package 11's block, on the assumption that no one makes a DLC package with an official package's number. Checked: the Julius pack (package 11) has no enemy data (`000info`, `data/credit`, `menu`, `opd/player/julius`, `player`, `sound`, `text`), so keys 156–165 are unused by it; its text bank is its own (`0x2C`, ours `0x28`). The Poison Worm stays row 0 (key 146).
- **Catacombs needs 19 new rows** (Mummy = HoD `mum`). Options put to the user: (1) all in package 10, keys 146–164, spilling into package 11's block (official Julius pack, never enemies) — one package number used; (2) packages 09 and 10, ≤ 10 rows each — no spill, two numbers used.

## Catacombs Compendium framework (2026-11-20; installed, seeded, untested)

- **User:** "base frameworks for all the enemies done in compendium ... give my save 1 kill in each ... not worrying about drops or AI".
- **Rows without code are enough for the Compendium:** the DLC loader adds every DLC row's name → package to the manager's map `+0x5C` (`8224D4A4`), which the Compendium page uses for the text bank (`8224BA18`); no module is needed until an enemy is placed.
- **`modding/tools/catacombs_enemies.py`:** the 20 Catacombs enemies without a HoD equivalent (Mummy = `mum`), package 10 rows 0–19, keys 146–165, Compendium No. 93–112 (worm row 0; others in CotM index order). Stats `hod_stats()` (HP × 0.18; attack 4 + 0.025 × CotM, 4–20; defense 0/1/2 by CotM DEF; score by EXP tier); no items, soul or elements; names from the manifest (text group 9), descriptions empty except the worm's. `catacombs_dlc.py` writes `EnemyParam10.dat` from it.
- **Pictures (`modding/tools/cotm_sprites.py`):** general CotM sprite reader: graphics row `0x080CDAA8 + 16 i` (palette, LZ77 tiles), sprite row `0x080CD400 + 12 i` (script, parts); multi-part frames with flips, palette banks relative to the lowest used; the idle frame (animation 0's first step), overrides Spirit 4, Mudman 4, Slime 10. Scaled up to 3× and centred. **Cerberus has none:** its sprite row's frames are its projectiles (16–32 px parts at VRAM tile base 192, 64 tiles); the boss body comes from elsewhere.
- **Save:** `savedata.dat` (0x3B00 bytes, no checksum) holds the defeated counters at file `0x3700 + 4 × key` (u32 big-endian); confirmed with the user's Axe Knight 2365 (key 4), Peeping Eye 200 (key 5), Poison Worm 1 (key 146). `catacombs_enemies.py seed-save` set keys 147–165 to 1 in the test copy (backup in `poison_worm_originals\saves\`).

## Cerberus (2026-11-20; research started)

- **User:** all Catacombs entries showed (log `harmonyrecomp_053` clean); oversized ones may show a crop, as Menace or Ryukotsuki do. Then: "let's actually do Cerberus next so we can replace Legion" (chapter 14's boss is `DLL_Region`).
- **CotM actors:** boss `0x174` (top `0x08098974`, state table `0x0866FB84`), part actors `0x175`–`0x17E` (state tables `0x0866FC28`…`0x0866FC8C`). First state `0x080989BC`: palette `0x083C6A04` → sprite palette banks 8–11 (`0x08097EB4`: DMA 0x40 halfwords to `0x05000300`), body sprite via `0x0809C2F0` → `0x0801147C(sprite, …, def 0x08101884, VRAM 0x06014000 + 32 × tile)`, a **streamed** sprite (the definition's tiles are copied to VRAM per frame).
- **Body sprite definition `0x08101884`:** parts `0x083C72AC` (8-byte records, frames end at flags bit 0, palette bank 8), script `0x083C7784` (frame arguments are part-record indexes: 0, 9, 18, 28…), raw 4bpp tiles `0x083C782C` (uncompressed; parts reference up to tile ~872). 26 frames: 0–7 walk, 8–9 crouch/rear, 10–11 leg pieces, 12–17 tail, 18–21 heads, 22–25 more pieces. Rendered: `cerberus_body.png` (scratch).
- **Behaviour, first pass (2026-11-20):** the emulator fixture (`trace_cotm_summons.py`, summon-oriented) can't run the boss: it needs a placement record at actor `+0xAC` (record `+4` → s16 x, y), a null-tolerant free (`0x08000BE8`), and more engine state; with memory auto-mapped it runs away. Static reading instead: nested state machine (state bytes at `+0x18`, depth `+0x22`, table at `+0x14`; top `0x08098974` dispatches `0x0866FB84`), one contiguous list of about 70 functions `0x080989BC`…`0x0809B2E0` shared by the body and the part actors. Setup `0x080989BC`: palette, streamed body sprite, then collision boxes from the stats row (`[+0x28]`, `[+0x48]`, `[+0x6C]+4`… each: kind 5, bank 8, attack from stats `+0`, box from the placement, `+0xE` from stats `+4`).
- **Enemy 68's own sprite row** (`0x080CD400 + 68 × 12`) is only the projectiles (tiles at VRAM base 192); the part actors set it with animation steps 0, 2, 4, 7, 9, 12. `0x08097D18` also copies a palette to background bank 12 (`0x05000180`), purpose not checked.

## Back to the designer as a .hodchapter (2026-11-20)

- **User:** "fires look better"; asked for chapter 14 back in the `.hodchapter` format to see whether the designer's editor reads it.
- `catacombs_dlc.py hodchapter` → `modding/build/catacombs/Catacombs-mwld6cy6dcg6 (Poison Worm).hodchapter` (also copied to the test copy's `stage\`). Same entry order as the editor's; `manifest.json`, `package.header` and `editor/level.hodlevel.zip` byte for byte; the package kept as the editor numbers it (31, chapter 0, text ids `0x7C0C…`, walls 31), plus: worms at the Moldy Corpse markers in both set files, the worm's 12 files numbered 31 (`EnemyParam31.dat`, `soulset_dlc31.dat`, sprites, the three guest modules), soul text merged into `textres31_*` groups 13/14.
- **Caveats:** the editor edits its level source, which still has the Moldy Corpses (the worms exist only in the built package; our tool re-adds them from the markers). Playing it needs our recomp build (the three modules are compiled into it); on another build loading `DLL_Cm050` would crash. Whether the editor's Mod Loader renumbers `EnemyParam31.dat`/`soulset_dlc31.dat` on install is unknown (its notes list only stage, map, bgm, wall, text and package files).

## CotM enemy manifest (2026-11-20)

`modding/cotm_enemies.json` is written by `modding/tools/cotm_enemies.py` from the user's ROM. It has 112 entries: every CotM enemy, boss, candle and the Coffin, without the 30 Battle Arena copies (indexes 106–135). It's a planning file and the game never reads it.

- **Switches, all off:**
  - `enabled`: a future build tool includes the enemy (stats row, art, module).
  - `compendium`: the enemy separately gets a Monster Compendium entry.
- **Your fields survive a re-run:** the switches, `hod_name` and `notes` are kept; only the ROM-derived fields refresh.
- **Names:** `hod_name` defaults to `DLL_Cm<CotM index>` (e.g. `DLL_Cm050` for the Poison Worm, `DLL_Cm068` for Cerberus). The `DLL_` prefix means the game loads it as its own module, the DLC way. `hod_stock` names the same monster where HoD already has one.
- **Actors:** `actors.placed` is the CotM actor type that every room using this enemy loads. 85 entries resolve that way; the other 27 are ambiguous because their rooms load two enemies (Cerberus shares its room with the Trick Candle). `actors.candidates` lists children, projectiles and ambiguous types, unverified.
  - **Check:** the Poison Worm entry matches the hand trace (0x160 placed; 0x161 small worm and 0x162 debris as candidates; area 1 rooms 1 and 8).
- **Attack flags are inferred:** the low nibble is the element; `0x40` adds that element's status (Stone, Poison, Curse); `0x10` adds knockback.
- **Not yet checked:** whether the Compendium and save data have room for extra entries. Check that before the first `compendium: true`.
- **Catacombs work set (user, 2026-11-20):** the enemies of the Catacombs, which the other person's stage is based on, are tagged `group: "catacombs"` and stay switched off:

  > Skeleton Bomber, Bone Head, Poison Worm, Earth Demon, Skeleton Spear, Mudman, Spirit, Gremlin, Hopper, Coffin, Mummy, Slime, Brain Float, Zombie Thief, Stone Armor, Fox Hunter, Arch Demon, Grizzly, Arachne, Trick Candle, Cerberus

  Tag with `cotm_enemies.py --group <tag> "<name>" ...`. CotM area 1 is the Catacombs: it holds 30 of the set's room placements.
- **Actors resolved by elimination** (`RESOLVED` in the tool), each being the only actor in the enemy's rooms that no other enemy explains (0x1DF is the candle):
  - Mudman 0x0FE, Gremlin 0x12F, Arachne 0x124.
  - Cerberus 0x174: the boss room, area 1 room 5; it heads Cerberus's 0x175–0x17E code block.
  - Trick Candle 0x14E: also in the boss room.
  - **Coffin is not in any room's enemy list:** something else spawns it, and that's still open.

## Stage 2a: Bat-based art test (2026-11-20, exe `dbe238f8`)

**Result (user, 2026-11-20): the art works.** The worm mass showed hanging where the bats are. Approached, it behaved as a Bat: it detached and flew off, drawn as the falling small worm. So the ROM-to-HoD sprite conversion, 1:1 scale, ceiling anchor and animation timing are right, and the behavior is the Bat's, as expected. The worm placement overlaps the middle stock bat (all three are still placed). Next: the own-module route.

The user chose to try the Bat version as a test. The final build will use its own module (the DLC way).

- **Constructor:** `pworm` → Bat constructor `822C7F90`. The row is copied from `armc02` with HP 58 (CotM 120 × HoD Skeleton 12 / CotM Skeleton 25), drops 0 and no Compendium entry.
- **Sprite name:** every enemy class passes a fixed resource name to the base constructor `8223FBB0` (stored at object `+0x30`). The sprite path is then `data/opd/enemy/<name>/p_<name>.opd`. `src/poison_worm.cpp` swaps the Bat's `armc02` for `pworm` during a `pworm` spawn (log: `[pworm] resource name 'armc02' -> 'pworm'`).
- **Stock classes load sprites only from the base `D:` device, never from DLC:** the first try logged `FAILED: D:\data\opd\enemy\pworm\p_pworm.opd`. For this test the sprite goes into the test copy's base `assets/data/opd/enemy/pworm/`. DLC monsters (`DLL_` modules) load from their own package, which is one more reason for the own-module route.
- **Art:** `modding/tools/poison_worm_art.py` builds `p_pworm.opd`, `c_pworm.col` and `f_pworm.csr` from the ROM, laid out like the Bat's sprite: 12 frames, 3 animations, 1:1 pixels, CotM ticks.
  - Anims 0 and 1 (the Bat's hang) play the parent loop.
  - Anim 2 (the Bat's flight) plays the falling child.
  - Parts are placed from the Bat's hang origin (75, 58).
- **Placement:** set (2560, 2224) = world (1280, 2224), on the ceiling between the stock bats.
- **Smoke test:** the title demo spawned it (HP 58.0, row `pworm`) and its sprite opened with no errors; only the optional `_idx.dds` and `_uv.uvb` atlas files were reported missing.
- **Expected in game:** it hangs like a worm and then flies at the player with the Bat's AI, showing the falling-worm frames.

## Stage 1 results (2026-11-20)

**Passed (user, 2026-11-20, exe `f4b76647`):** the `pworm` skeleton right of the Chapter 1 start is "tanky". It spawns under its own name, with its own EnemyParam row, next to stock enemies. A new enemy identity needs one registration hook plus native data.

**First in-game test (user, 2026-11-19 build):** four skeletons appeared on the y=1944 line where there are normally three, so `pworm` spawned. All four died in one hit, and that turned out to be the row's fault.

- **The row's HP field is `+0x04`, not `+0x0C`.** Setter `82240538`: object HP `+0x98`/`+0x9C` = row `+0x04` × a difficulty factor (`825928D0`) × player scaling. Row `+0x0C` feeds attack (`+0xA8`/`+0xAC`). The first build had raised attack (10 → 50) and left HP at the skeleton's 12.
- **Fix:** HP 12 → 600 (`HP_SCALE` 50); attack is the template's 10 again.

**Second build (exe `82039a4e`, row fixed):**

- **Spawn log:** `src/poison_worm.cpp` also overrides the spawn routine `8224C478` (defined in shard 1, called only from shards 4, 7, 14 and 33, so no rewrite is needed). When a `pworm` spawns it logs the handle, the row it got, its HP and its position.
- **Title-screen demo:** the game's own attract demo logged `[pworm] spawned … at 440,2336: row … 'pworm', HP 600.0`, and Alucard's Sword familiar targeted and hit it. The identity, the row lookup and the HP all work.
- **Stage set X is in half-pixel units, Y is not.** The record (880, 2336) spawns at world (440, 2336). The player starts (801…705, 2336) are at world x ≈ 400, which matches the demo Alucard at 400,2330. Convert set-file X ÷ 2 for world pixels.
- **Placement:** first (880, 2336) = world (440, 2336). The user found that nearly on top of the start, so it's now set (1472, 2336) = world (736, 2336), about 340 px right of the start and before the bats (world ≈ 1256).

**Isolation leak (found and fixed 2026-11-20):** two user sessions (logs 004 and 007) started the test exe directly instead of through `Play Test.bat`, so they used the main `Documents\harmonyrecomp`.

- **What happened:** at 03:50 the game unpacked the first package 22 (HP 12, attack 50) into Documents, and the 03:57 session reused that stale copy. That's why the user's skeleton still died in one hit.
- **Main saves:** not written. The only changes were the package folder and its header.
- **Cleanup:** both were moved to the test copy's `poison_worm_originals\leaked_from_documents_20261120`.
- **Fix:** worm builds (`HARMONYRECOMP_POISONWORM`) now always use the `userdata` folder next to the exe, however they're started (`harmonyrecomp_app.h`, `OnConfigurePaths`).
- **Check:** with exe `f4b76647`, both a direct start and `Play Test.bat` logged the test `userdata`, spawned `pworm` at world (736, 2336) with HP 600.0, and left Documents untouched.

## Stage 1: registration proof (built 2026-11-19)

**Verified without playing (2026-11-19, test exe `11d02633`):**

- The log shows `[pworm] registered 'pworm' (hash 108D654E) -> constructor 8236CD68 … inserted 1`, and package 22 unpacks.
- A live read-only probe at the title screen found the constructor map at 57 entries (56 native plus `pworm`).
- The EnemyParam maps (`+0x2C`, `+0x38`) are still empty at the title screen, so the game loads rows later. Whether the `pworm` row registers can't be seen until a stage loads.
- The main install's exe is unchanged.

A new enemy name, `pworm`, uses a stock enemy's code under its own identity.

- **Code:** `src/poison_worm.cpp` (CMake `HARMONYRECOMP_POISONWORM`, default OFF) overrides the registry setup `8224BA98`. It calls the original, then inserts `pworm` → the skeleton constructor `0x8236CD68` into manager `+0x20`, using the game's own hash (`825BFF28`) and map insert (`82378958`). It logs `[pworm] registered …`. No call-site rewrite is needed: the function is defined in shard 1 and called from shard 0.
- **Build:** `python modding/tools/rebuild_recomp.py ON POISONWORM`. Every build without the word now passes `HARMONYRECOMP_POISONWORM=OFF` explicitly, so the CMake cache can't carry it into a normal build.
- **Data:** `python modding/tools/poison_worm.py install` writes to the test copy only.
  - Test package 22, content id `000000000000000000000000000000505700001658` ("PW"), holds `data/enemy/EnemyParam22.dat`. Any DLC with a `data/enemy` folder gets flag 4, and the game then loads `EnemyParam<package number>.dat`.
  - The one row is a copy of `ya_skl` with HP 10 → 50, both drop rates 0 and no Compendium entry (`+0x4C`/`+0x4E` = 0).
  - Chapter 1 Normal gets one record, `pworm` at (1481, 1944). The stock skeletons stand at x 1381, 1581 and 1781 on the same floor.
- **Install the exe:** `poison_worm.py install-exe` (test copy only; it checks the exe has the hook). `uninstall` restores the originals kept in `poison_worm_originals\`.
- **Pass criteria:**
  - The log has `[pworm] registered … inserted 1`.
  - In Chapter 1 there's an extra skeleton between the stock ones that takes about five times the hits.
  - `enemyprobe.py` (run against the test game) lists one object whose row name is `pworm` beside `ya_skl` ones.
  - A chapter restart still gives exactly one.
- **Build state:** the `.setup` build output was already newer than the main install's exe before this work (other sessions' changes), so the test exe contains that newer source as well.

## 1. Circle of the Moon behavior (USA ROM, static read)

All addresses are GBA addresses in the user's own USA ROM (SHA-1 `d661b01e…`). The numbers below come from the original code, not from video.

### Identity and data

| Item | Value |
| --- | --- |
| Parent actor type | `0x160`, top function `0x08057BF8`, state table `0x0866E7FC` |
| Child actor type | `0x161`, top function `0x08058488`, state table `0x0866E814` |
| Actor function table | `0x0866C1B8 + type*4` |
| Enemy index | 50 (`INDEX_ENEMY_POISONWORM`), used by both parent and child |
| Stats row `0x080CB2B8 + 50*20` | attack flags `0x46`, HP 120, ATK 30, DEF 20, EXP 12, item `0x2E` at 400, item `0x25` at 50 |
| Child stats | HP **1**; attack flags/ATK from `0x080CBDD0 + 50*40` (+4/+6) = the same `0x46` / 30 |
| Placements | Area 1 room 8 (`0x0D7F58`): three parents on the ceiling at y=32, x = 224, 608, 1052, param 0 |

### Parent (sub-state `0x08057FF0`)

- **Idle animation:** script step 0, frames 0–3, 8 ticks each, looping. Each frame is one 32x16 OAM part at (-16, 0), so it hangs below its anchor point.
- **Crawl:** it creeps along the ceiling at 0.125 px/frame (`0x2000` in 16.16). Every 120–239 frames it re-aims toward the player's X. It stays within ±32 px of its spawn X and reverses at walls.
- **Trigger:** checked only when the release timer runs out. The player must be below the worm, within 96 px horizontally and within 156 px vertically.
- **Release rhythm:** it releases in bursts of 4, 20–40 frames apart, then pauses 210 frames. Out of range, it retries every 20–40 frames.
- **Cap:** no release while 12 or more type-`0x161` actors exist in the room (all parents count together).
- **Release point:** parent X ± 10 px; parent Y + 24 to 28 px. The child starts with a random horizontal speed of ±0.5 px/frame and zero vertical speed.
- **Hit reaction:** for the first 3 frames after a hit, it throws worm-chunk debris (actor `0x08058D60`, frames 12–19).
- **Death (`0x080582EC` → `0x08058344`):** stops moving, sinks at 0.5 px/frame, spawns an explosion every 6 ticks and debris, then a final puff after 60 ticks.

### Child (type `0x161`)

- **Falling (sub 0):** animation step 5, frames 4–7 ping-pong at 4 ticks each, with an 8x32 part. Gravity comes from the shared movement routine `0x08011EE8`. While falling it uses the second hitbox (frames 4–7).
- **Landing:** it picks a direction at random (50%) and crawls at 0.156 px/frame (`0x2800`).
- **Crawling (sub 1):** animation step 12, frames 8–11 at 8 ticks each, with a 32x8 part. It reverses at walls and faces its direction of travel.
- **Despawns:** when it leaves the camera rectangle widened by 32 px on the sides, 96 px above and 32 px below.
- **Dies:** at HP 0, or when its collider's contact bit (`+0x14 & 1`) is set. That bit is set by the shared overlap query `0x08016238`. Whether touching Nathan sets it (so a child dies on contact) is **unconfirmed**.
- **Parent death:** nothing links parent and child. Children already in play **survive** the parent's death.

### Poison (inferred)

The attack flags `0x46` mean element 6 (Poison), status bit `0x40` and no knockback bit `0x10`. Slime, Killer Bee and Battle Arena Bloody Sword carry the same flags. The same bit pattern explains others: Medusa Head `0x45` (element 5, Stone) and Legion/Marionette `0x4A` (element `0xA`, Dark). Both the parent body and the child carry `0x46`, so **both contacts poison**. This has not yet been confirmed in the player-damage routine.

### Graphics

| Item | Value |
| --- | --- |
| Graphics row | `0x080CDAA8 + 50*16`: palette `0x083C3BB0` (16 colours), BIOS-LZ77 tiles `0x083C3BD0` (0x800 bytes = 64 tiles) |
| Sprite row | `0x080CD400 + 50*12`: animation script `0x083C415C`, parts `0x083C40BC` (20 single-part frames) |
| Script steps | 0 = parent loop, 5 = child fall, 12 = child crawl, 17/20/23/26 = debris flickers (6 ticks) |
| Frame origin | The part offsets above. Keep them when converting to HoD. |

A preview renderer was used for the check (scratch, not in the mod). Its output matched the expected shapes: a hanging mass, a falling strand, a crawling worm and tumbling chunks. It belongs in `cotm_extract.py` once this goes ahead.

## 2. HoD enemy registration (TU2 exe, static read)

- **Manager:** `[0x8291D8F4]`.
- **Base registry:** a `{name, ctor}` table at `0x821DDC40` with 56 entries (`zombi` → `0x8236E708`, …). `0x8224BA98` inserts each one into manager `+0x20`, keyed by name hash `0x825BFF28`.
- **EnemyParam:**
  - Base rows: `0x8224D0FC`. DLC `EnemyParam%02d.dat` rows: the loop at `0x8224D2BC`.
  - Every row goes into `+0x2C` (index → row) and `+0x38` (hash of the row name at `+0x50` → index).
  - Rows whose dictionary-image flag `+0x4C` is set also go into `+0x68`.
- **Spawn `0x8224C478(name, x, y, r6, r7, r8)`:**
  - Refuses to spawn above 200 live enemies.
  - Names starting `DLL_` take the module path (`<dev>:\dll\enemy\DLL_<name>.dll`, map `+0x5C`).
  - Other names go to the `+0x20` ctor, then the param row is looked up by the **same name** in `+0x38` (`0x8224D008` → `0x82240538`).
  - Then it sets the position and calls vcall `+0x4C`.
- **Stage file `stage00_00_set.dat` (`SSD*`):**
  - Header +0x0C is the enemy section offset; count u16 at +0x1C (93 in Chapter 1).
  - Record = u32 param, u16 x, u16 y, char[24] name.
  - +0x08 holds 40-byte spawn zones (`sf_bor`, `zombi`). +0x40 holds four player starts: (801,2336) (769,2336) (737,2336) (705,2336).

### What this means for a new identity

| Need | How |
| --- | --- |
| Parameter row | **Table edit:** a row named e.g. `pworm` in our own DLC `EnemyParamNN.dat` (DLC rows reach `+0x38`) |
| Placement | **Table edit:** a record in `stage00_00_set.dat` |
| Name → constructor | No table holds it (code-defined, 56 fixed entries). One override of `0x8224BA98`: call the original, then insert `pworm` the same way |
| Proof step | Point `pworm` at the stock `zombi` ctor, set a different HP, and spawn both |

The alternative is the `DLL_` route: a rebased enemy module (Nathan's `dllTest12` precedent), such as a copy of an FC 8-bit DLC enemy. It gives a fully separate module, but costs a module rebase and recompile.

## Open items

- The exact tile and world coordinates under the first overhang past the starting room's right exit. These need `stage00_00_hit.hit2` parsing or an in-game check.
- Whether the stock ctor hardcodes its sprite path or derives it from the name.
- Whether a child dies on touching the player.
- Whether the shared hitbox at `0x080CFD58` is per-frame.

## Cerberus boss, build 1 (2026-11-20; built, untested)

- **Template choice:** Legion's module (`DLL_Region`), copied as `DLL_Cm068` at the DLC bosses' shared base `0x8BF00000` (one boss per stage; host modules match by guest path). Gergoth (`fafni`) would match the moves but lives in the exe (user: Legion then). All module classes share the base-class layout (`+0xA4` position, `+0xAC` velocity px/s, `+0x2B8` main sprite request, `+0x2C8` the exe enemy object, `+0x1C8` shot list); Legion/Ryukotsuki use a larger intermediate class (second vtable 319 slots vs 307).
- **Boss-only vtable slots:** slot 83 (receives online sync messages; `+0x440A` online, `+0x4408` host) and slot 6 (publishes sync data, `+0x4400`/`+0x4404`). Slot 4 decodes the placement parameter (Legion `0x25025` → `+0x4744`/`+0x4748`). Slot 31/32 are the game's hit callbacks (r4 = box); Legion's update calls its handler `0x8BF12D78` when `+0x44D9` is set. The chapter-clear path is still unknown: not in the row, not in the placement parameter, not in the `bossDoor` params (`u32 side, float`). Stage def `+0x28`/`+0x2C`/`+0x30` differ between official (0x60/0x160/3) and editor (0xFF/0xC7/0) chapters, meaning unknown; def also names a second (boss) BGM.
- **Art (`tools/cerberus_art.py`):** body sheet def `0x08101884` (parts `0x083C72AC`, script `0x083C7784`, raw tiles `0x083C782C`), composited with head (anchor table `0x08101890`), resting tail (frame 17) and the crouch/leap overlays into 54 frames, 40 animations (walk, walk with mouth open, stand, rear-up, crouch, leap, lowered, 16 head angles open/closed for the laser sweep). Body = bank 8; head banks 8+9 merged losslessly (bank 9's shades 3-7 → bank 8's unused 8/11/13/14/15). 32 px blocks on the feet grid, deduplicated: 154 blocks on 10 pages. Palettes 0/1/2 = CotM's walk/laser/orb colour sets. HoD part flags bits 8+ select the part's palette. Compendium picture now from the walking pose.
- **Behaviour (`src/cerberus_module.cpp`):** while alive, slot 7 runs the CotM AI at 60 ticks/s (walk, shake, leap at the player, rear-up/picker, the laser sequence with the head sweep but no beam, the orb sequence without orbs) and steers the exe by velocity; once slot 32 fires, Legion's update runs (native death) and is logged. Palette per attack tried through sprite `+0x5C`. Diagnostic dumps (`[cerb]`): after setup, first update, 120 frames, slot 32, dying frames.
- **Stats:** Gergoth's row numbers (HP 1200, attack 20, defense 0, score 3000) on Legion's row. **Placement:** Legion's record → `DLL_Cm068` at the floor below (2528, 1248), Normal and Hard.
- **Test (user, 2026-11-20, log `harmonyrecomp_054`):** "very broken": a ring of Cerberus pieces that leaped around, no hit box or hurt box, no attacks. The log shows the AI ran its whole cycle (wake, walk, shake, leaps at ±45°/135°, picker, laser and orb sequences), but module `+0x2B8` is 0 in Legion's module, so no animation was ever set, and slots 31/32 never fired.
- **Legion's layers:** the exe enemy object (`+0x2C8`) starts with 10 sprite requests 0x84 apart (`+0x00` animation, `+0x10` speed 1.0, `+0x29` visible). Legion's setup hides layer 0 (the core) and shows layers 1-9 (the corpse shell, animations 0x3C-0x59, past the end of Cerberus's 40). Presumably the game takes the boxes from the visible layers' frames. Legion's per-layer `0x8BF13308(i)` only breaks corpses off (`+0x44C0` bit i) with falling-body requests.
- **Build 2 (module only, installed, untested):** Cerberus draws on layer 0 (made visible); layers 1-9 are hidden every frame. Extra dump at 600 frames.
- **Test (user, build 2, log `harmonyrecomp_055`):** Cerberus showed (in the orb set's red: sprite `+0x5C` is the palette, confirmed) and hits registered (slot 31), but Legion's corpse layers still drew: `+0x29` = 0 does not hide a layer. No beam or orbs (not built), and the laser leap couldn't reach the ledge (the room copies CotM's: floor 1248, side ledges at y 1184 over x 2336-2432 / 2624-2720, a middle ledge at 1200, upper ledges at 1120/1136). No sounds.
- **Build 3 (2026-11-21; built, installing):**
  - The body sprite has 128 animations: ours, then blank frames, so Legion's layers 1-9 (animations 0x3C-0x59) draw nothing and carry no boxes.
  - Stage collision through `823C2D80` (floor push-out, counts one-way ledges): leaps/hops/falls land on whatever is below while coming down; walking off a ledge falls; the laser jump (B0) aims for the ledge top above the far side's x and comes down from 20 px above it.
  - **Projectiles as puppet shots:** `dllshotCm068` = Legion's body shot rebased to `0x85800000` (functions `0x85811AB8` setup, `0x85811D40` update), ID `0x4068`, sprite `p_Cm068s.opd` (`cerberus_art.build_shots`: enemy 68's row = small orb, blue orb, flare (2 frames), puff, flash (2), 4 bolts; tiles LZ77 at `0x083CE604`, OBJ tile base 192, script frame numbers are part indices; plus the laser's BG strip pieces pre-rotated at 31 angles × 3 widths; per-part palettes via flags bits 8+). The boss allocates a 64-row table (16 bytes: x, y, animation, flags; `0xFFFFFFFF` = remove) and fires each shot with request `+0x18` = table | row; the shot follows its row by velocity. Hit boxes come from the frames (damaging beam pieces, orbs at full size, bolts).
  - Laser: muzzle flash at the end of B6; beam of 25 pieces 16 px apart from 32 px out of the head anchor: thick and harmless during B7, damaging during the B8 upward sweep, thin for 4 ticks, then removed. Orbs: two from (x, y − 32), rise/swell/hover/drift as CotM F0-F4, flare at drift tick 53 and drop a 3-piece bolt column (32 px apart, 12 ticks each) every 12 ticks, alternating sides; D3 waits for both.
  - Slot 1 (`0x8BF11A18`) also queues the preload of (11, 0x4068).
- **Soul design (user, 2026-11-21):** Cerberus's Soma soul = the lightning orb: cast, it floats quickly up to a set height (lower if a ceiling blocks it; it stops there) and rains piercing lightning bolts downward, as Cerberus's attack. Not built yet.
- **Not yet:** sounds (CotM's would come from the user's ROM; HoD's enemy sound path not traced), screen shake, tail wag, the palette fade, the chapter-clear path.
- **Test (user, build 3, log `harmonyrecomp_058`):** beam and orbs work; issues: Legion fragments still drawn (the body sprite's blank animations made no difference, so they don't come from layers 1-9's animation numbers, or not only); bolts stopped 96 px down when an orb was high; seams between beam pieces on the diagonal; Cerberus leapt out of the arena (no ceiling check). User: the laser jump goes to the second (upper) ledge only; no leaps while on the ledges.
- **Build 4 (module + package only, installed, untested):** layers 1-9 get scale 0 (`+0x38`/`+0x3C`) and animation 127 every frame; the request list after Legion's setup is logged (is the shell made of shots?); beam pieces drawn 24 px long, 16 px apart; bolt columns continue to the arena floor (up to 12 pieces); ceiling query `823C29C8` at 64 px above the feet stops a rise; the laser jump targets the second ledge up from the floor (scan via `823C2D80`, stopping at a ceiling); no A4 leaps (or shake-into-leap) unless on the arena floor; B10 always hops down toward the middle.
- **Test (user, build 4, log `harmonyrecomp_059`):** fragments still there; very visible beam seams and misaligned pieces (the body shot still gets terrain push-out near walls); leaps briefly stuck in walls; Cerberus never turned (beam came out of its back). Findings: no requests are queued by Legion's setup (not shots); layers 1-9 showed animation 127 and scale 0 in the dump yet still drew, so a frame with zero parts leaves the old frame drawn, and `+0x38`/`+0x3C` are not what hid them; the facing write was a byte at `+0x30` of a big-endian u32 (wrong byte).
- **Legion's laser (`dllshotRegionLaser`):** three layers in the shot's list `+0x268`; per layer `+0x38`/`+0x3C` x/y scale (it stretches the beam, `0x83911FA4`) and `+0x50` rotation (radians: the module's only angle constants are π and π/2; `0x839123B8`, from the same value it feeds sin/cos).
- **Build 5 (modules + package, installed, untested):** facing as u32 at layer `+0x30`; blank frames carry one transparent 32 px block (body) / one transparent pixel (shots); the beam is one shot showing a 64 px straight frame (centred on its line, origin at its start), stretched to 400 px (`+0x38`) and turned (`+0x50`, sign from `cerberus_tuning.txt` `beam_rotation_sign`, default +1 = clockwise with y down, unverified), plus 25 invisible boxed shots along it only while damaging; rows grew to 32 bytes (rotation, x scale, y scale); arena 180 / walls 190 from the centre.
- **Test (user, build 5):** fragments still drawn (not fought). Base-class layer accessors (all modules): `0x8BF11210` returns layer k's `+0x2A`; the layer initialiser (`0x8BF15A20`) writes `+0x29` and `+0x2A` with the same value; another returns `+0x48`/`+0x4C` (the layer's offset). So `+0x2A` = shown, `+0x29` = animating. **Build 6 (module only, installed):** layers 1-9 get `+0x2A` = 0 every frame (layer 0 = 1), plus the full animation switch to blank.
- **Test (user, build 6):** shell still drawn, even in the chapter-start overview. **Cause found:** Legion's slot 3 (`0x8BF12090`, draw setup) writes `+0x14` into 31 layers (enemy object `+0x14` ... `+0xF8C`, stride 0x84) and hides layer 0 with `+0x29` = 0: Legion has 31 layers (core + 30 corpses, matching its 31 boxes), and `+0x29` is "shown" after all. Builds 2-6 only touched layers 1-9. **Build 7 (module only, installed):** layers 1-30 get `+0x29` = 0 (plus scale 0 and the blank animation) every frame, and right after Legion's slot 3 (draw setup) so the chapter-start overview never shows them.
- **Test (user, build 7):** Legion pieces gone. Laser image reversed; its start drifted off the mouth while sweeping; the walk looked stiff (movement not tied to the steps).
- **Build 8 (module + package, installed):** `cerberus_tuning.txt` `beam_rotation_sign = -1` (so layer `+0x50` turns counter-clockwise for positive values, y down); the beam and muzzle flash start at the open mouth (head art: 34 px ahead, 4 px below the anchor) turned by the same quantised angle the drawn head uses; the walk is stepped by the module (single-frame animations 40-47 shut / 48-55 open, from the CotM script timing) and moves 0.5 px/tick only on frames 1-3 and 5-7, as CotM.
- **Test (user, build 8, video `<research folder>\cerberus.mp4`, 86 frames at 15 fps; read with OpenCV):** beam direction and sweep right (51° down → ~34° up); the drawn head did not follow: barely tilted while the beam swept down-to-level, then steeply up (looked like the howl), then low again while the beam kept rising; the beam start left the mouth. The user's CotM capture shows the head pointing along the beam.
- **Build 9 (module + package, installed):** 31 aim frames per mouth state with the head turned to the BEAM angle (head angle + 0x1000), 0x2400 … −0x1800 by 0x200 (animations 8-38 open, 39-69 shut; walk frames moved to 70-77 / 78-85; 16 pages); the frame index and the mouth point (34, 4 in head space, turned the same) both come from that angle; a log line every 8 ticks of steps 6-9 records the head angle, aim index, the animation asked for, and the layer's animation/frame read back.
- **Test (user, build 9, log `harmonyrecomp_064`, clips `cerberus2.mp4` / `cerberus3.mp4`):** head still wrong during the laser; Cerberus paced on the upper middle ledge while the player stood below; occasional blink. The log shows every requested animation read back from the layer exactly, and the installed sprite renders correctly per animation, yet the clips show Cerberus's layer drawing animation N − 16 for N ≥ 16 (laser animation 19 → the howl, 3; the single-frame walk 70+ → aim poses with still legs) and N below 16. The projectile sprite is unaffected (bolts 16-19 and beam 21-23 drew right). Cause not found (something Legion's setup leaves on its layer 0?).
- **Build 10 (module + package, installed):** every body animation is requested + 16 (`kAnimBias`), and each change is logged; on a ledge Cerberus keeps walking the way it faces at a cycle's end (no re-facing, so it walks off); the laser takes the near-white colour set (HoD palette 2, CotM `0x083C6B04`) and the orbs the pink one (1), matching the user's CotM capture of the laser.
- **Test (user, build 10, log `harmonyrecomp_065`, clip `cerberus4.mp4`):** Cerberus invisible for long stretches (from the start, while asleep and walking: requests 18 and 86-93), the howl at request 19, crouch/leap at 20-22: no single offset explains it (19 → the howl in builds 9 and 10 although animation 19 is a laser pose in both files; the installed file is current and the only copy). Head snaps of 22.5° entering/leaving the laser; the orb attack's crouch reads as a jump.
- **Build 11 (module + package, installed):** calibration mode (`cerberus_tuning.txt` `calibrate = 1`): once the player is in the room Cerberus stands and shows raw animation N = 0..127 for 36 ticks each at x = arena left + 3 N (logged), then fights; `anim_bias` is a tuning value (16); the drawn head angle eases 0 → 0x2400 while rising (B6) and −0x1800 → 0 after the beam (B9) instead of jumping by the 0x1000 offset; the orb attack stands.
- **Calibration (user's clip `cerberus_test.mp4` + log `harmonyrecomp_066`):** aligned on the log (calibration ended 79.7 s into the clip, started at 2.8 s, 0.601 s per number): request N showed body FRAME N (16 raised, 17 howl, 18 crouch, 20 leap, 21 lowered, 22+ laser poses; invisible from 85, past the blank frame 84). **On Legion's layers `+0x00` is a frame number, not an animation** (Legion steps its own frames). That explains every pose problem so far: "animation 0" = a frozen frame 0 (stiff walk), animation numbers landing on unrelated frames (howl mid-laser, aim poses while walking), and build 10's +16 pushing the walk past the last frame (vanishing). The shot sprite (shot layers) does take animations.
- **Build 12 (module + package, installed):** Cerberus is animated frame by frame from its own timers (walk script timing, the howl's 0/16/17/16/0 at 10/13/20/13/10 ticks, single pose frames, laser frames from the eased head angle); no bias; calibration off.
- **Test (user, build 12, log `harmonyrecomp_067`):** everything much better; the death showed a pile of Cerberuses (Legion's death re-shows its corpse layers) sinking through the floor (Legion sinks: y 1184 → 1312+ over ~9 s), no explosion. The boss chest DID appear after Legion's death (so the boss end works through Legion's module or the engine). User asked about other bases (Astarte: her package 01 has no enemy module, so exe like Gergoth; module bosses are Legion, Beelzebub, 8-bit Dracula, Ryukotsuki): staying on Legion.
- **Build 13 (module + package, installed):** CotM death drawn by Cerberus while Legion's update still runs underneath (for the chest): each frame after Legion's update, layers 1-30 hidden, every non-Cerberus request dropped from the list, the position held (no sink); Cerberus rears up and holds the howl frame, flashes (palette 2 every other 2 ticks), 2 CotM explosions every 4 ticks around the body (shot sprite animation 24, palette 4 = the worm's explosion art) until 420 ticks, flickers from 330 and is gone at 450 ticks.
- **Next (user):** sounds (howl, leap, thud, laser, ...) from the user's CotM ROM; precedent: build_shield_audio.py / nathan_audio_assets.py.
- **Test (user, build 13, clip `cerberus_battle.mp4`):** explosions and chest (Arma Custos) right, but the death still burst into many Cerberus copies. Cause: Legion's hit handler `0x8BF12D78` breaks one of its 9 corpse groups per big hit (`0x8BF13308` → flying effects `0x8BF17448` drawn with the parent's sprite, so Cerberus frames; not requests, not layers) until the broken mask `+0x44C4` reaches 0x1FF, then runs the core's death `0x8BF12F98` (the fight's end and the chest). Death sets `+0x44C0` = 0x1FF, breaking all nine at once.
- **Build 14 (module + package, installed):** `+0x44C4` |= 0x1FF at slot 32 (before and after Legion's callback) and before every dying update, so Legion skips the corpse breaks and goes straight to its core death.
- **Test (user, build 14):** death clean (CotM death, no copies), boss chest appears. Cerberus visuals, AI, laser, orbs and death are done; sounds next.
- **Sounds (build 15, module + package, installed, untested):** official DLC bosses ship their own voice bank in `data/sound/` (`VX_ENEMY_FC_DRACULA` / `VXJ_...`, `VX_ENEMY_BEELZEBUB`, `VX_ENEMY_ANFAUGLIR`). The game asks the module for the name through **vtable slot 103** (Dracula `0x8BF11540` returns `"VX_ENEMY_FC_DRACULA"`, Beelzebub likewise, Legion `li r3,0`) and plays a cue when the module appends {cue name, x, y} (12 bytes) to its list at **module `+0xFC`** (`+0x100` begin, `+0x104` end, `+0x108` capacity; Dracula `0x8BF13E34`, cue `VX_EN_FC_DRACULA_LAND`). Cerberus: the debug path string at `0x8BF02D4C` is patched to `VX_ENEMY_CERBERUS`, slot 103 (`0x8BF01FFC`) points at Legion's attack-state handler `0x8BF13F90` (never run by Cerberus), overridden to return that address; cue names live in allocated game memory. Bank (`cerberus_audio.py`, category 7, volume 80, mono 22050 Hz, 1.2 MB, plus the `VXJ_` twin): howl 0x163, leap 0x164, growl 0x165, land 0x167, laser 0x166 (cut to 3 s), orb flare 0x169, death 0x186, rendered with agbplay (`<research folder>\research\agbplay-windows\agbplay\agbplay-cli.exe`). **Correction:** the laser is `0xB3 << 1` = 0x166 (`08005E80`); the bare `0xB3` at death goes to `08007E24`, which sets a game flag (table `0x02025368`), not a sound. Cues at CotM's points: growl at shake/B0/D0, leap at A4/B1/B10, land at every landing, howl when the rear-up starts, laser at B7 tick 10, flare when an orb flares, death howl at death.
- **Test (user, build 15):** sounds play, "a bit quiet".
- **Build 16 (package only, installed):** louder: the seven clips share one gain putting the loudest peak at -1 dBFS (+4.3 dB, CotM's relative mix kept) and the XACT volume byte goes 80 -> 110 (FAudio curve: 80 = -14 dB, 110 = -8.6 dB, 180 = 0 dB), about +10 dB in all. No module or exe change.

## Cerberus's lightning orb: Soma's soul and Charlotte's spell (2026-11-21)

Request (user): Soma's Cerberus soul = the lightning orb (cast, it floats quickly up to a set height, stopping lower under a ceiling, and rains piercing bolts down, like Cerberus's attack); Charlotte blocks the orb shots with her guard and learns the orb as a spell. Tool `modding/tools/cerberus_soul.py`; code `src/cerberus_orb_spell.h` (shared) with `src/cerberus_soul_module.cpp` and `src/cerberus_spell_module.cpp`.

- **How Charlotte learns from an enemy (static read; no hooks needed):**
  - Her guard-hit handler (`8244B258`; player vtable slot at `0x82201FD8`) takes the absorb path `8244B838` when the guarding volume's flags (`[[hit+4]+4]`) have `0x10`.
  - `8244B838` resolves the attacking shot from the hit record's handle (`+0x10`, via `[0x8291D9F0]+172`: 16-byte entries by `handle & 0xFFFF`), needs shot `+0x08 & 0x18`, and reads the item at **shot `+0x118`**. When that is a category 8 item (`821D4878`: 0x745-0x80C, Charlotte's spells = `learningset` index + 0x745), it checks the owner (`82452CD0`, list `+0xA98`), permission (`823CA1E8`, else message 383) and adds it to the inventory (`82459050`).
  - Shot `+0x118` is filled by the DLL-shot init `8248DB90` from the shot's registry record (`+0x1C8` → 424-byte record: `+0x19C` learnable byte, `+0x1A0` learning index), which comes from the module's **info block** (vtable `+0x60`): `+0x00` category, `+0x04` ID, `+0x08` attack attributes, `+0x14` learnable byte, `+0x18` learning index, `+0x1C` name.
  - 8-bit Death: its sickle attack is its own soul shot (request category 0, ID 78), whose info block says learnable 1, index 25 = `learningset_dlc04` row "R. Deathscythe" (module `dllshotLearningFCdeath`, category 8 ID 25).
  - **Cerberus's puppets** (`dllshotCm068`) write `+0x118` = 0x745 + 26 each frame on orb and bolt rows only (animations 0-13, 16-19), 0 otherwise.
- **Tables:**
  - `learningset_dlc10.dat` ("LERN", v1, count, first index, 0, then 58-byte rows): row 26 (item 0x75F) from Deathscythe's. Row fields: `+0x00`/`+0x04` name/description text index, `+0x0C` element (slash 1, strike 2, pierce 4, fire 8, ice 0x10, lightning 0x20, light 0x40), `+0x1C`/`+0x1E` power level 1/max, `+0x24` MP, `+0x2A` character mask (Charlotte 0x40), `+0x2E` icon, `+0x34` cast motion, `+0x38` rarity. Lightning, power 8/40, MP 24.
  - `soulset_dlc10.dat`: the worm's row (116) plus Cerberus 117 (item 0x6E8) from R. Zombie's: bullet, effect 26, power 40 per bolt piece, element `+0x12` = 0x20, MP 24.
  - Text groups 13/14: 0 worm soul, 1 Arma Custos, 2 Cerberus soul, 3 Lightning Orb (six languages; Japanese in kana only).
  - Boss chest (treasureBox type 4, both set files): (6, 117, weight 2500); only Soma receives it. Cerberus's row soul = (6, 117), rate 0, as the official DLC bosses (Legion 6, 8-bit Dracula 79, Ryukotsuki 87, all rate 0), so the Compendium shows it.
- **Modules** (from `dllshotSoulFCzombi`, as the worm soul): `dllshotSoulCm068` at `0x85880000` (category 0, ID 117) and `dllshotLearnCm068` at `0x85900000` (category 8, ID 26; the patched `li r10` also fills the learnable byte, so it is learnable as itself, like Death's). Both: attack attributes `0x402` (lightning), sprite `data/enemy/DLL_Cm068/p_Cm068s.opd`. The longer name `dllshotLearningCm068` does not fit in the template's name field.
- **Behaviour** (update slot 9, `0x85891D38` / `0x85911D38`): the cast shot is the orb. It starts at the hand (16 px forward, 40 up), rises at 6 px/tick up to 112 px (or 12 px under a ceiling), swells, then sways and flares. A bolt column starts every 12 ticks for 90 + 10 × level ticks. Each bolt piece is another shot of the module from the skill factory (`82487EF8`, args as Soma's cast `824501D0`: kind, ID, owner handle = shot `+0xA4`, &x/y, facing 1, 0, level, 0; it returns a handle). Pieces are 32 px apart, up to 12, and the column ends at a floor. The template's update never runs while a shot is alive, so a hit does not end it (piercing). At the end, timer `+0x320` is pushed past limit `+0x32C` and the template's update ends and destroys it. Logs: `[cerb-soul]` / `[cerb-spell]` cast and bolt-piece lines.
- **Test (user, log `harmonyrecomp_072`, `crash_20261121_081848_1.txt`, as Charlotte):** crash as soon as Cerberus's orbs appeared. Also, Charlotte's R. Fireball "not working" (cause not found yet). The crash trapped in `dllshotCm068`'s C runtime (vector too long while adding a 0x84 layer, `0x85813738`), called from the exe's shot teardown `8248F758` (via `824820D0`). Frames were mapped from host RVAs to guest functions through the `mov edx,guest; lea r8,fn` pairs in each DLL's `ReXModule_Register`.
- **Cause:** a shot is two objects. The exe's **wrapper** (0x1CC bytes, `8248DB90`) holds `+0x04` handle, `+0xA4` owner handle, `+0x118` learnable item and `+0x180` the module object. The **module object** (r3 of the module's vtable) is a separate object whose `+0x298` = the wrapper's handle (slot 305 setter). The build wrote `+0x118` on the module object, corrupting it. The spell code also read the handle and owner from the module object.
- **Fix (modules only, installed):** `dllshotCm068` writes the item to the wrapper (module `+0x298` → handle table → wrapper; checked by wrapper `+0x180` == the module object). `cerberus_orb_spell.h` takes the handle from `+0x298`, the owner from wrapper `+0xA4`, and the factory's returned handle → wrapper → `+0x180` for the new piece's module object.
- **R. Fireball (user, log `harmonyrecomp_073`):** Charlotte casts, MP is spent, no projectile; Heal, Energy Flow and R. Summon Skeleton work. R. Fireball (`dllshotFCfireball`, category 8 ID 23) draws only from the 8-bit DLC's shared sheet `data/enemy/DLL_FCcommon/p_FCcommon.opd`; the log shows the game looking for it on `DLC01:` (package 10), which lacks it. Four of our modules copied from 8-bit ones (`DLL_Cm050`, `dllshotSoulCm050`, `dllshotSoulCm068`, `dllshotLearnCm068`) still named that path, so the sheet was asked for in our package first and that lookup was reused. This probably predates the Cerberus soul (the worm module has carried the path since 2026-11-20). **Fix (data only, package 10 installed):** those copies now name `data/enemy/DLL_Cm050/p_Cm050c.opd` (missing on purpose; `poison_worm_module.FC_COMMON`). Rule: when copying an 8-bit module, redirect `DLL_FCcommon` too.
- **Test (user, log `harmonyrecomp_074`):** R. Fireball works again, in chapter 1 as well. Chapter 1 was broken too because our soul and spell modules are loaded at game start for every chapter, not only Catacombs. Charlotte's guard neither blocked nor learned Cerberus's orbs. Shot boxes are plain rectangles in every sheet (ours, FCcommon, FCdeath), so the difference is the shot kind: every learnable enemy attack is a spell or soul module fired by an enemy (8-bit Fishman → `dllshotFCfireball` category 8, Death → its soul shot category 0), while our orbs were category 11 (Legion's corpse shot).
- **Build (modules + package, installed):** Cerberus fires the orbs and bolts as **Lightning Orb shots** (request category 8, ID 26; also preloaded in slot 1, and kept through the death request filter). Each still carries table | row in request `+0x18`, which `8248DB90` stores at **wrapper `+0x170`**. `cerberus_orb_spell.h`: a shot whose wrapper flags have `0x10` (enemy owner; `82481D60`: owner flags `0x04`/`0x40` → `0x10`, `0x02` (player) → `0x08`) and a marker in `+0x170` follows that row (position, animation, mirror; `0xFFFFFFFF` ends it). The learnable item comes natively from the module's info block. `dllshotCm068` no longer writes `+0x118`; it keeps the beam, flash and explosions.
- **Test (user, log `harmonyrecomp_075`, `crash_20261121_090900`):** crash as Cerberus cast the orbs. The first Lightning Orb shot update logged handle `FFFFFFFF` and owner 0. Its update runs once from its own setup (slot 4) before the init links `+0x298`, so it was taken for a player cast. The rise then called the ceiling query `823C29C8` (tail-calls `823C2720`) with leftover r5/r6, which wrote to guest `0x471`. These terrain queries take 4 arguments: r5 = r6 = 0, as in Shield Rod's `Call4` and the boss's `CallGuest`.
- **Fix (spell modules, installed):** `Guest()` zeroes r5/r6. An update without a wrapper link does nothing (velocity 0) and waits; after 60 frames unlinked it logs a warning and lets the template end the shot.
- **Test (user, log `harmonyrecomp_076`):** no crash, but every Lightning Orb shot logged "never got its wrapper" and was ended by the template, which drew R. Zombie animation numbers from our sheet: tiny orbs, no main orb. The R. Zombie soul class does not keep the module `+0x298` link (always `FFFFFFFF` in its update).
- **Fix (spell modules + package, installed):** the wrapper is found once by scanning the handle table (`[0x8291D9F0]+0xAC`..`+0xB0`, 16-byte entries) for the object whose `+0x180` is this module object, then remembered and re-checked.
- **Test chest** (Lightning Orb in a pre-boss chest for Charlotte): added for one test, then removed at the user's request.
- **Test (user, log `harmonyrecomp_077`):** Cerberus's orbs look right; Charlotte learned Lightning Orb by guarding them and cast it. **Working.**
- **Test (user, 2026-11-21):** Soma's Cerberus soul works (granted into the test save with `cerberus_soul.py grant`). Soul and spell both confirmed; power/MP (soul 40 per piece, 24 MP; spell 8/40, 24 MP) are untuned first guesses.

## Skeleton Bomber (CotM enemy 7), build 1 (2026-11-21; built, untested)

- **Request (user):** work on Skeleton Bomber; "replace the nova skeletons with the skeleton bombers" (Nova Skeleton = `YA_SK7`, 25 records in each of chapter 14's two set files).
- **ROM read:** `modding/research/skeleton_bomber/SKELETON_BOMBER_SPEC.md` (actor `0xC6`, bomb `0xC8`; walk, throw timer and range, bomb launch and gravity, explosion boxes). Script frames are part indices; animations start by step index (0 walk, 5 throw, 9 bomb, 14 explosion, 27 death).
- **Modules:**
  - `DLL_Cm007` = 8-bit Bat copy at `0x89400000` (all addresses the worm's + 0x80000; allocator globals `0x894314A4`/`A8`), `src/skeleton_bomber_module.cpp`. It walks with the small worms' floor settings (`GiveGravity`) and runs CotM's walk, turn, throw and death. Hits are absorbed into a 12-tick stun.
  - `dllshotCm007` = Legion body shot copy at `0x85980000` (ID `0x4007`), `src/skeleton_bomber_shot_module.cpp`, the same puppets as Cerberus's. The bomber simulates each bomb: CotM speeds, gravity `0x16C1`, explosion on floor, wall or ceiling (r5 = r6 = 0 terrain calls), fire attributes `0x4000010A`.
  - Tools: `skeleton_bomber.py` (module, codegen, build, package, `place`) and `skeleton_bomber_art.py`.
- **Art:** body `p_Cm007.opd` (26 frames, 8 px lower for the Bat's floor rest, CotM body box; animations walk, throw, death) and shot `p_Cm007s.opd` (bomb 6 × 6 box, explosion with CotM's growing boxes).
- **Not yet:** explosion sound `0x18A` (needs a voice bank), CotM's five death puffs, exploding on contact with the player.
- **Test (user, build 1, log `harmonyrecomp_079`):** mostly fine, but some bombers turned and threw away from the player. 2 of 11 logged throws were CotM's facing-away case (the bomb barely leaves the hand). **Build 2 (bomber module only, installed):** the bomber turns to face the player when a throw starts (user's request; CotM keeps the walking direction).

## Skeleton Bomber soul (2026-11-22; built, untested)

- **Design (user):** "throws a bomb, obviously". Soma lobs one lit bomb from the hand (3 px/tick forward, 2.5 up, CotM bomb gravity). It explodes on the first enemy, floor, wall or ceiling with the CotM explosion (fire, growing boxes, 48 ticks).
- **Module:** `dllshotSoulCm007` = R. Zombie soul copy at `0x85A00000` (ID 118, attributes `0x102` fire, sprite `DLL_Cm007/p_Cm007s.opd`), `src/skeleton_bomber_soul_module.cpp`. Update `0x85A11D38` uses the Lightning Orb helpers (wrapper scan, terrain with r5 = r6 = 0). Slot 16 (`0x85A12038`, the template's "end now", which sets `+0x328`/`+0x329` and calls vtable `+412`) is taken over, so a hit makes a flying bomb explode instead of ending it.
- **Tables:** soul 118 (item `0x6E9`; power 90, fire `+0x12` = 8, 12 MP, bullet), text index 4. The Skeleton Bomber row drops it (soul (6, 118), rate 40/1000, shown in the Compendium). Tool `modding/tools/skeleton_bomber_soul.py` (`grant` puts it in the test save; done 2026-11-22).
- **Test (user, log `harmonyrecomp_080`):** bombs pass through enemies (9 casts, every explosion "terrain"); slot 16 is not called on hits. **Fix (soul module only, installed):** the shot's wrapper is a hit-record object whose contact callback `82484918` stores what it struck at `+0xB8`/`+0xBC`; the bomb compares them with their values at the cast every frame, and a change means a hit and an explosion. Logged as `[bomb-soul] ... touched`.
