// Poison Worm soul (test builds only; CMake HARMONYRECOMP_POISONWORM): code inside
// the soul's own shot module, dllshotSoulCm050 (the 8-bit DLC's R. Zombie soul,
// dllshotSoulFCzombi, rebased to 0x85700000 by modding/tools/poison_worm_soul.py).
//
// The R. Zombie soul's update (vtable slot 9, 0x85711D38; f1 = frame time) already
// does the terrain natively:
//   +0x318 state: 0 start, 1 airborne (vy += 640 px/s^2 until the exe-written floor
//          push +0x234 says it is on a floor, then it snaps onto it), 2 walk
//          (vx = dir * 60 px/s, turns at the wall contacts +0x23C / +0x240, falls
//          again when the floor ends), 3-5 end and destroy.
//   +0x5C/+0x60 position, +0x64/+0x68 velocity (px/s), +0x324 direction (+-1).
// The worm only changes the motion: thrown up and forward on the first frame
// (state 0) instead of dropping, and a worm's crawl instead of a zombie's walk.
#include "../generated/dllshotsoulcm050/harmonyrecomp_init.h"
#include <rex/memory/utils.h>
#include <bit>
#include <cstdint>

REX_EXTERN(__imp__sub_85711D38);

namespace poison_worm_soul {
namespace {
constexpr float kThrowSpeedX = 90.0f;    // px/s forward
constexpr float kThrowSpeedY = 210.0f;   // px/s up (the module adds 640 px/s^2 gravity)
constexpr float kCrawlSpeed = 24.0f;     // px/s on the floor (R. Zombie walks at 60)
constexpr float kHandForward = 20.0f;    // the throw starts at Soma's hand, not his feet (user, 2026-11-20):
constexpr float kHandUp = 40.0f;         // px in front of / above the shot's spawn point, which is at his feet
// Lifetime: the template sets +0x32C = 3 + 0.25 * soul level (+0x204) seconds at cast
// (slot 4); +0x320 counts up by frame time and the worm fades once it passes the limit.
// User (2026-11-20): stay out a decent amount longer.
constexpr float kLifeBase = 8.0f;
constexpr float kLifePerLevel = 0.5f;

uint32_t Read(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
float Float(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Read(base, a)); }
void Float(uint8_t* base, uint32_t a, float v) { rex::memory::store_and_swap<uint32_t>(base + a, std::bit_cast<uint32_t>(v)); }
}  // namespace
}  // namespace poison_worm_soul

// Per-frame update (vtable slot 9).
REX_EXTERN(sub_85711D38) {
  using namespace poison_worm_soul;
  const uint32_t o = ctx.r3.u32;
  const uint32_t state = Read(base, o + 0x318);
  float dir = Float(base, o + 0x324);
  if (!(dir == 1.0f || dir == -1.0f)) dir = 1.0f;
  if (state == 0) {                                  // thrown from the hand, not dropped at the feet
    Float(base, o + 0x5C, Float(base, o + 0x5C) + dir * kHandForward);
    Float(base, o + 0x60, Float(base, o + 0x60) - kHandUp);
    Float(base, o + 0x64, dir * kThrowSpeedX);
    Float(base, o + 0x68, -kThrowSpeedY);
    const float level = static_cast<float>(base[o + 0x204]);
    Float(base, o + 0x32C, kLifeBase + kLifePerLevel * level);
  }
  __imp__sub_85711D38(ctx, base);
  if (Read(base, o + 0x318) == 2) Float(base, o + 0x64, Float(base, o + 0x324) * kCrawlSpeed);
}
