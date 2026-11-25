// Umbra (glyph 10, module dllshotGlyphUmbra at 0x85C00000): "darkness soul seeks enemies"
// (user, 2026-11-24). OoE art ram08: 0-3 the soul in flight (head at the origin, a long
// trail to the left; OoE animation 0), 4 the swirl it is summoned from. OoE gave these frames
// no boxes (its hit was code); shanoa_glyphs.json adds a head box to 0-3, so damage is the
// game's own (glyph power + INT, dark), every frame it touches, passing through.
//
// Movement: a port of OoE's own code (test 4, user asked for a code dive; Castlevania - Order
// of Ecclesia (USA) ARM9, names from DSVEdit's "OoE Functions.txt"):
//   SkillUmbraUse 02075AB0 casts; the soul is made by 0207588C, updated by 020755C0 and drawn
//   by 02075498 (a 16-point polygon ribbon). Fixed point 20.12 px, angles 0x10000 = 360 deg, 60 Hz.
//   * spawn: speed (+0x14) 0x3000 = 3.0 px/frame, heading (+0x64) 0 or 0x8000 by facing, aim
//     point (+0x2C0) = the nearest enemy (0206B63C), or 160 px ahead, then 128 px HIGHER.
//   * phase 0 (+0x0E = 0): speed x0.96 a frame; turn rate (+0x50) +0x10 a frame. When speed
//     drops below 0x800 (0.5): turn rate /16, phase 1, aim point = the nearest enemy now (no
//     offset; none: the 160 px-ahead point). It does not re-aim after that: it zooms to a point.
//   * phase 1: turn rate +0x10 a frame until above 0x555 (7.5 deg), then x0.98 a frame; speed
//     x1.08 a frame while under 0x5000 (5.0).
//   * every frame: heading turns toward the aim point by at most the turn rate (0203B488),
//     moves (0205CD30), a 64-entry position history is shifted, and the ribbon's 16 points are
//     every 4th history entry (so the trail covers the last 64 frames); it hits whatever it
//     touches (02032534) and keeps going. It is removed 24 frames after leaving the screen.
// HoD draws sprites, not polygon ribbons, so the ribbon is approximated by the soul sprite
// rotated along and stretched to the point 60 frames back: it bunches up as the soul brakes and
// stretches out as it zooms, which is the slinky look. HoD's screen is larger, so "left the
// screen" is: farther than kLeaveRange from Shanoa, or kMaxTicks.
//
// Targets: the enemy hurt boxes the exe shares in guest memory (NearestHurt). HoD's rotation
// turns counter-clockwise on screen (Cerberus's beam needed rotation = -atan2(dy, dx)).
#include "../generated/dllshotglyphumbra/harmonyrecomp_init.h"
#include "shanoa_glyph_shot.h"

REX_EXTERN(__imp__sub_85C11D38);
REX_EXTERN(__imp__sub_85C12038);

namespace umbra {
namespace {
using namespace shanoa_glyph;
using namespace shanoa_glyphs;
constexpr Glyph kGlyph{3, kUmbraIndex, "umbra", kUmbraBlank};
constexpr uint32_t kFlyAnim = 0, kSwirlAnim = kUmbraHeld + 4;
constexpr float kPi = cerberus_orb::kPi;
constexpr float kAngle = 2.0f * kPi / 65536.0f;          // one OoE angle unit in radians
// OoE's numbers
// Test 5 (user): "a bit faster than expected": OoE's speeds x kSpeedScale (turning unchanged).
constexpr float kSpeedScale = 0.7f;
constexpr float kStartSpeed = 3.0f * kSpeedScale, kBrake = 0.96f, kSlow = 0.5f * kSpeedScale;
constexpr float kAccel = 1.08f, kTopSpeed = 5.0f * kSpeedScale;
constexpr float kRateStep = 0x10 * kAngle, kRateTop = 0x555 * kAngle, kRateDecay = 0.98f;
constexpr float kAheadX = 160.0f, kRaise = 128.0f;
constexpr int kHistory = 64, kTrailBack = 60;
// HoD-side choices
constexpr int kSummonTicks = 6;                          // the swirl at her hand
constexpr int kMaxTicks = 360;
constexpr float kLeaveRange = 480.0f, kSeekRange = 400.0f;
constexpr float kHandForward = 16.0f;
constexpr float kArtTrail = 63.0f;                       // the art's trail length (frames 0-3: -63..0)
constexpr float kRotationSign = -1.0f;

struct Trail {
  float px[kHistory], py[kHistory];
  int count = 0;
  float tx = 0, ty = 0, ahead_x = 0, ahead_y = 0, speed = 0, rate = 0;
  bool zoom = false, rate_top = false;
};
std::mutex g_trail_lock;
std::unordered_map<uint32_t, Trail> g_trails;            // module object -> trail state

float Wrap(float a) {
  while (a > kPi) a -= 2 * kPi;
  while (a < -kPi) a += 2 * kPi;
  return a;
}

void Step(PPCContext&, uint8_t* base, const Glyph&, uint32_t o, Shot& s, Look& look, float) {
  look.rotation = 0;
  Trail tr;
  {
    std::lock_guard lock(g_trail_lock);
    auto it = g_trails.find(o);
    if (it != g_trails.end() && !(s.phase == 0 && s.t == 0)) tr = it->second;
  }
  if (s.phase == 0) {                                   // the swirl at her hand, then launch
    if (s.t == 0) {
      float cx, cy;
      if (OwnerCentre(base, s, cx, cy)) { s.x = cx + s.dir * kHandForward; s.y = cy; }
      s.heading = s.dir > 0 ? 0.0f : kPi;
      tr.speed = kStartSpeed;
      tr.ahead_x = s.x + s.dir * kAheadX; tr.ahead_y = s.y;
      const Enemy e = NearestHurt(base, s.x, s.y, kSeekRange);
      tr.tx = e.handle ? e.x : tr.ahead_x;
      tr.ty = (e.handle ? e.y : tr.ahead_y) - kRaise;    // first aim: 128 px above
      s.target = e.handle;
      if (g_logged.fetch_add(1) < 60)
        REXLOG_INFO("[umbra] {:08X} summoned at ({:.0f}, {:.0f}); first aim ({:.0f}, {:.0f}) from enemy {:08X}{}", o, s.x,
                    s.y, tr.tx, tr.ty, e.handle, HurtTable(base) ? "" : " (no hurt-box table yet)");
    }
    look.anim = kSwirlAnim;
    look.mirrored = s.dir < 0;
    if (s.t >= kSummonTicks) { s.phase = 1; s.t = -1; }
  } else {
    if (!tr.zoom) {                                     // OoE phase 0: brake and curl up
      tr.speed *= kBrake;
      if (tr.speed < kSlow) {
        tr.rate /= 16.0f;
        tr.zoom = true;
        const Enemy e = NearestHurt(base, s.x, s.y, kSeekRange);
        tr.tx = e.handle ? e.x : tr.ahead_x;
        tr.ty = e.handle ? e.y : tr.ahead_y;
        if (g_logged.fetch_add(1) < 60)
          REXLOG_INFO("[umbra] {:08X} zooms at ({:.0f}, {:.0f}) from ({:.0f}, {:.0f}), enemy {:08X}", o, tr.tx, tr.ty, s.x, s.y,
                      e.handle);
      }
      tr.rate += kRateStep;
    } else {                                            // OoE phase 1: zoom to the point
      if (!tr.rate_top) {
        tr.rate += kRateStep;
        if (tr.rate > kRateTop) tr.rate_top = true;
      } else {
        tr.rate *= kRateDecay;
      }
      if (tr.speed < kTopSpeed) tr.speed *= kAccel;
    }
    const float want = std::atan2(tr.ty - s.y, tr.tx - s.x);
    s.heading = Wrap(s.heading + std::clamp(Wrap(want - s.heading), -tr.rate, tr.rate));
    s.x += std::cos(s.heading) * tr.speed;
    s.y += std::sin(s.heading) * tr.speed;
    // History (newest first), as OoE shifts its 64 entries each frame.
    for (int i = std::min(tr.count, kHistory - 1); i > 0; --i) { tr.px[i] = tr.px[i - 1]; tr.py[i] = tr.py[i - 1]; }
    tr.px[0] = s.x; tr.py[0] = s.y;
    tr.count = std::min(tr.count + 1, kHistory);
    // The ribbon, as one sprite: along and out to the point kTrailBack frames back.
    const int back = std::min(tr.count - 1, kTrailBack);
    const float dx = s.x - tr.px[back], dy = s.y - tr.py[back];
    const float len = std::sqrt(dx * dx + dy * dy);
    const float along = len > 0.5f ? std::atan2(dy, dx) : s.heading;
    look.anim = kFlyAnim;
    look.rotation = kRotationSign * along;              // the art faces right: head first, trail behind
    // Test 5: the full stretch read oddly; a gentler version of it.
    look.stretch = std::clamp(0.7f + 0.3f * len / kArtTrail, 0.6f, 1.6f);
    if (Struck(base, o, s) && g_logged.fetch_add(1) < 60)
      REXLOG_INFO("[umbra] {:08X} hit at ({:.0f}, {:.0f})", o, s.x, s.y);
    float cx = s.x, cy = s.y;
    OwnerCentre(base, s, cx, cy);
    if (s.t >= kMaxTicks || std::hypot(s.x - cx, s.y - cy) > kLeaveRange) s.ended = true;
  }
  std::lock_guard lock(g_trail_lock);
  if (s.ended) g_trails.erase(o); else g_trails[o] = tr;
}
}  // namespace
}  // namespace umbra

REX_EXTERN(sub_85C11D38) { shanoa_glyph::Update(ctx, base, umbra::kGlyph, __imp__sub_85C11D38, umbra::Step); }
REX_EXTERN(sub_85C12038) { shanoa_glyph::EndRequest(ctx, base, __imp__sub_85C12038); }
