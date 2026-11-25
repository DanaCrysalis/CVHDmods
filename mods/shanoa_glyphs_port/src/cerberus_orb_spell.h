// Cerberus's lightning orb as a player spell: Soma's Cerberus soul (dllshotSoulCm068) and
// Charlotte's Lightning Orb (dllshotLearnCm068). Test builds only (CMake
// HARMONYRECOMP_POISONWORM); modding/tools/cerberus_soul.py makes both modules from the
// 8-bit DLC's R. Zombie soul (dllshotSoulFCzombi), whose class code they keep.
//
// Design (user, 2026-11-21): cast, the orb floats quickly up to a set height (stopping lower
// under a ceiling) and rains piercing lightning bolts down, as Cerberus's attack does
// (cerberus_module.cpp TickOrb / TickBolts).
//
// The cast shot becomes the orb. Every bolt piece is another shot of the same module from
// the skill factory 82487EF8 (as Soma's own cast 824501D0: kind, ID, owner handle, &x/y,
// facing, 0, level, 0), owned by the caster (shot +0xA4, the owner handle the shot init
// 82481D60 stores), so each piece hits as the caster's attack. While the orb or a piece is
// alive this code drives it and the template's update never runs (so a hit never ends it:
// the bolts pierce); at the end its lifetime is pushed past its limit and the template's
// update ends and destroys it (R. Zombie soul: +0x320 timer, +0x32C limit, +0x318 state).
//
// Two objects make a shot: the exe's wrapper (0x1CC bytes, 8248DB90: +0x04 handle, +0xA4
// owner handle, +0x118 learnable item, +0x180 the module object) and the module object this
// code runs on (r3 of its vtable; +0x298 = the wrapper's handle, set through slot 305).
// Module object fields (all shot modules share the base class): +0x5C/+0x60 position,
// +0x64/+0x68 velocity px/s (the exe moves the shot), +0x204 level,
// +0x258 sprite request (+0x00 animation, +0x1C apply, +0x10 speed, +0x29 shown, +0x30
// mirrored, +0x38/+0x3C scale, +0x50 rotation), +0x268/+0x26C extra layers, +0x324
// direction (+-1.0, R. Zombie soul).
#pragma once
#include <rex/logging.h>
#include <rex/memory/utils.h>
#include <algorithm>
#include <atomic>
#include <bit>
#include <cmath>
#include <cstdint>
#include <mutex>
#include <random>
#include <unordered_map>

namespace cerberus_orb {
namespace {
uint32_t Read(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
void Write(uint8_t* base, uint32_t a, uint32_t v) { rex::memory::store_and_swap<uint32_t>(base + a, v); }
float Float(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Read(base, a)); }
void Float(uint8_t* base, uint32_t a, float v) { Write(base, a, std::bit_cast<uint32_t>(v)); }

constexpr uint32_t kHandleTable = 0x8291D9F0;   // [ ]+172: 16-byte entries {handle, object}, by handle & 0xFFFF
constexpr uint32_t kSkillFactory = 0x82487EF8;
constexpr uint32_t kFloorPush = 0x823C2D80, kCeilingPush = 0x823C29C8, kStageMap = 0x8291D918;
constexpr float kPi = 3.14159265f;

// Cerberus's shot sprite (cerberus_art.SHOT_ANIM)
enum Anim : uint32_t { kSmall = 0, kSmallFade = 6, kFlare = 13, kBolt = 16, kBlank = 25 };

// Tuning (ticks at 60 per second, px)
constexpr float kHandForward = 16.0f, kHandUp = 40.0f;   // the cast starts at the hand, not the feet
constexpr float kRiseSpeed = 6.0f;                       // "floats quickly up"
constexpr float kRiseHeight = 112.0f;                    // the set height above the hand
constexpr float kCeilingGap = 12.0f;                     // stops this far under a ceiling
constexpr int kSwellTicks = 5;
constexpr int kRainBase = 90, kRainPerLevel = 10;        // raining time: 1.5 s + 1/6 s per level
constexpr int kBoltEvery = 12;                           // a column every 12 ticks (CotM's orb)
constexpr float kDrift = 0.6f;                           // sway: px per tick, turning every 40 ticks
constexpr int kDriftTurn = 40;
constexpr int kFadeTicks = 24;
constexpr float kPieceStep = 32.0f;                      // bolt pieces 32 px apart (CotM 0x17E)
constexpr int kPieceTicks = 12, kMaxPieces = 12;         // a piece shows 4 frames x 3 ticks; columns to 384 px
constexpr int kForgetTicks = 600;                        // ended shots are forgotten after this

struct Shot {
  uint32_t handle = 0;
  bool bolt = false, ended = false;
  uint32_t row = 0;                    // an enemy's shot: Cerberus's puppet row (see EnemyRow)
  int phase = 0, t = 0, end_t = 0, wave = 0, bolt_n = 0, rain = kRainBase, gen = 0, level = 0;
  float x = 0, y = 0, risen = 0, base_y = 0, vx = kDrift, dir = 1;
  int order[4] = {0, 1, 2, 3};
};

struct Pending { bool active = false; Shot shot; };

std::mutex g_lock;
std::unordered_map<uint32_t, Shot> g_shots;   // object -> state (handle checked: objects are reused)
Pending g_pending;                             // a piece being made by the factory right now
std::unordered_map<uint32_t, int> g_unlinked;  // frames a shot has run without its wrapper link
std::atomic<int> g_logged{0};
std::mt19937 g_rng{0xCE5BE105u};

uint32_t Guest(const PPCContext& caller, uint8_t* base, uint32_t fn, uint32_t r3, uint32_t r4) {
  PPCContext ctx = caller;
  ctx.r1.u32 = (caller.r1.u32 - 0x200) & ~15u;
  Write(base, ctx.r1.u32, caller.r1.u32);
  ctx.r3.u64 = r3; ctx.r4.u64 = r4;
  ctx.r5.u64 = 0; ctx.r6.u64 = 0;     // the terrain queries take 4 arguments (shield_rod.cpp Call4):
  REX_CALL_INDIRECT_FUNC(fn);         // leftover r5/r6 crashed 823C29C8 -> 823C2720 (2026-11-21)
  return ctx.r3.u32;
}
bool Solid(const PPCContext& ctx, uint8_t* base, uint32_t fn, float x, float y) {
  if (!Read(base, kStageMap) || !std::isfinite(x) || !std::isfinite(y)) return false;
  return Guest(ctx, base, fn, uint32_t(int32_t(std::floor(x))), uint32_t(int32_t(std::floor(y)))) != 0;
}

uint32_t ObjectOf(uint8_t* base, uint32_t handle) {
  const uint32_t manager = Read(base, kHandleTable);
  if (!manager || !handle) return 0;
  const uint32_t table = Read(base, manager + 172);
  if (!table) return 0;
  const uint32_t entry = table + ((handle << 4) & 0xFFFF0u);
  return Read(base, entry) == handle ? Read(base, entry + 4) : 0;
}
// The module object's +0x298 (slot 305) is not kept by the R. Zombie soul class (2026-11-21:
// always FFFFFFFF in its update), so the wrapper is found once by scanning the handle table
// for the entry whose object's +0x180 is this module object, and remembered.
std::mutex g_wrap_lock;
std::unordered_map<uint32_t, uint32_t> g_wrappers;   // module object -> wrapper handle
uint32_t FindWrapperHandle(uint8_t* base, uint32_t o) {
  const uint32_t manager = Read(base, kHandleTable);
  if (!manager) return 0;
  const uint32_t table = Read(base, manager + 0xAC), end = Read(base, manager + 0xB0);
  if (!table || end <= table || end - table > 65536u * 16) return 0;
  for (uint32_t e = table; e + 16 <= end; e += 16) {
    const uint32_t h = Read(base, e), obj = Read(base, e + 4);
    if (h && h != 0xFFFFFFFF && obj >= 0x40000000 && obj < 0xA0000000 && Read(base, obj + 0x180) == o) return h;
  }
  return 0;
}
uint32_t WrapperHandle(uint8_t* base, uint32_t o) {
  {
    std::lock_guard lock(g_wrap_lock);
    auto it = g_wrappers.find(o);
    if (it != g_wrappers.end()) {
      const uint32_t w = ObjectOf(base, it->second);
      if (w && Read(base, w + 0x180) == o) return it->second;
      g_wrappers.erase(it);                              // reused object: look again
    }
  }
  const uint32_t h = FindWrapperHandle(base, o);
  if (h) {
    std::lock_guard lock(g_wrap_lock);
    g_wrappers[o] = h;
  }
  return h;
}
uint32_t Wrapper(uint8_t* base, uint32_t o) { return ObjectOf(base, WrapperHandle(base, o)); }
uint32_t Owner(uint8_t* base, uint32_t o) {
  const uint32_t w = Wrapper(base, o);
  return w ? Read(base, w + 0xA4) : 0;
}

void Draw(uint8_t* base, uint32_t o, uint32_t anim, bool mirrored) {
  if (const uint32_t s = Read(base, o + 0x258)) {
    base[s + 0x29] = 1;
    Float(base, s + 0x50, 0.0f);
    Float(base, s + 0x38, 1.0f);
    Float(base, s + 0x3C, 1.0f);
    if (Read(base, s + 0x00) != anim) {
      Write(base, s + 0x00, anim);
      base[s + 0x1C] = 1;
      Float(base, s + 0x10, 1.0f);
    }
    Write(base, s + 0x30, mirrored ? 2 : 0);
  }
  const uint32_t b = Read(base, o + 0x268), e = Read(base, o + 0x26C);
  if (b && e > b && e - b <= 8 * 0x84)
    for (uint32_t l = b; l < e; l += 0x84) base[l + 0x29] = 0;
}

// Move to (x, y) this frame by velocity, as the puppets do (the exe applies it).
void MoveTo(uint8_t* base, uint32_t o, float x, float y, float dt) {
  Float(base, o + 0x64, (x - Float(base, o + 0x5C)) / dt);
  Float(base, o + 0x68, (y - Float(base, o + 0x60)) / dt);
}

struct Module { uint32_t kind, id; const char* tag; };

// Cerberus fires his orbs and bolts as Lightning Orb shots (cerberus_module.cpp Spawn), so
// Charlotte's guard can learn them, as 8-bit Fishmen fire R. Fireball's own module. Such a
// shot is owned by an enemy (wrapper +0x08 bit 0x10, set by 82481D60 from the owner; a
// player's shots get 0x08) and carries the boss's table | row in the request's +0x18, which
// 8248DB90 stores at wrapper +0x170. Rows: 32 bytes, x, y, animation (0xFFFFFFFF: remove),
// flags (bit 0 mirrored), as cerberus_shot_module.cpp reads them.
uint32_t EnemyRow(uint8_t* base, uint32_t o) {
  const uint32_t w = Wrapper(base, o);
  if (!w) return 0;
  const uint32_t flags = Read(base, w + 0x08), marker = Read(base, w + 0x170);
  if (!(flags & 0x10) || (flags & 0x08) || marker < 0x10000 || marker >= 0xA0000000) return 0;
  return (marker & ~0xFFu) + (marker & 0xFF) * 32;
}

// One bolt piece from the skill factory, owned by the caster.
void SpawnPiece(PPCContext& ctx, uint8_t* base, const Module& m, uint32_t o, const Shot& from, float x, float y, int gen) {
  if (!Owner(base, o) || gen >= kMaxPieces || Solid(ctx, base, kFloorPush, x, y)) return;      // the column ends at a floor
  Shot piece;
  piece.bolt = true; piece.x = x; piece.y = y; piece.gen = gen; piece.level = from.level;
  std::shuffle(std::begin(piece.order), std::end(piece.order), g_rng);
  PPCContext call = ctx;
  call.r1.u32 = (ctx.r1.u32 - 0x400) & ~15u;
  Write(base, call.r1.u32, ctx.r1.u32);
  const uint32_t pos = call.r1.u32 + 0x200;                                   // inside this frame, above the callee's
  Float(base, pos, x);
  Float(base, pos + 4, y);
  call.r3.u64 = m.kind; call.r4.u64 = m.id; call.r5.u64 = Owner(base, o);
  call.r6.u64 = pos; call.r7.u64 = 1; call.r8.u64 = 0; call.r9.u64 = uint32_t(from.level); call.r10.u64 = 0;
  {
    std::lock_guard lock(g_lock);
    g_pending.active = true; g_pending.shot = piece;
  }
  rex::runtime::ResolveIndirectFunction(kSkillFactory)(call, base);
  const uint32_t handle = call.r3.u32;
  const uint32_t wrapper = ObjectOf(base, handle);
  const uint32_t obj = wrapper ? Read(base, wrapper + 0x180) : 0;     // the module object
  std::lock_guard lock(g_lock);
  g_pending.active = false;
  if (obj) {
    auto it = g_shots.find(obj);
    if (it == g_shots.end() || it->second.handle != handle) { piece.handle = handle; g_shots[obj] = piece; }
  }
  if (g_logged.fetch_add(1) < 40)
    REXLOG_INFO("[{}] bolt piece {} at ({:.0f}, {:.0f}): handle {:08X} object {:08X}", m.tag, gen, x, y, handle, obj);
}

// The template's update ends the shot: its timer past its limit, nothing drawn.
void End(Shot& s) { s.ended = true; s.end_t = 0; }

// Per-frame update (vtable slot 9). native = the template's own update.
template <typename Native>
void Update(PPCContext& ctx, uint8_t* base, const Module& m, Native native) {
  const uint32_t o = ctx.r3.u32;
  const uint32_t handle = WrapperHandle(base, o);
  // The setup (slot 4) runs this update once before the wrapper holds this module object, so
  // the shot cannot be told apart yet (2026-11-21: Cerberus's orb, read then, was taken for a
  // cast). Wait for the next frame.
  if (handle == 0 || handle == 0xFFFFFFFF) {
    Float(base, o + 0x64, 0.0f);
    Float(base, o + 0x68, 0.0f);
    int waited;
    {
      std::lock_guard lock(g_lock);
      waited = ++g_unlinked[o];
    }
    if (waited > 60) {                                  // never linked: let the template end it
      if (waited == 61) REXLOG_WARN("[{}] shot {:08X} never got its wrapper; ending it", m.tag, o);
      Float(base, o + 0x320, Float(base, o + 0x32C) + 1.0f);
      native(ctx, base);
      Draw(base, o, kBlank, false);
    }
    return;
  }
  {
    std::lock_guard lock(g_lock);
    g_unlinked.erase(o);
  }
  const float frame = float(ctx.f1.f64);
  const float dt = frame > 0 && frame < 1 ? frame : 1.0f / 60;
  Shot s;
  bool fresh = false;
  {
    std::lock_guard lock(g_lock);
    auto it = g_shots.find(o);
    if (it != g_shots.end() && it->second.handle == handle) s = it->second;
    else if (g_pending.active) { s = g_pending.shot; s.handle = handle; fresh = true; }
    else if (const uint32_t row = EnemyRow(base, o)) {   // Cerberus's orb or bolt
      s.handle = handle;
      s.row = row;
      s.x = Float(base, o + 0x5C);
      s.y = Float(base, o + 0x60);
      if (g_logged.fetch_add(1) < 40)
        REXLOG_INFO("[{}] Cerberus's shot {:08X} follows row {:08X} (animation {}) at ({:.0f}, {:.0f})", m.tag, o, row,
                    int32_t(Read(base, row + 8)), s.x, s.y);
    }
    else {                                               // a cast: the orb
      s.handle = handle;
      const float dir = Float(base, o + 0x324);
      s.dir = (dir == 1.0f || dir == -1.0f) ? dir : 1.0f;
      s.level = std::min<int>(base[o + 0x204], 9);
      s.rain = kRainBase + kRainPerLevel * s.level;
      s.x = Float(base, o + 0x5C) + s.dir * kHandForward;
      s.y = Float(base, o + 0x60) - kHandUp;
      s.vx = kDrift * s.dir;
      fresh = true;
      REXLOG_INFO("[{}] cast {:08X} (handle {:08X}, owner {:08X}, level {}) at ({:.0f}, {:.0f})", m.tag, o, handle,
                  Owner(base, o), s.level, s.x, s.y);
    }
  }
  if (fresh) {
    Float(base, o + 0x5C, s.x);
    Float(base, o + 0x60, s.y);
  }
  if (s.ended) {
    Float(base, o + 0x64, 0.0f);
    Float(base, o + 0x68, 0.0f);
    Float(base, o + 0x320, Float(base, o + 0x32C) + 1.0f);
    native(ctx, base);
    Draw(base, o, kBlank, false);
    std::lock_guard lock(g_lock);
    if (++s.end_t > kForgetTicks) g_shots.erase(o); else g_shots[o] = s;
    return;
  }
  ++s.t;
  uint32_t anim = kSmall;
  bool mirrored = false;
  if (s.row) {                                           // follow the boss's row
    anim = Read(base, s.row + 8);
    mirrored = Read(base, s.row + 12) & 1;
    if (anim == 0xFFFFFFFF) End(s);
    else { s.x = Float(base, s.row + 0); s.y = Float(base, s.row + 4); }
  } else if (s.bolt) {
    anim = kBolt + uint32_t(s.order[std::min(s.t / 3, 3)]);
    mirrored = (s.t / 3) & 1;
    if (s.t == 3) SpawnPiece(ctx, base, m, o, s, s.x, s.y + kPieceStep, s.gen + 1);
    if (s.t >= kPieceTicks) End(s);
  } else {
    switch (s.phase) {
      case 0: {                                          // rise to the set height, or under a ceiling
        anim = kSmall;
        const float step = std::min(kRiseSpeed, kRiseHeight - s.risen);
        if (Solid(ctx, base, kCeilingPush, s.x, s.y - step - kCeilingGap) || step <= 0) { s.phase = 1; s.t = 0; break; }
        s.y -= step; s.risen += step;
        if (s.risen >= kRiseHeight) { s.phase = 1; s.t = 0; }
        break;
      }
      case 1:                                            // swell into the orb
        anim = kSmall + uint32_t(std::min(s.t, 3));
        if (s.t >= kSwellTicks) { s.phase = 2; s.t = 0; s.base_y = s.y; }
        break;
      case 2:                                            // sway and rain bolts
        s.wave += 0x217;
        s.y = s.base_y - 6.0f * std::sin(float(s.wave) / 65536.0f * 2 * kPi);
        if (s.t % kDriftTurn == 0) s.vx = -s.vx;
        s.x += s.vx;
        anim = s.t < 8 ? kSmall + uint32_t(3 + std::min(s.t / 3, 2)) : kFlare;
        if (s.t >= 8 && (s.t - 8) % kBoltEvery == 0) {
          const float side = (++s.bolt_n & 1) ? 1.0f : -1.0f;
          SpawnPiece(ctx, base, m, o, s, s.x + side * float(std::uniform_int_distribution<int>(0, 4)(g_rng)),
                     s.y + kPieceStep, 0);
        }
        if (s.t >= s.rain) { s.phase = 3; s.t = 0; }
        break;
      case 3:                                            // shrink away
        anim = kSmallFade + uint32_t(std::max(0, 5 - s.t / 4));
        if (s.t >= kFadeTicks) End(s);
        break;
    }
  }
  if (s.ended) Draw(base, o, kBlank, false);
  else {
    MoveTo(base, o, s.x, s.y, dt);
    Draw(base, o, anim, mirrored);
  }
  std::lock_guard lock(g_lock);
  g_shots[o] = s;
}
}  // namespace
}  // namespace cerberus_orb
