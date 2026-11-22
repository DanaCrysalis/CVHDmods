// Card icon for Alucard's and Nathan's Enchanted equipment row (core: shared
// by mods/familiars and mods/nathan; art from core/tools/equip_card_icon.py).
//
// The equipment menus draw their icon column through five small functions
// (823E6958, 823EA810, 823ED418, 823F46A8, 823F47C8). Each loops over the
// display slots (0 X, 1 Y, 2 RB, 3 Enchanted, 4 B, 5-7 Up/Right/Down+B,
// 8-14 armour) and asks 823E0410(slot, dim) for the sprite frame of
// data/opd/menu/p_ui_equip0.opd. Slot 3 is the Enchanted row: 823E0410
// answers frame 14 (65 dimmed), but the loop only draws it while a byte on
// the screen object is set, and every screen sets that byte to
// "current character == Soma" (game context 82223348 + 0xFC1) when it opens.
// Two other readers use the same byte to show a Soma-only widget, so it is
// not changed permanently.
//
// For Alucard (2) and Nathan (12), whose Enchanted row holds familiar or
// attribute cards, the byte is set only while the icon column draws, and
// slot 3 answers the card frames 180 / 181 that modding/tools/equip_card_icon.py
// adds to the sprite. Soma and everyone else are untouched.
#include "../generated/default/harmonyrecomp_init.h"
#include "hod_hooks.h"
#include <rex/memory/utils.h>
#include <cstdint>

REX_EXTERN(__imp__sub_823E0410);
REX_EXTERN(__imp__sub_823E6958);
REX_EXTERN(__imp__sub_823EA810);
REX_EXTERN(__imp__sub_823ED418);
REX_EXTERN(__imp__sub_823F46A8);
REX_EXTERN(__imp__sub_823F47C8);

namespace harmony::equip_card_icon {
namespace {
constexpr uint32_t kGameContext = 0x82223348;   // () -> game context
constexpr uint32_t kCharacterOffset = 0xFC1;    // byte: current character ID
constexpr uint32_t kEnchantedSlot = 3;
constexpr uint32_t kCardFrame = 180, kCardDimFrame = 181;

bool CardCharacter(PPCContext& ctx, uint8_t* base) {
  PPCContext call = ctx;
  rex::runtime::ResolveIndirectFunction(kGameContext)(call, base);
  const uint32_t game = call.r3.u32;
  if (!game) return false;
  const uint8_t id = base[game + kCharacterOffset];
  // Alucard's Enchanted row holds familiar cards (mods/familiars), Nathan's
  // holds attribute cards (mods/nathan); either mod switched off leaves its
  // character's menu native.
  return (id == 2 && hod::Enabled(hod::Mod::kFamiliars)) || (id == 12 && hod::Enabled(hod::Mod::kNathan));
}

// Draws one icon column with the screen's "Soma" byte set for card characters.
template <typename Draw>
void Column(PPCContext& ctx, uint8_t* base, uint32_t flag_offset, Draw draw) {
  const uint32_t screen = ctx.r3.u32;
  if (!screen || !CardCharacter(ctx, base)) { draw(ctx, base); return; }
  const uint8_t old = base[screen + flag_offset];
  base[screen + flag_offset] = 1;
  draw(ctx, base);
  base[screen + flag_offset] = old;
}
}  // namespace
}  // namespace harmony::equip_card_icon

using namespace harmony::equip_card_icon;

// (display slot, dim) -> icon frame of p_ui_equip0.
REX_EXTERN(sub_823E0410) {
  if (ctx.r3.u32 == kEnchantedSlot && CardCharacter(ctx, base)) {
    ctx.r3.u64 = ctx.r4.u32 ? kCardDimFrame : kCardFrame;
    return;
  }
  __imp__sub_823E0410(ctx, base);
}

REX_EXTERN(sub_823E6958) { Column(ctx, base, 216, __imp__sub_823E6958); }
REX_EXTERN(sub_823EA810) { Column(ctx, base, 456, __imp__sub_823EA810); }
REX_EXTERN(sub_823ED418) { Column(ctx, base, 216, __imp__sub_823ED418); }
REX_EXTERN(sub_823F46A8) { Column(ctx, base, 224, __imp__sub_823F46A8); }
REX_EXTERN(sub_823F47C8) { Column(ctx, base, 224, __imp__sub_823F47C8); }
