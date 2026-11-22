// Poison Worm behavior inside its own enemy module, DLL_Cm050 (test builds only;
// CMake HARMONYRECOMP_POISONWORM). The module is the 8-bit DLC Bat (DLL_FCbat)
// rebased to 0x89380000 (modding/tools/poison_worm_module.py); this file
// replaces the Bat's hang-and-swoop with CotM's Poison Worm.
//
// Module object (0x44EC bytes, vtable 0x89381D90), from the Bat's code:
//   +0x9C/+0xA0  player position (float x, y)    +0xA4/+0xA8  own position
//   +0xAC/+0xB0  velocity in px/s (applied by the exe; confirmed in game)
//   +0x21F       requested animation              +0x2B8       sprite object
//   +0x44C0      Bat state (0 hang, 1 fly, ... 4 dying); +0x44D1/+0x44D2/+0x44D3 hit flags
// Slot 2 (0x893915A0) is spawn setup, slot 7 (0x893917E8) the per-frame update
// (f1 = frame time), export 1 (0x893913F0) the factory. The exe reaches all
// three through the vtable / export, so overriding them needs no rewrite.
//
// Parent (placed in the stage): hangs (animation 0), creeps toward the player's
// x within home_range of where it spawned, re-aiming every 2-4 s, never flies.
// While the player is below it (|dx| <= 96, 0 < dy <= 156, CotM's numbers) it
// releases small worms: bursts of 4, 20-40 frames apart, then 210 frames,
// with at most 12 small worms alive. Hits and death run the Bat's own code.
//
// Small worm (spawned by a parent through the game's spawn routine 8224C478
// with the same name, flagged as a child just before): HP 1; at setup it gets
// the 8-bit Skeleton's gravity and floor-collision settings (DLL_FCskl slot 2);
// falls with animation 1, then crawls with animation 2 at 0.156 px/frame in a
// random direction, turning at walls. Small worms outlive their parent (CotM).
//
// Tuning: poison_worm_tuning.txt next to the exe ("key = value"), read when a
// parent spawns; missing keys keep the defaults below.
#include "../generated/dll_cm050/harmonyrecomp_init.h"
#include <rex/filesystem.h>
#include <rex/logging.h>
#include <rex/memory/utils.h>
#include <rex/system/kernel_state.h>
#include <rex/system/xmemory.h>
#include <algorithm>
#include <atomic>
#include <bit>
#include <cstdio>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <mutex>
#include <random>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

REX_EXTERN(__imp__sub_893917E0);
REX_EXTERN(__imp__sub_893913F0);
REX_EXTERN(__imp__sub_893915A0);
REX_EXTERN(__imp__sub_893917E8);

namespace poison_worm {
namespace {
constexpr uint32_t kSpawn = 0x8224C478;       // exe: spawn enemy by name (r3 name, r4 x, r5 y, r6 facing, r7, r8)
constexpr uint32_t kName = 0x89381D84;        // "DLL_Cm050" inside this module
constexpr uint32_t kEntityManager = 0x8291D9F0;
constexpr uint32_t kPoisonTouch = 0x4000;     // attack attribute: poison (player side)
constexpr float kFrame = 60.0f;               // CotM per-frame values -> per second

struct Tuning {
  float creep_speed = 7.5f;      // CotM 0.125 px/frame
  float home_range = 32.0f;      // CotM: +-32 px of its spawn x
  float retarget_min = 2.0f;     // CotM: 120-239 frames
  float retarget_max = 4.0f;
  float range_x = 96.0f;         // CotM release range
  float range_y = 156.0f;
  float drop_y = 24.0f;          // CotM: released 24-28 px below the parent
  float drop_spread_x = 10.0f;
  float drop_speed_x = 30.0f;    // CotM: +-0.5 px/frame sideways
  float burst_gap_min = 20.0f / kFrame, burst_gap_max = 40.0f / kFrame;
  float burst_pause = 210.0f / kFrame;
  int burst = 4;
  int max_children = 12;
  float crawl_speed = 9.375f;    // CotM 0.15625 px/frame
  float gravity = 600.0f;        // px/s^2 for falling small worms (the exe adds none)
  float max_fall = 240.0f;       // px/s
  float max_drop = 400.0f;       // stop falling after this far without finding a floor
  float floor_sensor = 0.0f;     // +0x250: feet sensor below the position (Skeleton 8)
  float settle_max = 6.0f;       // largest landing correction (px); more means not a flat 16 px floor
  bool log_frames = false;
  bool shots = true;             // small worms are enemy shots (dllshotCm050w), not enemies (2026-11-20)
  float shot_life = 20.0f;       // s; must match kLife in poison_worm_shot_module.cpp (counts toward max_children)
  int hit_debris = 3;            // worm chunks thrown per hit (CotM: debris for 3 frames after a hit)
  int death_debris_first = 0;    // extra chunks the moment it dies (CotM: none)
  float death_debris_gap = 6.0f / kFrame;   // CotM: every 6 ticks while dying
  float death_time = 60.0f / kFrame;        // CotM: final puff after 60 ticks
  float explosion_y = 18.0f;     // px below the hang point (flames cover the mass)
  float death_sink = 0.0f;       // px/s; the ROM writes 0.5 px/frame, but in CotM it explodes in place (user, 2026-11-20)
};

struct Worm {
  bool started = false;
  bool child = false;
  float home_x = 0, home_y = 0;
  float retarget = 0, dir = 0;    // parent creep
  float release = 0;              // parent: seconds to the next release check
  int left_in_burst = 4;
  int phase = 0;                  // child: 0 falling, 1 crawling
  float last_x = 0, last_y = 0;
  int still = 0;                  // child: frames without movement
  int logged = 0;
  int anim = -1;                  // last animation sent (-1: none yet)
  int dump_at = -1;               // diagnostic: frame to log the sprite again
  float anim_time = 0;            // seconds into the current loop
  float settle_y = -1;            // small worm: exact resting y (floor - 8), -1 none
  int settle_frames = 0;
  bool dying = false;             // parent: CotM death sink running
  float death_t = 0, debris_t = 0, explode_t = 0;
  float clock = 0;                // parent: seconds alive
  std::vector<float> shot_expiry; // parent: when each released small-worm shot runs out
};

std::recursive_mutex g_lock;
std::unordered_map<uint32_t, Worm> g_worms;
std::unordered_set<uint32_t> g_new_children;  // flagged by the factory, picked up at setup
std::unordered_set<uint32_t> g_unloaded;      // made by the factory, shot preload not queued yet
thread_local bool g_spawning_child = false;
Tuning g_tuning;
std::mt19937 g_rng{0x50574D31};

uint32_t Read(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
float Float(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Read(base, a)); }
void Float(uint8_t* base, uint32_t a, float v) { rex::memory::store_and_swap<uint32_t>(base + a, std::bit_cast<uint32_t>(v)); }
float Uniform(float lo, float hi) { return std::uniform_real_distribution<float>(lo, hi)(g_rng); }
struct Worm;
void SetAnimation(const PPCContext& caller, uint8_t* base, uint32_t o, Worm& w, uint16_t anim);

Tuning LoadTuning() {
  Tuning t;
  std::ifstream in(rex::filesystem::GetExecutableFolder() / "poison_worm_tuning.txt");
  std::string line;
  while (std::getline(in, line)) {
    const auto eq = line.find('=');
    if (eq == std::string::npos || line.empty() || line[0] == '#') continue;
    auto key = line.substr(0, eq);
    key.erase(key.find_last_not_of(" \t") + 1);
    const float v = std::strtof(line.c_str() + eq + 1, nullptr);
    if (key == "creep_speed") t.creep_speed = v;
    else if (key == "home_range") t.home_range = v;
    else if (key == "retarget_min") t.retarget_min = v;
    else if (key == "retarget_max") t.retarget_max = v;
    else if (key == "range_x") t.range_x = v;
    else if (key == "range_y") t.range_y = v;
    else if (key == "drop_y") t.drop_y = v;
    else if (key == "crawl_speed") t.crawl_speed = v;
    else if (key == "gravity") t.gravity = v;
    else if (key == "max_fall") t.max_fall = v;
    else if (key == "max_drop") t.max_drop = v;
    else if (key == "floor_sensor") t.floor_sensor = v;
    else if (key == "settle_max") t.settle_max = v;
    else if (key == "max_children") t.max_children = int(v);
    else if (key == "burst") t.burst = int(v);
    else if (key == "burst_pause") t.burst_pause = v;
    else if (key == "log_frames") t.log_frames = v != 0;
    else if (key == "shots") t.shots = v != 0;
    else if (key == "shot_life") t.shot_life = v;
    else if (key == "hit_debris") t.hit_debris = int(v);
    else if (key == "death_debris_first") t.death_debris_first = int(v);
    else if (key == "death_debris_gap") t.death_debris_gap = v;
    else if (key == "death_time") t.death_time = v;
    else if (key == "death_sink") t.death_sink = v;
    else if (key == "explosion_y") t.explosion_y = v;
  }
  return t;
}

uint32_t EntityOf(uint8_t* base, uint32_t handle) {  // handle -> exe object (entity manager table)
  const auto manager = Read(base, kEntityManager);
  if (!manager || !handle) return 0;
  const auto table = Read(base, manager + 0xAC), end = Read(base, manager + 0xB0);
  const uint32_t offset = (handle & 0xFFFF) << 4;
  if (!table || end < table || end - table > 65536 * 16 || end - table < 16 || offset > end - table - 16) return 0;
  return Read(base, table + offset) == handle ? Read(base, table + offset + 4) : 0;
}

// Frame driving (unused since the live probe, 2026-11-20): the request's +0x10 is
// the playback speed; with 1.0 the exe steps the frames itself (+0x04 ticks,
// +0x08 frame), as it does for the parent. Kept for reference.
struct Step { uint8_t frame, ticks; };
constexpr Step kParentLoop[] = {{0, 8}, {1, 8}, {2, 8}, {3, 8}};
constexpr Step kFallLoop[] = {{4, 4}, {5, 4}, {6, 4}, {7, 4}, {6, 4}, {5, 4}};
constexpr Step kCrawlLoop[] = {{8, 8}, {9, 8}, {10, 8}, {11, 8}};

template <size_t N>
void DriveFrames(uint8_t* base, uint32_t o, Worm& w, const Step (&loop)[N], float dt) {
  const uint32_t sprite = Read(base, o + 0x2B8);
  if (!sprite) return;
  float total = 0;
  for (const auto& s : loop) total += s.ticks / 60.0f;
  w.anim_time = std::fmod(w.anim_time + dt, total);
  float t = w.anim_time;
  for (const auto& s : loop) {
    if (t < s.ticks / 60.0f) { rex::memory::store_and_swap<uint32_t>(base + sprite + 0x08, s.frame); return; }
    t -= s.ticks / 60.0f;
  }
}

// The small worms' EnemyParam row: a copy of the mass's (96 bytes), made once.
uint32_t g_child_row = 0;
uint32_t ChildRow(uint8_t* base, uint32_t row) {
  if (!g_child_row) {
    const auto at = REX_KERNEL_MEMORY()->SystemHeapAlloc(96);
    if (!at) return 0;
    std::memcpy(base + at, base + row, 96);
    auto put32 = [&](uint32_t off, uint32_t v) { rex::memory::store_and_swap<uint32_t>(base + at + off, v); };
    auto put16 = [&](uint32_t off, uint16_t v) { rex::memory::store_and_swap<uint16_t>(base + at + off, v); };
    put32(0x04, 1);                                  // HP
    put32(0x18, 0);                                  // kill reward (not read by the stats setter)
    put32(0x1C, 0); put32(0x20, 0);                  // items A / B
    put32(0x24, 0); put16(0x2C, 0);                  // soul, soul rate
    put16(0x46, 0); put16(0x48, 0);                  // item rates
    put16(0x4C, 0); put16(0x4E, 0);                  // no Compendium entry
    g_child_row = at;
    REXLOG_INFO("[pworm] small worm row at {:08X} (copy of {:08X}, no soul/drops/Compendium)", at, row);
  }
  return g_child_row;
}

int LiveChildren() {
  int n = 0;
  for (const auto& [o, w] : g_worms) n += w.child;
  return n + int(g_new_children.size());
}

// Spawn one small worm through the game's own spawn routine, as enemies that
// summon others do (r7 = r8 = 1). Returns its exe handle (0 if refused).
uint32_t SpawnChild(const PPCContext& caller, uint8_t* base, float x, float y) {
  PPCContext ctx = caller;                               // REX_CALL_INDIRECT_FUNC uses ctx/base
  ctx.r1.u32 = caller.r1.u32 - 0x200;                    // our own frame below the caller's
  rex::memory::store_and_swap<uint32_t>(base + ctx.r1.u32, caller.r1.u32);
  ctx.r3.u64 = kName;
  ctx.r4.u64 = uint32_t(int32_t(std::lround(x)));
  ctx.r5.u64 = uint32_t(int32_t(std::lround(y)));
  ctx.r6.u64 = 0;
  ctx.r7.u64 = 1;
  ctx.r8.u64 = 1;
  g_spawning_child = true;
  REX_CALL_INDIRECT_FUNC(kSpawn);
  g_spawning_child = false;
  const uint32_t handle = ctx.r3.u32;
  if (const auto object = EntityOf(base, handle)) {     // CotM: small worms have 1 HP
    Float(base, object + 0x98, 1.0f);
    Float(base, object + 0x9C, 1.0f);
    // Not a "real monster" (user, 2026-11-20; like the Man-eating Plant's seeds,
    // but with damage numbers): point the exe object's EnemyParam row (+0xC0, set
    // by 82240538) at a shared copy with no soul, drops, reward or Compendium
    // entry. Attack, resistances and the name stay the mass's.
    if (const uint32_t row = Read(base, object + 0xC0)) {
      if (const uint32_t child_row = ChildRow(base, row)) rex::memory::store_and_swap<uint32_t>(base + object + 0xC0, child_row);
    }
  }
  return handle;
}

// ---- Small worms as enemy shots (2026-11-20) --------------------------------
// The enemy-side spawn refuses past 200 enemies (Catacombs chapter 14 has 223),
// and small worms are not real monsters, so the mass fires them the way Legion
// fires its falling bodies: a 60-byte request appended to the object's list at
// +0x1C8 (+0x1CC begin, +0x1D0 end, +0x1D4 capacity end; vtable slot 21). The
// game's generic DLL enemy (82252BB0) fires every request each frame (byte +0x30
// = 0: registry 82486AB0 path, as Legion) and clears the list. Slot 1 queues a
// preload request per shot, read when the game builds the enemy (82250F78).
// Growing the list uses the module's game allocator / free pointers (set by the
// game when it loads the module; Legion's are at 0x8BF31564 / 0x8BF31568).
constexpr uint32_t kAllocPtr = 0x893B14A4;    // module global: game allocator (r3 = size)
constexpr uint32_t kFreePtr = 0x893B14A8;     // module global: game free (r3 = pointer)
constexpr uint32_t kRequest = 0x3C;
constexpr uint32_t kShotCategory = 0xB;       // enemy shot
constexpr uint32_t kShotId = 0x4050;          // dllshotCm050w (modding/tools/poison_worm_shot.py)
constexpr uint32_t kShotAttributes = 0x40000042 | kPoisonTouch;   // Legion's body request + poison

uint32_t CallGuest(const PPCContext& caller, uint8_t* base, uint32_t fn, uint32_t r3) {
  PPCContext ctx = caller;
  ctx.r1.u32 = caller.r1.u32 - 0x200;
  rex::memory::store_and_swap<uint32_t>(base + ctx.r1.u32, caller.r1.u32);
  ctx.r3.u64 = r3;
  REX_CALL_INDIRECT_FUNC(fn);
  return ctx.r3.u32;
}

// Room for one more request at the list's end; returns its address (0 if none).
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
    rex::memory::store_and_swap<uint32_t>(base + v + 4, fresh);
    rex::memory::store_and_swap<uint32_t>(base + v + 0xC, fresh + count * kRequest);
    at = fresh + size * kRequest;
  }
  std::memset(base + at, 0, kRequest);
  rex::memory::store_and_swap<uint32_t>(base + v + 8, at + kRequest);
  return at;
}

void Put(uint8_t* base, uint32_t a, uint32_t v) { rex::memory::store_and_swap<uint32_t>(base + a, v); }

// Defaults of Legion's request initializer (DLL_Region 0x8BF10000).
void RequestDefaults(uint8_t* base, uint32_t r) {
  Put(base, r + 0x10, kShotCategory);
  Put(base, r + 0x14, kShotId);
  Float(base, r + 0x24, 1.0f);
  Put(base, r + 0x28, 0x40000042);
  Float(base, r + 0x2C, 5.0f);
  base[r + 0x30] = 1;
  Float(base, r + 0x34, -1.0f);
  Put(base, r + 0x38, 0xFFFFFFFF);
}

// Fire one small worm, filled as Legion fills its body request (DLL_Region 0x8BF14968).
// Request +0x18 (the shot's +0x21C): 0 right / 1 left for a small worm; 2 left / 3
// right marks a worm-chunk debris, 4 an explosion (dllshotCm050w makes both harmless).
enum class Shot { kWorm, kChunk, kExplosion };
bool ReleaseShot(const PPCContext& caller, uint8_t* base, uint32_t o, float x, float y, float dir,
                 Shot kind = Shot::kWorm) {
  const bool debris = kind != Shot::kWorm;
  const uint32_t r = NewRequest(caller, base, o);
  if (!r) return false;
  RequestDefaults(base, r);
  Float(base, r + 0x00, x);
  Float(base, r + 0x04, y);
  Put(base, r + 0x18, kind == Shot::kExplosion ? 4 : kind == Shot::kChunk ? (dir < 0 ? 2 : 3) : (dir < 0 ? 1 : 0));
  Put(base, r + 0x20, 0);
  Float(base, r + 0x24, Float(base, o + 0x1F0) * 0.6f);   // power: vtable +0x260 (attack) x 0.6
  Put(base, r + 0x28, debris ? 0x40000000u : kShotAttributes);
  Float(base, r + 0x2C, Float(base, o + 0x1E0));          // vtable +0x254
  base[r + 0x30] = 0;                                     // registry path, as Legion
  Float(base, r + 0x34, 65.536f * 18.0f);
  const uint32_t owner = Read(base, o + 0x2C8);
  Put(base, r + 0x38, owner ? Read(base, owner + 0x18) : 0xFFFFFFFF);
  return true;
}

// One worm chunk from the mass's body (its sprite hangs 0-16 px below the position).
void ThrowDebris(const PPCContext& caller, uint8_t* base, uint32_t o) {
  const float x = Float(base, o + 0xA4) + Uniform(-12.0f, 12.0f);
  const float y = Float(base, o + 0xA8) + Uniform(2.0f, 12.0f);
  const float dir = Uniform(0.0f, 1.0f) < 0.5f ? -1.0f : 1.0f;
  const bool queued = ReleaseShot(caller, base, o, x, y, dir, Shot::kChunk);
  static int logged = 0;
  if (logged++ < 40)
    REXLOG_INFO("[pworm] {:08X} debris at {:.0f},{:.0f}: {} (list {:08X}..{:08X})", o, x, y, queued ? "queued" : "NOT queued",
                Read(base, o + 0x1CC), Read(base, o + 0x1D0));
}

// CotM's death explosion (effect spawner 0x08014848 kind 1, random spread 14 x 8 px).
// Its frames sit 3-19 px above their origin; at CotM's +8 px they went up into the
// ceiling, under the stage's foreground tiles ("hard to see", user 2026-11-20). The
// origin goes 18 px below the hang point instead, so the flames cover the mass's
// body (it hangs 0-16 px below), as in the user's CotM captures.
void Explode(const PPCContext& caller, uint8_t* base, uint32_t o) {
  const float x = Float(base, o + 0xA4) + Uniform(-10.0f, 10.0f);
  const float y = Float(base, o + 0xA8) + g_tuning.explosion_y + Uniform(-4.0f, 4.0f);
  ReleaseShot(caller, base, o, x, y, 1.0f, Shot::kExplosion);
}

void ParentFrame(const PPCContext& ctx, uint8_t* base, uint32_t o, Worm& w, float dt) {
  const float x = Float(base, o + 0xA4), y = Float(base, o + 0xA8);
  if (!w.started) {
    w.started = true;
    w.home_x = x; w.home_y = y;
    w.retarget = 0;
    w.release = 0;
    w.left_in_burst = g_tuning.burst;
    REXLOG_INFO("[pworm] parent {:08X} hangs at {:.0f},{:.0f}; frame time {:.4f}", o, x, y, dt);
  }
  w.anim = 0;                                            // animation 0 (hanging mass) is started by spawn setup
  const float px = Float(base, o + 0x9C), py = Float(base, o + 0xA0);
  w.retarget -= dt;
  if (w.retarget <= 0) {
    w.dir = px > x ? 1.0f : -1.0f;
    w.retarget = Uniform(g_tuning.retarget_min, g_tuning.retarget_max);
  }
  if (x < w.home_x - g_tuning.home_range) w.dir = 1.0f;
  if (x > w.home_x + g_tuning.home_range) w.dir = -1.0f;
  Float(base, o + 0xAC, w.dir * g_tuning.creep_speed);
  Float(base, o + 0xB0, 0.0f);

  w.clock += dt;
  std::erase_if(w.shot_expiry, [&](float t) { return t <= w.clock; });
  w.release -= dt;
  if (w.release <= 0) {
    const float dx = std::fabs(px - x), dy = py - y;
    if (dy > 0 && dx <= g_tuning.range_x && dy <= g_tuning.range_y && g_tuning.shots) {
      // Small worms as enemy shots: the cap counts this mass's shots still within their lifetime.
      if (int(w.shot_expiry.size()) < g_tuning.max_children) {
        const float cx = x + Uniform(-g_tuning.drop_spread_x, g_tuning.drop_spread_x);
        const float cy = y + g_tuning.drop_y + Uniform(0.0f, 4.0f);
        const float dir = Uniform(0.0f, 1.0f) < 0.5f ? -1.0f : 1.0f;   // CotM: random crawl direction
        const bool queued = ReleaseShot(ctx, base, o, cx, cy, dir);
        if (queued) w.shot_expiry.push_back(w.clock + g_tuning.shot_life);
        if (g_tuning.log_frames || !queued)
          REXLOG_INFO("[pworm] parent {:08X} shot at {:.0f},{:.0f} dir {:.0f}: {} (list {:08X}..{:08X})", o, cx, cy, dir,
                      queued ? "queued" : "NOT queued", Read(base, o + 0x1CC), Read(base, o + 0x1D0));
      }
      if (--w.left_in_burst <= 0) {
        w.left_in_burst = g_tuning.burst;
        w.release = g_tuning.burst_pause;
      } else {
        w.release = Uniform(g_tuning.burst_gap_min, g_tuning.burst_gap_max);
      }
    } else if (dy > 0 && dx <= g_tuning.range_x && dy <= g_tuning.range_y) {   // CotM: player below and near
      if (LiveChildren() < g_tuning.max_children) {
        const float cx = x + Uniform(-g_tuning.drop_spread_x, g_tuning.drop_spread_x);
        const float cy = y + g_tuning.drop_y + Uniform(0.0f, 4.0f);
        const auto handle = SpawnChild(ctx, base, cx, cy);
        if (g_tuning.log_frames) REXLOG_INFO("[pworm] parent {:08X} released at {:.0f},{:.0f}: handle {:08X}", o, cx, cy, handle);
        if (!handle) {
          // Spawn 8224C478 refuses (returns 0) when the enemy manager [0x8291D8F4]'s list
          // (+0x14 begin, +0x18 end, 4-byte entries) holds more than 200 (cmplwi 0xC8).
          const uint32_t mgr = Read(base, 0x8291D8F4);
          const uint32_t live = mgr ? (Read(base, mgr + 0x18) - Read(base, mgr + 0x14)) / 4 : 0;
          REXLOG_INFO("[pworm] spawn refused: enemy manager {:08X} list holds {} (cap 200)", mgr, live);
        }
      }
      if (--w.left_in_burst <= 0) {
        w.left_in_burst = g_tuning.burst;
        w.release = g_tuning.burst_pause;
      } else {
        w.release = Uniform(g_tuning.burst_gap_min, g_tuning.burst_gap_max);
      }
    } else {
      w.release = Uniform(g_tuning.burst_gap_min, g_tuning.burst_gap_max);
    }
  }
  if (g_tuning.log_frames && w.logged++ < 600 && w.logged % 60 == 1)
    REXLOG_INFO("[pworm] parent {:08X} x {:.1f} (home {:.0f}) dir {:.0f} player {:.0f},{:.0f} children {} shots {}", o, x,
                w.home_x, w.dir, px, py, LiveChildren(), w.shot_expiry.size());
}

// Animation switch on the sprite object (+0x2B8). Test history (2026-11-20):
//   Bat flight start (+0x00 anim, +0x28 0, +0x10 0, +0x54 0, +0x1C 1, +0x2B 1):
//     right frame, but frozen on it;
//   module command +0x388: no change;  Fishman (+0x54 0, +0x00 anim): no change.
//   Bat writes without +0x1C: no change. Log (harmonyrecomp_021): nothing in this
//     object moves over 30 frames, so it is a request the exe reads, and +0x1C is
//     the "apply" trigger. The earlier freeze: that build re-sent the request every
//     frame because it compared against sprite +0x00 (which the exe likely rewrites
//     after applying), restarting the animation on frame 0.
// Now: the Bat's full request, +0x1C included, sent once per change as tracked in
// Worm::anim (never by reading the sprite back). The sprite's first 0x60 bytes are
// still logged after a switch and 30 frames later (first small worms).
std::atomic<int> g_dumps{0};
void DumpSprite(uint8_t* base, uint32_t o, const char* when) {
  const uint32_t sprite = Read(base, o + 0x2B8);
  if (!sprite) return;
  std::string hex;
  char buf[12];
  for (uint32_t k = 0; k < 0x60; k += 4) {
    std::snprintf(buf, sizeof buf, "%08X ", Read(base, sprite + k));
    hex += buf;
  }
  REXLOG_INFO("[pworm] sprite {:08X} of {:08X} {}: {}", sprite, o, when, hex);
}

void SetAnimation(const PPCContext&, uint8_t* base, uint32_t o, Worm& w, uint16_t anim) {
  if (w.anim == anim) return;
  const uint32_t sprite = Read(base, o + 0x2B8);
  if (!sprite) return;
  w.anim = anim;
  w.anim_time = 0;
  rex::memory::store_and_swap<uint32_t>(base + sprite + 0x00, anim);
  Float(base, sprite + 0x54, 0.0f);
  base[sprite + 0x2B] = 1;
  base[sprite + 0x28] = 0;
  base[sprite + 0x1C] = 1;                                // apply (the Bat's flight start)
  Float(base, sprite + 0x10, 1.0f);                       // playback speed (live: parent 1.0; 0.0 froze the small worms)
  w.dump_at = (w.child && g_dumps.fetch_add(1) < 8) ? w.logged + 30 : -1;
  if (w.dump_at >= 0) DumpSprite(base, o, anim == 1 ? "after switch to falling" : "after switch to crawling");
}

// Facing: sprite +0x30 (the Bat writes 2 when the player is to its right, else 0).
void SetFacing(uint8_t* base, uint32_t o, float dir) {
  if (const uint32_t sprite = Read(base, o + 0x2B8)) rex::memory::store_and_swap<uint32_t>(base + sprite + 0x30, dir > 0 ? 2 : 0);
}

void ChildFrame(const PPCContext& ctx, uint8_t* base, uint32_t o, Worm& w, float dt) {
  const float x = Float(base, o + 0xA4), y = Float(base, o + 0xA8);
  if (!w.started) {
    w.started = true;
    w.phase = 0;
    w.home_y = y;
    w.dir = Uniform(-1.0f, 1.0f);                        // CotM: +-0.5 px/frame sideways while falling
    Float(base, o + 0xAC, w.dir * g_tuning.drop_speed_x);
    Float(base, o + 0xB0, 0.0f);
    w.last_x = x; w.last_y = y;
  }
  const bool moved_x = std::fabs(x - w.last_x) > 0.01f, moved_y = std::fabs(y - w.last_y) > 0.01f;
  const bool floor = Read(base, o + 0x258) != 0;         // exe-written contacts (8-bit Skeleton reads these)
  const bool wall_left = Read(base, o + 0x260) != 0, wall_right = Read(base, o + 0x264) != 0;
  if (w.phase == 0) {                                    // falling: our own gravity
    SetAnimation(ctx, base, o, w, 1);
    float vy = Float(base, o + 0xB0) + g_tuning.gravity * dt;
    if (vy > g_tuning.max_fall) vy = g_tuning.max_fall;
    Float(base, o + 0xB0, vy);
    w.still = (!moved_y && w.logged > 2) ? w.still + 1 : 0;
    const bool lost = y - w.home_y > g_tuning.max_drop;
    if (floor || w.still >= 2 || lost) {                 // landed
      w.phase = 1;
      w.dir = Uniform(0.0f, 1.0f) < 0.5f ? -1.0f : 1.0f; // CotM: 50% either way
      w.still = 0;
      Float(base, o + 0xB0, 0.0f);
      // Settle: the exe keeps the foot point (+0x4414) 8 px below the position and
      // stops the fall when its probe touches the floor, up to 4 px early (4 px a
      // frame at top fall speed). Flat floors sit on the 16 px tile grid, so the
      // exact rest is the next tile boundary at or below the foot, minus 8.
      if (floor) {
        const float foot = Float(base, o + 0x4414);
        const float surface = std::ceil(foot / 16.0f - 0.001f) * 16.0f;
        const float target = surface - 8.0f;
        if (target - y > 0.05f && target - y <= g_tuning.settle_max) { w.settle_y = target; w.settle_frames = 30; }
      }
      if (g_tuning.log_frames)
        REXLOG_INFO("[pworm] small worm {:08X} landed at {:.0f},{:.0f} ({})", o, x, y,
                    floor ? "floor contact" : lost ? "NO FLOOR FOUND" : "stopped falling");
    }
  } else {                                               // crawling
    SetAnimation(ctx, base, o, w, 2);
    w.still = moved_x ? 0 : w.still + 1;
    if ((w.dir < 0 && wall_left) || (w.dir > 0 && wall_right) || w.still >= 3) {   // CotM: turn at walls
      w.dir = -w.dir;
      w.still = 0;
    }
    Float(base, o + 0xAC, w.dir * g_tuning.crawl_speed);
    float vy = floor ? 0.0f : g_tuning.gravity * dt;     // stay on the floor
    if (w.settle_y >= 0) {                                // ease the last few px down to the exact rest
      const float dy = w.settle_y - y;
      if (dy > 0.05f && w.settle_frames-- > 0) {
        vy = std::min(dy / dt, 60.0f);
      } else {
        if (g_tuning.log_frames) REXLOG_INFO("[pworm] small worm {:08X} settled at y {:.2f} (target {:.0f})", o, y, w.settle_y);
        w.settle_y = -1;
        vy = 0;
      }
    }
    Float(base, o + 0xB0, vy);
    SetFacing(base, o, w.dir);
  }
  if (w.dump_at >= 0 && w.logged == w.dump_at) DumpSprite(base, o, "30 frames later");
  w.last_x = x; w.last_y = y;
  if (g_tuning.log_frames && w.logged < 240 && (w.logged % 20 == 0))
    REXLOG_INFO("[pworm] small worm {:08X} {} at {:.1f},{:.1f} v {:.1f},{:.1f} contacts floor {} walls {}{}", o,
                w.phase ? "crawl" : "fall", x, y, Float(base, o + 0xAC), Float(base, o + 0xB0), floor ? 1 : 0,
                wall_left ? 1 : 0, wall_right ? 1 : 0);
  w.logged++;
}

// 8-bit Skeleton's gravity and floor collision (DLL_FCskl slot 2, 0x88511670):
// vtable +0x28C(1) stores +0x229; bytes +0x268..+0x26B; terrain sensor floats.
void GiveGravity(uint8_t* base, uint32_t o) {
  base[o + 0x229] = 1;
  for (uint32_t b = 0x268; b <= 0x26B; ++b) base[o + b] = 1;
  Float(base, o + 0x23C, 12.0f);
  Float(base, o + 0x240, 0.0f);
  Float(base, o + 0x244, -34.0f);
  Float(base, o + 0x248, -8.0f);
  Float(base, o + 0x24C, -14.0f);
  Float(base, o + 0x250, g_tuning.floor_sensor);         // Skeleton: 8 (floated 8 px above the floor)
  rex::memory::store_and_swap<uint32_t>(base + o + 0x44A0, 0x24012);   // terrain mask of the 8-bit floor walkers
  rex::memory::store_and_swap<uint32_t>(base + o + 0x44A4, 0);
  Float(base, o + 0x254, -14.0f);
  if (const uint32_t sprite = Read(base, o + 0x2B8)) base[sprite + 0x66] = 1;
}
}  // namespace
}  // namespace poison_worm

// Factory (export 1): remember objects created by a parent's release.
REX_EXTERN(sub_893913F0) {
  __imp__sub_893913F0(ctx, base);
  if (ctx.r3.u32) {
    std::lock_guard lock(poison_worm::g_lock);
    poison_worm::g_unloaded.insert(ctx.r3.u32);                    // slot 1 queues its shot preload
    if (poison_worm::g_spawning_child) poison_worm::g_new_children.insert(ctx.r3.u32);
  }
}

// Slot 1 (the 8-bit Bat's is an empty blr): queue the preload request for the
// small-worm shot, as Legion's slot 1 (0x8BF11A18) queues its shots; the game
// reads the list when it builds the enemy (82250F78 -> 8248A690) and clears it.
// 0x893917E0 is one shared empty function: the Bat's vtable slots 1, 5, 6, 8, 9,
// 25, 81, 83, other vtables and the module's startup table (r3 = 0 there; the
// first build of this crashed loading Chapter 1, 2026-11-20) all point at it.
// So only the first call on an object the factory just made queues the preload;
// the game makes that call (vtable +4) right after the factory (82250F54).
REX_EXTERN(sub_893917E0) {
  using namespace poison_worm;
  const uint32_t o = ctx.r3.u32;
  __imp__sub_893917E0(ctx, base);
  {
    std::lock_guard lock(g_lock);
    if (!g_unloaded.erase(o)) return;
  }
  if (const uint32_t r = NewRequest(ctx, base, o)) {
    RequestDefaults(base, r);
    REXLOG_INFO("[pworm] {:08X} preload request for shot ({}, {:#x}) at {:08X}", o, kShotCategory, kShotId, r);
  } else {
    REXLOG_INFO("[pworm] {:08X} preload request failed (no allocator yet?)", o);
  }
}

// Spawn setup (slot 2): small worms get gravity and floor collision.
REX_EXTERN(sub_893915A0) {
  using namespace poison_worm;
  const uint32_t o = ctx.r3.u32;
  __imp__sub_893915A0(ctx, base);
  // Poison on contact, natively: the body flags at +0x1DC (set through vtable
  // +0x220, 0x40000029 after the Bat's setup) are the attack attributes the
  // player's damage routine 8244BF10 receives in r7, which maps 0x4000 -> poison,
  // 0x2000 -> curse (tested 2026-11-20), and a third bit -> stone. CotM: both
  // the mass and the small worms poison.
  rex::memory::store_and_swap<uint32_t>(base + o + 0x1DC, Read(base, o + 0x1DC) | kPoisonTouch);
  std::lock_guard lock(g_lock);
  if (g_worms.empty() && g_new_children.empty()) g_tuning = LoadTuning();   // a stage's first worm
  if (g_new_children.erase(o)) {
    GiveGravity(base, o);
    g_worms[o].child = true;
  }
}

// Per-frame update (slot 7).
REX_EXTERN(sub_893917E8) {
  using namespace poison_worm;
  const uint32_t o = ctx.r3.u32;
  // A hit that doesn't kill (the game's slot-31 callback sets +0x44D2) would switch
  // the Bat to state 1 and fly it with animation 1 (the small worm's falling frames);
  // its death then starts the game's death effect from that frame: "just a single
  // worm flying away weirdly" (user, 2026-11-20). The mass stays a mass: the hit is
  // absorbed here, so it keeps hanging and releasing, and dies from its own frame.
  const float frame = float(ctx.f1.f64);
  const float dt = frame > 0 && frame < 1 ? frame : 1.0f / 60;
  const bool hanging = !base[o + 0x44D1] && Read(base, o + 0x44C0) == 0;
  bool is_parent;
  {
    std::lock_guard lock(g_lock);
    auto it = g_worms.find(o);
    is_parent = it != g_worms.end() && !it->second.child && it->second.started;
  }
  if (base[o + 0x44D2] && !base[o + 0x44D3] && hanging) {
    base[o + 0x44D2] = 0;
    if (is_parent && g_tuning.shots) {                   // CotM: a hit throws worm-chunk debris
      for (int k = 0; k < g_tuning.hit_debris; ++k) ThrowDebris(ctx, base, o);
    }
    if (g_tuning.log_frames) REXLOG_INFO("[pworm] {:08X} hit (stays hanging)", o);
  }
  // CotM death (0x080582EC): stop, sink 0.5 px/frame, debris and explosions every
  // 6 ticks for 60 ticks; then the Bat's own death (hide, the game's death effect)
  // is the final puff. Collision goes off at once (+0x229, as the Bat's death does).
  if (base[o + 0x44D3] && hanging && is_parent && g_tuning.shots) {
    bool done = false;
    {
      std::lock_guard lock(g_lock);
      auto& w = g_worms[o];
      if (!w.dying) {
        w.dying = true;
        w.death_t = 0;
        w.debris_t = g_tuning.death_debris_gap - 2.0f / kFrame;   // CotM: tick % 6 == 2
        w.explode_t = g_tuning.death_debris_gap - 1.0f / kFrame;  // CotM: tick % 6 == 1
        base[o + 0x229] = 0;
        for (int k = 0; k < g_tuning.death_debris_first; ++k) ThrowDebris(ctx, base, o);
        if (g_tuning.log_frames) REXLOG_INFO("[pworm] {:08X} dies: sinking", o);
      }
      w.death_t += dt;
      w.debris_t += dt;
      w.explode_t += dt;
      if (w.explode_t >= g_tuning.death_debris_gap) {
        w.explode_t -= g_tuning.death_debris_gap;
        Explode(ctx, base, o);
      }
      if (w.debris_t >= g_tuning.death_debris_gap) {
        w.debris_t -= g_tuning.death_debris_gap;
        ThrowDebris(ctx, base, o);
      }
      done = w.death_t >= g_tuning.death_time;
    }
    Float(base, o + 0xAC, 0.0f);
    Float(base, o + 0xB0, done ? 0.0f : g_tuning.death_sink);
    if (!done) {
      const uint32_t sprite = Read(base, o + 0x2B8);
      if (sprite) std::memcpy(base + sprite + 0xC4, base + sprite + 0x40, 8);
      return;                                            // the Bat's death waits until the sink ends
    }
    if (g_tuning.log_frames) REXLOG_INFO("[pworm] {:08X} death sink over: final puff", o);
  }
  const bool normal = !base[o + 0x44D1] && !base[o + 0x44D2] && !base[o + 0x44D3] && Read(base, o + 0x44C0) == 0;
  if (!normal) {                                         // hit, dying, ...: the Bat's own code
    {
      std::lock_guard lock(g_lock);
      g_worms.erase(o);
    }
    __imp__sub_893917E8(ctx, base);
    return;
  }
  {
    std::lock_guard lock(g_lock);
    auto& w = g_worms[o];
    if (w.child) ChildFrame(ctx, base, o, w, dt);
    else ParentFrame(ctx, base, o, w, dt);
  }
  const uint32_t sprite = Read(base, o + 0x2B8);         // as the Bat's update ends
  if (sprite) std::memcpy(base + sprite + 0xC4, base + sprite + 0x40, 8);
}
