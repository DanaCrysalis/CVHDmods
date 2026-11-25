// Shanoa's OoE glyphs (Arcus, Ascia, Scutum, Umbra, Cubus; user, 2026-11-24): the shared
// shot engine for their five modules. Test builds only (HARMONYRECOMP_POISONWORM);
// modding/tools/shanoa_glyphs.py makes every module from the 8-bit DLC's R. Zombie soul
// (dllshotSoulFCzombi), whose class code they keep, with the info block patched to
// category 10 (weapon shots, like dllshotGlyphDextroCustos) or 3 (glyph shots, like
// dllshotGlyphLuminatio) and the weapon / glyph index as ID.
//
// Damage is native: the shot's frame boxes (OoE's own hitboxes, converted 1:1 by
// tools/ooe_glyph_art.py) are its attack boxes, and the power comes from 82533878 with the
// module's category. Category 10 goes to the physical attack 824519C8(owner, weapon index),
// i.e. the WEPN row's ATK at mastery 1..max scaled by Shanoa's glyph-mastery collection
// (8245D178, def mode 2) plus STR, exactly as Confodere and the Custos pair; category 3 is the
// glyph's power + INT.
//
// Same object model as the Cerberus orb (cerberus_orb_spell.h, whose low-level helpers this
// reuses): the exe's wrapper (+0x04 handle, +0xA4 owner handle, +0xB8/+0xBC what the last
// contact struck, +0x180 the module object) and the module object (r3; +0x5C/+0x60 position,
// +0x64/+0x68 velocity px/s, +0x204 level, +0x258 sprite request, +0x324 facing for the
// R. Zombie soul class, +0x320/+0x32C lifetime timer/limit). While a shot is alive this code
// drives it and the template's update never runs; at the end the lifetime is pushed past its
// limit and the template's update ends and destroys it.
//
// Child shots (Arcus's arrow) come from the skill factory 82487EF8 as Soma's casts do
// (kind, ID, owner handle, &x/y, facing, 0, level, 0), owned by the caster.
#pragma once
#include "cerberus_orb_spell.h"
#include "shanoa_glyphs_balance.h"
#include "hurt_record_guest.h"
#include "shanoa_glyph_guest.h"

namespace shanoa_glyph {
namespace {
using cerberus_orb::Float;
using cerberus_orb::Read;
using cerberus_orb::Write;
using cerberus_orb::ObjectOf;
using cerberus_orb::Owner;
using cerberus_orb::Solid;
using cerberus_orb::Wrapper;
using cerberus_orb::WrapperHandle;
using cerberus_orb::MoveTo;
using cerberus_orb::kFloorPush;
using cerberus_orb::kCeilingPush;
using cerberus_orb::kSkillFactory;
using cerberus_orb::kHandleTable;
constexpr uint32_t kWallA = 0x823C2468, kWallB = 0x823C2720;    // shield_rod.cpp Wall()
constexpr int kForgetTicks = 600;

struct Glyph {
  uint32_t kind, id;      // module category and ID (= weapon / glyph index)
  const char* tag;        // log tag
  uint32_t blank;         // the sprite's blank animation
};

struct Shot {
  uint32_t handle = 0;
  int role = 0;                        // 0 = the cast; others are the glyph's child shots
  bool ended = false;
  int t = 0, end_t = 0, phase = 0, level = 0;
  int aux = 0;                         // a glyph's own counter (Cubus: ticks already stayed)
  float x = 0, y = 0, vx = 0, vy = 0, dir = 1, rot = 0, heading = 0, start_y = 0;
  uint32_t owner = 0, target = 0;
  uint32_t struck[2] = {0, 0};         // the wrapper's +0xB8/+0xBC when last checked
};

// What the glyph's step wants drawn this frame.
struct Look {
  uint32_t anim = 0;
  bool mirrored = false, visible = true;
  float rotation = 0, scale = 1;
  float stretch = 1;                   // extra x scale (in the art's own axes, before rotation)
  uint16_t palette = 0;               // sprite request +0x5C (the R. Zombie template sets 1)
  // Sprite request +0x14 = draw depth in render list +0x18 (3, the players' list; depth ascends,
  // players 15000 + index, enemies about 25000; alucard_familiar.cpp). The template's depth put
  // the bow and the shield under Shanoa (test 2): 20000 is above every player.
  float depth = 20000.0f;
};

struct Pending { bool active = false; Shot shot; };

std::mutex g_lock;
std::unordered_map<uint32_t, Shot> g_shots;        // module object -> state (handle checked)
Pending g_pending;
std::unordered_map<uint32_t, int> g_unlinked;
std::atomic<int> g_logged{0};

// ---- the owner (Shanoa) -------------------------------------------------------------
uint32_t OwnerObject(uint8_t* base, const Shot& s) { return s.owner ? ObjectOf(base, s.owner) : 0; }
bool IsPlayer(uint8_t* base, uint32_t o) { return o && (Read(base, o + 8) & 2); }
// Body centre (shield_rod.cpp PlayerX/Y) and feet (nathan_dss_combinations.h HolyBarrier).
bool OwnerCentre(uint8_t* base, const Shot& s, float& x, float& y) {
  const uint32_t o = OwnerObject(base, s);
  if (!IsPlayer(base, o)) return false;
  x = Float(base, o + 0x8EC); y = Float(base, o + 0x8F0);
  return std::isfinite(x) && std::isfinite(y);
}
bool OwnerFeet(uint8_t* base, const Shot& s, float& x, float& y) {
  const uint32_t o = OwnerObject(base, s);
  if (!IsPlayer(base, o)) return false;
  x = Float(base, o + 0x8D4); y = Float(base, o + 0x8D8);
  return std::isfinite(x) && std::isfinite(y);
}
// Native facing: player component (+0x924) +0x250 == 1 is left (arma_custos.cpp).
float OwnerDir(uint8_t* base, const Shot& s, float fallback) {
  const uint32_t o = OwnerObject(base, s);
  if (!IsPlayer(base, o)) return fallback;
  const uint32_t player = Read(base, o + 0x924);
  return player ? (Read(base, player + 0x250) == 1 ? -1.0f : 1.0f) : fallback;
}

// The local player's held buttons (player component +0x2C0 -> input block, first word;
// alucard_familiar.cpp). Attack buttons 0x20 | 0x40. Returns false for a player without a
// local input block (another player's copy online).
constexpr uint32_t kPadAttack = 0x20 | 0x40;
bool OwnerHeld(uint8_t* base, const Shot& s, uint32_t mask, bool& held) {
  const uint32_t o = OwnerObject(base, s);
  if (!IsPlayer(base, o)) return false;
  const uint32_t player = Read(base, o + 0x924);
  const uint32_t input = player ? Read(base, player + 0x2C0) : 0;
  if (!input) return false;
  held = (Read(base, input) & mask) != 0;
  return true;
}

// Enemy shots inside a box are destroyed, as Nathan's Holy Barrier does (wrapper +8 flag 0x10
// = an enemy's shot, 0x08 a player's; +23 set = remove; +0x2C/+0x30 position). Returns count.
int BlockEnemyShots(uint8_t* base, float x0, float y0, float x1, float y1) {
  const uint32_t manager = Read(base, kHandleTable);
  if (!manager) return 0;
  const uint32_t first = Read(base, manager + 0xAC), end = Read(base, manager + 0xB0);
  if (!first || end <= first || end - first > 65536u * 16) return 0;
  int n = 0;
  for (uint32_t at = first; at + 16 <= end; at += 16) {
    const uint32_t e = Read(base, at + 4);
    if (!e) continue;
    const uint32_t flags = Read(base, e + 8);
    if (!(flags & 0x10) || (flags & (2 | 4 | 8)) || base[e + 23]) continue;
    const float x = Float(base, e + 0x2C), y = Float(base, e + 0x30);
    if (std::isfinite(x) && std::isfinite(y) && x >= x0 && x <= x1 && y >= y0 && y <= y1) { base[e + 23] = 1; ++n; }
  }
  return n;
}

// A native guard rectangle for this frame, as a held shield registers its own (8244B558: the
// collision registrar 823C4C40 with flags 0x80000010, owner = source = the player's handle,
// the guard callback object): enemy shots that touch it are guarded and break with their own
// animation, as on Alucard's shields (test 5: deleting them skipped that). Rectangle =
// {0x821E10C0, 1, left, top, right, bottom} in world px, on the stack (the registrar copies it).
bool RegisterGuard(const PPCContext& ctx, uint8_t* base, const Shot& s, float x0, float y0, float x1, float y1) {
  const uint32_t o = OwnerObject(base, s);
  if (!IsPlayer(base, o) || Read(base, o + 4) != s.owner) return false;
  PPCContext call = ctx;
  call.r1.u32 = (ctx.r1.u32 - 0x200) & ~15u;
  Write(base, call.r1.u32, ctx.r1.u32);
  const uint32_t rect = call.r1.u32 + 0x100;
  Write(base, rect, 0x821E10C0);
  Write(base, rect + 4, 1);
  Float(base, rect + 8, x0); Float(base, rect + 12, y0);
  Float(base, rect + 16, x1); Float(base, rect + 20, y1);
  call.r3.u64 = o; call.r4.u64 = rect;
  rex::runtime::ResolveIndirectFunction(0x8244B558)(call, base);
  return call.r3.u32 != 0xFFFFFFFFu;
}

// A sound by cue index (82250AD8(cue, x, y): the index into the SE name table at 0x821091C0,
// as HoD's Axe subweapon plays SE_PL_ATK_AXE 31 and its whirr 83).
void PlayCue(const PPCContext& ctx, uint8_t* base, uint32_t cue, float x, float y) {
  if (!std::isfinite(x) || !std::isfinite(y)) return;
  PPCContext call = ctx;
  call.r1.u32 = (ctx.r1.u32 - 0x100) & ~15u;
  Write(base, call.r1.u32, ctx.r1.u32);
  call.r3.u64 = cue; call.r4.s64 = int32_t(x); call.r5.s64 = int32_t(y);
  rex::runtime::ResolveIndirectFunction(0x82250AD8)(call, base);
}

// ---- the stage ------------------------------------------------------------------------
bool Terrain(PPCContext& ctx, uint8_t* base, float x, float y) {
  return Solid(ctx, base, kFloorPush, x, y) || Solid(ctx, base, kCeilingPush, x, y) ||
         Solid(ctx, base, kWallA, x, y) || Solid(ctx, base, kWallB, x, y);
}
bool Floor(PPCContext& ctx, uint8_t* base, float x, float y) { return Solid(ctx, base, kFloorPush, x, y); }

// ---- enemies (handle table entries {handle, object}: object +8 flags 4 = enemy, 2 = player,
// 0x10 = shot; +23 set while dying; +0x2C/+0x30 position; as alucard_familiar.cpp IsEnemy
// and nathan_dss_combinations.h HolyBarrier) --------------------------------------------
struct Enemy { uint32_t handle = 0; float x = 0, y = 0; };
bool EnemyAt(uint8_t* base, uint32_t handle, Enemy& e) {
  const uint32_t obj = ObjectOf(base, handle);
  if (!obj) return false;
  const uint32_t flags = Read(base, obj + 8);
  if (!(flags & 4) || (flags & 0x1A) || base[obj + 23]) return false;
  e.handle = handle; e.x = Float(base, obj + 0x2C); e.y = Float(base, obj + 0x30);
  return std::isfinite(e.x) && std::isfinite(e.y);
}
// Diagnostics (first casts): every enemy-flagged entity with its candidate position fields.
void LogEnemies(uint8_t* base, const char* tag, float x, float y) {
  const uint32_t manager = Read(base, kHandleTable);
  if (!manager) return;
  const uint32_t first = Read(base, manager + 0xAC), end = Read(base, manager + 0xB0);
  if (!first || end <= first || end - first > 65536u * 16) return;
  int n = 0;
  for (uint32_t at = first; at + 16 <= end && n < 12; at += 16) {
    const uint32_t h = Read(base, at), e = Read(base, at + 4);
    if (!h || h == 0xFFFFFFFF || !e || !(Read(base, e + 8) & 4)) continue;
    ++n;
    REXLOG_INFO("[{}]   entity {:08X} obj {:08X} flags {:08X} b23 {} +2C ({:.0f}, {:.0f}) +5C ({:.0f}, {:.0f}) +A4 ({:.0f}, {:.0f}); from ({:.0f}, {:.0f})",
                tag, h, e, Read(base, e + 8), base[e + 23], Float(base, e + 0x2C), Float(base, e + 0x30), Float(base, e + 0x5C),
                Float(base, e + 0x60), Float(base, e + 0xA4), Float(base, e + 0xA8), x, y);
  }
  REXLOG_INFO("[{}]   {} enemy-flagged entities listed", tag, n);
}
Enemy NearestEnemy(uint8_t* base, float x, float y, float range) {
  Enemy best;
  float best_d = range * range;
  const uint32_t manager = Read(base, kHandleTable);
  if (!manager) return best;
  const uint32_t first = Read(base, manager + 0xAC), end = Read(base, manager + 0xB0);
  if (!first || end <= first || end - first > 65536u * 16) return best;
  for (uint32_t at = first; at + 16 <= end; at += 16) {
    const uint32_t h = Read(base, at);
    Enemy e;
    if (!h || h == 0xFFFFFFFF || !EnemyAt(base, h, e)) continue;
    const float dx = e.x - x, dy = e.y - y, d = dx * dx + dy * dy;
    if (d < best_d) { best_d = d; best = e; }
  }
  return best;
}

// ---- enemy hurt boxes (the exe's guest table, hurt_record_guest.h; test 2: the enemy objects
// in the handle table hold no usable position, so targets come from the boxes the game itself
// registers for hits) -----------------------------------------------------------------------
uint32_t HurtTable(uint8_t* base) {
  static std::atomic<uint32_t> table{0};
  uint32_t t = table;
  if (!harmony::hurt_record::Valid(base, t)) {
    t = harmony::shanoa_guest::Published(harmony::shanoa_guest::kHurtRecordVar);
    if (!harmony::hurt_record::Valid(base, t)) return 0;
    table = t;
  }
  return t;
}
// The nearest live hurt box centre within range; with `keep`, that enemy's nearest box if it
// still has one in range (so a seeker does not flip between two enemies every frame).
Enemy NearestHurt(uint8_t* base, float x, float y, float range, uint32_t keep = 0) {
  Enemy best, kept;
  float best_d = range * range, kept_d = range * range;
  harmony::hurt_record::ForEachFresh(base, HurtTable(base), [&](const harmony::hurt_record::Box& b) {
    if (!std::isfinite(b.x) || !std::isfinite(b.y)) return;
    const float dx = b.x - x, dy = b.y - y, d = dx * dx + dy * dy;
    if (d < best_d) { best_d = d; best = Enemy{b.handle, b.x, b.y}; }
    if (keep && b.handle == keep && d < kept_d) { kept_d = d; kept = Enemy{b.handle, b.x, b.y}; }
  });
  return kept.handle ? kept : best;
}

// ---- contact: the wrapper's last-struck record changed since the last check -------------
bool Struck(uint8_t* base, uint32_t o, Shot& s) {
  const uint32_t w = Wrapper(base, o);
  if (!w) return false;
  const uint32_t a = Read(base, w + 0xB8), b = Read(base, w + 0xBC);
  const bool hit = a != s.struck[0] || b != s.struck[1];
  s.struck[0] = a; s.struck[1] = b;
  return hit;
}

// ---- drawing ----------------------------------------------------------------------------
void Draw(uint8_t* base, uint32_t o, const Look& l) {
  if (const uint32_t s = Read(base, o + 0x258)) {
    base[s + 0x29] = l.visible ? 1 : 0;
    Float(base, s + 0x50, l.rotation);           // radians (cerberus_module.cpp beam: atan2)
    Float(base, s + 0x38, l.scale * l.stretch);
    Float(base, s + 0x3C, l.scale);
    if (Read(base, s + 0x00) != l.anim) {
      Write(base, s + 0x00, l.anim);
      base[s + 0x1C] = 1;
      Float(base, s + 0x10, 1.0f);
    }
    Write(base, s + 0x30, l.mirrored ? 2 : 0);
    rex::memory::store_and_swap<uint16_t>(base + s + 0x5C, l.palette);   // cerberus_module.cpp: +0x5C palette
    Float(base, s + 0x14, l.depth);
  }
  const uint32_t b = Read(base, o + 0x268), e = Read(base, o + 0x26C);
  if (b && e > b && e - b <= 8 * 0x84)
    for (uint32_t layer = b; layer < e; layer += 0x84) base[layer + 0x29] = 0;
}

// ---- child shots ------------------------------------------------------------------------
bool Spawn(PPCContext& ctx, uint8_t* base, const Glyph& g, const Shot& from, Shot child) {
  if (!from.owner) return false;
  child.owner = from.owner; child.level = from.level;
  PPCContext call = ctx;
  call.r1.u32 = (ctx.r1.u32 - 0x400) & ~15u;
  Write(base, call.r1.u32, ctx.r1.u32);
  const uint32_t pos = call.r1.u32 + 0x200;
  Float(base, pos, child.x);
  Float(base, pos + 4, child.y);
  call.r3.u64 = g.kind; call.r4.u64 = g.id; call.r5.u64 = from.owner;
  call.r6.u64 = pos; call.r7.u64 = child.dir < 0 ? 0 : 1; call.r8.u64 = 0;
  call.r9.u64 = uint32_t(from.level); call.r10.u64 = 0;
  {
    std::lock_guard lock(g_lock);
    g_pending.active = true; g_pending.shot = child;
  }
  rex::runtime::ResolveIndirectFunction(kSkillFactory)(call, base);
  const uint32_t handle = call.r3.u32;
  const uint32_t wrapper = ObjectOf(base, handle);
  const uint32_t obj = wrapper ? Read(base, wrapper + 0x180) : 0;
  std::lock_guard lock(g_lock);
  g_pending.active = false;
  if (obj) {
    auto it = g_shots.find(obj);
    if (it == g_shots.end() || it->second.handle != handle) { child.handle = handle; g_shots[obj] = child; }
  }
  if (g_logged.fetch_add(1) < 60)
    REXLOG_INFO("[{}] child role {} at ({:.0f}, {:.0f}) facing {:.0f}: handle {:08X} object {:08X}", g.tag, child.role,
                child.x, child.y, child.dir, handle, obj);
  return obj != 0;
}

// ---- the update (vtable slot 9) ----------------------------------------------------------
// step(ctx, base, glyph, object, shot, look, dt) advances one tick; it sets shot.ended to end.
template <typename Native, typename Step>
void Update(PPCContext& ctx, uint8_t* base, const Glyph& g, Native native, Step step) {
  const uint32_t o = ctx.r3.u32;
  const uint32_t handle = WrapperHandle(base, o);
  if (handle == 0 || handle == 0xFFFFFFFF) {        // the setup's early call: wait for the link
    Float(base, o + 0x64, 0.0f);
    Float(base, o + 0x68, 0.0f);
    int waited;
    {
      std::lock_guard lock(g_lock);
      waited = ++g_unlinked[o];
    }
    if (waited > 60) {
      if (waited == 61) REXLOG_WARN("[{}] shot {:08X} never got its wrapper; ending it", g.tag, o);
      Float(base, o + 0x320, Float(base, o + 0x32C) + 1.0f);
      native(ctx, base);
      Look none; none.anim = g.blank; none.visible = false;
      Draw(base, o, none);
    }
    return;
  }
  Shot s;
  bool fresh = false;
  {
    std::lock_guard lock(g_lock);
    g_unlinked.erase(o);
    auto it = g_shots.find(o);
    if (it != g_shots.end() && it->second.handle == handle) s = it->second;
    else if (g_pending.active) { s = g_pending.shot; s.handle = handle; fresh = true; }
    else {                                           // a cast
      s.handle = handle;
      s.owner = Owner(base, o);
      const float dir = Float(base, o + 0x324);
      s.dir = OwnerDir(base, s, (dir == 1.0f || dir == -1.0f) ? dir : 1.0f);
      s.level = std::min<int>(base[o + 0x204], 9);
      s.x = Float(base, o + 0x5C);
      s.y = Float(base, o + 0x60);
      fresh = true;
      float cx = 0, cy = 0, fx = 0, fy = 0;
      OwnerCentre(base, s, cx, cy);
      OwnerFeet(base, s, fx, fy);
      REXLOG_INFO("[{}] cast {:08X} (handle {:08X}, owner {:08X}, level {}) shot at ({:.0f}, {:.0f}), "
                  "Shanoa centre ({:.0f}, {:.0f}) feet ({:.0f}, {:.0f}) facing {:.0f}",
                  g.tag, o, handle, s.owner, s.level, s.x, s.y, cx, cy, fx, fy, s.dir);
    }
    if (fresh) {
      if (const uint32_t w = Wrapper(base, o)) { s.struck[0] = Read(base, w + 0xB8); s.struck[1] = Read(base, w + 0xBC); }
    }
  }
  if (fresh) {
    // Test 3: writing the wanted position here left a child shot where the game made it (the arrow
    // came from her feet): MoveTo below steers from the real position instead.
    static std::atomic<bool> told{false};
    if (const uint32_t r = Read(base, o + 0x258); r && !told.exchange(true))
      REXLOG_INFO("[{}] template sprite request: depth (+0x14) {:.1f}, list (+0x18) {}, palette (+0x5C) {}", g.tag,
                  Float(base, r + 0x14), Read(base, r + 0x18), rex::memory::load_and_swap<uint16_t>(base + r + 0x5C));
  }
  if (s.ended) {
    Float(base, o + 0x64, 0.0f);
    Float(base, o + 0x68, 0.0f);
    Float(base, o + 0x320, Float(base, o + 0x32C) + 1.0f);
    native(ctx, base);
    Look none; none.anim = g.blank; none.visible = false;
    Draw(base, o, none);
    std::lock_guard lock(g_lock);
    if (++s.end_t > kForgetTicks) g_shots.erase(o); else g_shots[o] = s;
    return;
  }
  const float frame = float(ctx.f1.f64);
  const float dt = frame > 0 && frame < 1 ? frame : 1.0f / 60;
  Look look;
  look.anim = g.blank;
  step(ctx, base, g, o, s, look, dt);
  ++s.t;
  if (s.ended) {
    look.anim = g.blank; look.visible = false;
    Float(base, o + 0x64, 0.0f);
    Float(base, o + 0x68, 0.0f);
  } else {
    // Steer from where the game has the shot. A shot the game held back (pressed into terrain)
    // would otherwise be flung across the gap in one frame (test 5: Ascia "rocketed away"); cap
    // the step (16 px a frame), so it closes the gap over a few frames instead.
    const float ax = Float(base, o + 0x5C), ay = Float(base, o + 0x60);
    const float gx = s.x - ax, gy = s.y - ay, gap = std::sqrt(gx * gx + gy * gy);
    constexpr float kMaxStep = 16.0f;
    // Not on a shot's first frames: a new child (Arcus's arrow) must jump from where the game made
    // it to where it belongs (test 6: capped, the arrow rose from the bottom of the bow).
    if (s.t > 2 && std::isfinite(gap) && gap > kMaxStep) MoveTo(base, o, ax + gx * kMaxStep / gap, ay + gy * kMaxStep / gap, dt);
    else MoveTo(base, o, s.x, s.y, dt);
  }
  Draw(base, o, look);
  std::lock_guard lock(g_lock);
  g_shots[o] = s;
}

// Slot 16 (the template's "end now", called by some contacts): ignored while this code
// drives the shot (it decides when a shot ends); otherwise the template's own.
template <typename Native>
void EndRequest(PPCContext& ctx, uint8_t* base, Native native) {
  {
    std::lock_guard lock(g_lock);
    auto it = g_shots.find(ctx.r3.u32);
    if (it != g_shots.end() && !it->second.ended) return;
  }
  native(ctx, base);
}
}  // namespace
}  // namespace shanoa_glyph
