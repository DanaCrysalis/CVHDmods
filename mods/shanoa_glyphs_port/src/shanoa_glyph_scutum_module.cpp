// Scutum (weapon 163, module dllshotGlyphScutum at 0x85B80000): "shield raised overhead",
// held out like Alucard's shields (user, 2026-11-24). OoE art rap09: frame 0 the shield
// edge-on above her head, already placed in OoE's own coordinates (y -61..-37 from her
// feet); 1 and 2 other poses.
//
// The weapon attack raises the shield over her head, following her body (it drops when she
// crouches), for as long as THAT weapon slot's button stays held (at least kMinTicks). It deals
// no damage (user): ATK 0 and its sprite boxes are stripped (shanoa_glyphs.json "hitboxes": false).
// No guard stance and no lock-out: she can attack with her other slot while it is up (user).
//
// A guard to the game (user, 2026-11-24: "it should be, like an Alucard shield"):
//   * blocking: the shield's box is a native guard rectangle each frame (engine RegisterGuard,
//     8244B558): enemy shots that touch it are guarded and break with their own animation and
//     clang, as on Alucard's shields;
//   * the guard slot: while it is up, her owner +0xA64 holds Scutum's weapon slot, as HoD's own
//     guard start (82450658) sets it for a held shield; HoD sends it to the other players in its
//     per-player snapshot (PAMA +0x47, builder 82461F50 / receiver 824626F0). The owner's machine
//     keeps it set through a holder entry the exe re-applies after 82450658 each frame
//     (shanoa_glyph_guest.h, shanoa_glyph_bridge.cpp); other machines keep their copy of the
//     shield up while the received slot says so. Guard status 11 (the stance) is never set.
#include "../generated/dllshotglyphscutum/harmonyrecomp_init.h"
#include "shanoa_glyph_shot.h"

REX_EXTERN(__imp__sub_85B91D38);
REX_EXTERN(__imp__sub_85B92038);

namespace scutum {
namespace {
using namespace shanoa_glyph;
using namespace shanoa_glyphs;
constexpr Glyph kGlyph{10, kScutumIndex, "scutum", kScutumBlank};
constexpr uint32_t kOverheadAnim = kScutumHeld + 0;
constexpr int kMinTicks = 12, kMaxTicks = 60 * 60;
constexpr float kArtX0 = -16, kArtX1 = 16, kArtY0 = -12, kArtY1 = 12;    // frame 0 around the shot (after the shift)
constexpr float kBlockPad = 2;
constexpr float kForward = 5.0f, kAbove = 34.0f;   // from her body centre (test 6: a bit forward and down)
constexpr uint32_t kSlotButton[2] = {0x20, 0x40};  // held-button bits of weapon slots 0 / 1 (shield_rod.cpp)
constexpr uint32_t kEquipment = 0x9C8, kControl = 0x930;   // owner: equipment list, control type (1 = this machine)

// Which weapon slot holds Scutum (-1: neither); with both, the one whose button is held.
int32_t ScutumSlot(uint8_t* base, uint32_t owner, uint32_t held) {
  const uint32_t equipment = Read(base, owner + kEquipment);
  if (!equipment) return -1;
  int32_t found = -1;
  for (int32_t k = 0; k < 2; ++k)
    if (Read(base, equipment + 4 * k) == kScutumItem && (found < 0 || (held & kSlotButton[k]))) found = k;
  return found;
}
uint32_t HolderTable(uint8_t* base) {
  static std::atomic<uint32_t> table{0};
  uint32_t t = table;
  if (!harmony::shanoa_guest::ScutumValid(base, t)) {
    t = harmony::shanoa_guest::Published(harmony::shanoa_guest::kScutumVar);
    if (!harmony::shanoa_guest::ScutumValid(base, t)) return 0;
    table = t;
  }
  return t;
}

void Step(PPCContext& ctx, uint8_t* base, const Glyph&, uint32_t o, Shot& s, Look& look, float) {
  float cx, cy;
  if (OwnerCentre(base, s, cx, cy)) {
    s.dir = OwnerDir(base, s, s.dir);
    s.x = cx + s.dir * kForward;
    s.y = cy - kAbove;
  }
  look.anim = kOverheadAnim;
  look.mirrored = s.dir < 0;
  const bool guarding = RegisterGuard(ctx, base, s, s.x + kArtX0 - kBlockPad, s.y + kArtY0 - kBlockPad,
                                      s.x + kArtX1 + kBlockPad, s.y + kArtY1 + kBlockPad);
  const uint32_t owner = OwnerObject(base, s);
  if (!IsPlayer(base, owner)) { s.ended = true; return; }
  const bool local = Read(base, owner + kControl) == 1;
  bool held = false;
  const uint32_t player = Read(base, owner + 0x924);
  const uint32_t input = player ? Read(base, player + 0x2C0) : 0;
  const uint32_t buttons = local && input ? Read(base, input) : 0;
  const int32_t slot = ScutumSlot(base, owner, buttons);
  bool up;
  if (local) {
    up = slot >= 0 && (buttons & kSlotButton[slot]) != 0;
    const uint32_t table = HolderTable(base);
    if (up || s.t < kMinTicks) {
      if (slot >= 0) {
        Write(base, owner + harmony::shanoa_guest::kGuardSlot, uint32_t(slot));
        if (table) harmony::shanoa_guest::ScutumPut(base, table, owner, slot);
      }
    }
    held = up;
  } else {
    // Another player's shield: up while their guard slot (from the snapshot) says so.
    const int32_t sent = int32_t(Read(base, owner + harmony::shanoa_guest::kGuardSlot));
    held = sent >= 0 && sent == slot;
  }
  if (s.t == 1)
    REXLOG_INFO("[scutum] {:08X} up ({} player, slot {}), guard rectangle {}", o, local ? "this machine's" : "another",
                slot, guarding ? "registered" : "NOT registered");
  if (s.t >= kMaxTicks || (s.t >= kMinTicks && !held)) {
    if (local) {
      if (const uint32_t table = HolderTable(base)) harmony::shanoa_guest::ScutumRemove(base, table, owner);
      Write(base, owner + harmony::shanoa_guest::kGuardSlot, 0xFFFFFFFFu);
    }
    REXLOG_INFO("[scutum] {:08X} lowered after {} ticks ({})", o, s.t,
                local ? "button released" : "the other player's guard slot cleared");
    s.ended = true;
  }
}
}  // namespace
}  // namespace scutum

REX_EXTERN(sub_85B91D38) { shanoa_glyph::Update(ctx, base, scutum::kGlyph, __imp__sub_85B91D38, scutum::Step); }
REX_EXTERN(sub_85B92038) { shanoa_glyph::EndRequest(ctx, base, __imp__sub_85B92038); }
