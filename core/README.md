# core

What every section builds on. Manifest: [`core.json`](core.json).

## runtime/: the hook hub

ReXGlue links **one** definition per guest function. Before the hub, whichever mod hooked a function first owned it and called the other mods by name: Shield Rod's file called the familiars and Nathan, Refectio's called Arma Custos and the familiars, and two copies of five overrides existed for the builds with and without Nathan. No mod could be left out or switched off alone.

Now `hod_overrides.cpp` holds the one definition of each **shared** function, and each runs a **chain** that the sections join at start-up:

```cpp
#include "hod_hooks.h"

// 824476B8 owner draw: draw after the game's own body draw.
void OwnerDraw(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  next(ctx, base);                      // the rest of the chain, then the game
  if (owner) DrawMyEffect(ctx, base, owner);
}
HOD_HOOK(kOwnerDraw, kShieldRod, 50, OwnerDraw);
```

- A handler calls `next` before, after or around its work, or not at all to **consume** the call (a collider tagged as its own, a skill index it implements).
- Lower `order` runs first, as the outer layer. The orders reproduce the call order of the builds before the hub; [`docs/HOOKS.md`](../docs/HOOKS.md) lists every chain.
- `HOD_SHAPE_OBSERVER` registers a callback for every collision shape the game registers, called under the collision lock.
- A section's **own** overrides (functions no other section needs) stay in its files and start with `HOD_PASS_IF_OFF(<feature>, __imp__sub_…)`.
- If two sections ever need the same function, move it into the hub (`Hook` enum, `hod_hub.cpp` table, `hod_overrides.cpp`) instead of adding a second definition.

The hub also owns the **collision lock** (`823C4C40` registration and `823C5098` traversal; enemies register shapes on several game threads) and the **collision crash guard** (`823C4EC8`), which used to live in Shield Rod.

### Runtime switches (`hod_mods.cpp`)

Each feature (`shield-rod`, `familiars`, `refectio`, `arma-custos`, `nathan`, `catacombs`) runs only when it is compiled in **and** switched on. The switch is decided once, at the first hooked call:

1. `hod_native_mods.txt` next to `harmonyrecomp.exe`, if it names the feature (`shield-rod = off`);
2. otherwise on exactly when the feature's DLC package is listed in `dlc_packages.txt` (removing a package also switches its code off);
3. with no `dlc_packages.txt` at all, on.

`HOD_NATIVE_MODS=shield-rod=off,nathan=on` overrides the file for a test. The log shows each decision (`[hod] native mod …`) and every chain (`[hod] 824476B8 owner draw: …`).

### Shared data

- `hod_guest.h`: entity handle lookup, the enemy hurt-record flag test, the attack-collider layout, the glyph launcher return address.
- `hurt_record_guest.h`: the enemy hurt boxes in guest memory (tag `HURT`), written from the familiars' shape observer (registered as core) and read by Nathan's module, which cannot link to the exe.
- `equip_card_icon.cpp`: during the equipment menus' icon-column draw, Alucard (familiars on) and Nathan (nathan on) get a card icon on the Enchanted row. The icon art is the hand-made `art/equip_slot/card_slot_icon_source.png`, packed into the menu sprite by `tools/equip_card_icon.py`.

## cmake/hodmods.cmake

Options `HODMOD_SHIELD_ROD`, `HODMOD_FAMILIARS`, `HODMOD_GLYPHS` (default ON), `HARMONYRECOMP_NATHAN` (ON) and `HARMONYRECOMP_POISONWORM` (OFF: the Catacombs test build). It adds the sources, include paths and module sources, and rewrites same-shard call sites to the dispatch table so overrides are not bypassed.

## recomp/

`harmonyrecomp-v0.6.0.patch` is the whole change to the stock recomp: the CMake hook and three small fixes. Apply it with `tools/setup_recomp.py`, which checks that each file is stock v0.6.0, backs up, and can `--restore`. For trees changed by the older in-place builds, use `--from-legacy`. `legacy-patches/` keeps the old in-place patches for reference.

## tools/

The shared Python tools. Every tool starts with a one-line bootstrap that finds the repo (the folder with `hodmods.json`) and imports `hodpaths`, so the tools run from anywhere. `hodpaths.py` documents how the game folder, the work folder and old `modding/…` paths are found.
