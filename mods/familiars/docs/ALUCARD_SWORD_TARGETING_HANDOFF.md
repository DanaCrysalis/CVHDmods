# Alucard Sword targeting handoff

The user tested build `1CF0A968` on November 18, 2026. Sword still sometimes flies past Treant toward the Dead Warrior behind it. It also begins targeting the Man-Eating Plant only after Alucard gets close. The user confirmed the translucent blue trail looks better.

## Log evidence

Start with [harmonyrecomp_217.log](../../logs/harmonyrecomp_217.log), lines 924–976. Alucard had one Sword Card, so this run used the circular attack (`move 0`). Enemy resource names below were verified against the local `EnemyParam.dat` and English text table.

| Log line and time | Recorded decision |
| --- | --- |
| 951 · 02:32:00.455 | Sword locked Dead Warrior `halfh` (`9C`) at (1106, 2773) with Alucard at (860, 2794). This lock has no matching Sword attack or explicit abort in the log. |
| 952–954 · 02:32:02.786–04.187 | Sword locked Dead Warrior `9C` again, switched to Treant `ent` (`9D`) 152 ms later, and then queued a strike on Treant. At the retarget, Treant's recorded center was (975, 2780) and Alucard was at (922, 2721). |
| 958–965 · 02:32:07.869–19.285 | Sword locked onto Treant four more times. Three have a logged Sword strike. The last lock ended with a hurt shape disappearing at 02:32:20.152, shortly after Alucard Shield contact. |
| 967 · 02:32:25.237 | At Alucard (1430, 2794), the periodic idle scan reported Dullahan `dula00` (`9F`) at (2374, 2728) as the nearest readable hurt shape, outside range. |
| 968–976 · 02:32:27.385–43.850 | Sword first detected Man-Eating Plant `syoku` (`9E`) at (1528, 2747) with Alucard at (1462, 2794), a center delta of 66 px horizontally and 47 px vertically. The Plant produced five locks and four queued strikes, all on rectangular shapes in region 40. |

The log confirms the initial lock on the rear Dead Warrior and a successful retarget in one recorded approach. It contains no Sword strike on that Dead Warrior, so the earlier pass cannot be reconstructed from the current messages. An `attack` entry records that Sword queued a native collider. Enemy HP must be observed separately to confirm damage.

The Plant was visible to the scanner once Alucard moved closer. Its absence from the 02:32:25 idle sample, followed by a lock after Alucard moved only 32 world pixels horizontally, makes hurt-box availability or actor activation worth checking before changing range again. The samples are intermittent, and the log prints shape centers rather than the edges used for the range check.

## Where to investigate

- [alucard_familiar.cpp](../../.setup/package/src/src/alucard_familiar.cpp). `FindTarget` scans native collision regions and accepts flags matching `0x15` with bit `0x2` clear. It resolves the owner at record `+0x14`, with source at `+0x10` as fallback, then reads rectangle, circle, or quadrilateral bounds. Acquisition uses distance to the hurt-box edge within 240 px horizontally and 144 px vertically.
- `FindApproachTarget` picks a candidate, then `FirstInApproach` sweeps from Alucard toward its hurt box with a 56 px vertical half-height. `TickAttack` repeats the lane check every eight ticks during `Phase::Approach`. The recheck ends when Sword reaches its attack start position, before the circle's windup completes. If the current lock has no readable hurt shape, the lane helper has no endpoint and the loss grace can last up to 24 ticks.
- For the Treant case, capture the original candidate, every in-lane Treant shape and its entry fraction, Sword's current position, and the transition out of `Phase::Approach`. This should show whether Sword committed before Treant's hurt shape appeared, whether other shapes won the lane test, or whether the visible flight continued after a retarget.
- For the Plant, stand at the reported distance with the enemy alive and sample across an attack and idle cycle. Track whether `syoku` has a live actor and published collision records before acquisition. Capture flags, source and owner handles, shape kind, region, bounds, and the distance to each edge. Compare with the same snapshot after stepping closer. This distinguishes activation or missing hurt records from a filter or range rejection.

The deployment and asset rules are in the [original familiar handoff](ALUCARD_GHOST_HANDOFF.md). The game was closed at the end of run 217. If a live reproduction is needed, have the user set up the two encounters and leave the game open for inspection.

## Change after run 217 (Claude, November 18): targets come from registrations

Build `E42D372D`. Not yet tested in game.

**Suspected cause of both reports.** `FindTarget` walked the collision manager's region lists (`8291D918`) from the player update. Enemies register their hurt shapes from several game threads, and Shield Rod already serializes `823C4C40` and `823C5098` with `collision_lock` for that reason. The familiar walk took no lock, so it could see a region half rebuilt. Run 217 fits this:
- Treant (region 0) was missing at the 02:32:00 and 02:32:02.786 locks while the Dead Warrior behind it (region 40) was present. It appeared at the next lane check nine ticks later.
- The Man-Eating Plant (region 40) had no shape at the 02:32:25 sample, about 100 px from Alucard, while Dullahan (region 41) did.

**Change.**
- Shield Rod's `823C4C40` override now also calls `alucard_familiar::ObserveHurtShape(handle, shape, r5 region)` after every successful enemy hurt registration. It uses the same `0x15` / not-`0x2` filter as `CaptureTarget` and runs under `collision_lock`.
- The bounds are read by `HurtBounds` during that call, while the shape is valid. They go into a 512-slot table keyed by (handle, shape).
- `FindTarget` now reads only shapes registered within the last 100 ms (`kShapeFresh`) and re-checks that the enemy is alive. Its arguments and results are unchanged, so Ghost, Bat, Demon, Sword and `ResolveHit` all use it as before. The region it returns is the native one passed to `823C4C40`, which is what `SubmitContactHit` needs.
- Lock order: `collision_lock` → `seen_lock`, and familiar `lock` → `seen_lock`. `seen_lock` is only held while copying the table and never while calling the game.

**If it still misses enemies**, the enemy is not registering a hurt shape at all at that moment (inactive, or no hurtbox in that animation). That is native behaviour, not a race. Log `ObserveHurtShape` calls per handle to confirm.

## Run 219 (November 18): the hurt-box filter was wrong

Build `E42D372D` did not fix either report. The user pointed out that long-range attacks (a Gergoth laser, Charlotte's Demon Seed) hit the Plant and Treant from across the map, so their hurt boxes always exist. Build `AC1F2D3D` logged every enemy registration (`[familiar] hurt registration`, about one line per flag change) while the user walked past the first Dead Warrior, the Treant, the second Dead Warrior and the Plant.

| Enemy | Records while asleep | Records once awake |
| --- | --- | --- |
| Dead Warrior `halfh` | `40000009` (body), `40000001` (box ~46 px ahead) | same |
| Treant `ent` | `40000000`, `40000008`, both region 40 | adds `40000009` in region 0 (caller `8230D094`) |
| Man-Eating Plant `syoku` | `40000000`, `40000008` | adds `40000009` (`8235BF38`); its shots register `4000000A` / `4000004A` |
| Dullahan `dula00` | `40000000`, `40000018`, `40000009` | |

Entity flags were `4` for every enemy, so `IsEnemy` was never the problem.

**Fix (build `2E684D61`, untested):** the familiar hurt filter is now `flags & 0x8` with `0x2` clear. The copied Shield Rod filter, `flags & 0x15`, required bit `0x1`, which only awake enemies register. It also kept the Dead Warrior's `40000001` box, which this filter now drops.

The meaning of `0x1` is still unknown; it may be the enemy's touch-damage body. Shield Rod's `CaptureTarget` still uses `0x15`, so its homing spells probably ignore sleeping enemies the same way.

## Same filter in Shield Rod and Nathan (November 18, build `44BEA2FA`, untested)

The user confirmed the familiar fix (Sword). The record-flag test is now `harmony::alucard_familiar::IsHurtRecord` (`alucard_familiar.h`): `0x8` or `0x10`, without `0x2`.

| Code | Before | Now |
| --- | --- | --- |
| Shield Rod `CaptureTarget` registration filter (homing spells) | `0x15`, no `0x2` | `0x1D`, no `0x2` (adds `0x8`, keeps everything accepted before) |
| Shield Rod Axe Knight "reached an enemy" probe | `0x10` | `IsHurtRecord` |
| Nathan pooled-shot probe and `82484918` shot-hit mark (`nathan_dss_damage.cpp`) | `0x10` | `IsHurtRecord` |
| Nathan per-wave recovery check (`82484918`, summon kind 9) | `0x10` | `IsHurtRecord` |
| Nathan `FindDssTarget` (`nathan_dss_combinations.h`, homing and sticky DSS shots) | `0x10` | `IsHurtRecord` |

`FindDssTarget` runs in Nathan's own module (`harmonyrecomp_dllTest12`, `nathan_dss.cpp`), which cannot link to the exe's registration record. It still walks the collision lists without the lock, so it can still miss a region that another thread is rebuilding. If Nathan's homing still skips enemies, share the record through guest memory.

In PvP, opposing players (`80000008`) now pass the probe checks (`0x8`), so a shot that hits a player counts as landed.

## Hurt record shared with Nathan's module (November 18, build `764E0D13`, untested)

**Why.** `FindDssTarget` runs in Nathan's module (`harmonyrecomp_dllTest12.dll`), which cannot link exe functions. It used to walk the collision lists without the lock.

**How the record is shared** (`src/hurt_record_guest.h`):
- The exe's registration record is mirrored into a guest-memory table, allocated by `AlignedScratch` on the first registration. The table has a `"HURT"` header and 512 entries of 48 bytes.
- `ObserveHurtShape` writes each entry under `seen_lock`. Each entry carries a sequence word that is odd while it is being written, so a reader skips half-written entries.
- Each entry has a steady-clock millisecond stamp. Readers keep boxes up to 100 ms old.

**How Nathan finds it.** `alucard_familiar::Frame` runs for every player from the `8244FFF8` override. It writes the table's guest address into Nathan's player block at `+8176` (`kNathanPointer`), for any player whose component vtable is `836C28E8`.
- That word comes right after the summon contacts (`7856 + 8 × 40`). A `static_assert` in `nathan_dss_combinations.h` guards the layout.
- `ResetProjectiles` clears that area; the next player update writes the address again.

**How Nathan uses it.** `FindDssTarget(base, player, x, y, wanted)` reads the table when that address is valid. Otherwise it falls back to the old list walk with `IsHurtRecord`, which only happens in the frame after a reset.

The installer copies the exe and Nathan's module; both hashes were checked after install.

