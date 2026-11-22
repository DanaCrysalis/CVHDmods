// Alucard's attacking familiars (package 21).
//
// Behaviour is SotN's own (sotn-decomp src/servant/tt_001/ghost.c,
// UpdateServantDefault), run in SotN ticks (60 a second):
//  - it hovers 18 px behind Alucard and 32 px above his body centre, bobbing
//    4 px (rsin(bob) >> 10, bob += 32 a tick), steering at most 512/4096 of a
//    turn a tick with speed distance/64 a tick (distance/4 past 256 px);
//  - each tick it looks for an enemy in a box centred on Alucard (SotN's
//    48 px search around the ghost felt too tight in HoD);
//  - it flies at it (distance/8 a tick), clings once within 8 px
//    (distance/2), and attacks every `delay` ticks while clinging. A wisp
//    cloud (servant parts 9-20) starts 30 ticks before each attack;
//  - delay and soul steal come from SotN's table by familiar level/10
//    (120 120 100 100 90 90 75 75 60 ticks; soul steal from index 7). Here
//    the index is the number of Ghost Cards owned (1-9) minus one.
// Damage: a native attack rectangle (as Nathan's NativeHit) owned by Alucard,
// power L1 + (Lmax - L1) * (copies - 1) / 8 then + (P / 64 + 0.25) * INT, the
// game's spell rule. Soul steal heals Alucard a share of it, on his own
// machine only (owner +0x930 == 1), with the native green number.
//
// Online co-op, as Soma's familiars: the familiar runs on every machine for
// every Alucard whose Enchanted slot (equipment word 13) holds the Ghost Card.
// The attack rectangles belong to that Alucard, so HoD applies the damage only
// on his machine and shows the hits and numbers everywhere.
//
// Art: SotN's Ghost frames, appended to Alucard's body sprite by
// modding/tools/familiar_art.py (alucard_familiar_art.h), drawn with a
// pulsing opacity through his own sprite instance (Shield Rod's DrawFrame
// method), after his body draw. The frames' own palettes alternate the
// flame between blue and green.
#include "../generated/default/harmonyrecomp_init.h"
#include "alucard_familiar.h"
#include "alucard_familiar_art.h"
#include "alucard_familiar_balance.h"
#include "alucard_familiar_audio.h"
#include "hurt_record_guest.h"
#include "hod_guest.h"
#include "hod_hooks.h"
#include <rex/logging.h>
#include <rex/memory/utils.h>
#include <rex/system/xmemory.h>
#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <mutex>
#include <numbers>
#include <span>
#include <vector>
#include <string>

REX_EXTERN(__imp__sub_823D2648);

namespace harmony::alucard_familiar {
namespace {
constexpr uint32_t kAlucardVtable = 0x83002DA0;   // dllAlucard player vtable
constexpr float kDepth = 40000;                    // familiar draw depth, above enemies
constexpr int kGhostReach = 16;                    // Ghost hit half-size (8 missed, November 18)
constexpr unsigned kSpriteBytes = 192;
constexpr unsigned kColliderBytes = 832, kColliderTable = 512;
constexpr uint32_t kGameContext = 0x82223348;
// game + 0x1018: the native 0x3B00 save model (823CAC80; Nathan's card code
// reads it here and works in game). 0xFF0 was 0x28 too early, so every card
// count read 1 (user's test, November 18).
constexpr uint32_t kSaveModel = 0x1018;
constexpr uint32_t kInventory = 0x3E8;             // save: one byte per item, copies << 4
constexpr float kTick = 1.0f / 60;
constexpr int kDelay[9] = {120, 120, 100, 100, 90, 90, 75, 75, 60};

uint32_t Read(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
void Write(uint8_t* base, uint32_t a, uint32_t v) { rex::memory::store_and_swap<uint32_t>(base + a, v); }
float Float(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Read(base, a)); }
void Float(uint8_t* base, uint32_t a, float v) { Write(base, a, std::bit_cast<uint32_t>(v)); }

uint32_t EntityOf(uint8_t* base, uint32_t handle) {  // handle -> object (entity manager table)
  const auto manager = Read(base, 0x8291D9F0);
  if (!manager || !handle) return 0;
  const auto table = Read(base, manager + 0xAC), end = Read(base, manager + 0xB0);
  const uint32_t offset = (handle & 0xFFFF) << 4;
  if (!table || end < table || end - table > 65536 * 16 || end - table < 16 || offset > end - table - 16) return 0;
  return Read(base, table + offset) == handle ? Read(base, table + offset + 4) : 0;
}
uint32_t AlucardPlayer(uint8_t* base, uint32_t owner) {
  const auto player = owner && (Read(base, owner + 8) & 2) ? Read(base, owner + 0x924) : 0;
  return player && Read(base, player) == kAlucardVtable ? player : 0;
}
bool Alive(uint8_t* base, uint32_t player) {
  const auto stats = Read(base, player + 88);
  return stats && Float(base, stats + 4) > 0;
}
uint32_t AlignedScratch(uint32_t bytes) {
  const auto raw = REX_KERNEL_MEMORY()->SystemHeapAlloc(bytes + 15);
  return raw ? (raw + 15) & ~15u : 0;
}

// SotN fixed-point helpers (angles in 4096ths of a turn).
int Angle(float dx, float dy) {  // CalculateAngleToEntity: y up
  const int a = int(std::lround(std::atan2(-dy, dx) * 4096 / 6.283185307f));
  return a & 0xFFF;
}
int StepAngle(int target, int current, int step) {
  int d = ((target - current + 2048) & 0xFFF) - 2048;
  if (d > step) d = step; else if (d < -step) d = -step;
  return (current + d) & 0xFFF;
}
float Sin(int a) { return std::sin(a * 6.283185307f / 4096); }
float Cos(int a) { return std::cos(a * 6.283185307f / 4096); }

struct Target {
  uint32_t handle = 0;
  float x = 0, y = 0, x0 = 0, y0 = 0, x1 = 0, y1 = 0;
  uint32_t shape = 0;  // the registered shape object (0 for a union of shapes)
  unsigned region = 0, kind = 1;
  // The registration's call site and record flags. Enemies re-create their
  // shape objects every frame (Dullahan's armour came back at 7021F760,
  // 7024F760, 701BF760 in one fight, run 237), so these, not the shape
  // address, identify one body part from frame to frame.
  uint32_t part = 0, flags = 0;
};

bool IsEnemy(uint8_t* base, uint32_t entity) {
  if (!entity) return false;
  const auto flags = Read(base, entity + 8);
  return (flags & 4) && !(flags & 0x1A);
}

std::string EnemyName(uint8_t* base, uint32_t handle) {
  const auto enemy = EntityOf(base, handle);
  if (!IsEnemy(base, enemy)) return "unknown";
  const auto row = Read(base, enemy + 0xC0);
  if (row < 0x10000 || row > 0xFFFFFFA0u) return "unknown";
  const auto name = reinterpret_cast<const char*>(base + row + 0x50);
  const auto end = static_cast<const char*>(std::memchr(name, 0, 16));
  return std::string(name, end ? end : name + 16);
}

Target HurtBounds(uint8_t* base, uint32_t shape, uint32_t handle, unsigned region) {
  Target box;
  box.kind = Read(base, shape + 4);
  if (box.kind == 1) {
    const float ax = Float(base, shape + 8), ay = Float(base, shape + 12);
    const float bx = Float(base, shape + 16), by = Float(base, shape + 20);
    if (!std::isfinite(ax) || !std::isfinite(ay) || !std::isfinite(bx) || !std::isfinite(by)) return {};
    box.x0 = std::min(ax, bx); box.x1 = std::max(ax, bx);
    box.y0 = std::min(ay, by); box.y1 = std::max(ay, by);
    box.x = (ax + bx) * .5f; box.y = (ay + by) * .5f;
  } else if (box.kind == 2) {
    // Native circle-to-rectangle conversion (823C6928): radius at +8,
    // center at +16/+20.
    const float radius = Float(base, shape + 8);
    box.x = Float(base, shape + 16); box.y = Float(base, shape + 20);
    if (!std::isfinite(radius) || !(radius > 0)) return {};
    box.x0 = box.x - radius; box.x1 = box.x + radius;
    box.y0 = box.y - radius; box.y1 = box.y + radius;
  } else if (box.kind == 3) {
    // 824843C8 stores four world-space vertices in the shape.
    for (unsigned i = 0; i < 4; ++i) {
      const float x = Float(base, shape + 8 + 8 * i), y = Float(base, shape + 12 + 8 * i);
      if (!std::isfinite(x) || !std::isfinite(y)) return {};
      box.x0 = i ? std::min(box.x0, x) : x;
      box.y0 = i ? std::min(box.y0, y) : y;
      box.x1 = i ? std::max(box.x1, x) : x;
      box.y1 = i ? std::max(box.y1, y) : y;
      box.x += x * .25f; box.y += y * .25f;
    }
  } else {
    return {};
  }
  if (!std::isfinite(box.x) || !std::isfinite(box.y) ||
      !std::isfinite(box.x1 - box.x0) || !std::isfinite(box.y1 - box.y0)) return {};
  box.handle = handle;
  box.region = region;
  return box;
}

// Enemy hurt shapes as the game registers them (823C4C40, the Shield Rod
// override, under its collision lock). Enemies register from several game
// threads, so walking the collision manager's lists from the player update
// saw some regions half rebuilt: a Treant in region 0 missing while the Dead
// Warrior behind it (region 40) was there, and a Man-Eating Plant 100 px away
// missing entirely (run 217). A shape counts as live for kShapeFresh after its
// last registration; its bounds are read while the game says it is valid.
struct SeenShape {
  uint32_t shape = 0;
  Target box;
  std::chrono::steady_clock::time_point seen;
};
constexpr auto kShapeFresh = std::chrono::milliseconds(100);
std::array<SeenShape, hurt_record::kEntries> seen_shapes;
std::mutex seen_lock;
uint32_t guest_record = 0;  // the same boxes in guest memory, for Nathan's module (hurt_record_guest.h)
// Hurt boxes that took familiar hits without the enemy losing HP (a guarding
// hand, an invulnerable part: Dracula's last form blocks with his hands and
// is only hurt in its heads). Two such hits in a row on the same box make
// every familiar skip it for kImmuneFor; see NoteStrike.
struct Immune { uint32_t handle = 0, part = 0, flags = 0; std::chrono::steady_clock::time_point until; };
// Record bit 0x10 marks a guarding box: Dullahan's armour registers
// 0x40000018 (82307C18) beside its 0x40000009 head, Final Guard's shield
// 0x40000010. Hits on one give the "guard" message and no damage (user,
// November 18: the Ghost kept striking Dullahan's armour), so familiars skip
// them while the enemy has any other box, and rank them behind every other
// enemy's boxes. Dracula's last form registers its guarding hands as their
// own entity (DRA3, flags 0x40000019 from the shared box helper at
// 82284FC8, which picks 8, 9 or 0x19 per box), so the per-enemy rule left
// them, and being nearer Alucard they won over the heads (user, November 18).
constexpr uint32_t kGuardBit = 0x10;
constexpr auto kImmuneFor = std::chrono::seconds(8);
std::array<Immune, 32> immune_shapes;  // under seen_lock

std::vector<Target> FreshShapes() {
  std::vector<Target> out;
  const auto now = std::chrono::steady_clock::now();
  std::lock_guard guard(seen_lock);
  out.reserve(64);
  for (const auto& s : seen_shapes) {
    if (!s.box.handle || now - s.seen > kShapeFresh) continue;
    const bool immune = std::any_of(immune_shapes.begin(), immune_shapes.end(), [&](const Immune& i) {
      return i.handle == s.box.handle && i.part == s.box.part && i.flags == s.box.flags && now < i.until; });
    if (!immune) out.push_back(s.box);
  }
  std::vector<uint32_t> open;  // enemies with a box that does not guard
  for (const auto& t : out) if (!(t.flags & kGuardBit)) open.push_back(t.handle);
  std::erase_if(out, [&](const Target& t) {
    return (t.flags & kGuardBit) && std::find(open.begin(), open.end(), t.handle) != open.end(); });
  return out;
}

void MarkImmune(const Target& box) {
  const auto now = std::chrono::steady_clock::now();
  std::lock_guard guard(seen_lock);
  auto* slot = &immune_shapes[0];
  for (auto& i : immune_shapes) {
    if (i.handle == box.handle && i.part == box.part && i.flags == box.flags) { slot = &i; break; }
    if (i.until < slot->until) slot = &i;  // the oldest
  }
  *slot = {box.handle, box.part, box.flags, now + kImmuneFor};
}
struct Sweep {
  float x0, y0, x1, y1, half_width, half_height;
  float min_y = -std::numeric_limits<float>::infinity();

  float Entry(const Target& box) const {
    // Clip the motion segment to the hurt box expanded by the attack footprint.
    float enter = 0, exit = 1;
    const auto clip = [&](float start, float end, float lo, float hi) {
      const float movement = end - start;
      if (movement == 0) return start >= lo && start <= hi;
      const float first = (lo - start) / movement, second = (hi - start) / movement;
      const auto [a, b] = std::minmax(first, second);
      enter = std::max(enter, a);
      exit = std::min(exit, b);
      return enter <= exit;
    };
    if (clip(x0, x1, box.x0 - half_width, box.x1 + half_width) &&
        clip(y0, y1, box.y0 - half_height, box.y1 + half_height)) return enter;
    return std::numeric_limits<float>::infinity();
  }
};
// The nearest live enemy on either side of Alucard, from the registered hurt
// shapes (FreshShapes). When tracking a
// particular handle, ignore the search limits and select either its nearest
// actual hurt shape or the union of its shapes (for stable Ghost clinging).
Target FindTarget(uint8_t* base, float x, float y, uint32_t wanted = 0, bool nearest_shape = false,
                  const Sweep* contact = nullptr, std::span<const uint32_t> excluded = {},
                  float horizontal = kSearchHorizontal,
                  float vertical = kSearchVertical) {
  Target best; float nearest = 1e30f;
  for (auto shape_box : FreshShapes()) {
    const auto handle = shape_box.handle;
    const auto enemy = EntityOf(base, handle);
    if (!IsEnemy(base, enemy) || base[enemy + 23]) continue;
    if ((wanted && wanted != handle) || std::find(excluded.begin(), excluded.end(), handle) != excluded.end()) continue;
    if (wanted && !nearest_shape) {
      if (!best.handle) best = shape_box;
      else {
        best.x0 = std::min(best.x0, shape_box.x0); best.y0 = std::min(best.y0, shape_box.y0);
        best.x1 = std::max(best.x1, shape_box.x1); best.y1 = std::max(best.y1, shape_box.y1);
      }
      continue;
    }
    if (contact) {
      shape_box.y0 = std::max(shape_box.y0, contact->min_y);
      if (shape_box.y0 > shape_box.y1) continue;
    }
    const float dx = std::max({shape_box.x0 - x, 0.0f, x - shape_box.x1});
    const float dy = std::max({shape_box.y0 - y, 0.0f, y - shape_box.y1});
    if (!wanted && !contact && (dx > horizontal || dy > vertical)) continue;
    float d = contact && !wanted ? contact->Entry(shape_box) : dx * dx + dy * dy;
    if (!wanted && (shape_box.flags & kGuardBit)) d += 1e20f;  // only when nothing else is there
    if (contact && wanted && !std::isfinite(contact->Entry(shape_box))) continue;
    if (d < nearest) { nearest = d; best = shape_box; }
  }
  if (wanted && !nearest_shape && best.handle) {
    best.x = (best.x0 + best.x1) * .5f; best.y = (best.y0 + best.y1) * .5f; best.kind = 1;
    best.shape = 0; best.part = 0; best.flags = 0;
  }
  return best;
}

// Where the ghost hangs on: the point of the enemy's boxes nearest to it,
// kept 8 px inside (the centre of a small enemy), so it stops at the edge it
// arrives from instead of hunting for the middle of a big one.
void AimPoint(const Target& t, float gx, float gy, float& ax, float& ay) {
  if (t.kind != 1) {
    ax = t.x; ay = std::clamp(t.y, t.y0, t.y1);
    return;
  }
  const float mx = std::min(8.0f, (t.x1 - t.x0) * .5f), my = std::min(8.0f, (t.y1 - t.y0) * .5f);
  ax = std::clamp(gx, t.x0 + mx, t.x1 - mx); ay = std::clamp(gy, t.y0 + my, t.y1 - my);
}
// How far (x, y) is outside the box (0 inside).
float Outside(const Target& t, float x, float y) {
  const float dx = std::max({t.x0 - x, 0.0f, x - t.x1}), dy = std::max({t.y0 - y, 0.0f, y - t.y1});
  return std::sqrt(dx * dx + dy * dy);
}

enum class Phase { Follow, Approach, Strike };
enum class SwordMove { Circle, Rush };
struct Attack {
  Phase phase = Phase::Follow;
  uint32_t target = 0;
  int age = 0, cooldown = 0, spell = 0, missing_ticks = 0;
  bool struck = false, facing_left = false;
  SwordMove sword_move = SwordMove::Circle;
  float sword_approach_angle = 0;
  std::vector<uint32_t> sword_hits;
};

// A SotN servant animation being played: index into kFaerieSteps and ticks
// left on that step (alucard_familiar_art.h).
struct FaerieAnim { int anim = -1, step = 0, ticks = 0; };
enum class FaerieMode { Follow, Fly, Use, Rest };
struct Faerie {
  FaerieAnim body, wings;
  FaerieMode mode = FaerieMode::Follow;
  int action = 0;                 // 1 cure, 2 heal
  int wait = 0, wander = 0, angle = 0, max_angle = 0x20, flag = 0;
  float cure_cooldown = 0, heal_cooldown = 0;  // seconds
};

// Sword Brothers (below): step -1 = idle; the command's progress and the wheel.
struct Brothers {
  int step = -1, t = 0, copies = 0, combo = 0, timer = 0;
  float cx = 0, cy = 0, angle = 0, start = 0, radius = 0;
  uint32_t held = 0;
  // (sword, enemy) pairs already struck as the wheel flies apart: each of the
  // 64 swords hits every enemy it passes through once.
  std::vector<std::pair<int, uint32_t>> hit;
  // Sword strikes waiting their turn: an enemy takes one familiar hit at a
  // time, so several swords reaching a big enemy in the same frame (user,
  // November 19: Beelzebub took only a few) are released kBrothersSpacing
  // ticks apart per enemy.
  struct Strike { int sword; uint32_t enemy; float x, y; };
  std::vector<Strike> queue;
  std::vector<std::pair<uint32_t, int>> released;  // enemy, tick of its last release
  unsigned issued = 0, landed = 0;
};

struct Familiar {
  uint32_t owner = 0, handle = 0, item = 0;
  Attack attack;
  Faerie faerie;
  Brothers brothers;
  bool active = false, left = false;
  int step = 0, angle = 0, bob = 0, counter = 0, anim = 0, cloud = -1, opacity = 128, fade = -1;
  float x = 0, y = 0, vx = 0, vy = 0, ticks = 0;
  Target target;
  unsigned copies = 1, events = 0, idle = 0, target_logs = 0;
  // The last box struck and whether that hit took HP (Landed); see NoteStrike.
  struct { uint32_t handle = 0, part = 0, flags = 0; int misses = 0; bool waiting = false, landed = false; } probe;
  int lost = 0;  // ticks the target's hurt boxes have been missing
  int recheck = 0;  // Ghost: ticks since it last looked past a guarding target
  int recount = 0;  // ticks since the card count was last read
  // Ghost soul steal: hits that took HP (queued by Landed, on an enemy
  // thread) and the orbs flying from them to Alucard (see SoulSteal).
  struct Steal { uint32_t enemy = 0, orb = 0; float x = 0, y = 0, amount = 0; int ticks = 0; };
  std::vector<Steal> steals;
  int ring = 0, ring_ticks = 30;
  bool logged = false;
};
std::array<Familiar, 6> familiars;
std::mutex lock;
uint32_t scratch = 0, sound_scratch = 0;

// Positional sound by cue name (Shield Rod's SoundAt): 82239218(cue, x, y, 1).
void SoundAt(PPCContext& ctx, uint8_t* base, float x, float y, const char* cue) {
  if (!std::isfinite(x) || !std::isfinite(y)) return;
  if (!sound_scratch) sound_scratch = AlignedScratch(64);
  if (!sound_scratch) return;
  const auto length = std::strlen(cue); if (length >= 64) return;
  std::memcpy(base + sound_scratch, cue, length + 1);
  PPCContext call = ctx;
  call.r3.u64 = sound_scratch; call.r4.s64 = int32_t(x); call.r5.s64 = int32_t(y); call.r6.u64 = 1;
  rex::runtime::ResolveIndirectFunction(0x82239218)(call, base);
  static unsigned missing = 0;
  if (call.r3.s32 == -1 && missing++ < 4) REXLOG_WARN("[familiar] sound cue unavailable: {} (Shield Rod's bank)", cue);
}

// SotN's rand() stand-in for the occasional voice lines (all familiars run under `lock`).
unsigned Roll(unsigned n) {
  static uint32_t state = 0x2545F491u;
  state = state * 1664525u + 1013904223u;
  return (state >> 16) % n;
}

Familiar* Slot(uint8_t* base, uint32_t owner, bool create) {
  const auto handle = Read(base, owner + 4);
  for (auto& g : familiars) if (g.owner == owner && g.handle == handle) return &g;
  if (!create) return nullptr;
  for (auto& g : familiars) if (!g.owner || EntityOf(base, g.handle) != g.owner) { g = Familiar{}; g.owner = owner; g.handle = handle; return &g; }
  return nullptr;
}

unsigned CopiesOwned(PPCContext& ctx, uint8_t* base, uint32_t item) {
  PPCContext call = ctx;
  rex::runtime::ResolveIndirectFunction(kGameContext)(call, base);
  const auto game = call.r3.u32;
  if (!game) return 1;
  const unsigned copies = base[game + kSaveModel + kInventory + item] >> 4;
  return std::clamp(copies, 1u, kMaxFamiliarCopies);
}

float Power(PPCContext& ctx, uint8_t* base, uint32_t owner, unsigned copies,
            float min_power = kGhostPowerL1, float max_power = kGhostPowerMax) {
  const float p = min_power + (max_power - min_power) * float(copies - 1) / 8;
  PPCContext call = ctx; call.r3.u64 = owner;
  rex::runtime::ResolveIndirectFunction(0x824526D0)(call, base);  // INT total
  const float intelligence = float(call.f1.f64);
  const float total = p + (p / 64 + 0.25f) * (std::isfinite(intelligence) ? intelligence : 0.0f);
  return std::isfinite(total) ? std::fmax(1.0f, std::floor(total)) : 1.0f;
}

// 82484180 normally submits a rectangle to the region under the attacker's
// origin. Some large enemies expose hurt shapes in another region (including
// 0), so pass that shape's own region to the same native submission.
uint32_t SubmitContactHit(const PPCContext& ctx, uint8_t* base, uint32_t hit, float x, float y,
                      int half_width, int half_height, unsigned region) {
  constexpr uint32_t kRectangleVtable = 0x821E10C0;
  PPCContext call = ctx;
  call.r1.u32 = (ctx.r1.u32 - 0x180) & ~15u;
  const auto rect = call.r1.u32 + 112;
  Write(base, rect, kRectangleVtable);
  Write(base, rect + 4, 1);
  Float(base, rect + 8, x - half_width); Float(base, rect + 12, y - half_height);
  Float(base, rect + 16, x + half_width); Float(base, rect + 20, y + half_height);
  Write(base, call.r1.u32 + 84, base[hit + 0x9F]);  // native outgoing stack argument
  call.r3.u64 = rect;
  call.r4.u64 = Read(base, hit + 0xB0);
  call.r5.u64 = region;
  call.r6.u64 = Read(base, hit + 4); call.r7.u64 = Read(base, hit + 0xA4);
  call.r8.s64 = int64_t(Float(base, hit + 0x110));
  call.r9.u64 = 1; call.r10.u64 = hit + 0x44;
  call.f1.f64 = Float(base, hit + 0x114);
  rex::runtime::ResolveIndirectFunction(0x823C4C40)(call, base);
  Write(base, hit + 0xAC, call.r3.u32);
  return call.r3.u32;
}

// Native attack rectangle owned by `owner` (Nathan's NativeHit).
bool Hit(PPCContext& ctx, uint8_t* base, uint32_t owner, float x, float y, float damage,
         int half_width = 8, int half_height = 8, uint32_t element = 0,
         uint32_t contact_target = 0, float contact_min_y = -std::numeric_limits<float>::infinity(),
         uint8_t repeat_key = 0xFB) {
  const auto heap = Read(base, 0x828F57A4); if (!heap) return false;
  PPCContext call = ctx; call.r3.u64 = heap; call.r4.u64 = kColliderBytes; call.r5.u64 = 0;
  rex::runtime::ResolveIndirectFunction(0x825FC4B0)(call, base);
  const auto hit = call.r3.u32; if (!hit) return false;
  std::memset(base + hit, 0, kColliderBytes);
  call = ctx; call.r3.u64 = hit; call.r4.u64 = 0; call.r5.u64 = Read(base, owner + 4); call.r6.u64 = 12;
  rex::runtime::ResolveIndirectFunction(0x82481D60)(call, base);
  std::memcpy(base + hit + kColliderTable, base + 0x821EA0F0, 0x90);
  Write(base, hit, hit + kColliderTable);
  // As Shield Rod's colliders: +0x1C is the prepare phase (824823A0, which
  // submits the area: PrepareHit), +0x24 the attack phase (824827F0, which
  // resolves it: ResolveHit). With only the attack phase, areas reached the
  // lists after the enemies' own queries and most hits missed.
  Write(base, hit + kColliderTable + 0x24, 0x824827F0);
  Write(base, hit + kColliderTable + 0x80, 0x825F4170);
  Write(base, hit + kColliderTable + 0x1C, 0x824823A0);
  Write(base, hit + kColliderTable + 0x78, 0x825F4170);
  Float(base, hit + 0x2C, x); Float(base, hit + 0x30, y);
  Write(base, hit + 0x1A0, uint32_t(-half_width)); Write(base, hit + 0x1A4, uint32_t(-half_height));
  Write(base, hit + 0x1A8, half_width); Write(base, hit + 0x1AC, half_height);
  Float(base, hit + 0x44, 0); Float(base, hit + 0x48, 0);
  Float(base, hit + 0x110, damage);
  // Native 8224E4E8 keys repeat-hit immunity by owner, type and byte +9F,
  // for +114 seconds. These hits are Alucard's, so with the default key his
  // own weapon hits (and theirs) blocked each other for a second and the
  // Ghost's strikes did nothing (user, November 18). Shield Rod's spells use
  // keys FC-FE; the familiars use FB, with a short cooldown (each familiar
  // strikes a target at most every few tenths of a second anyway).
  Float(base, hit + 0x114, 0.25f);
  base[hit + 0x9F] = repeat_key;
  Write(base, hit + 0xB0, (Read(base, hit + 0xB0) & 0xC0000000u) | 2 | 0x40 | element);
  Write(base, hit + 0x190, kHitTag);
  Float(base, hit + 0x188, 0); Write(base, hit + 0x18C, 0);
  if (contact_target) {
    Write(base, hit + 0x194, contact_target);
    Float(base, hit + 0x198, contact_min_y);
    Float(base, hit + 0x1B0, x); Float(base, hit + 0x1B4, y);
    Write(base, hit + 0x1B8, half_width); Write(base, hit + 0x1BC, half_height);
  }
  // Submit the area now, from the player update, as Alucard's own attacks
  // register: enemies query the collision lists during their update, which
  // in most frames runs before a collider's own prepare phase, so areas
  // submitted there were seen only when the threads happened to line up
  // (test log, November 18: every hit submitted, one in three or fewer
  // landed, each in the same millisecond as its submission). The prepare
  // phase only retries an area that could not be submitted here.
  PPCContext area = ctx; area.r3.u64 = hit; area.r4.u64 = hit + 0x1A0;
  rex::runtime::ResolveIndirectFunction(0x82484180)(area, base);
  if (Read(base, hit + 0xAC) != 0xFFFFFFFFu) Write(base, hit + 0x18C, 1);
  return true;
}

// Soul steal as Alucard's Soul Steal spell shows it (com00, factory kind 2
// index 4, update 8253D040): for each enemy hit, 8253D6D0(enemy handle,
// owner handle, &start xy, b9E, b9F) creates the native orb that flies from
// the enemy to the owner. The orb only flies; healing goes through
// 8244E268(owner, f1 amount), the native recovery (green number, and the
// PARC record that syncs it online). The Ghost heals when its orb reaches
// Alucard (the orb object ends), or after kStealMaxTicks. Only the owner's
// machine gets here (Landed), so peers see the heal but not the orb.
constexpr uint32_t kSoulOrb = 0x8253D6D0, kRecover = 0x8244E268;
constexpr int kStealMaxTicks = 180;
uint32_t steal_scratch = 0;

void Recover(PPCContext& ctx, uint8_t* base, uint32_t owner, float amount) {
  PPCContext call = ctx; call.r3.u64 = owner; call.f1.f64 = amount;
  rex::runtime::ResolveIndirectFunction(kRecover)(call, base);
}

void SoulSteal(PPCContext& ctx, uint8_t* base, Familiar& g, uint32_t owner) {
  if (Read(base, owner + 0x930) != 1) { g.steals.clear(); return; }
  if (!steal_scratch) steal_scratch = AlignedScratch(16);
  for (auto& s : g.steals) {
    if (s.ticks++ == 0) {
      if (steal_scratch && EntityOf(base, s.enemy)) {
        Float(base, steal_scratch, s.x); Float(base, steal_scratch + 4, s.y);
        PPCContext call = ctx;
        call.r3.u64 = s.enemy; call.r4.u64 = Read(base, owner + 4); call.r5.u64 = steal_scratch;
        call.r6.u64 = 1; call.r7.u64 = 0;  // as the PADM drain path (824626F0) passes them
        rex::runtime::ResolveIndirectFunction(kSoulOrb)(call, base);
        s.orb = call.r3.u32;
      }
      if (!s.orb) s.ticks = kStealMaxTicks;  // no orb: heal now
      continue;
    }
    if (s.ticks >= kStealMaxTicks || !EntityOf(base, s.orb)) {
      Recover(ctx, base, owner, s.amount);
      // SotN plays its HP-restore sound (SFX_HEALTH_PICKUP) as the orb arrives.
      SoundAt(ctx, base, Float(base, owner + 0x8EC), Float(base, owner + 0x8F0), kGhostCueHeal);
      s.amount = 0;
    }
  }
  std::erase_if(g.steals, [](const Familiar::Steal& s) { return s.amount <= 0; });
}

// A familiar struck `box` (this machine's own player only: damage, and so
// Landed, happens only there). If its previous strike was on the same box and
// took no HP, count a miss; two in a row mark the box immune for a while.
void NoteStrike(uint8_t* base, Familiar& f, uint32_t owner, const Target& box) {
  if (!box.shape || Read(base, owner + 0x930) != 1) return;
  auto& p = f.probe;
  if (p.waiting && p.handle == box.handle && p.part == box.part && p.flags == box.flags) {
    if (p.landed) p.misses = 0;
    else if (++p.misses >= 2) {
      MarkImmune(box);
      p.misses = 0;
      REXLOG_INFO("[familiar] hurt box of {} {:08X} (registered at {:08X}, flags {:08X}) takes no damage; "
                  "skipping it for a while", EnemyName(base, box.handle), box.handle, box.part, box.flags);
    }
  } else {
    p.handle = box.handle; p.part = box.part; p.flags = box.flags; p.misses = 0;
  }
  p.waiting = true; p.landed = false;
}

// How far from Alucard a familiar's target may be before it gives up and
// comes back. The Ghost had none and stayed on a Final Guard (1 damage a
// hit) while Alucard went screens away (user, November 18).
const float kAttackLeash = std::hypot(kSearchHorizontal, kSearchVertical) + 88;

// One SotN tick of UpdateServantDefault.
void TickGhost(PPCContext& ctx, uint8_t* base, Familiar& g, uint32_t owner, uint32_t player) {
  const float px = Float(base, owner + 0x8EC), py = Float(base, owner + 0x8F0);
  const bool player_left = Read(base, player + 0x250) == 1;
  float tx = px + (player_left ? 18.0f : -18.0f);
  float ty = py - 32 + Sin(g.bob) * 4;
  g.bob = (g.bob + 32) & 0xFFF;
  g.anim = (g.anim + 1) % 16;
  g.opacity += g.fade; if (g.opacity <= 64 || g.opacity >= 128) g.fade = -g.fade;
  if (g.cloud >= 0) { g.ring = (g.ring + 50) & 0xFFF; if (++g.cloud > g.ring_ticks) g.cloud = -1; }
  if (!g.steals.empty()) SoulSteal(ctx, base, g, owner);

  auto steer = [&](float to_x, float to_y, int mode) {
    g.angle = StepAngle(Angle(to_x - g.x, to_y - g.y), g.angle, 512);
    const float dx = to_x - g.x, dy = to_y - g.y, distance = std::floor(std::sqrt(dx * dx + dy * dy));
    // SotN: distance/64 a tick following, distance/8 flying at a target. The
    // second reads far too fast in HoD, so it is slower and capped (settings).
    const float scale = mode == 2 ? 1.0f / kGhostApproachDivisor : 1.0f / 64;
    const float cap = mode == 2 ? kGhostApproachMax : 1e9f;
    const float speed = std::min(distance * scale, cap);
    g.vx = Cos(g.angle) * speed; g.vy = -Sin(g.angle) * speed;
    if (g.vx > 0 && g.vx < .25f) g.vx = .25f; else if (g.vx < 0 && g.vx > -.25f) g.vx = -.25f;
    if (g.vy > 0 && g.vy < .25f) g.vy = .25f; else if (g.vy < 0 && g.vy > -.25f) g.vy = -.25f;
    // SotN's catch-up (a quarter of the gap a frame) belongs to following
    // Alucard; flying at a target far away it made the Ghost jump (user, Nov 18).
    if (distance > 256 && mode == 1) { g.vx = dx / 4; g.vy = dy / 4; }
    return distance;
  };

  if (g.step <= 1) {
    // SotN compares whole pixels (posX.i.hi): reaching the spot behind
    // Alucard counts as arriving, which is what turns the ghost round.
    const long gx = long(std::floor(g.x)), target_x = long(std::floor(tx));
    if (player_left == g.left) {
      if (gx == target_x || (g.left && target_x < gx) || (!g.left && target_x > gx)) g.left = !player_left;
    } else if ((g.left && gx - target_x > 31) || (!g.left && target_x - gx > 31)) {
      g.left = player_left;
    }
    steer(tx, ty, 1);
    g.x += g.vx; g.y += g.vy;
    g.target = FindTarget(base, px, py);
    if (!g.target.handle && ++g.idle % 300 == 0 && g.events < 40) {  // diagnostics: every 5 s without a target
      ++g.events;
      const auto any = FindTarget(base, g.x, g.y, 0, false, nullptr, {}, 1e6f, 1e6f);
      char nearest[64] = "none";
      if (any.handle) std::snprintf(nearest, sizeof nearest, "%08X at %.0f,%.0f", any.handle, any.x, any.y);
      REXLOG_INFO("[familiar] Ghost idle at {:.0f},{:.0f} facing {} (Alucard {:.0f},{:.0f} facing {}); nearest enemy {}",
                  g.x, g.y, g.left ? "right" : "left", px, py, player_left ? "left" : "right", std::string(nearest));
    }
    if (g.target.handle) {
      g.idle = 0;
      g.step = 2; g.counter = 0;
      if (g.events++ < 40) REXLOG_INFO("[familiar] Ghost target {:08X} at {:.0f},{:.0f} (ghost {:.0f},{:.0f})",
                                       g.target.handle, g.target.x, g.target.y, g.x, g.y);
    }
    return;
  }
  auto now = FindTarget(base, g.x, g.y, g.target.handle);
  if (!now.handle) {
    // Hurt boxes go away for a moment during some enemy animations; hold on
    // to the last ones for a while unless the enemy itself is gone.
    const auto enemy = EntityOf(base, g.target.handle);
    if (!enemy || base[enemy + 23] || ++g.lost > kGhostLostGrace) {
      g.step = 1; g.target = {}; g.cloud = -1; g.lost = 0; return;
    }
    now = g.target;
  } else {
    g.lost = 0;
  }
  g.target = now;
  if (Outside(now, px, py) > kAttackLeash) {
    if (g.events++ < 40) REXLOG_INFO("[familiar] Ghost left {:08X}: Alucard is {:.0f} px away",
                                     now.handle, Outside(now, px, py));
    g.step = 1; g.target = {}; g.cloud = -1; g.lost = 0; g.counter = 0;
    return;
  }
  // A target with only guarding boxes (Dracula's hands): a few times a
  // second, switch to any enemy in range that can be hurt.
  if (++g.recheck >= 15) {
    g.recheck = 0;
    const auto box = FindTarget(base, g.x, g.y, g.target.handle, true);
    if (box.handle && (box.flags & kGuardBit)) {
      const auto other = FindTarget(base, px, py);
      if (other.handle && other.handle != g.target.handle && !(other.flags & kGuardBit)) {
        if (g.events++ < 40) REXLOG_INFO("[familiar] Ghost left guarding {} {:08X} for {} {:08X}",
                                         EnemyName(base, g.target.handle), g.target.handle,
                                         EnemyName(base, other.handle), other.handle);
        g.target = other; g.step = 2; g.counter = 0; g.cloud = -1; g.lost = 0;
        return;
      }
    }
  }
  float ax, ay; AimPoint(now, g.x, g.y, ax, ay);
  // Facing: towards the aim point, turning only past a dead zone (it used to
  // follow the sign of the speed, which flipped every frame while hovering).
  if (ax - g.x > kGhostFaceDeadZone) g.left = true;
  else if (g.x - ax > kGhostFaceDeadZone) g.left = false;
  const int delay = std::max(kGhostMinDelay, int(std::lround(kDelay[g.copies - 1] * kGhostDelayScale)));
  const int lead = std::min(30, delay - 1);  // the attack ring closes in over these last ticks
  const float outside = Outside(now, g.x, g.y);
  if (g.step == 3) {
    // Clinging. SotN steers at distance/2 a tick and restarts the attack
    // count whenever it is 8 px off; slowed down for HoD it could not keep
    // up with a walking enemy and never attacked. Instead it glides onto the
    // aim point (a share of the gap each tick, capped) with no turning arcs,
    // keeps counting within kGhostClingHold px of the enemy's boxes and
    // lets go only kGhostClingRelease px outside them.
    const float dx = ax - g.x, dy = ay - g.y, distance = std::sqrt(dx * dx + dy * dy);
    const float step = std::min(distance * kGhostClingShare, kGhostClingCatchUp);
    g.vx = distance > 0 ? dx / distance * step : 0; g.vy = distance > 0 ? dy / distance * step : 0;
    if (outside > kGhostClingRelease) {
      g.step = 2; g.counter = 0; g.cloud = -1;
      if (g.events++ < 40) REXLOG_INFO("[familiar] Ghost let go of {:08X} ({:.0f} px outside)", now.handle, outside);
    }
    else if (outside > kGhostClingHold) {}  // catching up: the count waits
    else if (++g.counter == delay - lead) {
      // UpdateAttackEntities: eight orbs on a circle of radius = ticks left,
      // turning 50/4096 a tick, with SotN's glass-shards sound (0x6B0, in
      // the familiar bank).
      g.cloud = 0; g.ring_ticks = lead; g.ring = 0;
      SoundAt(ctx, base, g.x, g.y, kGhostCueGlassShards);
    }
    else if (g.counter > delay) {
      // Strike inside the nearest hurt box the enemy has right now: the
      // union box it clings to has gaps between boxes, and hits aimed there
      // (or at boxes that had just gone away) struck dead air. With no live
      // box it waits a few frames. The hit goes through the contact path
      // (the box's own collision region), like the Sword's. Soul steal heals
      // from the HP the enemy actually lost (Landed, called by the 82246DF0
      // observer), not from every swing.
      const auto shape = FindTarget(base, g.x, g.y, g.target.handle, true);
      if (!shape.handle) {
        g.counter = delay - 6;
      } else {
        g.counter = 0;
        float hx, hy; AimPoint(shape, g.x, g.y, hx, hy);
        const float damage = Power(ctx, base, owner, g.copies);
        Hit(ctx, base, owner, hx, hy, damage, kGhostReach, kGhostReach, 0, shape.handle);
        NoteStrike(base, g, owner, shape);
        if (g.events++ < 40) REXLOG_INFO("[familiar] Ghost attack {} {:08X} (flags {:08X} at {:08X}): {:.0f} power at {:.0f},{:.0f}",
                                         EnemyName(base, shape.handle), shape.handle, shape.flags, shape.part, damage, hx, hy);
      }
    }
  } else {
    const float distance = steer(ax, ay, 2);
    if (distance < 12 || outside < 4) {
      g.counter = 0; g.step = 3;
      if (g.events++ < 40) REXLOG_INFO("[familiar] Ghost clinging to {:08X}", now.handle);
    }
  }
  g.x += g.vx; g.y += g.vy;
}

struct AttackStyle {
  const char* name;
  float min_power, max_power;
  int cooldown, windup, strike_ticks;
  float hover_x, hover_y, approach_x, approach_y, approach_speed, strike_speed;
  int reach_x, reach_y;
};

const AttackStyle* Style(uint32_t item) {
  static constexpr AttackStyle bat{"Bat", kBatPowerL1, kBatPowerMax, kBatCooldown, 3, 24,
                                   22, 34, 24, 34, 4.2f, 5.0f, 18, 16};
  static constexpr AttackStyle demon{"Demon", kDemonPowerL1, kDemonPowerMax, kDemonCooldown, 12, 12,
                                     32, 26, 29, 2, 3.5f, 0, 26, 22};
  static constexpr AttackStyle sword{"Sword", kSwordPowerL1, kSwordPowerMax, kSwordCooldown, 30, 0,
                                     28, 28, 8, 0, 6.0f, 0, 15, 13};
  switch (item) {
    case kBatItem: return &bat;
    case kDemonItem: return &demon;
    case kSwordItem: return &sword;
    default: return nullptr;
  }
}

// Demon frames 41–44 show fire, 45–48 ice, and 49–52 lightning.
constexpr uint32_t kDemonElements[] = {0x100, 0x200, 0x400};
// TT_004 selects the circle under level 70. The circle winds up for 30
// ticks, turns 1/32 revolution per tick for two turns, and pauses again.
// The higher-level route lines up and rushes at a selected enemy.
constexpr unsigned kSwordRushCopies = 7;
int SwordWindup(SwordMove move) { return move == SwordMove::Circle ? 30 : 60; }
int SwordActiveTicks(SwordMove move) { return move == SwordMove::Circle ? 64 : 45; }
int SwordRecoveryTicks(SwordMove move) { return move == SwordMove::Circle ? 30 : 15; }
constexpr float kRadiansPerDegree = std::numbers::pi_v<float> / 180;

struct SwordPose {
  float x, y, angle, hilt_x, hilt_y, tip_x, tip_y, pivot_x, pivot_y;
};

SwordPose SwordSlash(const Familiar& familiar, int age) {
  const auto ease = [](int tick, int duration) {
    const float t = std::clamp(float(tick) / duration, 0.0f, 1.0f);
    return t * t * (3 - 2 * t);
  };
  const auto move = familiar.attack.sword_move;
  const int strike_age = age - SwordWindup(move);
  const int direction = familiar.attack.facing_left ? -1 : 1;
  float angle = 0, advance = 0, drop = 0;
  if (move == SwordMove::Circle) {
    const int turns = std::clamp(strike_age, 0, SwordActiveTicks(move));
    const float settle = ease(strike_age - SwordActiveTicks(move), SwordRecoveryTicks(move));
    angle = direction * turns * (360.0f / 32) + std::lerp(familiar.attack.sword_approach_angle, 0.0f, settle);
  } else {
    // Project the high-level routine's line-up, drive through the enemy,
    // and rising exit into the stage plane.
    angle = std::lerp(familiar.attack.sword_approach_angle, direction * 72.0f, ease(age, 20));
    if (strike_age > 0) {
      const float drive = std::clamp(float(strike_age) / 28, 0.0f, 1.0f);
      const float exit = ease(strike_age - 28, 17);
      advance = 102 * drive + 20 * exit;
      drop = 30 * drive - 44 * exit;
      angle = direction * (72 + 60 * exit);
    }
    if (strike_age > SwordActiveTicks(move))
      angle = std::lerp(angle, 0.0f, ease(strike_age - SwordActiveTicks(move), SwordRecoveryTicks(move)));
  }
  const float dx = std::sin(angle * kRadiansPerDegree);
  const float dy = std::cos(angle * kRadiansPerDegree);
  const float x = familiar.x + direction * advance, y = familiar.y + drop;
  return {x, y, angle, x - dx * 15, y - dy * 15, x + dx * 26, y + dy * 26, x, y};
}

bool MoveToward(Familiar& familiar, float x, float y, float speed) {
  const float dx = x - familiar.x, dy = y - familiar.y;
  const float distance = std::hypot(dx, dy);
  if (distance <= speed) {
    familiar.x = x; familiar.y = y;
    return true;
  }
  familiar.x += dx * (speed / distance);
  familiar.y += dy * (speed / distance);
  return false;
}

constexpr float kSwordLaneHeight = 56.0f;
Target FirstInApproach(uint8_t* base, float x, float y, const Target& target, float half_height) {
  if (!target.handle) return target;
  float aim_x, aim_y;
  AimPoint(target, x, y, aim_x, aim_y);
  // Favor the first enemy between Alucard and the selected hurt box.
  const Sweep lane{x, y, aim_x, aim_y, 0, half_height};
  const auto first = FindTarget(base, x, y, 0, false, &lane);
  if (first.handle && (first.flags & kGuardBit) && !(target.flags & kGuardBit)) return target;
  return first.handle ? first : target;
}
Target FindApproachTarget(uint8_t* base, float x, float y, float half_height) {
  return FirstInApproach(base, x, y, FindTarget(base, x, y), half_height);
}

void LogSwordTarget(uint8_t* base, Familiar& familiar, const Target& target, float x, float y, const char* action) {
  if (familiar.target_logs++ >= 60) return;
  REXLOG_INFO("[familiar] Sword {} {} {:08X}, shape {} region {} at {:.0f},{:.0f} from {:.0f},{:.0f}",
              action, EnemyName(base, target.handle), target.handle, target.kind, target.region, target.x, target.y, x, y);
}

// The current blade and the segment swept by its tip share the rendered
// pose. Queue a native impact at each fresh enemy's own hurt box.
void HitWithSword(PPCContext& ctx, uint8_t* base, Familiar& familiar, uint32_t owner, const AttackStyle& style) {
  auto& attack = familiar.attack;
  const auto blade = SwordSlash(familiar, attack.age), prior = SwordSlash(familiar, attack.age - 1);
  // The blade's footprint (widened November 18: hits missed enemies the blade touched).
  const Sweep paths[] = {{blade.hilt_x, blade.hilt_y, blade.tip_x, blade.tip_y, 16, 14},
                         {prior.tip_x, prior.tip_y, blade.tip_x, blade.tip_y, 16, 14}};
  float power = 0;
  for (const auto& path : paths) {
    while (true) {
      const auto contact = FindTarget(base, blade.tip_x, blade.tip_y, 0, false, &path, attack.sword_hits);
      if (!contact.handle) break;
      float x, y;
      AimPoint(contact, blade.tip_x, blade.tip_y, x, y);
      if (!power) power = Power(ctx, base, owner, familiar.copies, style.min_power, style.max_power);
      if (!Hit(ctx, base, owner, x, y, power, style.reach_x, style.reach_y, 0, contact.handle)) return;
      attack.sword_hits.push_back(contact.handle);
      if (attack.sword_hits.size() == 1) NoteStrike(base, familiar, owner, contact);
      // sword.c: after a hit, a 2-in-16 chance of "Slice!" (roll 0) or "Slash!" (1).
      if (attack.sword_hits.size() == 1) {
        const unsigned roll = Roll(16);
        if (roll < 2) SoundAt(ctx, base, familiar.x, familiar.y, roll ? kSwordCueSlash : kSwordCueSlice);
      }
      if (familiar.events++ < 40)
        REXLOG_INFO("[familiar] Sword attack {} {:08X}: {:.0f} power, move {}",
                    EnemyName(base, contact.handle), contact.handle, power, int(attack.sword_move));
    }
  }
}

void FinishAttack(Attack& attack, const AttackStyle& style) {
  attack.phase = Phase::Follow;
  attack.target = 0;
  attack.age = 0;
  attack.cooldown = style.cooldown;
  attack.struck = false;
  attack.missing_ticks = 0;
  attack.sword_hits.clear();
  attack.sword_approach_angle = 0;
}

// ---- Sword Brothers --------------------------------------------------------
// SotN's spell 7, here a command of the Sword Card. The command is SotN's
// (dra CheckSwordBrothersInput): down, down-forward, forward, up-forward, up
// (each within 20 frames), hold up for 64 frames, let go, down within 20,
// then an attack button while crouching within 20. It costs kBrothersMp,
// paid on Alucard's own machine like Shield Rod's spells, and is announced
// with HoD's queue-only spawn event (kind 11 / sub 1, tags "SB" "RO") so the
// other machines replay it on their copy of him.
//
// The Sword then runs SotN's spell routine (sword.c func_us_801758C8) in 2D:
// it flies above Alucard, rises with a swoosh and calls "Gather, brother
// soul blades!", holds 70 frames, spins 5.625 degrees a frame for 32 frames,
// then keeps spinning and leaves a translucent copy every frame until 64
// copies make a wheel; 15 frames later a chime, and the wheel flies apart
// over 16 frames to kBrothersRadius. Every enemy the wheel reaches takes
// one native hit (SotN's damage object, func_us_80177590, uses spell 7's
// numbers); 30 frames later it is over.
constexpr uint32_t kBrothersTagA = 0x5342, kBrothersTagB = 0x524F;  // "SB" "RO"
constexpr uint32_t kPadLeft = 1, kPadRight = 2, kPadUp = 4, kPadDown = 8, kPadAttack = 0x20 | 0x40;
constexpr int kBrothersCopies = 64;
constexpr float kBrothersSpin = 360.0f / 64;  // 0x40 of SotN's 0x1000 a frame
// SotN's screen points, around Alucard: the top of the screen (where the
// swoop ends) and the centre (where the wheel turns), px above his centre.
constexpr float kBrothersTop = 200, kBrothersCentre = 40;
constexpr float kBrothersSpeed = 25;          // px a frame as the wheel flies apart

void StartBrothers(Familiar& f) {
  auto& b = f.brothers;
  b.step = 0; b.t = 0; b.copies = 0; b.radius = 0; b.hit.clear();
  b.queue.clear(); b.released.clear(); b.issued = b.landed = 0;
  b.angle = 180;  // the Sword's resting pose, tip up; the swoop turns it toward the top
  f.attack.phase = Phase::Follow; f.attack.age = 0; f.attack.struck = false; f.attack.sword_hits.clear();
}

void AnnounceBrothers(PPCContext& ctx, uint8_t* base, uint32_t owner) {
  PPCContext call = ctx;
  const uint32_t sp = (ctx.r1.u32 - 0x400) & ~15u;  // as Shield Rod's Announce
  std::memset(base + sp, 0, 0x100);
  call.r1.u64 = sp;
  call.r3.u64 = owner; call.r4.u64 = kSwordItem; call.r5.u64 = 11; call.r6.u64 = 1;
  call.r7.u64 = 0; call.r8.u64 = 0; call.r9.u64 = kBrothersTagA; call.r10.u64 = kBrothersTagB; call.f1.f64 = 0;
  rex::runtime::ResolveIndirectFunction(0x8244CA98)(call, base);
}

void CastBrothers(PPCContext& ctx, uint8_t* base, Familiar& f, uint32_t owner, uint32_t player) {
  const auto stats = Read(base, player + 88);
  if (!stats) return;
  const float mp = Float(base, stats + 8);
  if (!std::isfinite(mp) || mp < kBrothersMp) {
    REXLOG_INFO("[familiar] Sword Brothers: {:.0f} MP needed, {:.0f} left", kBrothersMp, mp);
    return;
  }
  Float(base, stats + 8, mp - kBrothersMp);
  StartBrothers(f);
  AnnounceBrothers(ctx, base, owner);
  REXLOG_INFO("[familiar] Sword Brothers cast for {:.0f} MP ({:.0f} left)", kBrothersMp, mp - kBrothersMp);
}

// One frame of the command (the local player's own input block, player +0x2C0).
void BrothersInput(PPCContext& ctx, uint8_t* base, Familiar& f, uint32_t owner, uint32_t player) {
  auto& b = f.brothers;
  const auto input = Read(base, player + 0x2C0);
  const uint32_t held = input ? Read(base, input) : 0, pressed = held & ~b.held;
  b.held = held;
  if (b.step >= 0) { b.combo = 0; return; }
  const uint32_t dirs = held & 0xF;
  const uint32_t forward = Read(base, player + 0x250) == 1 ? kPadLeft : kPadRight;
  const auto next = [&](int frames) { b.timer = frames; ++b.combo; };
  const auto expire = [&] { if (--b.timer <= 0) b.combo = 0; };
  // The user's smoother version of SotN's command (no holding up, no
  // crouching for the button): down, down-forward, forward, up-forward, up,
  // down, then X or Y, each within kStep frames of the last.
  constexpr int kStep = 30;
  static unsigned logged = 0;
  switch (b.combo) {
    case 0: if (dirs == kPadDown) next(kStep); break;
    case 1: if (dirs == (kPadDown | forward)) next(kStep); else expire(); break;
    case 2: if (dirs == forward) next(kStep); else expire(); break;
    case 3: if (dirs == (kPadUp | forward)) next(kStep); else expire(); break;
    case 4: if (dirs == kPadUp) next(kStep); else expire(); break;
    case 5:
      if (dirs == kPadDown) {
        next(kStep);
        if (logged++ < 20) REXLOG_INFO("[familiar] Sword Brothers command: waiting for X or Y");
      } else expire();
      break;
    case 6:
      if (pressed & kPadAttack) { b.combo = 0; CastBrothers(ctx, base, f, owner, player); }
      else expire();
      break;
    default: b.combo = 0; break;
  }
}

// Where copy `k` of the wheel sits and points (tip outward), SwordSlash's
// convention: angle 0 points the tip down, the hilt is 15 px behind centre.
struct Blade { float x, y, angle; };
Blade WheelBlade(const Brothers& b, float angle) {
  const float r = angle * kRadiansPerDegree, dx = std::sin(r), dy = std::cos(r);
  return {b.cx + dx * (15 + b.radius), b.cy + dy * (15 + b.radius), angle};
}

// One queued sword strike per enemy every kBrothersSpacing ticks, aimed at
// that enemy's hurt box nearest the spot the sword passed (it may have moved).
// Each sword keeps its own repeat-hit key (0x80 + sword), so the game counts
// every sword's strike as its own hit.
constexpr int kBrothersSpacing = 2;
void ReleaseStrikes(PPCContext& ctx, uint8_t* base, Familiar& f, uint32_t owner) {
  auto& b = f.brothers;
  const int now = b.t + (b.step == 7 ? 100000 : 0);  // b.t restarts at step 7
  float power = 0;
  std::vector<uint32_t> done;
  for (size_t i = 0; i < b.queue.size();) {
    const auto strike = b.queue[i];
    auto last = std::find_if(b.released.begin(), b.released.end(), [&](const auto& r) { return r.first == strike.enemy; });
    const auto enemy = EntityOf(base, strike.enemy);
    if (!enemy || base[enemy + 23]) { b.queue.erase(b.queue.begin() + i); continue; }  // gone or dead
    if (std::find(done.begin(), done.end(), strike.enemy) != done.end() ||
        (last != b.released.end() && now - last->second < kBrothersSpacing)) { ++i; continue; }
    done.push_back(strike.enemy);
    if (last == b.released.end()) b.released.emplace_back(strike.enemy, now); else last->second = now;
    float x = strike.x, y = strike.y;
    const auto box = FindTarget(base, x, y, strike.enemy, true);
    if (box.handle) AimPoint(box, strike.x, strike.y, x, y);
    if (!power) power = Power(ctx, base, owner, f.copies, kBrothersPowerL1, kBrothersPowerMax);
    if (Hit(ctx, base, owner, x, y, power, 8, 8, 0, strike.enemy, -std::numeric_limits<float>::infinity(),
            uint8_t(0x80 + strike.sword))) {
      ++b.issued;
      if (f.events++ < 40)
        REXLOG_INFO("[familiar] Sword Brothers sword {} hit {} {:08X}: {:.0f} power", strike.sword,
                    EnemyName(base, strike.enemy), strike.enemy, power);
    }
    b.queue.erase(b.queue.begin() + i);
  }
}

void TickBrothers(PPCContext& ctx, uint8_t* base, Familiar& f, uint32_t owner, float px, float py,
                  const AttackStyle& style) {
  auto& b = f.brothers;
  const auto ease = [](float t) { t = std::clamp(t, 0.0f, 1.0f); return t * t * (3 - 2 * t); };
  ++b.t;
  switch (b.step) {
    case 0: {
      // SotN steps 1-2: a swoosh, then a swooping flight to the top of the
      // screen above the centre, tip leading, turning a limited amount a frame.
      if (b.t == 1) SoundAt(ctx, base, f.x, f.y, kSwordCueSwoosh);
      const float tx = px, ty = py - kBrothersTop, dx = tx - f.x, dy = ty - f.y;
      const float heading = std::atan2(dx, dy) / kRadiansPerDegree;
      b.angle += std::clamp(std::remainder(heading - b.angle, 360.0f), -8.0f, 8.0f);
      const float r = b.angle * kRadiansPerDegree;
      f.x += std::sin(r) * 6; f.y += std::cos(r) * 6;
      if (std::hypot(tx - f.x, ty - f.y) < 8 || b.t > 120) {
        f.x = tx; f.y = ty; b.cx = px; b.cy = py - kBrothersCentre;
        b.step = 1; b.t = 0; b.angle = 0;  // point straight down
        SoundAt(ctx, base, f.x, f.y, kSwordCueSwoosh);
      }
      break;
    }
    case 1:  // SotN steps 3-4: descend, tip down, to the centre over 16 frames; then the call
      f.y = std::lerp(b.cy - (kBrothersTop - kBrothersCentre), b.cy, std::min(1.0f, b.t / 16.0f));
      f.x = b.cx;
      if (b.t >= 16) {
        b.step = 2; b.t = 0;
        SoundAt(ctx, base, f.x, f.y, kSwordCueBrothers);
      }
      break;
    case 2: if (b.t > 70) { b.step = 3; b.t = 0; } break;
    case 3:
      b.angle += kBrothersSpin;
      if (b.t >= 32) { b.step = 4; b.t = 0; b.start = b.angle; b.copies = 1; }
      break;
    case 4:
      b.angle += kBrothersSpin;
      if (++b.copies >= kBrothersCopies) { b.step = 5; b.t = 0; }
      break;
    case 5:
      if (b.t > 15) {
        b.step = 6; b.t = 0; b.hit.clear();
        SoundAt(ctx, base, b.cx, b.cy, kSwordCueMagicSwitch);
      }
      break;
    case 6: {
      // Each sword strikes what it flies through this frame (its path from
      // last frame's spot), once per enemy, with its own repeat-hit key
      // (0x80 + sword) so the game counts two swords on one big enemy as two
      // hits (user, November 19). Before, the ring hit each enemy once.
      const float before = b.radius;
      b.radius = std::min(kBrothersRadius, b.t * kBrothersSpeed);
      float power = 0;
      Brothers last = b; last.radius = before;
      std::vector<uint32_t> struck;
      for (int k = 0; k < kBrothersCopies; ++k) {
        const float angle = b.start + k * kBrothersSpin;
        const auto from = WheelBlade(last, angle), to = WheelBlade(b, angle);
        const Sweep path{from.x, from.y, to.x, to.y, 10, 10};
        struck.clear();
        for (const auto& [sword, enemy] : b.hit) if (sword == k) struck.push_back(enemy);
        for (int n = 0; n < 4; ++n) {
          const auto enemy = FindTarget(base, to.x, to.y, 0, false, &path, struck);
          if (!enemy.handle) break;
          struck.push_back(enemy.handle);
          b.hit.emplace_back(k, enemy.handle);
          float x, y; AimPoint(enemy, to.x, to.y, x, y);
          b.queue.push_back({k, enemy.handle, x, y});
        }
      }
      ReleaseStrikes(ctx, base, f, owner);
      if (b.radius >= kBrothersRadius) { b.step = 7; b.t = 0; }
      break;
    }
    case 7:
      ReleaseStrikes(ctx, base, f, owner);
      if (b.t > 30 && (b.queue.empty() || b.t > 240)) {
        REXLOG_INFO("[familiar] Sword Brothers: {} sword hits sent, {} took HP, {} dropped", b.issued, b.landed,
                    b.queue.size());
        b.step = -1; b.queue.clear();
        FinishAttack(f.attack, style);
        f.x = b.cx; f.y = b.cy;
      }
      break;
  }
}

void TickAttack(PPCContext& ctx, uint8_t* base, Familiar& familiar, uint32_t owner, uint32_t player,
                const AttackStyle& style) {
  auto& attack = familiar.attack;
  const bool bat = familiar.item == kBatItem, sword = familiar.item == kSwordItem;
  const bool demon = familiar.item == kDemonItem;
  const float px = Float(base, owner + 0x8EC), py = Float(base, owner + 0x8F0);
  if (!std::isfinite(px) || !std::isfinite(py)) return;
  if (sword && familiar.brothers.step >= 0) { TickBrothers(ctx, base, familiar, owner, px, py, style); return; }
  const bool player_left = Read(base, player + 0x250) == 1;
  const int forward = player_left ? -1 : 1;
  const float follow_x = px - forward * style.hover_x;
  const float follow_y = py - style.hover_y + 4 * Sin(familiar.bob);
  familiar.bob = (familiar.bob + 64) & 0xFFF;
  familiar.anim = (familiar.anim + 1) % 120;
  if (std::hypot(familiar.x - px, familiar.y - py) > kAttackLeash) {
    familiar.x = follow_x; familiar.y = follow_y;
    FinishAttack(attack, style);
  }
  if (attack.phase == Phase::Follow) {
    const float gap = std::hypot(follow_x - familiar.x, follow_y - familiar.y);
    MoveToward(familiar, follow_x, follow_y, std::clamp(gap * .12f, .3f, 5.5f));
    attack.facing_left = player_left;
    if (attack.cooldown > 0) { --attack.cooldown; return; }
    const auto target = bat || sword ? FindApproachTarget(base, px, py, sword ? kSwordLaneHeight : 14.0f)
                                     : FindTarget(base, px, py);
    if (target.handle) {
      attack.target = target.handle;
      attack.phase = Phase::Approach;
      attack.age = 0;
      attack.facing_left = target.x < px;
      if (sword) {
        familiar.idle = 0;
        attack.sword_move = familiar.copies >= kSwordRushCopies ? SwordMove::Rush : SwordMove::Circle;
        LogSwordTarget(base, familiar, target, px, py, "locked");
      }
    } else if (sword && ++familiar.idle % 240 == 0 && familiar.target_logs < 60) {
      const auto nearest = FindTarget(base, px, py, 0, false, nullptr, {}, 1e6f, 1e6f);
      if (nearest.handle) LogSwordTarget(base, familiar, nearest, px, py, "out of range, nearest");
      else {
        ++familiar.target_logs;
        REXLOG_INFO("[familiar] Sword idle at {:.0f},{:.0f}: no live enemy hurt shapes", px, py);
      }
    }
    return;
  }

  // Once Sword swings, finish even if the original target moves away or
  // dies. Every enemy the blade now crosses is eligible for damage.
  const int windup = sword ? SwordWindup(attack.sword_move) : style.windup;
  if (sword && attack.phase == Phase::Strike && attack.age >= windup) {
    const int active = SwordActiveTicks(attack.sword_move);
    const int strike_age = ++attack.age - windup;
    // sword.c: the circle attack's strike starts with a downward sweep, the
    // higher-level attack's with a wing flap.
    if (strike_age == 1)
      SoundAt(ctx, base, familiar.x, familiar.y, attack.sword_move == SwordMove::Rush ? kSwordCueWingFlap : kSwordCueSweep);
    if (strike_age <= active) HitWithSword(ctx, base, familiar, owner, style);
    if (strike_age >= active + SwordRecoveryTicks(attack.sword_move)) {
      const auto end = SwordSlash(familiar, attack.age);
      familiar.x = end.x; familiar.y = end.y;
      FinishAttack(attack, style);
    }
    return;
  }

  // An enemy can step into the lane while Sword is still flying toward a
  // farther target. Check again before it commits to the swing.
  if (sword && attack.phase == Phase::Approach && attack.age % 8 == 0) {
    const auto locked = FindTarget(base, px, py, attack.target, true);
    const auto first = FirstInApproach(base, px, py, locked, kSwordLaneHeight);
    if (first.handle && first.handle != attack.target) {
      LogSwordTarget(base, familiar, first, px, py, "retargeted to");
      attack.target = first.handle;
      attack.facing_left = first.x < px;
    }
  }

  const int direction = attack.facing_left ? -1 : 1;
  // Pick a real hurt shape near the attack so a multipart enemy's empty
  // space between shapes cannot become the intended point of impact.
  float aim_y_hint = sword ? py : familiar.y;
  float bat_torso_top = -std::numeric_limits<float>::infinity();
  if (bat) {
    const auto bounds = FindTarget(base, familiar.x, familiar.y, attack.target);
    if (bounds.handle && bounds.y1 - bounds.y0 >= 72) {
      // Large enemies can have upper hurt records attached to appendages.
      // Dive toward the lower body, even when starting above the target.
      bat_torso_top = std::lerp(bounds.y0, bounds.y1, .55f);
      aim_y_hint = std::lerp(bounds.y0, bounds.y1, .72f);
    }
  }
  const auto target = FindTarget(base, familiar.x, aim_y_hint, attack.target, true);
  if (!target.handle && !attack.struck) {
    const auto enemy = EntityOf(base, attack.target);
    if (!enemy || base[enemy + 23] || ++attack.missing_ticks > (sword ? 24 : 10)) {
      if (sword && familiar.target_logs++ < 60)
        REXLOG_INFO("[familiar] Sword lost {} {:08X}: hurt shape disappeared",
                    EnemyName(base, attack.target), attack.target);
      FinishAttack(attack, style);
    }
    return;
  }
  attack.missing_ticks = 0;
  if (target.handle && Outside(target, px, py) > kAttackLeash) {
    FinishAttack(attack, style);
    return;
  }
  float aim_x = familiar.x, aim_y = familiar.y;
  if (target.handle) AimPoint(target, familiar.x, aim_y_hint, aim_x, aim_y);
  const bool rush = sword && attack.sword_move == SwordMove::Rush;
  const float approach_x = rush ? 52.0f : style.approach_x;
  const float start_x = (direction > 0 ? target.x0 : target.x1) - direction * approach_x;
  const float start_y = aim_y - (rush ? 22.0f : style.approach_y);
  if (attack.phase == Phase::Approach) {
    // Keep a fixed approach side and stage against the enemy's edge. A
    // timeout lets the familiar return if the target moves out of reach.
    float speed = style.approach_speed;
    if (sword) {
      const float dx = start_x - familiar.x, dy = start_y - familiar.y;
      const float gap = std::hypot(dx, dy);
      speed = std::clamp(gap / 16, 1.5f, speed);
      if (gap > 2) {
        const float heading = std::atan2(dx, dy) / kRadiansPerDegree;
        float& angle = attack.sword_approach_angle;
        const float delta = std::remainder(heading - angle, 360.0f);
        constexpr float turn = 360.0f / 128;
        angle += std::clamp(delta, -turn, turn);
      }
    }
    if (MoveToward(familiar, start_x, start_y, speed)) {
      attack.phase = Phase::Strike;
      // demon.c names the spear as it casts (fire, ice, thunder for HoD's
      // lightning); here only on 2 casts in 16, like the Sword's lines (the
      // user found every cast too much). SotN's Bat dives silently; it
      // screeches on one dive in three.
      if (demon && Roll(16) < 1) {  // one cast in 16 (2 in 16 was still too often)
        constexpr const char* spears[] = {kDemonCueFireSpear, kDemonCueIceSpear, kDemonCueThunderSpear};
        SoundAt(ctx, base, familiar.x, familiar.y, spears[attack.spell % 3]);
      } else if (bat && Roll(3) == 0) {
        SoundAt(ctx, base, familiar.x, familiar.y, kBatCueScreech);
      }
      attack.age = 0;
      familiar.vx = familiar.vy = 0;
    } else if (++attack.age >= 135) {
      FinishAttack(attack, style);
    }
    return;
  }

  const int strike_age = ++attack.age - windup;
  if (strike_age <= 0) {
    if (rush) MoveToward(familiar, start_x, start_y, 1.5f);
    return;
  }
  float hit_x = familiar.x, hit_y = familiar.y;
  bool can_hit = false;
  Target bat_contact;
  if (bat) {
    if (attack.struck) {
      // Keep the impact velocity and bank upwards through the rest of the pass.
      familiar.vx = std::lerp(familiar.vx, direction * 2.8f, .16f);
      familiar.vy = std::lerp(familiar.vy, -2.4f, .20f);
      familiar.x += familiar.vx;
      familiar.y += familiar.vy;
    } else {
      const float speed = style.strike_speed * std::min(1.0f, .35f + .13f * strike_age);
      MoveToward(familiar, aim_x, aim_y, speed);
      familiar.vx = familiar.x - hit_x;
      familiar.vy = familiar.y - hit_y;
      // Sweep the visible bat's footprint across the whole tick, against every
      // hurt shape of the target, including the edge of large enemies.
      const Sweep dive{hit_x, hit_y, familiar.x, familiar.y, float(style.reach_x), float(style.reach_y), bat_torso_top};
      bat_contact = FindTarget(base, familiar.x, familiar.y, attack.target, true, &dive);
      can_hit = bat_contact.handle != 0;
      if (can_hit) AimPoint(bat_contact, familiar.x, familiar.y, hit_x, hit_y);
    }
  } else {
    hit_x += direction * 29.0f;
    can_hit = target.handle && strike_age >= 3 && std::abs(aim_x - hit_x) <= style.reach_x &&
              std::abs(aim_y - hit_y) <= style.reach_y;
  }
  // Resolve once per pass. The native attack request handles resistances,
  // ownership, damage numbers and any other enemies in the same rectangle.
  if (!attack.struck && can_hit) {
    const uint32_t element = demon ? kDemonElements[attack.spell] : 0;
    const float damage = Power(ctx, base, owner, familiar.copies, style.min_power, style.max_power);
    if (can_hit) NoteStrike(base, familiar, owner, bat ? bat_contact : target);
    attack.struck = Hit(ctx, base, owner, hit_x, hit_y, damage, style.reach_x, style.reach_y, element,
                        bat_contact.handle, bat_torso_top);
    if (attack.struck && familiar.events++ < 40)
      REXLOG_INFO("[familiar] {} attack {:08X}: {:.0f} power, element {:X}",
                  style.name, attack.target, damage, element);
  }
  if (strike_age >= style.strike_ticks) {
    if (demon) attack.spell = (attack.spell + 1) % std::size(kDemonElements);
    FinishAttack(attack, style);
  }
}

// ---- Faerie --------------------------------------------------------------
// SotN's Faerie (servant tt_002) reduced to the user's design: she never
// attacks and never uses items. She follows as UpdateServantDefault does:
// 24 px behind Alucard and 32 px above his body centre plus an 8 px figure
// eight, turning at most max_angle a tick and moving 0.5 / 1 / 2 / 4 px a
// tick as the gap passes 40 / 60 / 100 / 256 px (a quarter of the gap past
// that). When a status ailment is on him (poison, curse or stone) or his HP
// is under kFaerieHealBelow, she flies to the spot 24 px in front of and
// above him like SotN's UseUncurse / UsePotion, plays animation 18, acts on
// its 12th pose and rests 60 ticks. Cure and heal have separate cooldowns
// from the cards owned. The cure is the Remedy item's own call (8245B100:
// 8244DCA0(owner, status, 0, 0.0) for each active status). The heal is
// Charlotte's native Heal object from the skill factory (kind 8, index 2)
// at level = cards - 1, so it has Heal's power and look; if no object comes
// back she heals the same amount (82533878) directly. Only Alucard's own
// machine changes his status or HP, which HoD syncs; every machine runs her
// movement, animation and voice from the synced HP and status.
constexpr uint32_t kSkillFactory = 0x82487EF8, kSpellPower = 0x82533878, kCureStatus = 0x8244DCA0;
constexpr int kStatusCount = 3;           // 0 poison (mask 0x400), 1 curse (0x200), 2 stone (0x800)
constexpr int kFaerieUsePose = 11, kFaerieRestTicks = 60, kFaerieReachTicks = 150;
uint32_t heal_scratch = 0;

void SetAnim(FaerieAnim& a, int anim) {
  if (a.anim == anim || anim < 0 || anim >= 46 || kFaerieAnimStart[anim] == 0xFFFF) return;
  a.anim = anim; a.step = kFaerieAnimStart[anim]; a.ticks = kFaerieSteps[a.step].ticks;
}
// One tick of ServantUpdateAnim: a step of 0 ticks loops the animation,
// -1 holds the last pose and -2 goes to the animation in its part field.
void StepAnim(FaerieAnim& a) {
  if (a.anim < 0 || --a.ticks > 0) return;
  const auto& next = kFaerieSteps[a.step + 1];
  if (next.ticks > 0) { ++a.step; a.ticks = next.ticks; }
  else if (next.ticks == 0) { a.step = kFaerieAnimStart[a.anim]; a.ticks = kFaerieSteps[a.step].ticks; }
  else if (next.ticks == -1) a.ticks = 1 << 30;
  else { const int target = next.part; a.anim = -1; SetAnim(a, target); }
}
int Pose(const FaerieAnim& a) { return a.anim < 0 ? -1 : a.step - kFaerieAnimStart[a.anim]; }
uint32_t PartFrame(const FaerieAnim& a) {
  const int part = a.anim < 0 ? 0 : kFaerieSteps[a.step].part;
  return part > 1 && part < 126 ? kFaeriePartFrame[part] : 0;  // part 1 is SotN's blank
}
// Her wings are a separate sprite (UpdateSubEntityWings): sotn-decomp's
// g_WingAnimationParams for the body animations used here.
struct WingUse { int anim; bool behind; };
WingUse Wings(int body) {
  switch (body) {
    case 11: case 12: case 14: case 15: case 41: case 44: return {4, true};
    case 16: return {3, false};
    default: return {-1, false};  // 18: the use pose draws no wings
  }
}
// SelectAnimationFrame: hover, turn into flight, fly, or fly up / down.
void SelectFaerieAnim(Familiar& g, float vx, float vy) {
  auto& f = g.faerie;
  const float ax = std::abs(vx), ay = std::abs(vy);
  if (ay > ax) {
    if (ay < .5f) {
      if (f.flag == 1) { f.flag = 0; SetAnim(f.body, 41); }
      else if (f.flag == 2) { f.flag = 0; SetAnim(f.body, 14); }
    } else if (ay > 1) { f.flag = 2; SetAnim(f.body, vy >= 0 ? 11 : 12); }
  } else {
    if (ax > .5625f) {
      if (f.flag == 0) { f.flag = 1; SetAnim(f.body, 15); }
      else if (f.flag == 2) { f.flag = 0; SetAnim(f.body, 14); }
    } else if (ax < .375f) {
      if (f.flag == 1) { f.flag = 0; SetAnim(f.body, 41); }
      else if (f.flag == 2) { f.flag = 0; SetAnim(f.body, 14); }
    }
    if (ax > .5f) g.left = vx >= 0;  // SotN's facingLeft: her art faces left
  }
}

// The player component's status query (vtable +328, as the item code asks).
bool StatusActive(PPCContext& ctx, uint8_t* base, uint32_t owner, int status) {
  const auto component = Read(base, owner + 0x924);
  if (!component) return false;
  const auto method = Read(base, Read(base, component) + 328);
  if (method < 0x82000000 || method >= 0x90000000) return false;
  PPCContext call = ctx; call.r3.u64 = component; call.r4.u64 = uint32_t(status);
  rex::runtime::ResolveIndirectFunction(method)(call, base);
  return (call.r3.u32 & 0xFF) != 0;
}
bool AnyStatus(PPCContext& ctx, uint8_t* base, uint32_t owner) {
  for (int i = 0; i < kStatusCount; ++i) if (StatusActive(ctx, base, owner, i)) return true;
  return false;
}
bool LowHp(uint8_t* base, uint32_t player) {
  const auto stats = Read(base, player + 88); if (!stats) return false;
  const float hp = Float(base, stats + 4), maximum = Float(base, stats + 16) + Float(base, stats + 28);
  return std::isfinite(hp) && std::isfinite(maximum) && maximum > 0 && hp > 0 && hp < maximum * kFaerieHealBelow;
}
float Cooldown(const float (&range)[2], unsigned copies) {
  const unsigned n = std::clamp(copies, 1u, kMaxFamiliarCopies);
  return range[0] + (range[1] - range[0]) * float(n - 1) / float(kMaxFamiliarCopies - 1);
}

// Queue the familiar sound bank (Shield Rod's EnsureSounds): 82590680(path,
// kind 1 = XSB / 2 = XWB, common group), then 82590878 to start the loads.
void EnsureFamiliarSounds(PPCContext& ctx, uint8_t* base) {
  static uint32_t queue = 0, path_scratch = 0; static unsigned queued = 0;
  const auto current = Read(base, 0x82930B10);  // the native audio queue (changes on reload)
  if (!current) { queue = 0; queued = 0; return; }
  if (queue != current) { queue = current; queued = 0; }
  if (queued == 3) return;
  if (!path_scratch) path_scratch = AlignedScratch(64);
  if (!path_scratch) return;
  const char* paths[] = {kFamiliarBankXsb, kFamiliarBankXwb};
  bool changed = false;
  for (unsigned i = 0; i < 2; ++i) if (!(queued & (1u << i))) {
    std::memcpy(base + path_scratch, paths[i], std::strlen(paths[i]) + 1);
    PPCContext load = ctx; load.r3.u64 = path_scratch; load.r4.u64 = i + 1; load.r5.u64 = 0;
    rex::runtime::ResolveIndirectFunction(0x82590680)(load, base);
    if (load.r3.u32) { queued |= 1u << i; changed = true; }
  }
  if (changed) {
    PPCContext kick = ctx; rex::runtime::ResolveIndirectFunction(0x82590878)(kick, base);
    REXLOG_INFO("[familiar] familiar sound bank queue mask {} (3 = both files)", queued);
  }
}

void FaerieHeal(PPCContext& ctx, uint8_t* base, Familiar& g, uint32_t owner, uint32_t player) {
  const auto handle = Read(base, owner + 4);
  const unsigned level = std::clamp(g.copies, 1u, kMaxFamiliarCopies) - 1;
  if (!heal_scratch) heal_scratch = AlignedScratch(16);
  uint32_t spell = 0;
  if (heal_scratch) {
    Float(base, heal_scratch, Float(base, owner + 0x8EC)); Float(base, heal_scratch + 4, Float(base, owner + 0x8F0));
    PPCContext call = ctx;
    call.r3.u64 = kFaerieHealKind; call.r4.u64 = kFaerieHealIndex; call.r5.u64 = handle;
    call.r6.u64 = heal_scratch; call.r7.u64 = 0; call.r8.u64 = 0; call.r9.u64 = level; call.r10.u64 = 0;
    rex::runtime::ResolveIndirectFunction(kSkillFactory)(call, base);
    spell = call.r3.u32;
  }
  if (spell) {
    REXLOG_INFO("[familiar] Faerie cast Heal (level {}): object {:08X}", level + 1, spell);
    return;
  }
  PPCContext power = ctx;
  power.r3.u64 = kFaerieHealKind; power.r4.u64 = kFaerieHealIndex; power.r5.u64 = handle; power.r6.u64 = level;
  rex::runtime::ResolveIndirectFunction(kSpellPower)(power, base);
  const float amount = -float(power.f1.f64);
  const auto stats = Read(base, player + 88);
  if (!stats || !(amount > 0) || !std::isfinite(amount)) return;
  const float hp = Float(base, stats + 4), maximum = Float(base, stats + 16) + Float(base, stats + 28);
  const float gained = std::fmin(maximum, hp + amount) - hp;
  if (!(gained > 0)) return;
  Float(base, stats + 4, hp + gained);
  PPCContext popup = ctx; popup.r3.u64 = owner; popup.r4.u64 = 0; popup.r5.s64 = -int32_t(std::ceil(gained));
  rex::runtime::ResolveIndirectFunction(0x82454000)(popup, base);
  REXLOG_WARN("[familiar] Faerie: no Heal object (level {}); healed {:.0f} HP directly", level + 1, gained);
}

void FaerieAct(PPCContext& ctx, uint8_t* base, Familiar& g, uint32_t owner, uint32_t player) {
  auto& f = g.faerie;
  const bool local = Read(base, owner + 0x930) == 1;
  if (f.action == 1) {
    SoundAt(ctx, base, g.x, g.y, FAERIE_CURE_CUE);
    f.cure_cooldown = Cooldown(kFaerieCureCooldown, g.copies);
    if (!local) return;
    for (int i = 0; i < kStatusCount; ++i) {
      if (!StatusActive(ctx, base, owner, i)) continue;
      PPCContext call = ctx; call.r3.u64 = owner; call.r4.u64 = uint32_t(i); call.r5.u64 = 0; call.f1.f64 = 0;
      rex::runtime::ResolveIndirectFunction(kCureStatus)(call, base);
      if (g.events++ < 40)
        REXLOG_INFO("[familiar] Faerie cured status {} ({})", i, i == 0 ? "poison" : i == 1 ? "curse" : "stone");
    }
  } else {
    SoundAt(ctx, base, g.x, g.y, FAERIE_HEAL_CUE);
    f.heal_cooldown = Cooldown(kFaerieHealCooldown, g.copies);
    if (local) FaerieHeal(ctx, base, g, owner, player);
  }
}

void TickFaerie(PPCContext& ctx, uint8_t* base, Familiar& g, uint32_t owner, uint32_t player) {
  auto& f = g.faerie;
  const float px = Float(base, owner + 0x8EC), py = Float(base, owner + 0x8F0);
  if (!std::isfinite(px) || !std::isfinite(py)) return;
  const bool player_left = Read(base, player + 0x250) == 1;
  if (f.cure_cooldown > 0) f.cure_cooldown -= kTick;
  if (f.heal_cooldown > 0) f.heal_cooldown -= kTick;
  // Move toward (tx, ty) at SotN's servant rates (16.16 velocities: rcos << 3 = 0.5 px).
  auto fly = [&](float tx, float ty, bool cast) {
    const float dx = tx - g.x, dy = ty - g.y, d = std::sqrt(dx * dx + dy * dy);
    float speed = 2;
    if (!cast) {
      if (d < 40) { speed = .5f; f.max_angle = 0x20; } else if (d < 60) { speed = 1; f.max_angle = 0x40; }
      else if (d < 100) { speed = 2; f.max_angle = 0x60; } else { speed = 4; f.max_angle = 0x80; }
    }
    f.angle = StepAngle(Angle(dx, dy), f.angle, cast ? 0x180 : f.max_angle);
    if (!cast && d >= 256) { g.vx = dx / 4; g.vy = dy / 4; }
    else { g.vx = Cos(f.angle) * speed; g.vy = -Sin(f.angle) * speed; }
    SelectFaerieAnim(g, g.vx, g.vy);
    g.x += g.vx; g.y += g.vy;
    return d;
  };
  switch (f.mode) {
    case FaerieMode::Follow: {
      f.wander = (f.wander + 0x10) & 0xFFF;
      const float tx = px + (player_left ? 24.0f : -24.0f) + Cos(f.wander / 2) * 8;
      const float ty = py - 32 - Sin(f.wander) * 4;
      fly(tx, ty, false);
      // Ailments first (SotN tries its hammer and cures before potions),
      // then the heal below the HP threshold.
      int action = 0;
      if (f.cure_cooldown <= 0 && AnyStatus(ctx, base, owner)) action = 1;
      else if (f.heal_cooldown <= 0 && LowHp(base, player)) action = 2;
      if (action) {
        f.action = action; f.mode = FaerieMode::Fly; f.wait = 0; f.flag = 0; SetAnim(f.body, 14);
        if (g.events++ < 40) REXLOG_INFO("[familiar] Faerie {}", action == 1 ? "sees a status ailment" : "sees low HP");
      }
      break;
    }
    case FaerieMode::Fly: {
      const float d = fly(px + (player_left ? -24.0f : 24.0f), py - 24, true);
      if (d < 2 || ++f.wait > kFaerieReachTicks) { f.mode = FaerieMode::Use; f.wait = 0; SetAnim(f.body, 18); }
      break;
    }
    case FaerieMode::Use:
      g.left = !player_left;  // SotN: facingLeft = !PLAYER.facingLeft, toward him
      if (Pose(f.body) == kFaerieUsePose) {
        FaerieAct(ctx, base, g, owner, player);
        f.mode = FaerieMode::Rest; f.wait = 0;
      }
      break;
    case FaerieMode::Rest:
      if (++f.wait > kFaerieRestTicks) { f.mode = FaerieMode::Follow; f.flag = 0; SetAnim(f.body, 14); }
      break;
  }
  StepAnim(f.body);
  const auto wing = Wings(f.body.anim);
  if (wing.anim >= 0) { SetAnim(f.wings, wing.anim); StepAnim(f.wings); }
}

// Render list for the familiars. Lists draw in order and depth sorts only
// within one. A live scan (November 18) found enemy sprites in lists 3 and 5
// at depth about 25000, with Alucard's body in list 3: in list 3 the Ghost
// drew under the list-5 parts whatever its depth. In list 5 at kDepth it is
// above both. (Card Swap's list 6 is above foreground terrain; 5 is not used
// for that.) Zoomed views (lists 7-10) keep Alucard's list.
constexpr uint32_t kFamiliarList = 5;
struct Layer { uint32_t list = 0xFFFFFFFFu; float depth = kDepth; };
Layer draw_layer;

uint32_t DrawFrame(const PPCContext& original, uint8_t* base, uint32_t body, uint32_t frame,
                   float x, float y, bool flip, float opacity, bool additive = false,
                   float rotation_degrees = 0, float depth = kDepth, uint32_t tint = 0xFFFFFFFFu) {
  const float sx = Float(base, body + 0x28), sy = Float(base, body + 0x2C);
  if (!std::isfinite(sx) || !std::isfinite(sy) || std::abs(sx) < 1e-6f || std::abs(sy) < 1e-6f) return 0;
  if (!std::isfinite(x) || !std::isfinite(y) || std::abs(x) > 1e8f || std::abs(y) > 1e8f) return 0;
  if (!scratch) scratch = AlignedScratch(kSpriteBytes + 64);
  if (!scratch) return 0;
  const auto sprite = scratch;
  std::memcpy(base + sprite, base + body, kSpriteBytes);   // Alucard's own resource at +12
  base[sprite + 0x54] = base[sprite + 0x55] = 0;
  Write(base, sprite + 0xA0, 0); base[sprite + 0xA4] = 1;
  base[sprite + 0x1C] = flip ? 1 : 0;
  rex::memory::store_and_swap<uint16_t>(base + sprite + 116, 0);
  rex::memory::store_and_swap<uint16_t>(base + sprite + 118, 0);
  Float(base, sprite + 0x28, std::abs(sx)); Float(base, sprite + 0x2C, std::abs(sy));
  // Normal alpha: SotN's additive blend over its dark rooms reads as a solid
  // skull, which additive over HoD's brighter scenes would wash out.
  Float(base, sprite + 80, opacity); base[sprite + 140] = additive ? 1 : 0;
  // 823D69E0 passes the sprite's Euler angles to the native radian matrix routine.
  Float(base, sprite + 48, 0); Float(base, sprite + 52, 0);
  Float(base, sprite + 56, rotation_degrees * kRadiansPerDegree);
  // Draw order: 823D2648 copies +0x60 into the packet and each render list
  // draws ascending. The copy inherits Alucard's player depth (15000 + index,
  // 824479D8), which is under enemies; above every layer base (10000-30000)
  // it draws over them, still in his list, so foreground terrain stays on top.
  Float(base, sprite + 0x60, std::max(depth, draw_layer.depth));
  if (draw_layer.list != 0xFFFFFFFFu) Write(base, sprite + 0x78, draw_layer.list);
  // 823D2648's r7 carries the mirroring (bit 2 = horizontal; 823D31C8 builds
  // it from sprite +0x1C for ordinary draws): the frame is mirrored about
  // its anchor only when this bit is set.
  PPCContext draw = original;
  draw.r3.u64 = sprite; draw.r4.u64 = frame; draw.r7.u64 = flip ? 2 : 0; draw.r8.u64 = tint; draw.r9.u64 = 0;
  draw.r5.u64 = uint32_t(int32_t(std::lround(x))); draw.r6.u64 = uint32_t(int32_t(std::lround(y)));
  __imp__sub_823D2648(draw, base);
  return draw.r3.u32;
}
uint32_t BatFlightFrame(int tick) {
  // Durations and frame order from the SotN Bat's flight loop (TT_000 + 0x4A8).
  // The narrow wings-folded silhouette lasts one tick during each wingbeat.
  struct Pose { unsigned frame; int ticks; };
  constexpr Pose poses[] = {{0, 4}, {1, 1}, {2, 1}, {9, 1}, {3, 1}, {4, 1}, {5, 4},
                            {6, 2}, {7, 2}, {8, 2}, {9, 1}, {2, 2}, {1, 2}};
  tick %= 24;
  for (const auto& pose : poses) {
    if (tick < pose.ticks) return kBatFirstFrame + pose.frame;
    tick -= pose.ticks;
  }
  return kBatFirstFrame;
}

void DrawSwordTrail(const PPCContext& original, uint8_t* base, uint32_t body, const Familiar& familiar) {
  const int windup = SwordWindup(familiar.attack.sword_move);
  const int age = familiar.attack.age;
  const int strike = age - windup;
  constexpr int trail_ticks = 16, segment_ticks = 2;
  const int active = SwordActiveTicks(familiar.attack.sword_move);
  if (strike <= 0 || strike >= active + trail_ticks) return;
  const int first = std::max(windup, age - trail_ticks);
  const int last = std::min(age, windup + active);
  const auto center = SwordSlash(familiar, age);
  // Native single-part packets use local X/right, Y/up. A strip of adjacent
  // tinted quads fills the blade's path without drawing extra sword sprites.
  struct Vertex { float x, y; };
  const auto edge = [&](int tick, bool outer) {
    const auto blade = SwordSlash(familiar, tick);
    const float t = std::clamp(float(age - tick) / trail_ticks, 0.0f, 1.0f);
    // Both ends taper toward the blade tip. A shallow crescent leaves the
    // hilt and the bulk of the blade readable throughout the sweep.
    const float width = .32f * 4 * t * (1 - t);
    const float radius = outer ? 1.04f : 1.03f - width;
    float x = std::lerp(blade.pivot_x, blade.tip_x, radius), y = std::lerp(blade.pivot_y, blade.tip_y, radius);
    if (familiar.attack.sword_move == SwordMove::Rush) {
      x = blade.tip_x;
      y = blade.tip_y + (outer ? -1 : 1) * width * 23;
    }
    return Vertex{x - center.pivot_x, center.pivot_y - y};
  };
  for (int start = first; start < last; start += segment_ticks) {
    const int end = std::min(start + segment_ticks, last);
    Vertex strip[] = {edge(start, true), edge(start, false), edge(end, false), edge(end, true)};
    float area = 0;
    for (unsigned i = 0; i < std::size(strip); ++i) {
      const auto& a = strip[i];
      const auto& b = strip[(i + 1) % std::size(strip)];
      area += a.x * b.y - a.y * b.x;
    }
    if (std::abs(area) < .01f) continue;
    if (area < 0) { std::swap(strip[0], strip[3]); std::swap(strip[1], strip[2]); }
    const float fade = std::clamp(1.0f - (age - (start + end) * .5f) / trail_ticks, 0.0f, 1.0f);
    // For these sprite packets the blend shader takes alpha from the
    // low byte of the packed vertex tint (r8), separate from sprite +80.
    const auto alpha = uint32_t(std::lround(96 * fade));
    if (!alpha) continue;
    const uint32_t tint = 0xFFFFFF00u | alpha;
    const auto packet = DrawFrame(original, base, body, kSwordTrailFrame, center.pivot_x, center.pivot_y,
                                  false, 1, false, 0, kDepth - 1, tint);
    if (!packet) continue;
    const auto vertices = Read(base, packet + 424);
    if (!vertices) continue;
    const float u = (Float(base, vertices + 32) + Float(base, vertices + 2 * 40 + 32)) * .5f;
    const float v = (Float(base, vertices + 36) + Float(base, vertices + 2 * 40 + 36)) * .5f;
    for (unsigned i = 0; i < std::size(strip); ++i) {
      const auto out = vertices + i * 40;
      Float(base, out, strip[i].x); Float(base, out + 4, strip[i].y);
      Float(base, out + 32, u); Float(base, out + 36, v);
    }
  }
}

void DrawFaerie(const PPCContext& original, uint8_t* base, uint32_t body, const Familiar& g) {
  const auto wing = Wings(g.faerie.body.anim);
  const uint32_t wings = wing.anim >= 0 ? PartFrame(g.faerie.wings) : 0, figure = PartFrame(g.faerie.body);
  if (wings && wing.behind) DrawFrame(original, base, body, wings, g.x, g.y, g.left, 1.0f);
  if (figure) DrawFrame(original, base, body, figure, g.x, g.y, g.left, 1.0f);
  if (wings && !wing.behind) DrawFrame(original, base, body, wings, g.x, g.y, g.left, 1.0f);
}
// The spinning Sword and its wheel of translucent brothers.
void DrawBrothers(const PPCContext& original, uint8_t* base, uint32_t body, const Familiar& f) {
  const auto& b = f.brothers;
  const uint32_t frame = f.copies >= kMaxFamiliarCopies ? kSwordUpgradedFrame : kSwordFirstFrame;
  const float fade = b.step == 7 ? std::max(0.0f, 1 - b.t / 30.0f) : 1.0f;
  if (b.step >= 4)
    for (int k = 0; k < std::min(b.copies, kBrothersCopies); ++k) {
      const auto blade = WheelBlade(b, b.start + k * kBrothersSpin);
      DrawFrame(original, base, body, frame, blade.x, blade.y, false, .55f * fade, true, blade.angle);
    }
  if (b.step >= 3) {
    Brothers centre = b; centre.radius = 0;
    const auto blade = WheelBlade(centre, b.angle);
    DrawFrame(original, base, body, frame, blade.x, blade.y, false, fade, false, blade.angle);
  } else {
    DrawFrame(original, base, body, frame, f.x, f.y, false, 1.0f, false, b.angle);
  }
}
void DrawAttacker(const PPCContext& original, uint8_t* base, uint32_t body, const Familiar& familiar) {
  const auto& attack = familiar.attack;
  const bool striking = attack.phase == Phase::Strike;
  uint32_t frame;
  bool flip = attack.facing_left;
  float rotation = 0;
  if (familiar.item == kBatItem) {
    frame = BatFlightFrame(familiar.anim);
    if (striking) rotation = std::clamp(familiar.vy * 5, -22.0f, 22.0f) * (attack.facing_left ? -1 : 1);
    flip = !flip;  // the disc's Bat faces left
  } else if (familiar.item == kDemonItem) {
    constexpr unsigned flap[] = {0, 1, 2, 3, 4, 3, 2, 1};
    frame = kDemonFirstFrame + flap[familiar.anim / 3 % std::size(flap)];
    if (striking && attack.age > 8) {
      frame = kDemonFirstFrame + 5 + 4 * attack.spell + std::min(3, (attack.age - 9) / 4);
    }
  } else {
    if (familiar.brothers.step >= 0) { DrawBrothers(original, base, body, familiar); return; }
    frame = familiar.copies >= kMaxFamiliarCopies ? kSwordUpgradedFrame : kSwordFirstFrame;
    if (attack.phase == Phase::Approach) rotation = attack.sword_approach_angle;
    if (striking) {
      const auto blade = SwordSlash(familiar, attack.age);
      DrawSwordTrail(original, base, body, familiar);
      DrawFrame(original, base, body, frame, blade.x, blade.y, false, 1, false, blade.angle);
      return;
    }
    flip = false;
  }
  DrawFrame(original, base, body, frame, familiar.x, familiar.y, flip, 1.0f, false, rotation);
}
}  // namespace

// Attack phase of a familiar collider (as Nathan's pooled shots): submit its
// rectangle once to HoD's collision manager (82484180) and resolve the request
// (823C4E00), so enemy resistance, damage numbers, kill credit and drops stay
// native and only the owner's machine applies damage (8224E700). Lives 0.12 s.
// A familiar hit's area is submitted in the collision prepare phase
// (824823A0, routed here by shield_rod.cpp), like native attacks and Shield
// Rod's spells; enemies query the lists filled there. Submitting it in the
// attack phase as before, the area was only sometimes in the lists when an
// enemy looked, so most hits missed (user, November 18: the Ghost "missed
// many many times" before a hit landed). Lives 0.12 s.
void PrepareHit(PPCContext& ctx, uint8_t* base, uint32_t hit) {
  const auto status = Read(base, hit + 0x18C);
  if (status & 2) { base[hit + 0x17] = 1; return; }  // resolved last frame
  float dt = float(ctx.f1.f64); if (!(dt > 0 && dt <= .1f)) dt = kTick;
  const float age = Float(base, hit + 0x188) + dt; Float(base, hit + 0x188, age);
  if (age > .12f) { base[hit + 0x17] = 1; return; }
  if (status & 1) return;
  const auto contact_target = Read(base, hit + 0x194);
  uint32_t request;
  if (contact_target) {
    // The monster can replace its hurt shapes between the strike and this
    // phase. Wait briefly for a live shape at the impact point.
    float x = Float(base, hit + 0x1B0), y = Float(base, hit + 0x1B4);
    const int hw = int(Read(base, hit + 0x1B8)), hh = int(Read(base, hit + 0x1BC));
    const Sweep impact{x, y, x, y, float(hw), float(hh), Float(base, hit + 0x198)};
    const auto contact = FindTarget(base, x, y, contact_target, true, &impact);
    if (!contact.handle) return;
    AimPoint(contact, x, y, x, y);
    // Submit through the native area path (82484180), which picks the
    // collision region from the area's own position (823C3150) as native
    // attacks and Shield Rod's spells do. Passing the hurt shape's region
    // straight to 823C4C40 (SubmitContactHit) left hits unseen until a
    // native attack of Alucard's (a weapon swing) went through (user test,
    // November 18).
    Float(base, hit + 0x2C, x); Float(base, hit + 0x30, y);
    Write(base, hit + 0x1A0, uint32_t(-hw)); Write(base, hit + 0x1A4, uint32_t(-hh));
    Write(base, hit + 0x1A8, hw); Write(base, hit + 0x1AC, hh);
    PPCContext area = ctx; area.r3.u64 = hit; area.r4.u64 = hit + 0x1A0;
    rex::runtime::ResolveIndirectFunction(0x82484180)(area, base);
    request = Read(base, hit + 0xAC);
  } else {
    PPCContext area = ctx; area.r3.u64 = hit; area.r4.u64 = hit + 0x1A0;
    rex::runtime::ResolveIndirectFunction(0x82484180)(area, base);
    request = Read(base, hit + 0xAC);
  }
  if (request != 0xFFFFFFFFu) Write(base, hit + 0x18C, 1);
}

// Attack phase (824827F0): resolve the submitted request once, so enemy
// resistance, damage numbers, kill credit and drops stay native and only the
// owner's machine applies damage (8224E700).
void ResolveHit(PPCContext& ctx, uint8_t* base, uint32_t hit) {
  const auto status = Read(base, hit + 0x18C);
  if (!(status & 1) || (status & 2)) return;
  Write(base, hit + 0x18C, status | 2);
  const auto request = Read(base, hit + 0xAC);
  if (request == 0xFFFFFFFFu) return;
  uint32_t mask = 0x40000000u;
  const auto flags = Read(base, hit + 0xB0);
  if (flags & 0x80000000u) {
    PPCContext call = ctx; rex::runtime::ResolveIndirectFunction(kGameContext)(call, base);
    const auto game = call.r3.u32;
    mask = game && Read(base, game + 0xFB8) == 2 ? 15 : 12;
  } else if (flags & 0x40000000u) {
    mask = 3;
  }
  std::memset(base + hit + 0x1C0, 0, 16);
  PPCContext resolve = ctx; resolve.r3.u64 = hit + 0x1C0; resolve.r4.u64 = request; resolve.r5.u64 = mask;
  rex::runtime::ResolveIndirectFunction(0x823C4E00)(resolve, base);
}

// Nathan's module reads the guest hurt record through his player block
// (every player update; the hub runs this as core, so it keeps working while
// the familiars themselves are switched off).
void PublishHurtRecord(uint8_t* base, uint32_t owner) {
  constexpr uint32_t kNathanVtable = 0x836C28E8;
  const auto component = owner && (Read(base, owner + 8) & 2) ? Read(base, owner + 0x924) : 0;
  std::lock_guard guard(seen_lock);
  if (guest_record && component && Read(base, component) == kNathanVtable)
    Write(base, component + hurt_record::kNathanPointer, guest_record);
}

void Frame(PPCContext& ctx, uint8_t* base, uint32_t owner, double seconds) {
  const auto player = AlucardPlayer(base, owner);
  if (!player) return;
  const auto equipment = Read(base, owner + 0x9C8);
  const auto item = equipment ? Read(base, equipment + 13 * 4) : 0;
  const auto style = Style(item);
  const bool faerie = item == kFaerieItem;
  const bool equipped = item == kGhostItem || faerie || style;
  std::lock_guard guard(lock);
  auto* g = Slot(base, owner, equipped);
  if (!g) return;
  if (!equipped || !Alive(base, player)) {
    // SotN's Faerie cries out when Alucard dies (SFX_FAERIE_OH_NO).
    if (g->active && equipped && g->item == kFaerieItem) SoundAt(ctx, base, g->x, g->y, kFaerieCueOhNo);
    g->active = false; g->step = 0; return;
  }
  if (g->item != item) {
    const auto handle = g->handle;
    *g = Familiar{};
    g->owner = owner; g->handle = handle; g->item = item;
  }
  if (!g->active) {
    g->active = true; g->step = 1; g->counter = 0; g->cloud = -1; g->target = {}; g->lost = 0;
    const bool player_left = Read(base, player + 0x250) == 1;
    const float x = style ? style->hover_x : faerie ? 24.0f : 18.0f, y = style ? style->hover_y : 32.0f;
    g->x = Float(base, owner + 0x8EC) + (player_left ? x : -x);
    g->y = Float(base, owner + 0x8F0) - y;
    g->vx = g->vy = 0; g->left = !player_left; g->ticks = 0;
    g->attack = {};
    g->attack.facing_left = player_left;
    g->faerie = {};
    g->faerie.wander = int(owner >> 4) & 0xFFF;
    SetAnim(g->faerie.body, 14);
    const bool local = Read(base, owner + 0x930) == 1;
    // Copies affect the new familiars' attack power only. Remote clients
    // can animate the same cadence from the equipped item alone.
    g->copies = (local || !style) ? CopiesOwned(ctx, base, item) : 1;
    if (!g->logged) {
      g->logged = true;
      REXLOG_INFO("[familiar] {} on for player {} ({}), {} card(s)", style ? style->name : faerie ? "Faerie" : "Ghost",
                  Read(base, owner + 0x938), local ? "local" : "remote", g->copies);
    }
  }
  if (!std::isfinite(g->x) || !std::isfinite(g->y)) { g->active = false; return; }
  float dt = float(seconds);
  if (!(dt > 0) || dt > .25f) dt = kTick;
  g->ticks += dt / kTick;
  EnsureFamiliarSounds(ctx, base);  // every familiar's sounds are in SE_FAMILIAR
  if (item == kSwordItem && Read(base, owner + 0x930) == 1) BrothersInput(ctx, base, *g, owner, player);
  // A card of the equipped familiar picked up during the run takes effect
  // within a second: power, the Ghost's delay and soul steal, the Faerie's
  // cooldowns, the Sword's art (user, November 19). Read as when it came out.
  if (++g->recount >= 60 && (Read(base, owner + 0x930) == 1 || !style)) {
    g->recount = 0;
    const unsigned copies = CopiesOwned(ctx, base, item);
    if (copies != g->copies) {
      static unsigned changes = 0;
      if (changes++ < 20) REXLOG_INFO("[familiar] {} now has {} card(s) (was {})",
                                      style ? style->name : faerie ? "Faerie" : "Ghost", copies, g->copies);
      g->copies = copies;
    }
  }
  for (int n = 0; g->ticks >= 1 && n < 4; ++n) {
    g->ticks -= 1;
    if (faerie) TickFaerie(ctx, base, *g, owner, player);
    else if (style) TickAttack(ctx, base, *g, owner, player, *style);
    else TickGhost(ctx, base, *g, owner, player);
  }
  if (g->ticks > 1) g->ticks = 0;
}

void Draw(const PPCContext& original, uint8_t* base, uint32_t body) {
  if (!body) return;
  std::lock_guard guard(lock);
  draw_layer = {};
  if (Read(base, body + 0x78) < kFamiliarList) draw_layer.list = kFamiliarList;
  for (auto& g : familiars) {
    if (!g.owner || !g.active || EntityOf(base, g.handle) != g.owner || Read(base, g.owner + 0x2C) != body) continue;
    if (g.item == kFaerieItem) {
      DrawFaerie(original, base, body, g);
      continue;
    }
    if (g.item != kGhostItem) {
      DrawAttacker(original, base, body, g);
      continue;
    }
    // Idle: servant parts 1-8, two ticks each. Odd parts carry the blue
    // flame palette and even ones the green, so the fire alternates as in
    // SotN; the opacity pulse is SotN's, kept between 80 and 100 %.
    const unsigned part = 1 + g.anim / 2;
    const float opacity = .8f + .2f * (g.opacity - 64) / 64.0f;
    DrawFrame(original, base, body, kGhostFirstFrame + part - 1, g.x, g.y, g.left, opacity);
    if (g.cloud >= 0) {  // attack ring: 8 orbs closing in, additive like SotN's DRAW_TRANSP prims
      const float radius = float(std::max(0, g.ring_ticks - g.cloud));
      for (int i = 0; i < 8; ++i) {
        const int a = (g.ring + (i << 9)) & 0xFFF;
        DrawFrame(original, base, body, kGhostOrbFrame, g.x + Cos(a) * radius, g.y - Sin(a) * radius, false, 1.0f, true);
      }
    }
  }
}
void ObserveHurtShape(uint8_t* base, uint32_t handle, uint32_t shape, uint32_t flags, uint32_t region, uint32_t caller) {
  const auto enemy = EntityOf(base, handle);
  if (!shape || !enemy || !(Read(base, enemy + 8) & 4)) return;
  // Hurt boxes are the enemy records with bit 0x8 (run 219: a sleeping Treant
  // or Man-Eating Plant registers only 0x40000008, which long-range spells hit
  // from across the map; awake enemies add 0x40000009 bodies). Shield Rod's
  // 0x15 test needed bit 0x1, so sleeping enemies were invisible until Alucard
  // walked up to them. 0x2 (with 0x8 on the Plant's shots) is left out.
  const bool accepted = (flags & 0x8) && !(flags & 2) && IsEnemy(base, enemy);  // not IsHurtRecord: 0x10 alone unseen
  if (!accepted) return;
  const auto box = HurtBounds(base, shape, handle, region);
  if (!box.handle) return;
  const auto now = std::chrono::steady_clock::now();
  std::lock_guard guard(seen_lock);
  // One slot per box. Shape objects do not identify a box: most enemies
  // re-create theirs every frame, and Dracula's last form registers all six
  // of its boxes (three heads 0x9, a wide 0x8, two guarding hands 0x19, every
  // frame, run 242) through one stack object (82284F48: r3 = r1+0xB0), so
  // keyed by it each box overwrote the last and only a hand was ever seen
  // (user, November 19: weapons hit the heads, the Ghost the hands). A box is
  // the same as a cached one with its enemy, call site and flags whose centre
  // is within kSameBox px (it moves a few px a frame).
  constexpr float kSameBox = 8;
  SeenShape* slot = nullptr;
  SeenShape* same = nullptr;
  float closest = kSameBox * kSameBox;
  for (auto& s : seen_shapes) {
    if (s.box.handle == handle && s.box.part == caller && s.box.flags == flags) {
      const float dx = s.box.x - box.x, dy = s.box.y - box.y, d = dx * dx + dy * dy;
      if (d <= closest) { closest = d; same = &s; }
    }
    if (!slot || !s.box.handle || (slot->box.handle && s.seen < slot->seen)) slot = &s;  // free or oldest
  }
  if (same) slot = same;
  slot->shape = shape; slot->box = box; slot->box.shape = shape; slot->seen = now;
  slot->box.part = caller; slot->box.flags = flags;
  if (!guest_record) {
    guest_record = AlignedScratch(hurt_record::kBytes);
    if (guest_record) hurt_record::Init(base, guest_record);
  }
  if (guest_record) {
    hurt_record::Box shared;
    shared.handle = box.handle; shared.region = box.region; shared.kind = box.kind;
    shared.x = box.x; shared.y = box.y; shared.x0 = box.x0; shared.y0 = box.y0; shared.x1 = box.x1; shared.y1 = box.y1;
    hurt_record::WriteEntry(base, guest_record, unsigned(slot - seen_shapes.data()), shared, hurt_record::NowMs());
  }
}
// An enemy just lost `damage` HP to a familiar's hit (the 82246DF0 observer
// in shield_rod.cpp; only the machine that applies damage gets here). The
// Ghost's soul steal heals from it.
void Landed(PPCContext& ctx, uint8_t* base, uint32_t hit, float damage) {
  const auto owner = EntityOf(base, Read(base, hit + 0xA4));
  const auto player = owner ? AlucardPlayer(base, owner) : 0;
  if (!player || !(damage > 0)) return;
  std::unique_lock guard(lock, std::try_to_lock);
  if (!guard) return;
  auto* g = Slot(base, owner, false);
  if (!g || !g->active) return;
  g->probe.landed = true;
  if (base[hit + 0x9F] >= 0x80 && base[hit + 0x9F] < 0x80 + kBrothersCopies) ++g->brothers.landed;
  if (g->item != kGhostItem || g->copies - 1 < kGhostStealFromIndex || g->steals.size() >= 8) return;
  Familiar::Steal steal;
  steal.enemy = Read(base, hit + 0x194);
  steal.x = Float(base, hit + 0x2C); steal.y = Float(base, hit + 0x30);
  // The HP the hit took, at most kGhostStealMax (user, November 19).
  steal.amount = float(std::max(1, int(std::lround(std::min(damage, kGhostStealMax)))));
  g->steals.push_back(steal);
}

// A remote Alucard's announced Sword Brothers (see AnnounceBrothers): run it
// on this machine's copy of him. Its hits belong to him, so only his machine
// applies their damage.
void SpawnEvent(PPCContext& ctx, uint8_t* base) {
  const auto owner = ctx.r3.u32;
  if (!owner || ctx.r5.u32 != 11 || ctx.r6.s32 != 1 || (ctx.r4.u32 & 0xFFFF) != kSwordItem ||
      (ctx.r9.u32 & 0xFFFF) != kBrothersTagA || (ctx.r10.u32 & 0xFFFF) != kBrothersTagB ||
      !(Read(base, owner + 8) & 2) || Read(base, owner + 0x930) == 1) return;
  std::lock_guard guard(lock);
  auto* g = Slot(base, owner, false);
  if (!g || !g->active || g->item != kSwordItem) return;
  StartBrothers(*g);
  REXLOG_INFO("[familiar] online player {} cast Sword Brothers", Read(base, owner + 0x938));
}
}  // namespace harmony::alucard_familiar

// ---- Handlers in the shared chains (core/runtime/hod_hooks.h) -------------
// The familiars have no overrides of their own: everything they need runs
// through these registrations. Orders are listed in docs/HOOKS.md.
namespace {
namespace fm = harmony::alucard_familiar;

float GuestFloat(uint8_t* base, uint32_t a) { return std::bit_cast<float>(hod::Read32(base, a)); }

// 8244CA98: a remote Alucard's Sword Brothers cast (see AnnounceBrothers).
void SpawnEventHandler(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  fm::SpawnEvent(ctx, base);
  next(ctx, base);
}
// 824823A0 / 824827F0: the familiars' own attack areas ("FMLG").
void ColliderPrepare(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto hit = ctx.r3.u32;
  if (hod::AttackCollider(base, hit) && hod::ColliderTag(base, hit) == fm::kHitTag) { fm::PrepareHit(ctx, base, hit); return; }
  next(ctx, base);
}
void ColliderAttack(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto hit = ctx.r3.u32;
  if (hod::AttackCollider(base, hit) && hod::ColliderTag(base, hit) == fm::kHitTag) { fm::ResolveHit(ctx, base, hit); return; }
  next(ctx, base);
}
// 823C4C40 (under the collision lock): every registered shape feeds the
// enemy hurt-box cache the familiars target from, and its guest copy that
// Nathan's module reads. Registered as core: it serves both mods.
void HurtShapeFeed(const PPCContext& original, uint8_t* base, uint32_t handle, uint32_t result) {
  if (result == 0xFFFFFFFFu) return;
  fm::ObserveHurtShape(base, handle, original.r3.u32, original.r4.u32, original.r5.u32, uint32_t(original.lr));
}
// 82246DF0: an enemy really lost HP to a familiar hit (the Ghost's soul steal).
void EnemyHp(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto enemy = ctx.r3.u32, pair = ctx.r5.u32;
  uint32_t hit = 0, target = 0;
  float before = 0;
  if (enemy && pair && (ctx.r4.u32 & 1) && (hod::Read32(base, enemy + 8) & 4) &&
      hod::EntityOf(base, hod::Read32(base, enemy + 4)) == enemy) {
    const auto attack = hod::Read32(base, pair);
    if (hod::GuestAddress(attack)) {
      const auto candidate = hod::EntityOf(base, hod::Read32(base, attack + 0x10));
      if (hod::AttackCollider(base, candidate) && hod::ColliderTag(base, candidate) == fm::kHitTag) {
        hit = candidate;
        target = hod::Read32(base, enemy + 4);
        before = GuestFloat(base, enemy + 152);
      }
    }
  }
  next(ctx, base);
  if (hit && hod::EntityOf(base, target) == enemy && std::isfinite(before) && GuestFloat(base, enemy + 152) < before)
    fm::Landed(ctx, base, hit, before - GuestFloat(base, enemy + 152));
}
// 8244FFF8 player update: every Alucard's familiar, on every machine.
void PlayerUpdate(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  const double seconds = ctx.f1.f64;
  next(ctx, base);
  fm::Frame(ctx, base, owner, seconds);
}
void PublishHurtRecordHandler(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  next(ctx, base);
  fm::PublishHurtRecord(base, owner);
}
// 824476B8 owner draw: the familiar, after Alucard's body.
void OwnerDraw(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  next(ctx, base);
  if (owner) fm::Draw(ctx, base, hod::Read32(base, owner + 0x2C));
}
}  // namespace

HOD_HOOK(kSpawnEvent, kFamiliars, 20, SpawnEventHandler);
HOD_HOOK(kColliderPrepare, kFamiliars, 30, ColliderPrepare);
HOD_HOOK(kColliderAttack, kFamiliars, 20, ColliderAttack);
HOD_SHAPE_OBSERVER(kCore, 20, HurtShapeFeed);
HOD_HOOK(kEnemyHp, kFamiliars, 20, EnemyHp);
HOD_HOOK(kPlayerUpdate, kFamiliars, 10, PlayerUpdate);
HOD_HOOK(kPlayerUpdate, kCore, 5, PublishHurtRecordHandler);
HOD_HOOK(kOwnerDraw, kFamiliars, 40, OwnerDraw);
