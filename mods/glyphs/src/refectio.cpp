// Refectio (package 20): a Shanoa glyph that heals her over time.
//
// The glyph itself is data: a DLC glyph row (modding/tools/refectio.py) made
// from Luminatio's row, so the menus, MP cost, cast motion, permission and
// chest drops are all native. Like every DLC glyph, casting it ends in the
// skill factory 82487EF8(kind 3 = glyph, global glyph index, owner handle,
// position, ..., level - 1 in r9). Base glyphs 0-3 are exe classes; any other
// index is looked up in the DLC shot registry (82486AB0), which has nothing
// for Refectio, so natively the cast creates no object and returns 0.
//
// This file answers the factory for Refectio's index instead: it works out
// the glyph's power with the game's own spell formula (82533878, the same
// numbers Charlotte's Heal uses: L1 + (Lmax - L1) * level / 8, then
// + (P / 64 + 0.25) * INT; negative power is healing) and spreads that total
// over kTicks ticks, one every kTickSeconds, on the caster's own player
// update (8244FFF8, which receives the frame's seconds in f1). Recasting
// while it runs restarts it; it does not stack. It ends on death or when the
// player object goes away (stage exit).
//
// Online co-op: only the caster's machine heals (owner +0x930 == 1); HoD
// syncs HP from there, as it does for Charlotte's Heal. Each tick shows the
// native green recovery number (82454000) on the caster's screen.
//
// Mastery: native glyphs gain one point per enemy hit (8245D008); each tick
// that restores HP counts as Refectio's hit.
//
// Retries: when the cast comes from the hand-item launcher (8246FB18 calls
// 824881C8 -> 82487EF8, return address 8246FC40), r6 is launcher + 0x48 and
// launcher + 0x9C is its "fired" flag. It is set here on the first call, so
// one launcher can start the regen once at most.
#include "../generated/default/harmonyrecomp_init.h"
#include "refectio.h"
#include "refectio_balance.h"
#include "hod_guest.h"
#include "hod_hooks.h"
#include <rex/logging.h>
#include <rex/memory/utils.h>
#include <rex/system/xmemory.h>
#include <rex/system/kernel_state.h>
#include <rex/filesystem/vfs.h>
#include <cstdio>
#include <string>
#include <algorithm>
#include <array>
#include <bit>
#include <cstring>
#include <cmath>
#include <cstdint>
#include <mutex>

REX_EXTERN(__imp__sub_82487EF8);
REX_EXTERN(__imp__sub_8244FFF8);
REX_EXTERN(__imp__sub_8248A690);
REX_EXTERN(__imp__sub_823D2648);

namespace harmony::refectio {
namespace {
constexpr uint32_t kGlyphKind = 3;                 // factory / power kind for glyphs
constexpr uint32_t kLauncherReturn = 0x8246FC40;   // 8246FB18's call into 824881C8
constexpr uint32_t kSpellPower = 0x82533878;       // (kind, index, owner handle, level) -> f1
constexpr uint32_t kRecoveryNumber = 0x82454000;   // (owner, 0, -amount): green number
constexpr uint32_t kAddMastery = 0x8245D008;       // (owner handle, 3 = glyph, glyph index)
constexpr float kRepeatGuard = 0.5f;               // seconds; other callers only

uint32_t Read(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
float Float(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Read(base, a)); }
void Float(uint8_t* base, uint32_t a, float v) {
  rex::memory::store_and_swap<uint32_t>(base + a, std::bit_cast<uint32_t>(v));
}

uint32_t EntityOf(uint8_t* base, uint32_t handle) {  // handle -> object (entity manager table)
  const auto manager = Read(base, 0x8291D9F0);
  if (!manager || !handle) return 0;
  const auto table = Read(base, manager + 0xAC);
  if (!table) return 0;
  const auto end = Read(base, manager + 0xB0);
  const uint32_t offset = (handle & 0xFFFF) << 4;
  if (end < table || end - table > 65536 * 16 || end - table < 16 || offset > end - table - 16) return 0;
  const auto entry = table + offset;
  return Read(base, entry) == handle ? Read(base, entry + 4) : 0;
}
uint32_t PlayerOf(uint8_t* base, uint32_t owner) {
  return owner && (Read(base, owner + 8) & 2) ? Read(base, owner + 0x924) : 0;
}
bool Local(uint8_t* base, uint32_t owner) { return Read(base, owner + 0x930) == 1; }
uint32_t Stats(uint8_t* base, uint32_t owner) {
  const auto player = PlayerOf(base, owner);
  return player ? Read(base, player + 88) : 0;
}
bool Alive(uint8_t* base, uint32_t owner) {
  const auto stats = Stats(base, owner);
  return stats && Float(base, stats + 4) > 0 && Read(base, stats + 308) == 0;
}

struct Regen {
  uint32_t owner = 0, handle = 0;
  float total = 0;      // HP over the whole regen
  unsigned done = 0;    // ticks paid
  float clock = 0;      // seconds since the last tick
  float age = 0;        // seconds since the cast
};
std::array<Regen, 8> regens{};
std::mutex lock;

Regen* Find(uint32_t owner) {
  for (auto& r : regens) if (r.owner == owner) return &r;
  return nullptr;
}

// ---------------------------------------------------------------- effect -----
// Cast rings use the six two-frame poses of OoE's ring sequence. Its
// Refectio routine (020806C0) animates an attached plume and emits small
// detached flecks every fourth tick. Its plume renderer (02080658) draws
// two translucent layers in ten strips warped by recent positions.
constexpr uint32_t kSpriteLookup = 0x823D2520;     // sprite instance (+8 name hash) -> +12 resource
constexpr uint32_t kLoadResource = 0x82486F58;     // (path, 0): skill resource preload
constexpr unsigned kSpriteBytes = 192;
constexpr float kFleckLife = 32;  // 020808E8 requests 0x20 ticks
constexpr float kTurn = 6.28318530718f;
constexpr float kSmokeSway = kTurn * 0x444 / 65536;  // OoE 02080114
constexpr float kPlumeHeight = 0.72f;
struct SmokePoint { float x = 0, y = 0; };
struct Fleck {
  float x = 0, y = 0, scale_x = 1, scale_y = 1;
  float drift = 0, rise = 0, age = -1;
  unsigned pose = 0;
};
struct Fx {
  uint32_t owner = 0, handle = 0;
  float ring = -1;     // frames since the cast; < 0 = no rings
  float smoke = 0;     // frames of smoke left
  float smoke_age = 0;
  float spawn = 0;     // frames until the next fleck
  uint32_t seed = 1;
  bool ring_started = false;
  bool has_trail = false;
  float plume_phase = 0;
  SmokePoint last_anchor;
  std::array<SmokePoint, 2 * kSmokeBands + 2> trail{};
  std::array<Fleck, 16> flecks{};
};
std::array<Fx, 8> effects{};
uint32_t scratch = 0, path = 0;       // guest memory: sprite copies, the path string
int name_choice = -1;                 // which spelling of the resource name resolved
uint32_t requested_for = 0;           // resource manager the load was requested from

Fx* FindFx(uint32_t owner) {
  for (auto& f : effects) if (f.owner == owner) return &f;
  return nullptr;
}
float Random(Fx& f) {                 // xorshift, 0..1
  f.seed ^= f.seed << 13; f.seed ^= f.seed >> 17; f.seed ^= f.seed << 5;
  return (f.seed & 0xFFFFFF) / float(0x1000000);
}
uint32_t Hash(const char* s) {        // 825BFF28: FNV-1, case-sensitive
  uint32_t h = 0x811C9DC5u;
  for (; *s; ++s) { h *= 0x01000193u; h ^= uint8_t(*s); }
  return h;
}
uint32_t Scratch(uint8_t* base) {
  if (!scratch) {
    const auto raw = REX_KERNEL_MEMORY()->SystemHeapAlloc(2 * kSpriteBytes + 256 + 15);
    if (!raw) return 0;
    scratch = (raw + 15) & ~15u;
    path = scratch + 2 * kSpriteBytes;
    static_assert(sizeof kFxPath < 256);
    std::memcpy(base + path, kFxPath, sizeof kFxPath);
  }
  return scratch;
}

// The loaded sprite resource, or 0. HoD keys resources by an FNV-1 hash of
// the name; which spelling the loader used is found once and remembered.
uint32_t Resource(PPCContext& ctx, uint8_t* base, uint32_t body) {
  if (!body || !Scratch(base)) return 0;
  static const char* const names[] = {kFxName, "P_RFX00", "p_rfx00.opd", "rfx00"};
  const int first = name_choice >= 0 ? name_choice : 0, last = name_choice >= 0 ? name_choice + 1 : 4;
  for (int k = first; k < last; ++k) {
    const auto lookup = scratch;
    std::memcpy(base + lookup, base + body, kSpriteBytes);
    base[lookup] = 1;
    rex::memory::store_and_swap<uint32_t>(base + lookup + 8, Hash(names[k]));
    rex::memory::store_and_swap<uint32_t>(base + lookup + 12, 0);
    rex::memory::store_and_swap<uint32_t>(base + lookup + 0xA0, 0);
    PPCContext query = ctx;
    query.r3.u64 = lookup;
    rex::runtime::ResolveIndirectFunction(kSpriteLookup)(query, base);
    if (const auto resource = Read(base, lookup + 12)) {
      if (name_choice < 0) REXLOG_INFO("[refectio] effect sprite found as \"{}\"", names[k]);
      name_choice = k;
      return resource;
    }
  }
  return 0;
}

// Ask HoD to load the sprite (the same preload native skills use), once per
// resource manager, i.e. once per stage. A bare "data/..." path only reaches
// the base game (D:); DLC packages are mounted as DLC00:, DLC01:, ... in an
// order that differs per install, so the device holding package 20's sprite
// is looked up in the file system first.
void RequestLoad(PPCContext& ctx, uint8_t* base) {
  const auto registry = Read(base, 0x8291D9C4), manager = Read(base, 0x8291D920);
  if (!registry || !manager || !Scratch(base) || requested_for == manager) return;
  requested_for = manager;
  // The loader splits names on '/', and the game's own resource paths are
  // "DLCnn:data/..." (e.g. "%s:data/enemy/dictionary/enemy_%03d.dds"); the
  // "DLCnn:\data\..." form is only for raw file reads. Passing that form
  // crashed the loader (823D2280 read guest address 1).
  std::string found;
  for (unsigned n = 0; n < 64 && found.empty(); ++n) {
    char device[8];
    std::snprintf(device, sizeof device, "DLC%02u:", n);
    std::string file = std::string(device) + "\\" + kFxPath;
    std::replace(file.begin(), file.end(), '/', '\\');
    if (REX_KERNEL_FS()->ResolvePath(file)) found = std::string(device) + kFxPath;
  }
  if (found.empty()) {
    REXLOG_WARN("[refectio] effect sprite {} is missing from mounted DLC", kFxPath);
    return;
  }
  std::memcpy(base + path, found.c_str(), found.size() + 1);
  PPCContext load = ctx;
  load.r3.u64 = path;
  load.r4.u64 = 0;
  rex::runtime::ResolveIndirectFunction(kLoadResource)(load, base);
  REXLOG_INFO("[refectio] requested effect sprite {}", found);
}

// One frame of the effect sprite at a world position (the Shield Rod's
// detached-sprite route: a scratch copy of the body's sprite instance with
// the resource swapped and pivot at the frame origin).
uint32_t DrawSprite(const PPCContext& original, uint8_t* base, uint32_t body, uint32_t resource,
                uint32_t frame, float x, float y, float scale_x, float scale_y,
                float opacity, bool additive, float rotation = 0, bool flip = false) {
  const auto sprite = scratch + kSpriteBytes;
  std::memcpy(base + sprite, base + body, kSpriteBytes);
  rex::memory::store_and_swap<uint32_t>(base + sprite + 12, resource);
  base[sprite + 0x54] = base[sprite + 0x55] = 0;
  rex::memory::store_and_swap<uint32_t>(base + sprite + 0xA0, 0);
  base[sprite + 0xA4] = 1;
  base[sprite + 0x1C] = flip ? 1 : 0;
  rex::memory::store_and_swap<uint16_t>(base + sprite + 116, 0);
  rex::memory::store_and_swap<uint16_t>(base + sprite + 118, 0);
  Float(base, sprite + 0x28, scale_x);
  Float(base, sprite + 0x2C, scale_y);
  Float(base, sprite + 80, 1);
  base[sprite + 140] = additive ? 1 : 0;
  Float(base, sprite + 48, 0);
  Float(base, sprite + 52, 0);
  Float(base, sprite + 56, rotation);
  if (!std::isfinite(x) || !std::isfinite(y)) return 0;
  PPCContext draw = original;
  draw.r3.u64 = sprite; draw.r4.u64 = frame;
  draw.r5.u64 = uint32_t(int32_t(std::lround(x))); draw.r6.u64 = uint32_t(int32_t(std::lround(y)));
  // 823D2648 copies r8 to each vertex. The blend shader takes its
  // opacity from the low byte; sprite +80 is separate.
  const auto alpha = uint32_t(std::lround(255 * opacity));
  draw.r7.u64 = flip ? 2 : 0;
  draw.r8.u64 = 0xFFFFFF00u | alpha;
  draw.r9.u64 = 0;
  __imp__sub_823D2648(draw, base);
  return draw.r3.u32;
}

void StartFx(uint32_t owner, uint32_t handle) {
  Fx* f = FindFx(owner);
  if (!f) for (auto& e : effects) if (!e.owner) { f = &e; break; }
  if (!f) return;
  const bool same_caster = f->handle == handle;
  Fx cast;
  cast.owner = owner;
  cast.handle = handle;
  cast.ring = 0;
  cast.smoke = kTicks * kTickSeconds * 60;
  cast.seed = same_caster ? f->seed : (handle * 2654435761u) | 1;
  if (same_caster) cast.flecks = f->flecks;
  *f = cast;
}

void UpdateFx(uint8_t* base, uint32_t owner, float frames) {
  Fx* f = FindFx(owner);
  if (!f) return;
  if (EntityOf(base, f->handle) != owner || !PlayerOf(base, owner) || !Alive(base, owner)) {
    *f = Fx{};
    return;
  }
  if (f->ring >= 0 && f->ring_started) {
    f->ring += frames;
    if (f->ring >= kRingBDelay + kRingFrames * kRingStep) f->ring = -1;
  }
  bool live = false;
  for (auto& fleck : f->flecks) {
    if (fleck.age < 0) continue;
    const float next = fleck.age + frames;
    if (next >= kFleckLife) {
      fleck.age = -1;
      continue;
    }
    fleck.x += fleck.drift * frames;
    fleck.y -= fleck.rise * frames * (1 - (fleck.age + next) / (2 * kFleckLife));
    fleck.age = next;
    live = true;
  }

  if (f->smoke > 0) {
    const float span = std::min(frames, f->smoke);
    const float old_age = f->smoke_age;
    f->smoke_age += span;
    f->smoke -= span;

    const float cx = Float(base, owner + 0x8EC), cy = Float(base, owner + 0x8F0);
    const auto body = Read(base, owner + 0x2C);
    const float sx = body ? std::abs(Float(base, body + 0x28)) : 0;
    const float sy = body ? std::abs(Float(base, body + 0x2C)) : 0;
    if (!f->has_trail) {
      f->trail.fill({cx, cy});
      f->last_anchor = {cx, cy};
      f->has_trail = true;
    }
    // The DS records the wave at 60 Hz. Sample at the same tick boundaries
    // even when HoD delivers a fractional frame or several frames at once.
    for (unsigned tick = unsigned(old_age) + 1; tick <= unsigned(f->smoke_age); ++tick) {
      const float t = (tick - old_age) / frames;
      const float x = std::lerp(f->last_anchor.x, cx, t);
      const float y = std::lerp(f->last_anchor.y, cy, t);
      f->plume_phase = std::fmod(f->plume_phase + (16 + 1008 * Random(*f)) * kTurn / 65536, kTurn);
      std::move_backward(f->trail.begin(), f->trail.end() - 1, f->trail.end());
      f->trail.front() = {x + 4 * sx * std::sin(f->plume_phase),
                          y + 16 * sy * kPlumeHeight * std::sin(tick * kSmokeSway)};
    }
    f->last_anchor = {cx, cy};
    while (f->spawn < span) {
      const float age = frames - f->spawn;
      f->spawn += kWispEvery;
      if (age >= kFleckLife || !(sx > 0) || !(sy > 0) || !std::isfinite(sx) || !std::isfinite(sy)) continue;
      for (auto& fleck : f->flecks) {
        if (fleck.age >= 0) continue;
        const float drift = (Random(*f) * 2 - 1) * kWispDrift * sx;
        const float rise = (kWispRiseMin + Random(*f) * (kWispRiseMax - kWispRiseMin)) * sy;
        const float x = cx + (Random(*f) * 2 - 1) * kWispSpreadX * sx;
        const float y = cy + (kWispOffsetY + (Random(*f) * 2 - 1) * kWispSpreadY) * sy;
        fleck = Fleck{x + drift * age, y - rise * age * (1 - age / (2 * kFleckLife)),
                      sx, sy, drift, rise, age, unsigned(Random(*f) * kFleckFrames)};
        live = true;
        break;
      }
    }
    f->spawn -= span;
  }

  if (!live && f->smoke <= 0 && (!f->ring_started || f->ring < 0)) *f = Fx{};
}

// Adjacent strips share the same warped edge. HoD gives each strip its
// own quad, so modify those vertices instead of translating the whole strip.
void DrawSmoke(const PPCContext& ctx, uint8_t* base, uint32_t body, uint32_t resource,
               const Fx& fx, float cx, float cy, float sx, float sy) {
  const unsigned pose = unsigned(fx.smoke_age / kWispStep) % kWispFrames;
  const float fraction = fx.smoke_age - std::floor(fx.smoke_age);
  const float pulse = 0.5f * std::abs(std::sin(fx.smoke_age * kTurn / 256));
  const float width = 1.25f + 0.5f * std::abs(std::sin(fx.plume_phase + fraction * kTurn / 126));
  const float height = kPlumeHeight * std::min(1.0f, (fx.smoke_age + 1) / 32);
  const float fade = std::min(1.0f, fx.smoke / 16);
  const float rotation = std::sin(fx.smoke_age * kSmokeSway) * kTurn / 128;
  const bool flip = (base[body + 0x1C] & 1) != 0;
  const float y = cy - 8 * sy; // upper-body anchor in HoD

  // 02080318 starts with the last four texture rows and works upward.
  // Edge 0 stays on the caster; only the free end uses the oldest sample.
  std::array<SmokePoint, kSmokeBands + 1> edges{};
  for (unsigned edge = 1; edge <= kSmokeBands; ++edge) {
    const auto& older = fx.trail[2 * edge];
    const auto& newer = fx.trail[2 * edge - 1];
    const float span = float(edge) / (kSmokeBands + 1);
    edges[edge] = {span * (std::lerp(older.x, newer.x, fraction) - cx),
                   0.5f * span * (std::lerp(older.y, newer.y, fraction) - cy)};
  }

  for (unsigned layer = 0; layer < 2; ++layer) {
    const float opacity = pulse + 0.5f * layer;
    const float scale = layer == 0 ? 1.2f : 1.0f;
    const float scale_x = sx * width * scale, scale_y = sy * height * scale;
    std::array<uint32_t, kSmokeBands + 1> tint{};
    for (unsigned edge = 0; edge <= kSmokeBands; ++edge) {
      const float profile = 2 + 12 * std::sin(kTurn * edge / (2 * kSmokeBands));
      const float alpha = (1 + profile * opacity) / 31 * fade;
      tint[edge] = 0xFFFFFF00u | uint32_t(std::lround(255 * alpha));
    }
    float bottom_y = edges.front().y;
    for (unsigned edge = 0; edge < kSmokeBands; ++edge) {
      const unsigned band = kSmokeBands - 1 - edge;
      const auto packet = DrawSprite(ctx, base, body, resource, kSmokeBand0 + pose * kSmokeBands + band,
                                     cx, y, scale_x, scale_y, 1, false, rotation, flip);
      const auto vertices = packet ? Read(base, packet + 424) : 0;
      if (!vertices) {
        bottom_y = edges[edge + 1].y;
        continue;
      }
      // Use the actual band height to keep neighboring quads joined
      // without turning them over when the caster jumps.
      const float band_height = std::abs(Float(base, vertices + 4) - Float(base, vertices + 44)) * scale_y;
      const float top_y = std::min(edges[edge + 1].y, bottom_y + 0.8f * band_height);
      const float center_x = (Float(base, vertices) + Float(base, vertices + 120)) * 0.5f;
      // The native renderer pulls one side back by a quarter on a bend.
      // Use the same shear at both sides of each shared edge.
      for (unsigned i = 0; i < 4; ++i) {
        const bool bottom = i == 1 || i == 2;
        const unsigned boundary = edge + !bottom;
        const auto vertex = vertices + i * 40;
        const float x = Float(base, vertex);
        const float bend = boundary ? edges[boundary].x - edges[boundary - 1].x : 0;
        const bool inside = (x < center_x && bend > 0) || (x > center_x && bend < 0);
        const float shift_x = edges[boundary].x * (inside ? 0.75f : 1.0f);
        Float(base, vertex, x + shift_x / scale_x);
        Float(base, vertex + 4, Float(base, vertex + 4) - (bottom ? bottom_y : top_y) / scale_y);
        rex::memory::store_and_swap<uint32_t>(base + vertex + 28, tint[boundary]);
      }
      bottom_y = top_y;
    }
  }
}

float Heal(PPCContext& ctx, uint8_t* base, uint32_t owner, float amount) {
  const auto stats = Stats(base, owner);
  if (!stats || !(amount > 0)) return 0;
  const float maximum = Float(base, stats + 16) + Float(base, stats + 28), before = Float(base, stats + 4);
  const float after = std::fmin(maximum, before + amount), gained = after - before;
  if (!(gained > 0)) return 0;
  Float(base, stats + 4, after);
  PPCContext popup = ctx;
  popup.r3.u64 = owner;
  popup.r4.u64 = 0;
  popup.r5.s64 = -int32_t(std::ceil(gained));  // HP can be fractional; a real recovery never shows 0
  rex::runtime::ResolveIndirectFunction(kRecoveryNumber)(popup, base);
  return gained;
}

void Cast(PPCContext& ctx, uint8_t* base, uint32_t handle, uint32_t level, uint32_t launcher) {
  const auto owner = EntityOf(base, handle);
  if (!owner || !PlayerOf(base, owner)) return;
  if (launcher) {
    if (base[launcher + 0x9C]) return;  // this launcher already fired
    base[launcher + 0x9C] = 1;
  }
  if (!Alive(base, owner)) return;
  {  // the effect shows for any player this machine sees cast it
    std::lock_guard guard(lock);
    StartFx(owner, handle);
    if (!Resource(ctx, base, Read(base, owner + 0x2C))) RequestLoad(ctx, base);
  }
  if (!Local(base, owner)) return;
  PPCContext call = ctx;  // never disturb the caller's registers
  call.r3.u64 = kGlyphKind;
  call.r4.u64 = kGlyphIndex;
  call.r5.u64 = handle;
  call.r6.u64 = level & 0xFF;
  rex::runtime::ResolveIndirectFunction(kSpellPower)(call, base);
  const float total = -float(call.f1.f64);
  if (!(total > 0) || !std::isfinite(total)) {
    REXLOG_WARN("[refectio] glyph power {} is not a heal; nothing to do", -total);
    return;
  }
  std::lock_guard guard(lock);
  Regen* r = Find(owner);
  if (r && !launcher && r->age < kRepeatGuard) return;
  if (!r) for (auto& e : regens) if (!e.owner) { r = &e; break; }
  if (!r) return;
  *r = Regen{owner, handle, total};
  REXLOG_INFO("[refectio] cast: level {}, {:.1f} HP over {} ticks of {:.2f} s", level + 1, total, kTicks, kTickSeconds);
}

void Frame(PPCContext& ctx, uint8_t* base, uint32_t owner, double seconds) {
  std::lock_guard guard(lock);
  if (seconds > 0 && seconds <= 0.25) UpdateFx(base, owner, float(seconds * 60));
  Regen* r = Find(owner);
  if (!r) return;
  if (EntityOf(base, r->handle) != owner || !PlayerOf(base, owner) || !Local(base, owner) || !Alive(base, owner)) {
    *r = Regen{};
    return;
  }
  float dt = float(seconds);
  if (!(dt > 0)) return;
  if (dt > 0.25f) dt = 0.25f;  // a long hitch does not pay several ticks at once
  r->age += dt;
  r->clock += dt;
  while (r->clock >= kTickSeconds && r->done < kTicks) {
    r->clock -= kTickSeconds;
    ++r->done;
    // Whole-HP ticks that add up to the total: floor(T*k/n) - floor(T*(k-1)/n).
    const float amount = std::floor(r->total * r->done / kTicks) - std::floor(r->total * (r->done - 1) / kTicks);
    // Native glyphs earn one mastery point per enemy hit (their hit method
    // calls 8245D008, which applies the game's rate and Master Ring and only
    // acts for this machine's player). A heal has no hit, so every tick that
    // restores HP counts as one.
    if (Heal(ctx, base, owner, amount) > 0) {
      PPCContext award = ctx;
      award.r3.u64 = r->handle;
      award.r4.u64 = kGlyphKind;
      award.r5.u64 = kGlyphIndex;
      rex::runtime::ResolveIndirectFunction(kAddMastery)(award, base);
    }
  }
  if (r->done >= kTicks) *r = Regen{};
}
}  // namespace

void Draw(const PPCContext& original, uint8_t* base, uint32_t owner) {
  std::lock_guard guard(lock);
  Fx* f = FindFx(owner);
  if (!f) return;
  const auto body = Read(base, owner + 0x2C);
  PPCContext query = original;
  const auto resource = Resource(query, base, body);
  if (!resource) return;
  const float sx = std::abs(Float(base, body + 0x28));
  const float sy = std::abs(Float(base, body + 0x2C));
  if (!(sx > 0) || !(sy > 0) || !std::isfinite(sx) || !std::isfinite(sy)) return;
  const float cx = Float(base, owner + 0x8EC), cy = Float(base, owner + 0x8F0);
  if (f->ring >= 0) {
    // The first load is asynchronous. Start the ring clock at its first draw.
    f->ring_started = true;
    const float ring_y = cy + kRingOffsetY * sy;
    const auto a = unsigned(f->ring / kRingStep);
    if (a < kRingFrames) DrawSprite(original, base, body, resource, kRingA0 + a, cx, ring_y, sx, sy, 1, true);
    if (f->ring >= kRingBDelay) {
      const auto b = unsigned((f->ring - kRingBDelay) / kRingStep);
      if (b < kRingFrames) DrawSprite(original, base, body, resource, kRingB0 + b, cx, ring_y, sx, sy, 1, true);
    }
  }
  if (f->smoke > 0 && f->has_trail) DrawSmoke(original, base, body, resource, *f, cx, cy, sx, sy);
  for (const auto& fleck : f->flecks) {
    if (fleck.age < 0) continue;
    const float remaining = 1 - fleck.age / kFleckLife;
    const float alpha = (1 + std::round(24 * remaining)) / 31;
    DrawSprite(original, base, body, resource, kFleckFrame0 + fleck.pose,
               fleck.x, fleck.y, fleck.scale_x, fleck.scale_y, alpha, false);
  }
}
}  // namespace harmony::refectio

// ---- Handlers in the shared chains (core/runtime/hod_hooks.h) -------------
namespace {
namespace rf = harmony::refectio;

// 8248A690 skill preload (kind, index), when the item is equipped: Refectio's
// index has no native resources, so load its effect sprite here.
void SkillPreload(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  if (ctx.r3.u32 == rf::kGlyphKind && ctx.r4.u32 == rf::kGlyphIndex) {
    {
      std::lock_guard guard(rf::lock);
      rf::RequestLoad(ctx, base);
    }
    ctx.r3.u64 = 1;  // handled
    return;
  }
  next(ctx, base);
}

// 82487EF8 skill factory (kind, index, owner handle, ...): Refectio has no
// skill object; it starts the regen and returns 0 as natively.
void SkillFactory(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  if (ctx.r3.u32 == rf::kGlyphKind && ctx.r4.u32 == rf::kGlyphIndex) {
    const uint32_t launcher = ctx.lr == hod::kGlyphLauncherReturn ? ctx.r6.u32 - 0x48 : 0;
    rf::Cast(ctx, base, ctx.r5.u32, ctx.r9.u32, launcher);
    ctx.r3.u64 = 0;
    return;
  }
  next(ctx, base);
}

// 8244FFF8 player update (owner, f1 = frame seconds): the next heal tick.
void PlayerUpdate(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  const double seconds = ctx.f1.f64;
  next(ctx, base);
  rf::Frame(ctx, base, owner, seconds);
}

// 824476B8 owner draw: the cast rings and rising wisps.
void OwnerDraw(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  next(ctx, base);
  if (owner) rf::Draw(ctx, base, owner);
}
}  // namespace

HOD_HOOK(kSkillPreload, kRefectio, 10, SkillPreload);
HOD_HOOK(kSkillFactory, kRefectio, 10, SkillFactory);
HOD_HOOK(kPlayerUpdate, kRefectio, 30, PlayerUpdate);
HOD_HOOK(kOwnerDraw, kRefectio, 20, OwnerDraw);
