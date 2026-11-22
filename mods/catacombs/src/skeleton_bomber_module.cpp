// Skeleton Bomber (CotM enemy 7) inside its own enemy module, DLL_Cm007 (test builds only;
// CMake HARMONYRECOMP_POISONWORM). The module is the 8-bit DLC Bat (DLL_FCbat) rebased to
// 0x89400000 (modding/tools/skeleton_bomber.py), as the Poison Worm's is at 0x89380000, so
// every address here is the worm's + 0x80000. Behaviour from the user's own ROM
// (modding/research/skeleton_bomber/SKELETON_BOMBER_SPEC.md, code 0x0802BEF4-0x0802CC08).
//
// Module object (the Bat's): +0x9C/+0xA0 player position, +0xA4/+0xA8 own position,
// +0xAC/+0xB0 velocity px/s (the exe applies it), +0x2B8 sprite request (+0x00 animation,
// +0x1C apply, +0x10 speed, +0x30 facing: 2 = mirrored to face right; the art faces left),
// +0x44C0 Bat state, +0x44D2 hit, +0x44D3 dying, +0x1C8 shot request list. With the 8-bit
// Skeleton's terrain settings (GiveGravity, as the small Poison Worms) the exe keeps it on
// the floor, 8 px above it, and reports contacts: +0x258 floor, +0x260 / +0x264 walls.
//
// CotM (60 ticks per second):
//   walk  0.25 px/tick (animation 0). A turn timer (40 at spawn) counts down; at 0 it turns
//         and restarts at 30-40 ticks (it was heading toward the player while within 48 px,
//         or away while farther) or 10-15 (otherwise). A wall turns it, timer 30-40.
//   throw a throw timer (0 at spawn): at 0 it restarts at 150-210 ticks, and with the player
//         within 136 px across and 112 px up/down the bomber stops and throws (animation 1:
//         15 + 6 + 15 ticks); else the timer is quartered. The bomb leaves at the third
//         frame, 14 px ahead and 24 px up from the feet: across = (facing the player)
//         min(dx, 160) / 136 px/tick, else 0-1/16; up = 2 px/tick, plus
//         3 (min(dx, 160) + min(dy, 120)) / 496 when the player is above. Then it walks on in
//         a random direction.
//   bomb  gravity 0x16C1 / 65536 px/tick^2 (animation 0 of the shot sprite); it explodes when
//         it touches a floor, wall or ceiling (animation 1, 48 ticks, CotM's growing boxes,
//         fire); off for good after 6 s in the air.
//   death animation 2 (32 ticks: the bones scatter), then the Bat's own death (the game's
//         death effect).
#include "../generated/dll_cm007/harmonyrecomp_init.h"
#include <rex/logging.h>
#include <rex/memory/utils.h>
#include <algorithm>
#include <atomic>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <random>
#include <unordered_map>
#include <unordered_set>
#include <vector>

REX_EXTERN(__imp__sub_894117E0);
REX_EXTERN(__imp__sub_894113F0);
REX_EXTERN(__imp__sub_894115A0);
REX_EXTERN(__imp__sub_894117E8);

namespace skeleton_bomber {
namespace {
uint32_t Read(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
void Put(uint8_t* base, uint32_t a, uint32_t v) { rex::memory::store_and_swap<uint32_t>(base + a, v); }
float Float(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Read(base, a)); }
void Float(uint8_t* base, uint32_t a, float v) { Put(base, a, std::bit_cast<uint32_t>(v)); }

constexpr float kTick = 1.0f / 60.0f;
constexpr uint32_t kAllocPtr = 0x894314A4, kFreePtr = 0x894314A8;   // module globals the game sets
constexpr uint32_t kRequest = 0x3C;
constexpr uint32_t kShotCategory = 0xB, kShotId = 0x4007;          // dllshotCm007
constexpr uint32_t kRemove = 0xFFFFFFFF;
constexpr int kRows = 32;
constexpr uint32_t kFloorPush = 0x823C2D80, kCeilingPush = 0x823C29C8, kStageMap = 0x8291D918;
constexpr uint32_t kWallA = 0x823C2468, kWallB = 0x823C2720;          // shield_rod.cpp Wall()
constexpr uint32_t kFire = 0x4000010A;                              // attack attributes: fire (as 8-bit Fishman's fireball)
constexpr float kFeet = 8.0f;                                       // Bat-based walkers rest 8 px above the floor

// Body animations (skeleton_bomber_art.BODY_ANIM) and the shot's (SHOT_ANIM)
enum : uint16_t { kAnimWalk = 0, kAnimThrow = 1, kAnimDeath = 2 };
enum : uint32_t { kShotBomb = 0, kShotBlast = 1 };

// CotM numbers (per tick)
constexpr float kWalk = 0.25f;
constexpr int kThrowTicks = 15 + 6 + 15, kRelease = 15 + 6, kDeathTicks = 32, kBlastTicks = 48, kBombLife = 360;
constexpr float kGravity = float(0x16C1) / 65536.0f;

struct Bomb { int row; float x, y, vx, vy; int t; bool blast; };

struct Bomber {
  bool started = false, throwing = false, dying = false;
  int dir = -1, turn_t = 40, throw_t = 0, t = 0, stun = 0, death_t = 0;
  float acc = 0;
  uint16_t anim = 0xFFFF;
  std::vector<Bomb> bombs;
};

std::mutex g_lock;
std::unordered_map<uint32_t, Bomber> g_bombers;
std::unordered_set<uint32_t> g_unloaded;           // made by the factory, preload not queued yet
std::unordered_map<uint32_t, uint32_t> g_tables;   // bomber -> its puppet table (guest)
std::unordered_map<uint32_t, std::vector<bool>> g_used;
std::mt19937 g_rng{0x5B0B3E7u};
std::atomic<int> g_logged{0};

int Random(int n) { return std::uniform_int_distribution<int>(0, n - 1)(g_rng); }

uint32_t CallGuest(const PPCContext& caller, uint8_t* base, uint32_t fn, uint32_t r3, uint32_t r4 = 0) {
  PPCContext ctx = caller;
  ctx.r1.u32 = (caller.r1.u32 - 0x200) & ~15u;
  Put(base, ctx.r1.u32, caller.r1.u32);
  ctx.r3.u64 = r3; ctx.r4.u64 = r4;
  ctx.r5.u64 = 0; ctx.r6.u64 = 0;                  // the terrain queries take 4 arguments
  REX_CALL_INDIRECT_FUNC(fn);
  return ctx.r3.u32;
}
bool Solid(const PPCContext& ctx, uint8_t* base, uint32_t fn, float x, float y) {
  if (!Read(base, kStageMap) || !std::isfinite(x) || !std::isfinite(y)) return false;
  return CallGuest(ctx, base, fn, uint32_t(int32_t(std::floor(x))), uint32_t(int32_t(std::floor(y)))) != 0;
}
bool Terrain(const PPCContext& ctx, uint8_t* base, float x, float y) {
  return Solid(ctx, base, kFloorPush, x, y) || Solid(ctx, base, kCeilingPush, x, y) ||
         Solid(ctx, base, kWallA, x, y) || Solid(ctx, base, kWallB, x, y);
}

// ---- shot requests and the puppet table (as Cerberus's, cerberus_module.cpp) ------------
uint32_t NewRequest(const PPCContext& caller, uint8_t* base, uint32_t o) {
  const uint32_t v = o + 0x1C8;
  const uint32_t begin = Read(base, v + 4), end = Read(base, v + 8), cap = Read(base, v + 0xC);
  uint32_t at = 0;
  if (begin && end >= begin && cap >= end + kRequest) {
    at = end;
  } else {
    const uint32_t size = begin && end > begin ? (end - begin) / kRequest : 0;
    const uint32_t count = std::max<uint32_t>(8, size * 2);
    const uint32_t alloc = Read(base, kAllocPtr), release = Read(base, kFreePtr);
    if (!alloc) return 0;
    const uint32_t fresh = CallGuest(caller, base, alloc, count * kRequest);
    if (!fresh) return 0;
    if (size) std::memcpy(base + fresh, base + begin, size * kRequest);
    if (begin && release) CallGuest(caller, base, release, begin);
    Put(base, v + 4, fresh);
    Put(base, v + 0xC, fresh + count * kRequest);
    at = fresh + size * kRequest;
  }
  std::memset(base + at, 0, kRequest);
  Put(base, v + 8, at + kRequest);
  return at;
}

void RequestDefaults(uint8_t* base, uint32_t r) {    // as Legion fills its requests (0x8BF14968)
  Put(base, r + 0x10, kShotCategory);
  Put(base, r + 0x14, kShotId);
  Float(base, r + 0x24, 1.0f);
  Put(base, r + 0x28, 0x40000000);
  Float(base, r + 0x2C, 5.0f);
  base[r + 0x30] = 1;
  Float(base, r + 0x34, -1.0f);
  Put(base, r + 0x38, 0xFFFFFFFF);
}

uint32_t Row(uint32_t table, int row) { return table + 32 * row; }

void SetRow(uint8_t* base, uint32_t table, int row, float x, float y, uint32_t anim, bool mirrored) {
  const uint32_t r = Row(table, row);
  Float(base, r + 0, x);
  Float(base, r + 4, y);
  Put(base, r + 8, anim);
  Put(base, r + 12, mirrored ? 1 : 0);
  Float(base, r + 16, 0.0f);
  Float(base, r + 20, 1.0f);
  Float(base, r + 24, 1.0f);
}

// A new puppet shot on a free row; returns the row (-1 if none). Caller holds g_lock.
int Spawn(const PPCContext& ctx, uint8_t* base, uint32_t o, float x, float y, uint32_t anim) {
  uint32_t& table = g_tables[o];
  auto& used = g_used[o];
  if (!table) {
    const uint32_t alloc = Read(base, kAllocPtr);
    if (!alloc) return -1;
    const uint32_t raw = CallGuest(ctx, base, alloc, kRows * 32 + 0x100);
    if (!raw) return -1;
    table = (raw + 0xFF) & ~0xFFu;                     // row number in the low byte of the marker
    for (int k = 0; k < kRows; ++k) { std::memset(base + Row(table, k), 0, 32); Put(base, Row(table, k) + 8, kRemove); }
    used.assign(kRows, false);
  }
  int row = -1;
  for (int k = 0; k < kRows; ++k) if (!used[k]) { row = k; break; }
  if (row < 0) return -1;
  const uint32_t r = NewRequest(ctx, base, o);
  if (!r) return -1;
  used[row] = true;
  SetRow(base, table, row, x, y, anim, false);
  RequestDefaults(base, r);
  Float(base, r + 0x00, x);
  Float(base, r + 0x04, y);
  Put(base, r + 0x18, table | uint32_t(row));
  Put(base, r + 0x20, 0);
  Float(base, r + 0x24, Float(base, o + 0x1F0));     // the row's attack (vtable +0x260)
  Put(base, r + 0x28, kFire);
  Float(base, r + 0x2C, Float(base, o + 0x1E0));
  base[r + 0x30] = 0;                                 // registry path, as Legion
  Float(base, r + 0x34, 65.536f * 18.0f);
  const uint32_t owner = Read(base, o + 0x2C8);
  Put(base, r + 0x38, owner ? Read(base, owner + 0x18) : 0xFFFFFFFF);
  return row;
}

void Remove(uint8_t* base, uint32_t o, int row) {
  const uint32_t table = g_tables[o];
  if (!table || row < 0) return;
  Put(base, Row(table, row) + 8, kRemove);
  g_used[o][row] = false;                              // the shot reads the removal next frame
}

// ---- the bomber ---------------------------------------------------------------------------
void SetAnimation(uint8_t* base, uint32_t o, Bomber& b, uint16_t anim) {
  if (b.anim == anim) return;
  const uint32_t sprite = Read(base, o + 0x2B8);
  if (!sprite) return;
  b.anim = anim;
  Put(base, sprite + 0x00, anim);
  Float(base, sprite + 0x54, 0.0f);
  base[sprite + 0x2B] = 1;
  base[sprite + 0x28] = 0;
  base[sprite + 0x1C] = 1;
  Float(base, sprite + 0x10, 1.0f);
}

void SetFacing(uint8_t* base, uint32_t o, int dir) {
  if (const uint32_t sprite = Read(base, o + 0x2B8)) Put(base, sprite + 0x30, dir > 0 ? 2 : 0);
}

void Throw(const PPCContext& ctx, uint8_t* base, uint32_t o, Bomber& b) {
  const float x = Float(base, o + 0xA4), feet = Float(base, o + 0xA8) + kFeet;
  const float px = Float(base, o + 0x9C), py = Float(base, o + 0xA0);
  const float dx = std::min(std::fabs(px - x), 160.0f), dy = std::min(std::fabs(py - feet), 120.0f);
  const bool facing_player = (px - x) * float(b.dir) > 0;
  Bomb bomb{-1, x + 14.0f * float(b.dir), feet - 24.0f, 0, 0, 0, false};
  bomb.vx = float(b.dir) * (facing_player ? dx / 136.0f : float(Random(0x1001)) / 65536.0f);
  bomb.vy = -2.0f - (py < feet ? 3.0f * (dx + dy) / 496.0f : 0.0f);
  bomb.row = Spawn(ctx, base, o, bomb.x, bomb.y, kShotBomb);
  if (bomb.row >= 0) b.bombs.push_back(bomb);
  if (g_logged.fetch_add(1) < 60)
    REXLOG_INFO("[bomber] {:08X} throws from ({:.0f}, {:.0f}) v ({:.2f}, {:.2f}) at player ({:.0f}, {:.0f}): row {}", o, bomb.x,
                bomb.y, bomb.vx, bomb.vy, px, py, bomb.row);
}

void TickBombs(const PPCContext& ctx, uint8_t* base, uint32_t o, Bomber& b) {
  const uint32_t table = g_tables[o];
  for (Bomb& m : b.bombs) {
    ++m.t;
    if (m.blast) {
      if (m.t >= kBlastTicks) { Remove(base, o, m.row); m.row = -1; }
      continue;
    }
    m.x += m.vx; m.y += m.vy; m.vy += kGravity;
    const bool hit = Terrain(ctx, base, m.x, m.y + 3) || Terrain(ctx, base, m.x + (m.vx >= 0 ? 3.0f : -3.0f), m.y) ||
                     Terrain(ctx, base, m.x, m.y - 3);
    if (hit) {                                         // CotM: explode (sound 0x18A)
      m.blast = true; m.t = 0;
      SetRow(base, table, m.row, m.x, m.y, kShotBlast, false);
      continue;
    }
    if (m.t >= kBombLife) { Remove(base, o, m.row); m.row = -1; continue; }
    SetRow(base, table, m.row, m.x, m.y, kShotBomb, m.vx < 0);
  }
  std::erase_if(b.bombs, [](const Bomb& m) { return m.row < 0; });
}

void Tick(const PPCContext& ctx, uint8_t* base, uint32_t o, Bomber& b) {
  ++b.t;
  TickBombs(ctx, base, o, b);
  const float x = Float(base, o + 0xA4), feet = Float(base, o + 0xA8) + kFeet;
  const float px = Float(base, o + 0x9C), py = Float(base, o + 0xA0);
  if (b.stun > 0) { --b.stun; Float(base, o + 0xAC, 0.0f); return; }
  if (b.throwing) {                                    // 0x0802C40C / 0x0802C4C4
    Float(base, o + 0xAC, 0.0f);
    SetAnimation(base, o, b, kAnimThrow);
    if (++b.death_t == kRelease) Throw(ctx, base, o, b);   // death_t doubles as the throw clock
    if (b.death_t >= kThrowTicks) {
      b.throwing = false; b.death_t = 0;
      b.dir = Random(2) ? 1 : -1;                      // CotM: walks on either way
      SetAnimation(base, o, b, kAnimWalk);
    }
    SetFacing(base, o, b.dir);
    return;
  }
  // walk (0x0802C2B4)
  SetAnimation(base, o, b, kAnimWalk);
  if (--b.throw_t <= 0) {
    b.throw_t = Random(61) + 150;
    if (std::fabs(px - x) <= 136.0f && std::fabs(py - feet) <= 112.0f) {
      b.throwing = true; b.death_t = 0;
      // CotM keeps the walking direction, so a bomber walking away drops the bomb behind
      // it; user (2026-11-21): always throw toward the player, so it turns to face them.
      b.dir = px >= x ? 1 : -1;
      SetFacing(base, o, b.dir);
      Float(base, o + 0xAC, 0.0f);
      return;
    }
    b.throw_t /= 4;
  }
  const bool wall = (b.dir < 0 && Read(base, o + 0x260)) || (b.dir > 0 && Read(base, o + 0x264));
  if (wall) { b.dir = -b.dir; b.turn_t = Random(11) + 30; }
  if (--b.turn_t <= 0) {
    const bool far = std::fabs(px - x) > 48.0f;
    const bool toward = (px - x) * float(b.dir) > 0;
    b.turn_t = (toward ? !far : far) ? Random(11) + 30 : Random(6) + 10;   // 0x0802C396
    b.dir = -b.dir;
  }
  Float(base, o + 0xAC, float(b.dir) * kWalk * 60.0f);
  SetFacing(base, o, b.dir);
}

// The 8-bit Skeleton's gravity and floor collision (poison_worm_module.cpp GiveGravity).
void GiveGravity(uint8_t* base, uint32_t o) {
  base[o + 0x229] = 1;
  for (uint32_t k = 0x268; k <= 0x26B; ++k) base[o + k] = 1;
  Float(base, o + 0x23C, 12.0f);
  Float(base, o + 0x240, 0.0f);
  Float(base, o + 0x244, -34.0f);
  Float(base, o + 0x248, -8.0f);
  Float(base, o + 0x24C, -14.0f);
  Float(base, o + 0x250, 8.0f);
  Put(base, o + 0x44A0, 0x24012);
  Put(base, o + 0x44A4, 0);
  Float(base, o + 0x254, -14.0f);
  if (const uint32_t sprite = Read(base, o + 0x2B8)) base[sprite + 0x66] = 1;
}
}  // namespace
}  // namespace skeleton_bomber

// Factory (export 1): remember new objects; slot 1 queues their shot preload.
REX_EXTERN(sub_894113F0) {
  __imp__sub_894113F0(ctx, base);
  if (ctx.r3.u32) {
    std::lock_guard lock(skeleton_bomber::g_lock);
    skeleton_bomber::g_unloaded.insert(ctx.r3.u32);
  }
}

// Slot 1 (the Bat's shared empty function; only the first call after the factory counts).
REX_EXTERN(sub_894117E0) {
  using namespace skeleton_bomber;
  const uint32_t o = ctx.r3.u32;
  __imp__sub_894117E0(ctx, base);
  {
    std::lock_guard lock(g_lock);
    if (!g_unloaded.erase(o)) return;
  }
  if (const uint32_t r = NewRequest(ctx, base, o)) {
    RequestDefaults(base, r);
    REXLOG_INFO("[bomber] {:08X} preload request for shot ({}, {:#x})", o, kShotCategory, kShotId);
  }
}

// Spawn setup (slot 2): a floor walker.
REX_EXTERN(sub_894115A0) {
  using namespace skeleton_bomber;
  const uint32_t o = ctx.r3.u32;
  __imp__sub_894115A0(ctx, base);
  GiveGravity(base, o);
  std::lock_guard lock(g_lock);
  g_bombers[o] = Bomber{};
  g_tables.erase(o);
  g_used.erase(o);
}

// Per-frame update (slot 7).
REX_EXTERN(sub_894117E8) {
  using namespace skeleton_bomber;
  const uint32_t o = ctx.r3.u32;
  const float frame = float(ctx.f1.f64);
  const float dt = frame > 0 && frame < 1 ? frame : kTick;
  const bool dying = base[o + 0x44D3] != 0;
  std::unique_lock lock(g_lock);
  auto& b = g_bombers[o];
  if (base[o + 0x44D2] && !dying) {                   // a hit: CotM's short stun, not the Bat's flight
    base[o + 0x44D2] = 0;
    b.stun = 12;
  }
  if (dying) {                                         // CotM death: the bones scatter, then the Bat's death
    if (!b.dying) {
      b.dying = true; b.death_t = 0;
      base[o + 0x229] = 0;
      Float(base, o + 0xAC, 0.0f);
      Float(base, o + 0xB0, 0.0f);
      SetAnimation(base, o, b, kAnimDeath);
    }
    b.acc += dt;
    while (b.acc >= kTick) { b.acc -= kTick; ++b.death_t; TickBombs(ctx, base, o, b); }
    if (b.death_t < kDeathTicks) {
      const uint32_t sprite = Read(base, o + 0x2B8);
      if (sprite) std::memcpy(base + sprite + 0xC4, base + sprite + 0x40, 8);
      return;
    }
    for (Bomb& m : b.bombs) if (!m.blast) Remove(base, o, m.row);   // bombs in the air go with it
    g_bombers.erase(o);
    lock.unlock();
    __imp__sub_894117E8(ctx, base);
    return;
  }
  if (Read(base, o + 0x44C0) != 0) {                   // any other Bat state: its own code
    lock.unlock();
    __imp__sub_894117E8(ctx, base);
    return;
  }
  if (!b.started) {
    b.started = true;
    b.dir = Float(base, o + 0x9C) >= Float(base, o + 0xA4) ? 1 : -1;
    if (g_logged.fetch_add(1) < 60)
      REXLOG_INFO("[bomber] {:08X} starts at ({:.0f}, {:.0f})", o, Float(base, o + 0xA4), Float(base, o + 0xA8));
  }
  b.acc = std::min(b.acc + dt, 4 * kTick);
  while (b.acc >= kTick) { b.acc -= kTick; Tick(ctx, base, o, b); }
  // the exe keeps it on the floor (gravity from the 8-bit Skeleton's settings)
  if (!Read(base, o + 0x258)) Float(base, o + 0xB0, std::min(Float(base, o + 0xB0) + 600.0f * dt, 300.0f));
  else Float(base, o + 0xB0, 0.0f);
  const uint32_t sprite = Read(base, o + 0x2B8);       // as the Bat's update ends
  if (sprite) std::memcpy(base + sprite + 0xC4, base + sprite + 0x40, 8);
}
