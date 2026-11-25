// Arcus (weapon 161, module dllshotGlyphArcus at 0x85A80000): "bow firing forward" (user,
// 2026-11-24). OoE art rap03: frame 0 the arrow (OoE hitbox -7,-4 16x8), 1-11 the bow
// drawing and loosing, 12-16 the sparkle it appears with; OoE animation 0 plays sparkle ->
// draw -> release (64 ticks).
//
// The weapon attack (the cast) is the bow: it plays animation 0 where her hand was at the attack
// and stays there (user, test 4); its frames have no boxes, so it deals no damage. At kReleaseTick it looses the
// arrow, a second shot of this module (child role 1) from the skill factory, owned by her, so
// the arrow hits as her weapon attack (ATK from the WEPN row, scaled by glyph mastery, + STR).
// The arrow flies straight ahead and ends on its first enemy, a wall, or after kArrowTicks.
// The bow draws above her (sprite depth, shanoa_glyph_shot.h Look::depth; test 2: it was under her).
// Tuning (first pass, my numbers): release tick, arrow speed and range, hand offset.
#include "../generated/dllshotglypharcus/harmonyrecomp_init.h"
#include "shanoa_glyph_shot.h"

REX_EXTERN(__imp__sub_85A91D38);
REX_EXTERN(__imp__sub_85A92038);

namespace arcus {
namespace {
using namespace shanoa_glyph;
using namespace shanoa_glyphs;
constexpr Glyph kGlyph{10, kArcusIndex, "arcus", kArcusBlank};
constexpr uint32_t kBowAnim = 0;                       // OoE animation 0
constexpr uint32_t kArrowAnim = kArcusHeld + 0;        // frame 0 held
constexpr int kReleaseTick = 53;                       // OoE animation 0 reaches frame 10 (string released) at tick 53
constexpr int kBowTicks = 64;                          // the whole animation (test 3: cut at 48 the bow never finished)
constexpr int kArrowTicks = 60;
constexpr float kArrowSpeed = 10.0f;                   // px per tick: 600 px in kArrowTicks
constexpr float kHandForward = 24.0f, kHandDown = 0.0f; // from her body centre (test 2: 12 sat on top of her)

// The fired arrow starts where the bow's nocked arrow is drawn: frame 9 draws the arrow's own
// texture block (frame 0's) at x -19 instead of -14, so 5 px back, same height.
constexpr float kNockBack = 5.0f;
constexpr int kSpawnTick = 1;                          // the arrow is made early, hidden, and waits on the bow

void Step(PPCContext& ctx, uint8_t* base, const Glyph& g, uint32_t o, Shot& s, Look& look, float) {
  if (s.role == 0) {                                   // the bow
    // Test 4 (user): the bow stays where she attacked (placed once, at her hand then).
    float cx, cy;
    if (s.t == 0 && OwnerCentre(base, s, cx, cy)) {
      s.dir = OwnerDir(base, s, s.dir);
      s.x = cx + s.dir * kHandForward;
      s.y = cy + kHandDown;
    }
    look.anim = kBowAnim;
    look.mirrored = s.dir < 0;                         // the art faces right
    // Test 6: a child shot starts where the game makes it and needs frames to reach its spot, so
    // the arrow rose into place visibly. It is made at the start, hidden, settles on the bow, and
    // is shown and loosed at the release frame.
    if (s.t == kSpawnTick) {
      Shot arrow;
      arrow.role = 1; arrow.dir = s.dir;
      arrow.x = s.x - s.dir * kNockBack; arrow.y = s.y;
      arrow.aux = kReleaseTick - kSpawnTick;           // ticks to wait
      Spawn(ctx, base, g, s, arrow);
    }
    if (s.t >= kBowTicks) s.ended = true;
    return;
  }
  // the arrow
  look.mirrored = s.dir < 0;
  if (s.t < s.aux) {                                   // waiting on the bow, hidden and harmless
    look.anim = kArcusBlank;
    look.visible = false;
    return;
  }
  look.anim = kArrowAnim;
  if (s.t > s.aux && Struck(base, o, s)) {
    REXLOG_INFO("[arcus] arrow {:08X} hit at ({:.0f}, {:.0f})", o, s.x, s.y);
    s.ended = true;
    return;
  }
  if (s.t == s.aux) Struck(base, o, s);                // start counting contacts from the release
  s.x += s.dir * kArrowSpeed;
  if (Terrain(ctx, base, s.x + s.dir * 8.0f, s.y) || s.t >= s.aux + kArrowTicks) s.ended = true;
}
}  // namespace
}  // namespace arcus

REX_EXTERN(sub_85A91D38) { shanoa_glyph::Update(ctx, base, arcus::kGlyph, __imp__sub_85A91D38, arcus::Step); }
REX_EXTERN(sub_85A92038) { shanoa_glyph::EndRequest(ctx, base, __imp__sub_85A92038); }
