// Arma Custos (Catacombs package 10): Shanoa's STR buff glyph, Cerberus's
// boss-chest drop.
//
// Data (glyph row, text, boss-chest entry, optional OoE art) comes from
// modding/tools/arma_custos.py; numbers from the generated arma_custos_balance.h.
// Casting reaches the skill factory 82487EF8 with (kind 3, kGlyphIndex) like
// every DLC glyph; refectio.cpp's override hands that call here. The cast:
//   * starts a kSeconds STR buff on the caster's own machine. The bonus is
//     live: level value (kStrLevel1..kStrMax over glyph mastery) x (1 +
//     kMissingHpBonus x missing-HP fraction), x kCustosPair while Dextro and
//     Sinestro Custos are in both weapon slots. It is added to the game's STR
//     total (82452658), which physical attacks use (824519C8). Food buffs live
//     in the player's stats object (player vtable +0x13C record), so eating
//     food never replaces it, and it never replaces food. Recasting restarts
//     the timer; it ends on death or stage exit.
//   * shows OoE's own art if the package was built from the player's ROM: the
//     red ring burst, then Cerberus's third head above and behind her for the
//     length of the buff, facing her way, at steady opacity with OoE's own
//     pose loop as its only motion. The sprite loads with the stage. Without
//     that sprite nothing is drawn.
//   * shows on the status screen (8245D9A0 summary): STR at +0x1C, and each
//     hand's ATK (+0x10/+0x14) gains what that STR adds to an attack.
// Mastery: a buff has no hits, so it earns one native mastery point (8245D008,
// game rate and Master Ring included) per kMasteryEvery seconds it runs.
#include "../generated/default/harmonyrecomp_init.h"
#include "arma_custos.h"
#include "hod_guest.h"
#include "hod_hooks.h"
#include "arma_custos_balance.h"
#include <rex/logging.h>
#include <rex/memory/utils.h>
#include <rex/system/xmemory.h>
#include <rex/system/kernel_state.h>
#include <rex/filesystem/vfs.h>
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <chrono>
#include <mutex>
#include <string>

REX_EXTERN(__imp__sub_823D2648);

namespace harmony::arma_custos {
namespace {
constexpr uint32_t kGlyphKind = 3;
constexpr uint32_t kAddMastery = 0x8245D008;      // (owner handle, 3 = glyph, glyph index)
constexpr uint32_t kSpriteLookup = 0x823D2520;    // sprite instance (+8 name hash) -> +12 resource
constexpr uint32_t kLoadResource = 0x82486F58;    // (path, 0)
constexpr unsigned kSpriteBytes = 192;

uint32_t Read(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
float Float(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Read(base, a)); }
void Float(uint8_t* base, uint32_t a, float v) { rex::memory::store_and_swap<uint32_t>(base + a, std::bit_cast<uint32_t>(v)); }

uint32_t EntityOf(uint8_t* base, uint32_t handle) {
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
// Only real death (HP 0) ends the buff. (Nathan's Alive also tests stats +308,
// which is not death; using it here cut the buff short.)
bool Alive(uint8_t* base, uint32_t owner) {
  const auto stats = Stats(base, owner);
  return stats && Float(base, stats + 4) > 0;
}
// Native facing: player +0x250 == 1 is left (read by player vtable +0x288). The
// body sprite's mirror flag lags a frame and is not used.
bool FacingLeft(uint8_t* base, uint32_t owner) {
  const auto player = PlayerOf(base, owner);
  return player && Read(base, player + 0x250) == 1;
}

struct Buff {
  uint32_t owner = 0, handle = 0;
  float remaining = 0;   // seconds of STR left (caster's machine only)
  float visual = 0;      // seconds of head left (any machine that saw the cast)
  float shown = 0;       // seconds the head has been up
  float ring = -1;       // frames since the cast; < 0 = no ring burst
  float mastery = 0;     // seconds toward the next mastery point
  uint32_t level = 0;    // glyph level - 1 (0..8)
  float game = 0;        // game seconds since the cast (for the end log)
  std::chrono::steady_clock::time_point wall{};  // wall clock at the cast
  bool drawn = false;    // the head has drawn at least once (its clock starts then)
};
std::array<Buff, 8> buffs{};
std::recursive_mutex lock;      // STR queries may arrive while a cast holds it
uint32_t scratch = 0, path = 0;
int name_choice = -1;
uint32_t requested_for = 0;           // resource manager the last request went to
uint32_t found_for = 0;               // resource manager the sprite was found in
unsigned attempts = 0;                // requests sent for the current manager
float since_request = 0;              // game seconds since the last request
bool missing_art = false;             // the package has no sprite (built without the ROM)

Buff* Find(uint32_t owner) {
  for (auto& b : buffs) if (b.owner == owner) return &b;
  return nullptr;
}
uint32_t Hash(const char* s) {
  uint32_t h = 0x811C9DC5u;
  for (; *s; ++s) { h *= 0x01000193u; h ^= uint8_t(*s); }
  return h;
}
uint32_t Scratch() {
  if (!scratch) {
    const auto raw = REX_KERNEL_MEMORY()->SystemHeapAlloc(2 * kSpriteBytes + 256 + 15);
    if (!raw) return 0;
    scratch = (raw + 15) & ~15u;
    path = scratch + 2 * kSpriteBytes;
  }
  return scratch;
}
uint32_t Resource(PPCContext& ctx, uint8_t* base, uint32_t body) {
  if (!body || !Scratch()) return 0;
  static const char* const names[] = {kFxName, "P_ACX00", "p_acx00.opd", "acx00"};
  const int first = name_choice >= 0 ? name_choice : 0, last = name_choice >= 0 ? name_choice + 1 : 4;
  for (int k = first; k < last; ++k) {
    std::memcpy(base + scratch, base + body, kSpriteBytes);
    base[scratch] = 1;
    rex::memory::store_and_swap<uint32_t>(base + scratch + 8, Hash(names[k]));
    rex::memory::store_and_swap<uint32_t>(base + scratch + 12, 0);
    rex::memory::store_and_swap<uint32_t>(base + scratch + 0xA0, 0);
    PPCContext query = ctx;
    query.r3.u64 = scratch;
    rex::runtime::ResolveIndirectFunction(kSpriteLookup)(query, base);
    if (const auto resource = Read(base, scratch + 12)) {
      if (name_choice < 0) REXLOG_INFO("[arma custos] head sprite found as \"{}\"", names[k]);
      name_choice = k;
      return resource;
    }
  }
  return 0;
}
// Same route as Refectio: find the DLC device holding the sprite, then load it
// with the game's resource path form "DLCnn:data/..." (forward slashes).
// A request sent while the stage is still loading can be dropped (the first
// test of a stage-start preload never found the sprite), so `retry` sends it
// again for the same manager; see KeepLoaded.
void RequestLoad(PPCContext& ctx, uint8_t* base, bool retry = false) {
  const auto registry = Read(base, 0x8291D9C4), manager = Read(base, 0x8291D920);
  if (!registry || !manager || !Scratch() || (requested_for == manager && !retry)) return;
  if (requested_for != manager) { attempts = 0; missing_art = false; }
  requested_for = manager; since_request = 0; ++attempts;
  std::string found;
  for (unsigned n = 0; n < 64 && found.empty(); ++n) {
    char device[8];
    std::snprintf(device, sizeof device, "DLC%02u:", n);
    std::string file = std::string(device) + "\\" + kFxPath;
    std::replace(file.begin(), file.end(), '/', '\\');
    if (REX_KERNEL_FS()->ResolvePath(file)) found = std::string(device) + kFxPath;
  }
  if (found.empty()) {  // package built without the player's OoE ROM: no visuals
    missing_art = true;
    REXLOG_INFO("[arma custos] no head art ({} not in the package; built without the OoE ROM)", kFxPath);
    return;
  }
  std::memcpy(base + path, found.c_str(), found.size() + 1);
  PPCContext load = ctx;
  load.r3.u64 = path;
  load.r4.u64 = 0;
  rex::runtime::ResolveIndirectFunction(kLoadResource)(load, base);
  REXLOG_INFO("[arma custos] requested head sprite {} (attempt {})", found, attempts);
}
// Once a second after a request, until the sprite is found: look it up, and
// send the request again if it is still missing (at most 4 requests a stage).
void KeepLoaded(PPCContext& ctx, uint8_t* base, uint32_t owner, float dt) {
  const auto manager = Read(base, 0x8291D920);
  if (!manager || found_for == manager) return;
  if (requested_for != manager) { RequestLoad(ctx, base); return; }
  if (missing_art || (since_request += dt) < 1.0f) return;
  if (Resource(ctx, base, Read(base, owner + 0x2C))) { found_for = manager; return; }
  if (attempts < 4) RequestLoad(ctx, base, true);
  else since_request = -1e9f;   // give up for this stage
}
void DrawSprite(const PPCContext& original, uint8_t* base, uint32_t body, uint32_t resource, uint32_t frame,
                float x, float y, float sx, float sy, float opacity, bool additive, bool flip) {
  const auto sprite = scratch + kSpriteBytes;
  std::memcpy(base + sprite, base + body, kSpriteBytes);
  rex::memory::store_and_swap<uint32_t>(base + sprite + 12, resource);
  base[sprite + 0x54] = base[sprite + 0x55] = 0;
  rex::memory::store_and_swap<uint32_t>(base + sprite + 0xA0, 0);
  base[sprite + 0xA4] = 1;
  base[sprite + 0x1C] = flip ? 1 : 0;
  rex::memory::store_and_swap<uint16_t>(base + sprite + 116, 0);
  rex::memory::store_and_swap<uint16_t>(base + sprite + 118, 0);
  Float(base, sprite + 0x28, sx);
  Float(base, sprite + 0x2C, sy);
  Float(base, sprite + 80, 1);
  base[sprite + 140] = additive ? 1 : 0;
  Float(base, sprite + 48, 0); Float(base, sprite + 52, 0); Float(base, sprite + 56, 0);
  if (!std::isfinite(x) || !std::isfinite(y)) return;
  PPCContext draw = original;
  draw.r3.u64 = sprite; draw.r4.u64 = frame;
  draw.r5.u64 = uint32_t(int32_t(std::lround(x))); draw.r6.u64 = uint32_t(int32_t(std::lround(y)));
  draw.r7.u64 = flip ? 2 : 0;                               // 823D2648: 2 = mirrored
  draw.r8.u64 = 0xFFFFFF00u | uint32_t(std::lround(255 * std::clamp(opacity, 0.0f, 1.0f)));  // vertex alpha
  draw.r9.u64 = 0;
  __imp__sub_823D2648(draw, base);
}
// Arma Custos in any of the player's equipment slots (owner +0x9C8, 15 slots
// as in the save model; weapons are 0 / 1, glyphs sit in later slots).
constexpr uint32_t kItem = 0x80D + kGlyphIndex;
bool Equipped(uint8_t* base, uint32_t owner) {
  const auto equipment = Read(base, owner + 0x9C8);
  if (!equipment) return false;
  for (unsigned slot = 0; slot < 15; ++slot) if (Read(base, equipment + 4 * slot) == kItem) return true;
  return false;
}
bool CustosPair(uint8_t* base, uint32_t owner) {
  const auto equipment = Read(base, owner + 0x9C8);         // weapon slots 0 / 1 (X / Y)
  if (!equipment) return false;
  const uint32_t a = Read(base, equipment), b = Read(base, equipment + 4);
  return (a == kDextroCustos && b == kSinestroCustos) || (a == kSinestroCustos && b == kDextroCustos);
}
void End(const Buff& b, const char* why) {
  const double wall = std::chrono::duration<double>(std::chrono::steady_clock::now() - b.wall).count();
  REXLOG_INFO("[arma custos] buff ended ({}): {:.1f} s of game time, {:.1f} s on the clock", why, b.game, wall);
}
}  // namespace

bool Handles(uint32_t kind, uint32_t index) { return kind == kGlyphKind && index == kGlyphIndex; }

void Preload(PPCContext& ctx, uint8_t* base) {
  std::lock_guard guard(lock);
  RequestLoad(ctx, base);
}

void Cast(PPCContext& ctx, uint8_t* base, uint32_t handle, uint32_t level, uint32_t launcher) {
  const auto owner = EntityOf(base, handle);
  if (!owner || !PlayerOf(base, owner)) return;
  if (launcher) {
    if (base[launcher + 0x9C]) return;  // this launcher already fired
    base[launcher + 0x9C] = 1;
  }
  if (!Alive(base, owner)) return;
  std::lock_guard guard(lock);
  Buff* b = Find(owner);
  if (!b) for (auto& e : buffs) if (!e.owner) { b = &e; break; }
  if (!b) return;
  const bool up = b->owner == owner && b->visual > 0;
  b->owner = owner; b->handle = handle;
  b->visual = kSeconds; b->ring = 0; b->game = 0; b->wall = std::chrono::steady_clock::now();
  if (!up) { b->shown = 0; b->drawn = false; }
  if (Local(base, owner)) {
    b->remaining = kSeconds; b->level = std::min<uint32_t>(level & 0xFF, 8); b->mastery = 0;
    REXLOG_INFO("[arma custos] cast: level {}, STR +{:.1f} now ({}), {} s", b->level + 1,
                StrengthBonus(base, owner), CustosPair(base, owner) ? "Custos pair" : "no Custos pair", kSeconds);
  }
  if (!Resource(ctx, base, Read(base, owner + 0x2C))) RequestLoad(ctx, base, true);
}

double StrengthBonus(uint8_t* base, uint32_t owner) {
  std::lock_guard guard(lock);
  Buff b{};
  for (const auto& e : buffs) if (e.owner == owner) { b = e; break; }
  if (!b.owner || !(b.remaining > 0) || !Local(base, owner) || !Alive(base, owner)) return 0;
  const auto stats = Stats(base, owner);
  const float maximum = Float(base, stats + 16) + Float(base, stats + 28), hp = Float(base, stats + 4);
  const float missing = maximum > 0 ? std::clamp(1 - hp / maximum, 0.0f, 1.0f) : 0;
  double bonus = kStrLevel1 + (kStrMax - kStrLevel1) * b.level / 8.0;
  bonus *= 1 + kMissingHpBonus * missing;
  if (CustosPair(base, owner)) bonus *= kCustosPair;
  return bonus;
}

// Status / equipment screens build their own stat summary (8245D9A0:
// character, out) instead of asking the battle getters, which is why the STR
// buff did not show there. As the Shield Rod does for Alucard's buffs, add it
// to that temporary output: STR at +0x1C, and to each hand's ATK (+0x10 / +0x14)
// what the extra STR adds to an attack, (W/64 + 0.25) x bonus (824519C8), with
// the weapon value W recovered from the shown ATK and STR.
void Summary(PPCContext& ctx, uint8_t* base, uint32_t character, uint32_t out) {
  if (!out || (character != 0 && character != 6)) return;   // 0 = the live player, 6 = Shanoa
  PPCContext query = ctx;
  query.r3.u64 = 0;
  rex::runtime::ResolveIndirectFunction(0x8245CCE8)(query, base);   // the local player's handle
  const auto owner = EntityOf(base, query.r3.u32);
  if (!owner || !PlayerOf(base, owner)) return;
  const double bonus = StrengthBonus(base, owner);
  if (!(bonus > 0)) return;
  const float str = Float(base, out + 0x1C);
  if (!std::isfinite(str)) return;
  Float(base, out + 0x1C, float(str + bonus));
  for (unsigned hand = 0; hand < 2; ++hand) {
    const auto at = out + 0x10 + 4 * hand;
    const float atk = Float(base, at);
    if (!(atk > 0) || !std::isfinite(atk)) continue;
    const double weapon = std::max(0.0, (atk - 0.25 * str) / (1 + str / 64.0));
    Float(base, at, float(atk + (weapon / 64 + 0.25) * bonus));
  }
}

void Frame(PPCContext& ctx, uint8_t* base, uint32_t owner, double seconds) {
  if (!(seconds > 0) || seconds > 0.25) return;
  std::lock_guard guard(lock);
  // Load the head sprite with the stage (once per resource manager), so the
  // first cast does not wait for it.
  // Only while she has Arma Custos equipped (also when equipped mid-stage).
  if (Local(base, owner) && seconds > 0 && seconds <= 0.25 && Equipped(base, owner)) KeepLoaded(ctx, base, owner, float(seconds));
  Buff* b = Find(owner);
  if (!b) return;
  const bool gone = EntityOf(base, b->handle) != owner || !PlayerOf(base, owner);
  if (gone || !Alive(base, owner)) {
    if (b->remaining > 0) End(*b, gone ? "player left" : "death");
    *b = Buff{}; return;
  }
  const float dt = float(seconds);
  b->game += dt;
  if (b->ring >= 0 && (b->ring += dt * 60) >= kRingBDelay + kRingFrames * kRingStep) b->ring = -1;
  if (b->visual > 0) { b->visual -= dt; if (b->drawn) b->shown += dt; }
  if (b->remaining > 0 && Local(base, owner)) {
    b->remaining -= dt;
    if (b->remaining <= 0) End(*b, "expired");
    for (b->mastery += dt; b->mastery >= kMasteryEvery; b->mastery -= kMasteryEvery) {
      PPCContext award = ctx;
      award.r3.u64 = b->handle; award.r4.u64 = kGlyphKind; award.r5.u64 = kGlyphIndex;
      rex::runtime::ResolveIndirectFunction(kAddMastery)(award, base);
    }
  }
  if (b->remaining <= 0 && b->visual <= 0 && b->ring < 0) *b = Buff{};
}

void Draw(const PPCContext& original, uint8_t* base, uint32_t owner) {
  std::lock_guard guard(lock);
  Buff* b = Find(owner);
  if (!b || (b->visual <= 0 && b->ring < 0)) return;
  const auto body = Read(base, owner + 0x2C);
  PPCContext query = original;
  const auto resource = Resource(query, base, body);
  if (!resource) return;
  const float sx = std::abs(Float(base, body + 0x28)), sy = std::abs(Float(base, body + 0x2C));
  if (!(sx > 0) || !(sy > 0) || !std::isfinite(sx) || !std::isfinite(sy)) return;
  const float cx = Float(base, owner + 0x8EC), cy = Float(base, owner + 0x8F0);
  const bool left = FacingLeft(base, owner);              // she faces left: mirror the head
  if (b->visual > 0) {
    // OoE's head faces right; it sits behind her, facing her way. Steady
    // opacity: the only motion is OoE's own pose loop. Its clock starts at
    // the first frame that actually draws (the first load is asynchronous).
    b->drawn = true;
    const auto pose = kHeadLoop[unsigned(b->shown * 60 / kHeadStep) % sizeof kHeadLoop];
    const float opacity = kHeadOpacity * std::min(1.0f, b->shown / 0.3f) * std::min(1.0f, b->visual / 1.0f);
    const float x = cx + (left ? -kHeadOffsetX : kHeadOffsetX) * sx, y = cy + kHeadOffsetY * sy;
    DrawSprite(original, base, body, resource, kHead0 + pose, x, y, sx, sy, opacity, false, left);
  }
  if (b->ring >= 0) {
    const auto a = unsigned(b->ring / kRingStep);
    if (a < kRingFrames) DrawSprite(original, base, body, resource, kRingA0 + a, cx, cy, sx, sy, 1, true, false);
    if (b->ring >= kRingBDelay) {
      const auto c = unsigned((b->ring - kRingBDelay) / kRingStep);
      if (c < kRingFrames) DrawSprite(original, base, body, resource, kRingB0 + c, cx, cy, sx, sy, 1, true, false);
    }
  }
}
}  // namespace harmony::arma_custos

// ---- Handlers in the shared chains (core/runtime/hod_hooks.h) -------------
namespace {
namespace ac = harmony::arma_custos;

// 8248A690 skill preload / 82487EF8 skill factory for this glyph.
void SkillPreload(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  if (ac::Handles(ctx.r3.u32, ctx.r4.u32)) { ac::Preload(ctx, base); ctx.r3.u64 = 1; return; }
  next(ctx, base);
}
void SkillFactory(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  if (ac::Handles(ctx.r3.u32, ctx.r4.u32)) {
    const uint32_t launcher = ctx.lr == hod::kGlyphLauncherReturn ? ctx.r6.u32 - 0x48 : 0;
    ac::Cast(ctx, base, ctx.r5.u32, ctx.r9.u32, launcher);
    ctx.r3.u64 = 0;
    return;
  }
  next(ctx, base);
}
// 8244FFF8 player update: the buff timer and the head's sprite load.
void PlayerUpdate(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  const double seconds = ctx.f1.f64;
  next(ctx, base);
  ac::Frame(ctx, base, owner, seconds);
}
// 824476B8 owner draw: Cerberus's third head above Shanoa.
void OwnerDraw(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  next(ctx, base);
  if (owner) ac::Draw(ctx, base, owner);
}
// 8245D9A0 status summary: the buff on the status screen's STR and ATK.
void StatusSummary(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto character = ctx.r3.u32, out = ctx.r4.u32;
  next(ctx, base);
  ac::Summary(ctx, base, character, out);
}
// 82452658 STR / attack value: the buff's STR.
void AttackValue(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  next(ctx, base);
  ctx.f1.f64 += ac::StrengthBonus(base, owner);
}
}  // namespace

HOD_HOOK(kSkillPreload, kArmaCustos, 20, SkillPreload);
HOD_HOOK(kSkillFactory, kArmaCustos, 20, SkillFactory);
HOD_HOOK(kPlayerUpdate, kArmaCustos, 20, PlayerUpdate);
HOD_HOOK(kOwnerDraw, kArmaCustos, 30, OwnerDraw);
HOD_HOOK(kStatusSummary, kArmaCustos, 20, StatusSummary);
HOD_HOOK(kAttackValue, kArmaCustos, 10, AttackValue);
