// Cerberus (CotM boss, enemy 68) inside its own boss module, DLL_Cm068 (test builds
// only; CMake HARMONYRECOMP_POISONWORM). The module is Legion's (DLL_Region) at the DLC
// bosses' shared base 0x8BF00000 (modding/tools/cerberus_module.py); behaviour from
// modding/research/cerberus/CERBERUS_SPEC.md (the ROM's own numbers, 60 ticks a second).
//
// While alive this file runs Cerberus instead of Legion's update; Legion's own update
// takes over once the game reports the death (slot 32), so the native boss death runs.
// Build 3 (2026-11-21): stage collision (lands on ledges, walks off them, the laser
// leap aims for the side ledge), the laser beam and the lightning orbs with their bolts
// as puppet shots (dllshotCm068, cerberus_shot_module.cpp): this file runs CotM's
// projectile logic and writes each shot's position and animation into a table in game
// memory; each shot follows its row.
//
// Legion's vtable (0x8BF01E60): slot 1 0x8BF11A18 (queues shot preloads), slot 2 setup
// 0x8BF11B08, slot 7 update 0x8BF12548 (f1 = frame time), slots 31 0x8BF13798 / 32
// 0x8BF13810 the game's hit callbacks (r4 = the box). Base-class fields as in the Bat:
//   +0x9C/+0xA0 player position, +0xA4/+0xA8 own position, +0xAC/+0xB0 velocity (px/s),
//   +0x1C8 shot request list, +0x2C8 the exe enemy object, whose first 10 x 0x84 bytes
//   are Legion's sprite layers (+0x00 animation, +0x1C apply, +0x30 2 = mirrored,
//   +0x5C palette; layers 1-9 draw whatever +0x29 says, so the body sprite gives
//   Legion's animation numbers blank frames).
// Sprite (modding/tools/cerberus_art.py): art faces left; animations as ANIM there.
#include "../generated/dll_cm068/harmonyrecomp_init.h"
#include <rex/filesystem.h>
#include <rex/logging.h>
#include <rex/memory/utils.h>
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <mutex>
#include <random>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

REX_EXTERN(__imp__sub_8BF11A18);
REX_EXTERN(__imp__sub_8BF11B08);
REX_EXTERN(__imp__sub_8BF12090);
REX_EXTERN(__imp__sub_8BF12548);
REX_EXTERN(__imp__sub_8BF13798);
REX_EXTERN(__imp__sub_8BF13810);

namespace cerberus {
namespace {
constexpr float kTick = 1.0f / 60;                // CotM runs its logic once per 60 Hz frame
constexpr float kFx = 1.0f / 65536;               // CotM 16.16 fixed point -> px
constexpr float kPi = 3.14159265f;
constexpr float kGravity = 0x2D82 * kFx;          // leaps (px/tick^2)
constexpr float kWalkGravity = 0x16C1 * kFx;      // walking off a ledge, the orbs' rise
constexpr float kArena = 180.0f;                  // CotM keeps the body within 64..448 of a 512 px room
constexpr float kWall = 190.0f;                   // airborne limit from the room centre (220 pushed into walls)
constexpr float kWake = 160.0f;                   // CotM wakes within 112 px once the fight starts

// Body FRAMES (cerberus_art.poses order). Legion's layers take a frame number at +0x00,
// not an animation (calibration clip cerberus_test.mp4, 2026-11-21: request N showed frame
// N; Legion steps its own frames), so this file animates Cerberus frame by frame.
enum Frame : uint16_t { kFWalk = 0, kFWalkOpen = 8, kFRaised = 16, kFUp = 17, kFCrouch = 18, kFCrouchOpen = 19,
                        kFLeap = 20, kFLowered = 21, kFAimOpen = 22, kFAimClosed = 53, kFBlank = 84 };
constexpr int kWalkTicks[8] = {16, 10, 10, 12, 16, 10, 10, 12};   // the walk script (body steps 0-8)
constexpr int kRearTicks[5] = {10, 13, 20, 13, 10};                  // the howl (body steps 9-14)
constexpr uint16_t kRearFrames[5] = {kFWalk, kFRaised, kFUp, kFRaised, kFWalk};
constexpr int kAimFrames = 31;                    // beam angle 0x2400 ... -0x1800 by 0x200 (cerberus_art.HEAD_ANGLES)
// Shot animations (cerberus_art.SHOT_ANIM)
enum ShotAnim : uint32_t { kSmall = 0, kSmallFade = 6, kOrb = 12, kFlare = 13, kPuff = 14, kFlash = 15,
                           kBolt = 16, kBeamHit = 20, kBeam = 21, kExplosion = 24 };
constexpr int kBeamPieces = 25;                   // hit boxes 16 px apart: CotM's 50 boxes 8 px apart, 400 px
constexpr float kBeamPiece = 64.0f;               // the beam frame's length (cerberus_art.BEAM_PIECE)
constexpr int kRearTotal = 10 + 13 + 20 + 13 + 10;
constexpr int kWalkCycle = 16 + 10 + 10 + 12 + 16 + 10 + 10 + 12;
enum Mode { kSleep, kWalkLoop, kPick, kLaser, kOrbs, kDead };

// Game services
constexpr uint32_t kAlloc = 0x8BF31564, kFree = 0x8BF31568;   // allocator / free the game writes into Legion's globals
constexpr uint32_t kFloorPush = 0x823C2D80;      // exe: (x, y) -> px up out of a floor or ledge (0: none)
constexpr uint32_t kCeilingPush = 0x823C29C8;    // exe: the same against ceilings (0: none)
constexpr float kHead = 64.0f;                    // the top of Cerberus above its feet
constexpr uint32_t kStageMap = 0x8291D918;
constexpr uint32_t kRequest = 0x3C;
constexpr uint32_t kShotCategory = 0xB, kShotId = 0x4068;     // dllshotCm068
// The orbs and bolts are shots of Charlotte's Lightning Orb itself (dllshotLearnCm068,
// learningset 26), as 8-bit Fishmen fire R. Fireball's own module: her guard catches and
// learns only such spell shots (2026-11-21: the dllshotCm068 orbs passed through it). They
// follow the same rows: the request's +0x18 (table | row) lands in the shot wrapper's +0x170
// (8248DB90), where cerberus_orb_spell.h reads it.
constexpr uint32_t kSpellCategory = 8, kSpellId = 26;
constexpr uint32_t kRemove = 0xFFFFFFFF;
constexpr int kRows = 64;
constexpr uint32_t kHarmless = 0x40000000, kBeamAttack = 0x4000000A, kLightning = 0x4000040A;

struct Orb {
  bool live = false, done = true;
  int row = -1, phase = 0, t = 0, dir = 1, wave = 0, bolt_t = 0;
  float x = 0, y = 0, vx = 0, vy = 0, base_y = 0;
};
struct Bolt { int row; float x, y; int t, gen; int order[4]; };

struct Cerb {
  bool started = false, awake = false, hit = false, dead = false;
  float x0 = 0, floor = 0;            // room centre (spawn x) and floor (spawn y)
  float x = 0, y = 0, vx = 0, vy = 0; // px, px/tick
  bool falling = false;
  int facing = -1;                    // -1 left (the art), +1 right
  Mode mode = kSleep;
  int step = 0, t = 0;                // sub-state and its tick counter
  int cycles = 0, walk_t = 0, mouth_t = 0;
  int attack = 0, next = 0;           // AI state 0 walk/leap, 1 laser, 2 orbs
  bool used[3] = {};
  int angle = 0;                      // head angle (CotM units, 0x10000 = 360 degrees)
  bool mouth = false;
  float target_x = 0;
  int shake = 0;
  float acc = 0;
  uint16_t anim = 0xFFFF;
  int palette = 0;
  // puppet shots
  uint32_t table = 0;
  bool row_used[kRows] = {};
  int row_cool[kRows] = {};
  int beam[kBeamPieces];
  int beam_vis = -1;
  int beam_mode = 0;
  int flash = -1, flash_t = 0;
  Orb orbs[2];
  std::vector<Bolt> bolts;
  int logged = 0, frames = 0, dead_frames = 0, shots = 0;
  int calib = 0, forced_anim = -1;                // calibration mode (cerberus_tuning.txt)
  int death_t = 0;                                 // ticks into the CotM death
  std::vector<std::pair<int, int>> booms;          // death explosions: (row, ticks)
  Cerb() { std::fill(std::begin(beam), std::end(beam), -1); }
};

std::mutex g_lock;
std::unordered_map<uint32_t, Cerb> g_cerbs;
std::unordered_set<uint32_t> g_preloaded;
std::mt19937 g_rng{0x43455242};

uint32_t Read(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
void Put(uint8_t* base, uint32_t a, uint32_t v) { rex::memory::store_and_swap<uint32_t>(base + a, v); }
float Float(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Read(base, a)); }
void Float(uint8_t* base, uint32_t a, float v) { Put(base, a, std::bit_cast<uint32_t>(v)); }
int Random(int n) { return std::uniform_int_distribution<int>(0, n - 1)(g_rng); }

struct Env { const PPCContext& ctx; uint8_t* base; uint32_t o; };

uint32_t CallGuest(const PPCContext& caller, uint8_t* base, uint32_t fn, uint32_t r3, uint32_t r4 = 0,
                   uint32_t r5 = 0, uint32_t r6 = 0) {
  PPCContext ctx = caller;
  ctx.r1.u32 = caller.r1.u32 - 0x200;
  rex::memory::store_and_swap<uint32_t>(base + ctx.r1.u32, caller.r1.u32);
  ctx.r3.u64 = r3; ctx.r4.u64 = r4; ctx.r5.u64 = r5; ctx.r6.u64 = r6;
  REX_CALL_INDIRECT_FUNC(fn);
  return ctx.r3.u32;
}

// Pixels a point must move up to leave a floor or ledge (negative), 0 in the open
// (shield_rod.cpp FloorPush; flag 0 counts one-way ledges).
int FloorPush(const Env& e, float x, float y) {
  if (!Read(e.base, kStageMap) || !std::isfinite(x) || !std::isfinite(y)) return 0;
  return int32_t(CallGuest(e.ctx, e.base, kFloorPush, uint32_t(int32_t(std::floor(x))),
                           uint32_t(int32_t(std::floor(y)))));
}
bool Ceiling(const Env& e, float x, float y) {
  if (!Read(e.base, kStageMap) || !std::isfinite(x) || !std::isfinite(y)) return false;
  return CallGuest(e.ctx, e.base, kCeilingPush, uint32_t(int32_t(std::floor(x))), uint32_t(int32_t(std::floor(y)))) != 0;
}

const char* ModeName(Mode m) {
  switch (m) {
    case kSleep: return "sleep"; case kWalkLoop: return "walk/leap"; case kPick: return "pick";
    case kLaser: return "laser"; case kOrbs: return "orbs"; default: return "dead";
  }
}

void Go(Cerb& c, Mode m, int step) {
  if (c.logged < 400) {
    ++c.logged;
    REXLOG_INFO("[cerb] {} {} -> {} {} at ({:.0f}, {:.0f})", ModeName(c.mode), c.step, ModeName(m), step, c.x, c.y);
  }
  c.mode = m; c.step = step; c.t = 0;
}
void Next(Cerb& c) { Go(c, c.mode, c.step + 1); }
void Face(Cerb& c, float px) { c.facing = px >= c.x ? 1 : -1; }

// ---- shot requests and the puppet table ------------------------------------------------
uint32_t NewRequest(const Env& e) {
  uint8_t* base = e.base;
  const uint32_t v = e.o + 0x1C8;
  const uint32_t begin = Read(base, v + 4), end = Read(base, v + 8), cap = Read(base, v + 0xC);
  uint32_t at = 0;
  if (begin && end >= begin && cap >= end + kRequest) {
    at = end;
  } else {
    const uint32_t alloc = Read(base, kAlloc), release = Read(base, kFree);
    if (!alloc) return 0;
    const uint32_t size = begin ? (end - begin) / kRequest : 0;
    const uint32_t count = std::max<uint32_t>(8, size * 2);
    const uint32_t fresh = CallGuest(e.ctx, base, alloc, count * kRequest);
    if (!fresh) return 0;
    if (size) std::memcpy(base + fresh, base + begin, size * kRequest);
    if (begin && release) CallGuest(e.ctx, base, release, begin);
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
  Put(base, r + 0x28, kHarmless);
  Float(base, r + 0x2C, 5.0f);
  base[r + 0x30] = 1;
  Float(base, r + 0x34, -1.0f);
  Put(base, r + 0x38, 0xFFFFFFFF);
}

uint32_t Row(const Cerb& c, int row) { return c.table + 32 * row; }

// Tuning, read once from cerberus_tuning.txt next to the exe ("key = value").
struct Tuning {
  float beam_rotation_sign = 1.0f;   // the layer rotation's direction (+: clockwise, y down); unverified
  float beam_length = 400.0f;        // px (CotM's boxes reach 400 px)
  int anim_bias = 16;                // added to every body animation number (see SetAnimation)
  bool calibrate = false;            // show animations 0-127 in turn, position = 3 px per number
};
Tuning g_tuning;
bool g_tuned = false;
void LoadTuning() {
  if (g_tuned) return;
  g_tuned = true;
  std::ifstream in(rex::filesystem::GetExecutableFolder() / "cerberus_tuning.txt");
  std::string line;
  while (std::getline(in, line)) {
    const auto eq = line.find('=');
    if (eq == std::string::npos || line.empty() || line[0] == '#') continue;
    auto key = line.substr(0, eq);
    key.erase(key.find_last_not_of(" 	") + 1);
    const float v = std::strtof(line.c_str() + eq + 1, nullptr);
    if (key == "beam_rotation_sign") g_tuning.beam_rotation_sign = v;
    else if (key == "beam_length") g_tuning.beam_length = v;
    else if (key == "anim_bias") g_tuning.anim_bias = int(v);
    else if (key == "calibrate") g_tuning.calibrate = v != 0;
  }
  REXLOG_INFO("[cerb] tuning: beam_rotation_sign {} beam_length {} anim_bias {} calibrate {}", g_tuning.beam_rotation_sign,
              g_tuning.beam_length, g_tuning.anim_bias, g_tuning.calibrate);
}

void SetRow(const Env& e, Cerb& c, int row, float x, float y, uint32_t anim, bool mirrored) {
  if (row < 0 || !c.table) return;
  const uint32_t r = Row(c, row);
  Float(e.base, r + 0, x);
  Float(e.base, r + 4, y);
  Put(e.base, r + 8, anim);
  Put(e.base, r + 12, mirrored ? 1 : 0);
}

void SetRowTransform(const Env& e, Cerb& c, int row, float rotation, float sx, float sy) {
  if (row < 0 || !c.table) return;
  const uint32_t r = Row(c, row);
  Float(e.base, r + 16, rotation);
  Float(e.base, r + 20, sx);
  Float(e.base, r + 24, sy);
}

void Remove(const Env& e, Cerb& c, int& row) {
  if (row < 0) return;
  if (c.table) Put(e.base, Row(c, row) + 8, kRemove);
  c.row_used[row] = false;
  c.row_cool[row] = 30;                               // ticks before reuse: the shot reads the removal first
  row = -1;
}

// One shot following a new row. power x the row's attack; attrs = the shot's touch attributes.
int Spawn(const Env& e, Cerb& c, float x, float y, uint32_t anim, bool mirrored, uint32_t attrs, float power,
          bool spell = false) {
  uint8_t* base = e.base;
  if (!c.table) {
    const uint32_t alloc = Read(base, kAlloc);
    if (!alloc) return -1;
    const uint32_t raw = CallGuest(e.ctx, base, alloc, kRows * 32 + 0x100);
    if (!raw) return -1;
    c.table = (raw + 0xFF) & ~0xFFu;                  // row number in the low byte of the request marker
    for (int k = 0; k < kRows; ++k) {
      std::memset(base + Row(c, k), 0, 32);
      Put(base, Row(c, k) + 8, kRemove);
    }
    REXLOG_INFO("[cerb] {:08X} puppet table at {:08X}", e.o, c.table);
  }
  int row = -1;
  for (int k = 0; k < kRows; ++k)
    if (!c.row_used[k] && c.row_cool[k] == 0) { row = k; break; }
  if (row < 0) return -1;
  const uint32_t r = NewRequest(e);
  if (!r) return -1;
  SetRow(e, c, row, x, y, anim, mirrored);
  SetRowTransform(e, c, row, 0.0f, 1.0f, 1.0f);
  c.row_used[row] = true;
  RequestDefaults(base, r);
  Float(base, r + 0x00, x);
  Float(base, r + 0x04, y);
  Put(base, r + 0x18, c.table | uint32_t(row));
  if (spell) {
    Put(base, r + 0x10, kSpellCategory);
    Put(base, r + 0x14, kSpellId);
  }
  Put(base, r + 0x20, 0);
  Float(base, r + 0x24, Float(base, e.o + 0x1F0) * power);   // vtable +0x260: the row's attack
  Put(base, r + 0x28, attrs);
  Float(base, r + 0x2C, Float(base, e.o + 0x1E0));
  base[r + 0x30] = 0;                                 // registry path, as Legion
  Float(base, r + 0x34, 65.536f * 18.0f);
  const uint32_t owner = Read(base, e.o + 0x2C8);
  Put(base, r + 0x38, owner ? Read(base, owner + 0x18) : 0xFFFFFFFF);
  if (c.shots++ < 30) REXLOG_INFO("[cerb] shot row {} anim {} at ({:.0f}, {:.0f}){}", row, anim, x, y, spell ? " (Lightning Orb shot)" : "");
  return row;
}

void RemoveAll(const Env& e, Cerb& c) {
  for (int& r : c.beam) Remove(e, c, r);
  Remove(e, c, c.beam_vis);
  Remove(e, c, c.flash);
  for (Orb& o : c.orbs) { Remove(e, c, o.row); o.live = false; o.done = true; }
  for (Bolt& b : c.bolts) Remove(e, c, b.row);
  c.bolts.clear();
}

// ---- sounds ------------------------------------------------------------------------------
// The voice bank VX_ENEMY_CERBERUS (package 10, cerberus_audio.py) is loaded by the game
// through vtable slot 103 (see sub_8BF13F90 below). A cue plays when the module appends
// {cue name, x, y} to its list at +0xFC (+0x100 begin, +0x104 end, +0x108 capacity end), as
// 8-bit Dracula does (0x8BF13E34).
enum Cue { kSndHowl, kSndLeap, kSndGrowl, kSndLand, kSndLaser, kSndFlare, kSndDeath, kCueCount };
constexpr const char* kCueNames[kCueCount] = {"VX_EN_CERB_HOWL", "VX_EN_CERB_LEAP", "VX_EN_CERB_GROWL",
                                              "VX_EN_CERB_LAND", "VX_EN_CERB_LASER", "VX_EN_CERB_FLARE",
                                              "VX_EN_CERB_DEATH"};
uint32_t g_cue_names[kCueCount] = {};

void Sound(const Env& e, const Cerb& c, Cue cue) {
  uint8_t* base = e.base;
  if (!g_cue_names[0]) {                              // the names, once, in game memory
    const uint32_t alloc = Read(base, kAlloc);
    if (!alloc) return;
    const uint32_t mem = CallGuest(e.ctx, base, alloc, 32 * kCueCount);
    if (!mem) return;
    for (int k = 0; k < kCueCount; ++k) {
      std::memset(base + mem + 32 * k, 0, 32);
      std::memcpy(base + mem + 32 * k, kCueNames[k], std::strlen(kCueNames[k]));
      g_cue_names[k] = mem + 32 * k;
    }
  }
  const uint32_t v = e.o + 0xFC;
  uint32_t begin = Read(base, v + 4), end = Read(base, v + 8), cap = Read(base, v + 0xC);
  if (!begin || end + 12 > cap) {                     // grow the list (Dracula: 0x8BF17E80)
    const uint32_t alloc = Read(base, kAlloc), release = Read(base, kFree);
    if (!alloc) return;
    const uint32_t size = begin ? (end - begin) : 0;
    const uint32_t bytes = std::max<uint32_t>(12 * 8, size * 2);
    const uint32_t fresh = CallGuest(e.ctx, base, alloc, bytes);
    if (!fresh) return;
    if (size) std::memcpy(base + fresh, base + begin, size);
    if (begin && release) CallGuest(e.ctx, base, release, begin);
    begin = fresh; end = fresh + size; cap = fresh + bytes;
    Put(base, v + 4, begin);
    Put(base, v + 0xC, cap);
  }
  Put(base, end + 0, g_cue_names[cue]);
  Float(base, end + 4, c.x);
  Float(base, end + 8, c.y - 32.0f);
  Put(base, v + 8, end + 12);
  static int logged = 0;
  if (logged++ < 40) REXLOG_INFO("[cerb] sound {}", kCueNames[cue]);
}

// ---- death (CotM 0x0866FBA0: X0-X2) ---------------------------------------------------
// Rears up and howls (sound 0x186), holds it while flashing and bursting with explosions
// (2 every 4 ticks around the body), then flickers out. Legion's own death runs alongside
// (it ends the fight and brings the boss chest, user 2026-11-21), but its layers stay
// hidden, its shots are dropped and Cerberus does not sink with it.
constexpr int kDeathFlicker = 330, kDeathGone = 450, kDeathBooms = 420;
bool DeathShown(const Cerb& c) {
  const int t = c.death_t;
  if (t < kDeathFlicker) return true;
  if (t >= kDeathGone) return false;
  const int period = std::max(2, 12 - (t - kDeathFlicker) / 12);
  return (t / period) % 2 == 0;
}

void DeathTick(const Env& e, Cerb& c) {
  if (++c.death_t == 1) Sound(e, c, kSndDeath);        // X0: death howl 0x186
  for (auto& [row, t] : c.booms)
    if (++t >= 32) Remove(e, c, row);
  std::erase_if(c.booms, [](const auto& b) { return b.first < 0; });
  if (c.death_t % 4 == 0 && c.death_t < kDeathBooms) {
    for (int k = 0; k < 2; ++k) {
      const float bx = c.x + float(Random(81) - 40), by = c.y - 30.0f + float(Random(43) - 24);
      const int row = Spawn(e, c, bx, by, kExplosion, Random(2), kHarmless, 0.0f);
      if (row >= 0) c.booms.push_back({row, 0});
    }
  }
}

// ---- movement ---------------------------------------------------------------------------
// Leaps, hops and falls: gravity, land on whatever floor or ledge is below (only while
// coming down: ledges are one-way), stop at the room's walls. True on landing.
bool Airborne(const Env& e, Cerb& c, float gravity = kGravity) {
  c.vy += gravity;
  c.x += c.vx; c.y += c.vy;
  if (std::fabs(c.x - c.x0) > kWall) { c.x = c.x0 + std::copysign(kWall, c.x - c.x0); c.vx = 0; }
  if (c.vy < 0 && Ceiling(e, c.x, c.y - kHead)) {    // bumped the ceiling: fall back (build 3 left the room)
    c.y -= c.vy;
    c.vy = 0;
  }
  if (c.vy > 0) {
    const int push = FloorPush(e, c.x, c.y);
    if (push < 0 && push > -24) { c.y += push; c.vx = c.vy = 0; return true; }
    if (c.y >= c.floor + 64) { c.y = c.floor; c.vx = c.vy = 0; return true; }   // never lost below the room
  }
  return false;
}

// The laser ledge at x: the second ledge up from the arena floor (user, 2026-11-21: "the
// jump only takes it to the second platform for laser attack"); the first if there is
// only one; the current height if none. Stops at the ceiling.
float LaserLedge(const Env& e, const Cerb& c, float x) {
  float tops[2];
  int found = 0;
  for (float y = c.floor - 8; y > c.floor - 240 && found < 2; y -= 4) {
    if (Ceiling(e, x, y)) break;
    const int push = FloorPush(e, x, y);
    if (push < 0) {
      tops[found++] = y + push;
      y += push;                                      // continue above this ledge
    }
  }
  return found == 2 ? tops[1] : found == 1 ? tops[0] : c.y;
}

bool OnFloor(const Cerb& c) { return c.y >= c.floor - 2; }

// A jump landing at (tx, ty) coming down from 20 px above the higher end.
void JumpTo(Cerb& c, float tx, float ty) {
  const float top = std::min(c.y, ty) - 20.0f;
  c.vy = -std::sqrt(2 * kGravity * (c.y - top));
  const float up = -c.vy / kGravity;
  const float down = std::sqrt(2 * (ty - top) / kGravity);
  c.vx = (tx - c.x) / (up + down);
}

int WalkFrame(int t) {
  for (int k = 0; k < 8; ++k) {
    if (t < kWalkTicks[k]) return k;
    t -= kWalkTicks[k];
  }
  return 0;
}

// The aim frame for the current head angle: the head is drawn along the beam (head angle +
// 0x1000, CotM's offset), as CotM shows it (user's video, 2026-11-21).
// The drawn head angle eases between the head's resting angle and the beam's: while the
// head rises (B6) it turns 0 -> the beam's start (0x2400), while the beam is on it follows
// the beam, and after (B9) it turns back from the beam's end (-0x1800) to 0, so there is
// no 22.5 degree snap at either end (user's cerberus4.mp4).
int DrawAngle(const Cerb& c) {
  if (c.mode == kLaser && c.step == 6) return c.angle * 0x2400 / 0x1400;
  if (c.mode == kLaser && c.step == 9 && c.t >= 8) return c.angle * 0x1800 / 0x2800;
  return c.angle + 0x1000;
}
int AimIndex(const Cerb& c) { return std::clamp((0x2400 - DrawAngle(c) + 0x100) / 0x200, 0, kAimFrames - 1); }

// The open mouth of the drawn aim frame: 34 px ahead of and 4 px below the head's anchor,
// turned with the head.
void Mouth(const Cerb& c, float& mx, float& my) {
  const float a = (0x2400 - 0x200 * AimIndex(c)) / 65536.0f * 2 * kPi;
  const float cs = std::cos(a), sn = std::sin(a);
  mx = c.x + 20.0f * c.facing + c.facing * (34 * cs - 4 * sn);
  my = c.y - 38.0f + 34 * sn + 4 * cs;
}

// CotM walk step (0x0809A610): 0.5 px/tick by facing, but only on the stepping frames
// (not walk frames 0 and 4, where the feet are planted); turns at the arena's ends;
// random mouth opening for 16 ticks; walking off a ledge falls (gravity 0x16C1).
void WalkStep(const Env& e, Cerb& c) {
  if (c.mouth_t > 0) --c.mouth_t;
  else if (Random(128) == 0) c.mouth_t = 16;
  if (c.falling) {
    if (Airborne(e, c, kWalkGravity)) c.falling = false;
    return;
  }
  if (c.x <= c.x0 - kArena) c.facing = 1;
  if (c.x > c.x0 + kArena) c.facing = -1;
  const int f = WalkFrame(c.walk_t);
  if (f != 0 && f != 4) c.x += 0.5f * c.facing;
  if (FloorPush(e, c.x, c.y + 2) == 0) { c.falling = true; c.vx = 0.5f * c.facing; c.vy = 0; }
}

// The attack after a rear-up (C2): from the current one, prefer the other attack not yet
// used; both new or both used: either (CotM table 0x081017C5).
int PickNext(Cerb& c) {
  static const int other[3][2] = {{1, 2}, {0, 2}, {0, 1}};
  const int a = other[c.attack][0], b = other[c.attack][1];
  if (c.used[a] != c.used[b]) return c.used[a] ? b : a;
  return Random(2) ? b : a;
}

// ---- the laser (emitter 0x176) ----------------------------------------------------------
// Beam angle = head angle + 0x1000 (positive = down), mirrored when facing left; it starts
// 32 px out from the head's anchor (body frame 25: (20, -38)). One shot draws it: a 64 px
// straight frame stretched to the beam's length and turned to its angle (layer +0x38 /
// +0x50, as Legion's laser). While it damages (mode 2), invisible box shots every 16 px
// along it carry the hits (CotM: 50 boxes 8 px apart).
void Beam(const Env& e, Cerb& c, int mode) {
  if (mode != 2)
    for (int& r : c.beam) Remove(e, c, r);
  if (mode == 0) {
    Remove(e, c, c.beam_vis);
    c.beam_mode = 0;
    return;
  }
  const int a = c.angle + 0x1000;
  const float rad = a / 65536.0f * 2 * kPi;
  const float dx = std::cos(rad) * c.facing, dy = std::sin(rad);
  float ox, oy;
  Mouth(c, ox, oy);                                   // CotM: 32 px out along the beam (0x0809C510)
  const uint32_t anim = kBeam + (mode == 3 ? 0 : mode == 2 ? 1 : 2);
  const float rotation = g_tuning.beam_rotation_sign * std::atan2(dy, dx);
  if (c.beam_vis < 0) c.beam_vis = Spawn(e, c, ox, oy, anim, false, kHarmless, 0.0f);
  SetRow(e, c, c.beam_vis, ox, oy, anim, false);
  SetRowTransform(e, c, c.beam_vis, rotation, g_tuning.beam_length / kBeamPiece, 1.0f);
  if (mode == 2) {
    for (int i = 0; i < kBeamPieces; ++i) {
      const float px = ox + dx * (8 + 16 * i), py = oy + dy * (8 + 16 * i);
      if (c.beam[i] < 0) c.beam[i] = Spawn(e, c, px, py, kBeamHit, false, kBeamAttack, 1.0f);
      else SetRow(e, c, c.beam[i], px, py, kBeamHit, false);
    }
  }
  if (c.beam_mode != mode && c.logged < 400) {
    ++c.logged;
    REXLOG_INFO("[cerb] beam mode {} angle {:#x} rotation {:.3f} from ({:.0f}, {:.0f})", mode, a & 0xFFFF, rotation, ox, oy);
  }
  c.beam_mode = mode;
}

// ---- lightning orbs (0x177) and bolts (0x17E) -----------------------------------------
void BoltColumn(const Env& e, Cerb& c, float x, float y, int gen) {
  Bolt b{-1, x, y, 0, gen, {0, 1, 2, 3}};
  std::shuffle(std::begin(b.order), std::end(b.order), g_rng);
  b.row = Spawn(e, c, x, y, kBolt + b.order[0], Random(2), kLightning, 0.8f, true);
  if (b.row >= 0) c.bolts.push_back(b);
}

void TickBolts(const Env& e, Cerb& c) {
  std::vector<Bolt> spawn;
  for (Bolt& b : c.bolts) {
    ++b.t;
    if (b.t % 3 == 0 && b.t < 12) SetRow(e, c, b.row, b.x, b.y, kBolt + b.order[b.t / 3], Random(2));
    // CotM stops a column after 3 pieces; here it reaches the arena floor (user, 2026-11-21)
    if (b.t == 3 && b.gen < 12 && b.y + 16 < c.floor) spawn.push_back({-1, b.x, b.y + 32, 0, b.gen + 1, {}});
    if (b.t >= 12) Remove(e, c, b.row);
  }
  std::erase_if(c.bolts, [](const Bolt& b) { return b.row < 0; });
  for (const Bolt& s : spawn) BoltColumn(e, c, s.x, s.y, s.gen);
}

void LaunchOrb(const Env& e, Cerb& c, Orb& o, int dir) {
  o = Orb{};
  o.live = true; o.done = false; o.dir = dir;
  o.x = c.x; o.y = c.y - 32;
  o.vx = dir * 1.25f; o.vy = -3.5f;
  o.row = Spawn(e, c, o.x, o.y, kSmall + 0, false, kLightning, 0.8f, true);
}

void TickOrb(const Env& e, Cerb& c, Orb& o) {
  if (!o.live) return;
  ++o.t;
  uint32_t anim = kOrb;
  auto bob = [&] { o.wave += 0x217; o.y = o.base_y - 8.0f * std::sin(o.wave / 65536.0f * 2 * kPi); };
  switch (o.phase) {
    case 0:                                           // F0 rise until the top of the arc
      o.vy += kWalkGravity; o.x += o.vx; o.y += o.vy;
      anim = kSmall + 0;
      if (o.vy >= 0) { o.base_y = o.y; o.phase = 1; o.t = 0; }
      break;
    case 1:                                           // F1 swell (half size to 1.33), then the blue orb
      anim = kSmall + std::min(o.t, 3);
      if (o.t >= 5) { o.phase = 2; o.t = 0; }
      break;
    case 2:                                           // F2 hover with a bob, then drift
      bob();
      if (o.t >= 30) { o.vx = o.dir * 0.5f; o.phase = 3; o.t = 0; }
      break;
    case 3:                                           // F3 drift; swell and flare; bolts; 360 ticks
      bob();
      o.x += o.vx;
      if (o.t % 128 == 0) o.vx = -o.vx;
      if (o.t >= 45 && o.t < 53) anim = kSmall + (o.t < 48 ? 3 : o.t < 51 ? 4 : 5);
      if (o.t >= 53) {
        if (o.t == 53) Sound(e, c, kSndFlare);       // 0x169
        anim = kFlare;
        if (++o.bolt_t % 12 == 0) {
          const float side = (o.bolt_t % 24 == 0) ? 1.0f : -1.0f;
          BoltColumn(e, c, o.x + side * Random(5), o.y + 32, 0);
        }
      }
      if (o.t >= 360) { o.phase = 4; o.t = 0; }
      break;
    case 4:                                           // F4 shrink away (no box), then gone
      bob();
      o.x += o.vx;
      anim = kSmallFade + std::max(0, 5 - o.t / 4);
      if (o.t >= 24) { Remove(e, c, o.row); o.live = false; o.done = true; return; }
      break;
  }
  SetRow(e, c, o.row, o.x, o.y, anim, false);
}

// ---- the AI (CotM 0x0866FB90 and below) -------------------------------------------------
void Tick(const Env& e, Cerb& c, float px, float py) {
  ++c.t;
  for (int k = 0; k < kRows; ++k) if (c.row_cool[k] > 0) --c.row_cool[k];
  for (Orb& o : c.orbs) TickOrb(e, c, o);
  TickBolts(e, c);
  if (c.flash >= 0 && ++c.flash_t >= 10) Remove(e, c, c.flash);
  switch (c.mode) {
    case kSleep:                                      // A1: face the player; wake by distance or a hit
      Face(c, px);
      if (!c.awake && (c.hit || (std::fabs(px - c.x) < kWake && std::fabs(py - c.y) < 160.0f))) {
        c.awake = true; c.t = 0;
        REXLOG_INFO("[cerb] wakes ({}), player at ({:.0f}, {:.0f})", c.hit ? "hit" : "near", px, py);
      }
      if (c.awake && c.t >= 30) { c.attack = 0; c.used[0] = true; c.cycles = 0; Go(c, kWalkLoop, 2); }
      break;
    case kWalkLoop:
      switch (c.step) {
        case 2:                                       // A2 walk; decisions at each walk cycle's end
          WalkStep(e, c);
          if (!c.falling && ++c.walk_t >= kWalkCycle) {
            c.walk_t = 0;
            ++c.cycles;
            if ((c.cycles & 0xF) == 2) {
              if (c.cycles & 0x80) { Go(c, kPick, 0); break; }
              if (OnFloor(c)) { c.mouth = false; Go(c, kWalkLoop, 4); }   // no leaps from a ledge (user)
            } else if (!OnFloor(c)) {
              // on a ledge: keep walking the same way until it drops off (re-facing a player
              // below kept it pacing on the ledge, cerberus2.mp4)
            } else if (Random(4) == 0) {
              Face(c, px);
            } else {
              Face(c, px); Sound(e, c, kSndGrowl); Go(c, kWalkLoop, 3);
            }
          }
          break;
        case 3:                                       // A3 shake 60 ticks, then leap or walk on
          c.shake = (c.t / 2) % 2 ? 1 : -1;
          if (c.t >= 60) {
            c.shake = 0;
            if (Random(2) && OnFloor(c)) Go(c, kWalkLoop, 4);
            else { Face(c, px); c.walk_t = 0; Go(c, kWalkLoop, 2); }
          }
          break;
        case 4:                                       // A4 wind-up: step forward, open mouth, aim, leap
          Face(c, px);
          if (c.t <= 10) c.x = std::clamp(c.x + 0.5f * c.facing, c.x0 - kArena, c.x0 + kArena);
          if (c.t >= 40) c.mouth = true;
          if (c.t >= 60) {
            float a = std::atan2(py - c.y, px - c.x);           // screen angle, y down
            const float lo = -3 * kPi / 4, hi = -kPi / 4;      // 0xA000..0xE000: up-forward
            if (a < lo || a > hi) a = (c.facing < 0) ? lo : hi;
            c.vx = 8.0f * std::cos(a); c.vy = 8.0f * std::sin(a);
            REXLOG_INFO("[cerb] leap at {:.0f} degrees", a * 57.29578f);
            Sound(e, c, kSndLeap);
            Go(c, kWalkLoop, 5);
          }
          break;
        case 5:                                       // A5-A6 airborne until a floor or ledge
          if (Airborne(e, c)) { Sound(e, c, kSndLand); Go(c, kWalkLoop, 7); }
          break;
        case 7:                                       // A7 land (screen shake, thud 0x167)
          c.mouth = false; Go(c, kWalkLoop, 8);
          break;
        case 8:                                       // A8 recover; two walk cycles later the picker
          if (c.t >= 60) { c.cycles = 0x81; Face(c, px); c.walk_t = 0; Go(c, kWalkLoop, 2); }
          break;
      }
      break;
    case kPick:
      switch (c.step) {
        case 0: c.mouth = false; Next(c); break;                          // C0
        case 1: Face(c, px); if (c.t >= 30) { Sound(e, c, kSndHowl); Next(c); } break;   // C1, howl 0x163
        case 2:                                                           // C2 rear up, choose
          if (c.t >= kRearTotal) {
            c.next = PickNext(c);
            // 0x17D: the coming attack's colours. CotM's laser Cerberus is white (user's
            // capture): the near-white set is HoD palette 2, the pink one 1.
            c.palette = c.next == 1 ? 2 : c.next == 2 ? 1 : 0;
            REXLOG_INFO("[cerb] picks attack {} (used {}{}{})", c.next, c.used[0], c.used[1], c.used[2]);
            Next(c);
          }
          break;
        case 3:                                                           // C3 wait, then the attack
          if (c.t >= 90) {
            c.attack = c.next;
            c.used[c.attack] = true;
            if (c.attack == 0) { c.cycles = 0; c.walk_t = 0; Go(c, kWalkLoop, 2); }
            else if (c.attack == 1) Go(c, kLaser, 0);
            else Go(c, kOrbs, 0);
          }
          break;
      }
      break;
    case kLaser:
      switch (c.step) {
        case 0: {                                     // B0: leap onto the far side's ledge (CotM x 120 / 392)
          c.mouth = true;
          c.target_x = c.x > c.x0 ? c.x0 - 136 : c.x0 + 136;
          const float ty = LaserLedge(e, c, c.target_x);
          c.facing = c.target_x >= c.x ? 1 : -1;
          if (std::fabs(c.target_x - c.x) < 8 && std::fabs(ty - c.y) < 4) { Go(c, kLaser, 3); break; }
          JumpTo(c, c.target_x, ty);
          Sound(e, c, kSndGrowl);                         // 0x165
          REXLOG_INFO("[cerb] laser: jump to ({:.0f}, {:.0f})", c.target_x, ty);
          Next(c);
          break;
        }
        case 1: if (c.t >= 20) { Sound(e, c, kSndLeap); Next(c); } break;  // B1 wind-up, 0x164
        case 2: if (Airborne(e, c)) { Sound(e, c, kSndLand); c.mouth = false; Next(c); } break;  // B2 land
        case 3:                                                           // B3 face the centre, hop
          c.facing = c.x <= c.x0 ? 1 : -1;
          if (c.t >= 10) { c.vx = 0; c.vy = -5.0f; c.mouth = true; Next(c); }
          break;
        case 4: if (Airborne(e, c)) { Sound(e, c, kSndLand); c.mouth = false; Next(c); } break;  // B4 land
        case 5: if (c.t >= 10) { c.angle = 0; Next(c); } break;           // B5 head lowered
        case 6:                                                           // B6 aim down to 0x1400; flash
          if (c.t >= 10) {
            c.angle = std::min(c.angle + 0x80, 0x1400);
            if (c.angle == 0x1400) {
              c.mouth = true;
              float mx, my;
              Mouth(c, mx, my);
              c.flash = Spawn(e, c, mx, my, kFlash, c.facing < 0, kHarmless, 0.0f);
              c.flash_t = 0;
              Next(c);
            }
          }
          break;
        case 7:                                                           // B7 charge (thick beam, harmless)
          if (c.t == 10) Sound(e, c, kSndLaser);        // 0x166 (0xB3 << 1), the hum
          Beam(e, c, 3);
          if (c.t >= 36) Next(c);
          break;
        case 8:                                                           // B8 sweep up to 0xD800 (damaging)
          c.angle = std::max(c.angle - 0x80, -0x2800);
          Beam(e, c, 2);
          if (c.angle == -0x2800) Next(c);
          break;
        case 9:                                                           // B9 thin, off, head back
          if (c.t < 4) Beam(e, c, 2);
          else if (c.t < 8) Beam(e, c, 1);
          else {
            if (c.t == 8) Beam(e, c, 0);
            c.mouth = false;
            c.angle = std::min(c.angle + 0x80, 0);
            if (c.angle == 0) Next(c);
          }
          break;
        case 10:                                                          // B10 hop down toward the middle
          if (c.t >= 10) {
            c.vy = -4.0f;
            c.vx = 2.5f * c.facing;                   // CotM: 0 when the player is near; always off the ledge here
            Sound(e, c, kSndLeap);
            c.mouth = true;
            Next(c);
          }
          break;
        case 11: if (Airborne(e, c)) { Sound(e, c, kSndLand); c.mouth = false; Next(c); } break;
        case 12: if (c.t >= 10) Go(c, kPick, 0); break;
      }
      break;
    case kOrbs:
      switch (c.step) {
        case 0: c.mouth = false; Sound(e, c, kSndGrowl); Next(c); break;     // D0, growl 0x165
        case 1:                                                           // D1 shake; two orbs; rear up
          if (c.t >= 20) c.shake = (c.t / 2) % 2 ? 1 : -1;
          if (c.t >= 60) {
            c.shake = 0;
            LaunchOrb(e, c, c.orbs[0], 1);
            LaunchOrb(e, c, c.orbs[1], -1);
            REXLOG_INFO("[cerb] orbs launched from ({:.0f}, {:.0f})", c.x, c.y - 32);
            Next(c);
          }
          break;
        case 2: if (c.t >= kRearTotal) Next(c); break;                    // D2
        case 3:                                                           // D3 until an orb is done
          c.shake = (c.t / 2) % 2 ? 1 : -1;
          if ((c.orbs[0].done && c.orbs[1].done) || c.t >= 900) { c.shake = 0; Next(c); }
          break;
        case 4: if (c.t >= 20) Go(c, kPick, 0); break;
      }
      break;
    case kDead:
      break;
  }
}

int RearFrame(int t) {
  for (int k = 0; k < 5; ++k) {
    if (t < kRearTicks[k]) return kRearFrames[k];
    t -= kRearTicks[k];
  }
  return kFWalk;
}

uint16_t AnimFor(const Cerb& c) {                     // the body frame to show now
  const uint16_t walk = uint16_t((c.mouth_t > 0 ? kFWalkOpen : kFWalk) + WalkFrame(c.walk_t));
  switch (c.mode) {
    case kSleep: return kFWalk;
    case kWalkLoop:
      switch (c.step) {
        case 2: return c.falling ? kFLeap : walk;
        case 3: return kFCrouch;
        case 4: return c.mouth ? kFCrouchOpen : kFCrouch;
        case 5: return kFLeap;
        default: return kFCrouch;
      }
    case kPick: return c.step == 2 ? uint16_t(RearFrame(c.t)) : kFWalk;
    case kLaser:
      switch (c.step) {
        case 0: return kFCrouchOpen;
        case 1: case 2: case 4: case 11: return kFLeap;
        case 3: case 10: case 12: return kFCrouch;
        case 5: return kFLowered;
        default:
          return uint16_t((c.mouth ? kFAimOpen : kFAimClosed) + AimIndex(c));
      }
    case kOrbs: return c.step == 2 ? uint16_t(RearFrame(c.t)) : kFWalk;   // stands (CotM's crouch read as a jump)
    default: return kFWalk;
  }
}

void SetAnimation(uint8_t* base, uint32_t sprite, Cerb& c, uint16_t anim) {
  if (c.anim == anim) return;
  c.anim = anim;
  static int changes = 0;
  if (changes++ < 60) REXLOG_INFO("[cerb] frame {}", anim);
  Put(base, sprite + 0x00, anim);
  Float(base, sprite + 0x54, 0.0f);
  base[sprite + 0x2B] = 1;
  base[sprite + 0x28] = 0;
  base[sprite + 0x1C] = 1;                                // apply
  Float(base, sprite + 0x10, 1.0f);                       // playback speed
}

void Dump(uint8_t* base, uint32_t o, const char* when) {
  const uint32_t owner = Read(base, o + 0x2C8);
  REXLOG_INFO("[cerb] {:08X} {}: enemy object {:08X}, pos ({:.1f}, {:.1f}), vel ({:.1f}, {:.1f}), "
              "player ({:.1f}, {:.1f}), attack {:.1f}", o, when, owner, Float(base, o + 0xA4), Float(base, o + 0xA8),
              Float(base, o + 0xAC), Float(base, o + 0xB0), Float(base, o + 0x9C), Float(base, o + 0xA0),
              Float(base, o + 0x1F0));
  auto hex = [&](uint32_t a, uint32_t n) {
    std::string s;
    char buf[12];
    for (uint32_t i = 0; i < n; i += 4) {
      std::snprintf(buf, sizeof buf, "%08X ", Read(base, a + i));
      s += buf;
    }
    return s;
  };
  if (owner) {
    for (uint32_t k = 0; k <= 2; ++k)
      REXLOG_INFO("[cerb]   layer {}: {}", k, hex(owner + 0x84 * k, 0x64));
  }
  REXLOG_INFO("[cerb]   legion +0x44C0: {}", hex(o + 0x44C0, 0x30));
  REXLOG_INFO("[cerb]   legion +0x4560: {}", hex(o + 0x4560, 0x20));
}
}  // namespace
}  // namespace cerberus

// Slot 1: Legion's shot preloads, then Cerberus's (category 11, 0x4068), once per object.
REX_EXTERN(sub_8BF11A18) {
  using namespace cerberus;
  const uint32_t o = ctx.r3.u32;
  __imp__sub_8BF11A18(ctx, base);
  if (o < 0x10000) return;
  {
    std::lock_guard lock(g_lock);
    if (!g_preloaded.insert(o).second) return;
  }
  const Env e{ctx, base, o};
  if (const uint32_t r = NewRequest(e)) {
    RequestDefaults(base, r);
    REXLOG_INFO("[cerb] {:08X} preload request for shot ({}, {:#x})", o, kShotCategory, kShotId);
  } else {
    REXLOG_INFO("[cerb] {:08X} preload request failed", o);
  }
  if (const uint32_t r = NewRequest(e)) {                       // the orbs and bolts (Lightning Orb)
    RequestDefaults(base, r);
    Put(base, r + 0x10, kSpellCategory);
    Put(base, r + 0x14, kSpellId);
    REXLOG_INFO("[cerb] {:08X} preload request for shot ({}, {})", o, kSpellCategory, kSpellId);
  }
}

// Vtable slot 103, the voice bank's name (cerberus_module.py points it at this function,
// Legion's attack state 0x8BF13F90, which Cerberus never runs): the module's old debug path,
// patched to "VX_ENEMY_CERBERUS".
REX_EXTERN(sub_8BF13F90) {
  constexpr uint32_t kBankName = 0x8BF02D4C;
  static int logged = 0;
  if (logged++ < 4) REXLOG_INFO("[cerb] voice bank asked for: {}", reinterpret_cast<const char*>(base + kBankName));
  ctx.r3.u64 = kBankName;
}

// Setup (slot 2): Legion's own, then a look at what it made.
REX_EXTERN(sub_8BF11B08) {
  using namespace cerberus;
  const uint32_t o = ctx.r3.u32;
  __imp__sub_8BF11B08(ctx, base);
  {
    std::lock_guard lock(g_lock);
    g_cerbs.erase(o);
  }
  Dump(base, o, "after Legion's setup");
  // Does Legion's setup queue shots (its corpse shell)? Log the request list.
  const uint32_t b = Read(base, o + 0x1CC), end = Read(base, o + 0x1D0);
  if (b && end >= b && end - b < 64 * kRequest)
    for (uint32_t r = b; r < end; r += kRequest)
      REXLOG_INFO("[cerb]   setup request ({}, {:#x}) at ({:.0f}, {:.0f})", Read(base, r + 0x10), Read(base, r + 0x14),
                  Float(base, r + 0x00), Float(base, r + 0x04));
}

// Draw setup (slot 3): Legion's turns its core (layer 0) off and its 30 corpse layers on;
// Cerberus is layer 0 and the corpses stay off from the first frame (the chapter-start
// overview draws before the first update).
REX_EXTERN(sub_8BF12090) {
  using namespace cerberus;
  const uint32_t o = ctx.r3.u32;
  __imp__sub_8BF12090(ctx, base);
  if (const uint32_t layers = Read(base, o + 0x2C8)) {
    base[layers + 0x29] = 1;
    for (uint32_t k = 1; k <= 30; ++k) base[layers + 0x84 * k + 0x29] = 0;
  }
}

// The game's hit callbacks (slot 31 / 32, r4 = the box): any hit wakes Cerberus; slot 32
// (the Bat's death flag; Legion's +0x44D9 path) hands the object to Legion's update.
REX_EXTERN(sub_8BF13798) {
  using namespace cerberus;
  const uint32_t o = ctx.r3.u32, box = ctx.r4.u32;
  {
    std::lock_guard lock(g_lock);
    auto& c = g_cerbs[o];
    c.hit = true;
    if (c.logged < 400) { ++c.logged; REXLOG_INFO("[cerb] {:08X} slot 31 (hit) box {:08X}", o, box); }
  }
  __imp__sub_8BF13798(ctx, base);
}

REX_EXTERN(sub_8BF13810) {
  using namespace cerberus;
  const uint32_t o = ctx.r3.u32, box = ctx.r4.u32;
  {
    std::lock_guard lock(g_lock);
    auto& c = g_cerbs[o];
    c.hit = true;
    if (c.logged < 400) { ++c.logged; REXLOG_INFO("[cerb] {:08X} slot 32 box {:08X}: Legion's death path from here", o, box); }
    if (!c.dead) RemoveAll(Env{ctx, base, o}, c);
    c.dead = true;
  }
  // Legion's corpses are 9 groups; its hit handler (0x8BF12D78) breaks one off per big hit
  // (0x8BF13308: a flying effect drawn with the parent's sprite, i.e. Cerberus copies,
  // build 13's "exploded into multiple") until the "broken" mask +0x44C4 reaches 0x1FF, and
  // then runs the core's own death (0x8BF12F98), which ends the fight and brings the chest.
  // Cerberus has no corpses: mark them all broken so Legion goes straight to its core death.
  Put(base, o + 0x44C4, Read(base, o + 0x44C4) | 0x1FF);
  __imp__sub_8BF13810(ctx, base);
  Put(base, o + 0x44C4, Read(base, o + 0x44C4) | 0x1FF);
  Dump(base, o, "after slot 32");
}

// Per-frame update (slot 7).
REX_EXTERN(sub_8BF12548) {
  using namespace cerberus;
  const uint32_t o = ctx.r3.u32;
  const float frame = float(ctx.f1.f64);
  const float dt = frame > 0 && frame < 1 ? frame : kTick;
  bool dead;
  int frames;
  {
    std::lock_guard lock(g_lock);
    auto& c = g_cerbs[o];
    dead = c.dead;
    frames = ++c.frames;
    if (dead) ++c.dead_frames;
  }
  if (frames == 1 || frames == 600) Dump(base, o, frames == 1 ? "first update" : "600 frames");
  if (dead) {
    Put(base, o + 0x44C4, Read(base, o + 0x44C4) | 0x1FF);   // no corpse breaks (see slot 32)
    __imp__sub_8BF12548(ctx, base);                       // Legion's update: its death and the boss's end
    std::lock_guard lock(g_lock);
    auto& c = g_cerbs[o];
    const uint32_t layers = Read(base, o + 0x2C8);
    if (layers) {
      // Legion's death shows its corpse layers again and queues falling bodies: Cerberus
      // keeps them hidden and drops every request that is not one of its own shots.
      for (uint32_t k = 1; k <= 30; ++k) base[layers + 0x84 * k + 0x29] = 0;
      const uint32_t rb = Read(base, o + 0x1CC), re = Read(base, o + 0x1D0);
      if (rb && re > rb && re - rb < 256 * kRequest) {
        uint32_t keep = rb;
        for (uint32_t r = rb; r < re; r += kRequest)
          if (Read(base, r + 0x14) == kShotId || (Read(base, r + 0x10) == kSpellCategory && Read(base, r + 0x14) == kSpellId)) {
            if (keep != r) std::memmove(base + keep, base + r, kRequest);
            keep += kRequest;
          }
        Put(base, o + 0x1D0, keep);
      }
      const Env e{ctx, base, o};
      c.acc = std::min(c.acc + dt, 4 * kTick);
      while (c.acc >= kTick) { c.acc -= kTick; DeathTick(e, c); }
      const int t = c.death_t;
      base[layers + 0x29] = DeathShown(c) ? 1 : 0;
      SetAnimation(base, layers, c, uint16_t(t < 23 ? RearFrame(t) : kFUp));
      Put(base, layers + 0x30, c.facing > 0 ? 2 : 0);
      const bool flash = t < kDeathGone && (t / 2) % 2;            // CotM: palette bank 14 every other beat
      rex::memory::store_and_swap<uint16_t>(base + layers + 0x5C, uint16_t(flash ? 2 : c.palette));
      Float(base, o + 0xAC, (c.x - Float(base, o + 0xA4)) / dt);   // stays put (Legion sinks)
      Float(base, o + 0xB0, (c.y - Float(base, o + 0xA8)) / dt);
    }
    if (c.dead_frames % 15 == 1 && c.dead_frames < 1200)
      REXLOG_INFO("[cerb] {:08X} dying frame {}: +0x4560 {} +0x4564 {} +0x44C0 {:#x} +0x44D9 {} +0x4658 {} "
                  "+0x466C {} pos ({:.0f}, {:.0f})", o, c.dead_frames, Read(base, o + 0x4560), Read(base, o + 0x4564),
                  Read(base, o + 0x44C0), base[o + 0x44D9], base[o + 0x4658], base[o + 0x466C],
                  Float(base, o + 0xA4), Float(base, o + 0xA8));
    return;
  }
  // Cerberus is layer 0 of the exe object (Legion leaves it hidden); layers 1-9 show
  // Legion's animation numbers, which are blank frames in Cerberus's sprite.
  const uint32_t sprite = Read(base, o + 0x2C8);
  if (sprite) {
    base[sprite + 0x29] = 1;
    // Build 3 still drew Legion's shell with blank animations behind layers 1-9: shrink
    // those layers to nothing (+0x38/+0x3C are each layer's x/y scale, 1.0 from setup).
    // Builds 2-6 still drew the shell: Legion has 31 layers, not 10. Its draw setup
    // (slot 3, 0x8BF12090) writes +0x14 in layers 0-30 (up to +0xF8C) and hides the core
    // with layer 0's +0x29 = 0 (+0x29 = shown); the corpse shell is layers 1-30.
    for (uint32_t k = 1; k <= 30; ++k) {
      const uint32_t l = sprite + 0x84 * k;
      base[l + 0x29] = 0;
      Float(base, l + 0x38, 0.0f);
      Float(base, l + 0x3C, 0.0f);
      if (Read(base, l + 0x00) != kFBlank) {
        Put(base, l + 0x00, kFBlank);
        Float(base, l + 0x54, 0.0f);
        base[l + 0x2B] = 1;
        base[l + 0x28] = 0;
        base[l + 0x1C] = 1;
      }
    }
  }
  std::lock_guard lock(g_lock);
  auto& c = g_cerbs[o];
  const float ax = Float(base, o + 0xA4), ay = Float(base, o + 0xA8);
  if (!c.started) {
    c.started = true;
    c.x0 = c.x = ax;
    c.floor = c.y = ay;
    REXLOG_INFO("[cerb] {:08X} starts at ({:.0f}, {:.0f}): arena {:.0f}..{:.0f}", o, ax, ay, ax - kArena, ax + kArena);
  }
  LoadTuning();
  const float px = Float(base, o + 0x9C), py = Float(base, o + 0xA0);
  const Env e{ctx, base, o};
  c.acc = std::min(c.acc + dt, 4 * kTick);
  while (c.acc >= kTick) {
    c.acc -= kTick;
    if (g_tuning.calibrate && c.calib >= 0) {
      // Calibration: once the player is in the room, stand and show animation N =
      // ticks / 36 for N = 0..127 at x = arena left + 3 N (the clip reads N back).
      if (c.calib == 0 && !(std::fabs(px - c.x0) < 256 && std::fabs(py - c.floor) < 200)) continue;
      const int n = c.calib / 36;
      if (n > 127) { c.calib = -1; REXLOG_INFO("[cerb] calibration done"); continue; }
      if (c.calib % 36 == 0) REXLOG_INFO("[cerb] calibration: animation {} at x {:.0f}", n, c.x0 - 190 + 3 * n);
      c.x = c.x0 - 190 + 3.0f * n;
      c.y = c.floor;
      c.facing = -1;
      ++c.calib;
      c.forced_anim = n;
      continue;
    }
    c.forced_anim = -1;
    Tick(e, c, px, py);
  }
  // The exe moves the object by its velocity: steer it onto the CotM path.
  const float tx = c.x + c.shake;
  Float(base, o + 0xAC, (tx - ax) / dt);
  Float(base, o + 0xB0, (c.y - ay) / dt);
  if (sprite) {
    SetAnimation(base, sprite, c, c.forced_anim >= 0 ? uint16_t(c.forced_anim) : AnimFor(c));
    if (c.mode == kLaser && c.step >= 6 && c.step <= 9 && c.t % 8 == 0 && c.logged < 400) {
      ++c.logged;
      REXLOG_INFO("[cerb] laser step {} t {}: head angle {:#x} aim {} anim {} layer anim {} frame {} mouth {}",
                  c.step, c.t, c.angle & 0xFFFF, AimIndex(c), c.anim, Read(base, sprite + 0x00),
                  Read(base, sprite + 0x08), c.mouth);
    }
    Put(base, sprite + 0x30, c.facing > 0 ? 2 : 0);       // u32, as the Bat: 2 = mirrored (the art faces left)
    rex::memory::store_and_swap<uint16_t>(base + sprite + 0x5C, uint16_t(c.palette));   // attack colours
  }
}
