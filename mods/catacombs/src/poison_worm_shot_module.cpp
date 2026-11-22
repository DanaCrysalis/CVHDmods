// Small Poison Worm as an enemy shot (test builds only; CMake HARMONYRECOMP_POISONWORM):
// code inside its own shot module, dllshotCm050w = Legion's falling body
// (dllshotRegionHuman, category 11 ID 0x65) rebased to 0x85780000 with shot ID 0x4050,
// poison added and the worm's sprite (modding/tools/poison_worm_shot.py).
// The mass (DLL_Cm050) fires it through its shot request list (+0x1C8).
//
// Legion's body, from its code (template addresses + 0x01F00000 here):
//   slot 4 (0x85791AB8) setup: +0x324 state 0, +0x330 facing (1 = left, from the
//     request's +0x18), +0x328 speed factor 1.0, +0x32C speed = facing * 30 px/s,
//     +0x64 = +0x32C, sprites +0x258 (body, random animation 0x72/0x74/0x76) and
//     +0x268 (death, animation 0x71); sprite +0x30 = 2 when moving right, else 0.
//   slot 8 (0x85791D08): lifetime +0x31C += dt; past 300 s (state < 2) -> state 2.
//   slot 9 (0x85791D40) update, f1 = frame time:
//     state 0 airborne: vy += 588 px/s^2 up to 300 px/s (terrain callback slot 14
//       lands it: state 1); 1 on the floor: vx = +0x32C * +0x328; floor push
//       +0x234 == 0 -> falls again (state 0); 2 start dying (death sprite), 3 dying
//       spray, 4 destroy.
// The worm keeps all of that and changes: crawl speed (CotM 9.375 px/s), turning
// at walls (wall contacts +0x23C left / +0x240 right, as the R. Zombie soul's walk
// uses them), and a lifetime of kLife seconds (the mass counts its shots for that
// long toward its 12).
#include "../generated/dllshotcm050w/harmonyrecomp_init.h"
#include <rex/logging.h>
#include <rex/memory/utils.h>
#include <atomic>
#include <mutex>
#include <unordered_map>
#include <random>
#include <bit>
#include <cstdint>

REX_EXTERN(__imp__sub_85791AB8);
REX_EXTERN(__imp__sub_85791D40);

namespace poison_worm_shot {
namespace {
constexpr float kCrawl = 9.375f;     // px/s (CotM 0.15625 px/frame); the mass's crawl_speed
constexpr float kLife = 20.0f;       // s; the mass's shot_life
std::atomic<int> g_logged{0};

uint32_t Read(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
void Write(uint8_t* base, uint32_t a, uint32_t v) { rex::memory::store_and_swap<uint32_t>(base + a, v); }
float Float(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Read(base, a)); }
void Float(uint8_t* base, uint32_t a, float v) { Write(base, a, std::bit_cast<uint32_t>(v)); }

constexpr uint32_t kFallAnim = 0x70;  // poison_worm_art.SHOT_FALL_ANIM: the small worm's falling frames
constexpr uint32_t kCrawlAnim = 0x72; // crawl (every other slot of p_Cm050w.opd crawls too)
constexpr uint32_t kDeathAnim = 0x71; // poison_worm_art.SHOT_DEATH_ANIM: debris flicker
std::mutex g_lock;

// Worm-chunk debris (the mass's hits and death, CotM actor 0x08058D60): the mass
// marks the request's facing (+0x18 -> this object's +0x21C) 2 = left / 3 = right.
// A chunk flies up and out under gravity, shows a debris animation (frames 12-19,
// which carry no hitboxes in this sprite) and is removed (state 4) after its life.
constexpr uint32_t kDebrisAnims[] = {0x60, 0x61, 0x62, 0x63};   // poison_worm_art.SHOT_DEBRIS_ANIMS
constexpr float kDebrisGravity = 420.0f;
// CotM's explosion (poison_worm_art.SHOT_EXPLOSION_ANIM): 4+4+6+6+6+6 ticks, played once.
// Marker 4 = an explosion from the mass's death; a chunk turns into one when it ends
// (user, 2026-11-20: hits launch fake worms "that would explode shortly after").
constexpr uint32_t kExplosionAnim = 0x64;
constexpr float kExplosionTime = 32.0f / 60.0f;
struct Debris { float vx, vy, age, life; uint32_t anim; bool exploding; };
std::unordered_map<uint32_t, Debris> g_debris;
std::mt19937 g_rng{0x50574D32};
float Uniform(float lo, float hi) { return std::uniform_real_distribution<float>(lo, hi)(g_rng); }

// Drawing (log harmonyrecomp_043, 2026-11-20). The body sprite +0x258 is what shows
// at the shot's position; it is hidden at setup (+0x29 = 0) until the body lands.
// Vtable +0x2D0 does not change an animation: it appends a sprite layer (0x84 bytes)
// to the list at +0x264 (+0x268 begin, +0x26C end); the setup's layer (the first,
// "+0x268") draws at Legion's body offset. Legion changes an animation by writing
// the sprite's +0x00 and setting +0x1C (as the mass does with its own sprite).
// So the worm draws only on +0x258 and hides the layers.
void SetAnim(uint8_t* base, uint32_t sprite, uint32_t anim) {
  if (Read(base, sprite + 0x00) == anim) return;
  Write(base, sprite + 0x00, anim);
  base[sprite + 0x1C] = 1;
}

void Draw(uint8_t* base, uint32_t o, uint32_t anim) {
  if (const uint32_t s = Read(base, o + 0x258)) {
    base[s + 0x29] = 1;
    SetAnim(base, s, anim);
  }
  const uint32_t b = Read(base, o + 0x268), e = Read(base, o + 0x26C);
  if (b && e > b && e - b <= 8 * 0x84)
    for (uint32_t l = b; l < e; l += 0x84) base[l + 0x29] = 0;
}

void Face(uint8_t* base, uint32_t o, bool left) {
  base[o + 0x330] = left ? 1 : 0;
  if (const uint32_t s = Read(base, o + 0x258)) Write(base, s + 0x30, left ? 0 : 2);
}

int g_anim_logs = 0;
void LogDraw(uint8_t* base, uint32_t o, const char* what) {
  if (g_anim_logs++ >= 40) return;
  const uint32_t s = Read(base, o + 0x258);
  REXLOG_INFO("[pworm] shot {:08X} {}: sprite anim {:#x} visible {}", o, what, s ? Read(base, s + 0x00) : 0,
              s ? base[s + 0x29] : 0);
}
}  // namespace
}  // namespace poison_worm_shot

// Setup (slot 4): the worm's crawl speed instead of the body's walk.
REX_EXTERN(sub_85791AB8) {
  using namespace poison_worm_shot;
  const uint32_t o = ctx.r3.u32;
  __imp__sub_85791AB8(ctx, base);
  const uint32_t marker = Read(base, o + 0x21C);
  if (marker == 2 || marker == 3 || marker == 4) {
    const bool chunk_left = marker == 2;
    Debris d;
    {
      std::lock_guard lock(g_lock);
      if (marker == 4)
        d = Debris{0.0f, 0.0f, 0.0f, kExplosionTime, kExplosionAnim, true};
      else
        d = Debris{(chunk_left ? -1.0f : 1.0f) * Uniform(30.0f, 90.0f), -Uniform(90.0f, 180.0f), 0.0f,
                   Uniform(0.35f, 0.6f), kDebrisAnims[g_rng() % 4], false};
      g_debris[o] = d;
    }
    Face(base, o, chunk_left);
    Draw(base, o, d.anim);
    Float(base, o + 0x64, d.vx);
    Float(base, o + 0x68, d.vy);
    LogDraw(base, o, marker == 4 ? "explosion" : "debris chunk");
    return;
  }
  const bool left = base[o + 0x330] != 0;
  Float(base, o + 0x32C, left ? -kCrawl : kCrawl);
  Float(base, o + 0x64, Float(base, o + 0x32C) * Float(base, o + 0x328));
  Draw(base, o, kFallAnim);
  if (g_logged.fetch_add(1) < 24)
    REXLOG_INFO("[pworm] small-worm shot {:08X} at {:.0f},{:.0f} facing {} (marker {})", o, Float(base, o + 0x5C),
                Float(base, o + 0x60), left ? "left" : "right", marker);
}

// Per-frame update (slot 9): lifetime and wall turns around the body's own update.
REX_EXTERN(sub_85791D40) {
  using namespace poison_worm_shot;
  const uint32_t o = ctx.r3.u32;
  {
    std::unique_lock lock(g_lock);
    auto it = g_debris.find(o);
    if (it != g_debris.end()) {                          // a chunk: its own flight, not the body's states
      const float frame = float(ctx.f1.f64);
      const float dt = frame > 0 && frame < 1 ? frame : 1.0f / 60;
      Debris& d = it->second;
      d.age += dt;
      if (!d.exploding) d.vy += kDebrisGravity * dt;
      if (!d.exploding && d.age >= d.life) {             // the fake worm bursts
        d = Debris{0.0f, 0.0f, 0.0f, kExplosionTime, kExplosionAnim, true};
      }
      Float(base, o + 0x64, d.vx);
      Float(base, o + 0x68, d.vy);
      Draw(base, o, d.anim);
      if (d.age < d.life) return;
      g_debris.erase(it);
      lock.unlock();
      Write(base, o + 0x324, 4);                         // the body's update destroys it (vtable +0x158)
      __imp__sub_85791D40(ctx, base);
      return;
    }
  }
  const int32_t state = int32_t(Read(base, o + 0x324));
  if (state < 2 && Float(base, o + 0x31C) > kLife) Write(base, o + 0x324, 2);   // crawls off: dies with its spray
  __imp__sub_85791D40(ctx, base);
  const uint32_t now = Read(base, o + 0x324);
  Draw(base, o, now == 0 ? kFallAnim : now == 1 ? kCrawlAnim : kDeathAnim);
  {
    std::lock_guard lock(g_lock);
    static std::unordered_map<uint32_t, uint32_t> last;
    auto& prev = last[o];
    if (prev != now + 1) {
      if (now == 1 && prev == 1 && g_logged.fetch_add(1) < 48)
        REXLOG_INFO("[pworm] small-worm shot {:08X} landed at {:.0f},{:.0f} after {:.2f} s", o, Float(base, o + 0x5C),
                    Float(base, o + 0x60), Float(base, o + 0x31C));
      LogDraw(base, o, now == 0 ? "falls" : now == 1 ? "crawls" : "dies");
      prev = now + 1;
    }
    if (now >= 4) last.erase(o);
  }
  if (now == 1) {                                                               // on the floor
    const bool left = base[o + 0x330] != 0;
    if (Read(base, o + (left ? 0x23C : 0x240)) != 0) {
      Face(base, o, !left);
      Float(base, o + 0x32C, -Float(base, o + 0x32C));
      if (g_logged.fetch_add(1) < 24) REXLOG_INFO("[pworm] small-worm shot {:08X} turned at a wall", o);
    }
    Float(base, o + 0x64, Float(base, o + 0x32C) * Float(base, o + 0x328));
  }
}
