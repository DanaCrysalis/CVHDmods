// Ascia (weapon 162, module dllshotGlyphAscia at 0x85B00000): "axe tossed in an arc" (user,
// 2026-11-24). OoE art rap04: frame 0 the hand axe (OoE hitbox -11,-13 24x24; frames 1/2
// are Vol Ascia's axe and a hammer, unused). OoE turns the one frame in code, so it spins here
// through the sprite request's rotation (radians).
//
// Thrown from her hand up and forward, it falls under gravity, spinning, and passes through
// enemies (each is struck by the game's own per-attacker hit limit) and walls, as the classic
// axe does, until terrain (below); it ends after kAxeTicks. Damage: her weapon attack (WEPN ATK scaled by glyph
// mastery + STR).
#include "../generated/dllshotglyphascia/harmonyrecomp_init.h"
#include "shanoa_glyph_shot.h"

REX_EXTERN(__imp__sub_85B11D38);
REX_EXTERN(__imp__sub_85B12038);

namespace ascia {
namespace {
using namespace shanoa_glyph;
using namespace shanoa_glyphs;
constexpr Glyph kGlyph{10, kAsciaIndex, "ascia", kAsciaBlank};
constexpr uint32_t kAxeAnim = kAsciaHeld + 0;
// The arc as OoE throws it (user's reference youtu.be/z22A8rHZc8I at 2:42, measured from the
// frames: ~70 px above the hand after 27 ticks, ~83 px at 45, ~30 px forward by then): a high,
// narrow lob. Test 2 (3.2 / 7.5 / 0.32) was far too wide.
constexpr float kThrowX = 0.75f, kThrowY = -3.7f;       // px per tick
constexpr float kGravity = 0.083f;                      // px per tick^2: apex ~82 px up at ~45 ticks, ~34 px ahead
constexpr float kSpin = 0.25f;                          // radians per tick
constexpr int kAxeTicks = 160;                          // back at hand height at ~90 ticks, then falls on
constexpr float kHandForward = 8.0f, kHandUp = 8.0f;
// Terrain (user, tests 6/7; HoD's Axe subweapon in axe_subweapon.mp4): any contact clangs and
// sparks, and the axe fades out, harmless: off a ceiling it drops, off a wall it falls back a
// little, off the floor it hops. (Test 7: the throw setup ran again when the fade restarted its
// timer, so the axe jumped back to Shanoa; it now runs once.)
constexpr float kCeilingDrop = 0.3f, kFloorHop = -1.6f, kSlide = 0.5f, kWallBack = -0.3f;
constexpr int kFadeTicks = 20, kSparkTicks = 8;
constexpr uint32_t kClangCue = 48;                      // SE_HIT_N_AVOID (the "no damage" tink); to tune
constexpr uint32_t kSparkAnim = kAsciaSpark;            // OoE raw16 animation 0, merged into the sprite

void Impact(PPCContext& ctx, uint8_t* base, const Glyph& g, const Shot& s, float x, float y) {
  PlayCue(ctx, base, kClangCue, x, y);
  Shot spark;
  spark.role = 2; spark.dir = s.dir; spark.x = x; spark.y = y;
  Spawn(ctx, base, g, s, spark);
}

void Step(PPCContext& ctx, uint8_t* base, const Glyph& g, uint32_t o, Shot& s, Look& look, float) {
  look.visible = true;
  look.mirrored = s.dir < 0;
  if (s.role == 2) {                                    // the impact spark
    // Hidden until it has reached the contact point (a new shot starts where the game makes it).
    const float gx = Float(base, o + 0x5C) - s.x, gy = Float(base, o + 0x60) - s.y;
    if (s.phase == 0) {
      look.anim = kAsciaBlank;
      look.visible = false;
      if (gx * gx + gy * gy < 4.0f || s.t >= 8) { s.phase = 1; s.t = -1; }
      return;
    }
    look.anim = kSparkAnim;
    if (s.t >= kSparkTicks) s.ended = true;
    return;
  }
  if (!s.aux) {                                          // the throw, once
    s.aux = 1;
    float cx, cy;
    if (OwnerCentre(base, s, cx, cy)) { s.x = cx + s.dir * kHandForward; s.y = cy - kHandUp; }
    s.vx = s.dir * kThrowX;
    s.vy = kThrowY;
  }
  if (s.phase == 1) {                                   // hopped off the floor, fading (no hits)
    if (!Terrain(ctx, base, s.x + s.vx, s.y)) s.x += s.vx; else s.vx = 0;
    if (!Terrain(ctx, base, s.x, s.y + s.vy)) s.y += s.vy; else s.vy = 0;
    s.vy += kGravity * 2;
    s.rot += s.dir * kSpin * 0.5f;
    look.anim = kAsciaGhost + 0;                         // frame 0 without its box
    look.rotation = s.rot;
    look.visible = (s.t / 2) % 2 == 0;                   // flickers out
    if (s.t >= kFadeTicks) s.ended = true;
    return;
  }
  const float nx = s.x + s.vx, ny = s.y + s.vy;
  if (s.t > 2) {
    const bool side = Terrain(ctx, base, nx, s.y), vertical = Terrain(ctx, base, s.x, ny);
    if (side || vertical || Terrain(ctx, base, nx, ny)) {
      if (vertical && s.vy > 0) {                       // floor: hop
        Impact(ctx, base, g, s, s.x, s.y + 8.0f);
        s.vy = kFloorHop; s.vx *= kSlide;
      } else if (vertical) {                            // ceiling: drop
        Impact(ctx, base, g, s, s.x, s.y - 8.0f);
        s.vy = kCeilingDrop; s.vx *= kSlide;
      } else {                                          // wall: fall back a little
        Impact(ctx, base, g, s, s.x + (s.vx > 0 ? 8.0f : -8.0f), s.y);
        s.vx *= kWallBack; s.vy = std::max(s.vy, 0.0f);
      }
      s.phase = 1; s.t = -1;                            // clang, then fade
      look.anim = kAsciaGhost + 0; look.rotation = s.rot;
      return;
    }
  }
  s.x += s.vx;
  s.y += s.vy;
  s.vy += kGravity;
  s.rot += s.dir * kSpin;
  look.anim = kAxeAnim;
  look.rotation = s.rot;
  if (s.t >= kAxeTicks) s.ended = true;
}
}  // namespace
}  // namespace ascia

REX_EXTERN(sub_85B11D38) { shanoa_glyph::Update(ctx, base, ascia::kGlyph, __imp__sub_85B11D38, ascia::Step); }
REX_EXTERN(sub_85B12038) { shanoa_glyph::EndRequest(ctx, base, __imp__sub_85B12038); }
