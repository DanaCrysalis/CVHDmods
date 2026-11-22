// Soma's Skeleton Bomber soul (soul 118): the module dllshotSoulCm007 (R. Zombie soul's code,
// modding/tools/skeleton_bomber_soul.py). Design (user, 2026-11-22): throws a bomb.
//
// The cast shot is the bomb: lobbed from Soma's hand (16 px ahead, 40 up) at 3 px/tick
// forward and 2.5 up, with the CotM bomb's gravity (0x16C1 / 65536 px/tick^2), animation 0.
// It explodes on the first enemy or the first floor, wall or ceiling. An enemy touch shows
// in the shot's wrapper (a hit-record object): its contact callback 82484918 stores what it
// struck at +0xB8 / +0xBC, so a change there while flying is a hit (2026-11-22: the
// template's slot 16 is not called on hits; the bombs flew through enemies). Then: the CotM explosion, animation 1,
// 48 ticks, whose frames carry the growing boxes (skeleton_bomber_art.BLAST_BOXES), then
// the template ends the shot (its timer +0x320 pushed past its limit +0x32C). Uses the
// Lightning Orb's helpers (cerberus_orb_spell.h): wrapper lookup, terrain calls, drawing.
#include "../generated/dllshotsoulcm007/harmonyrecomp_init.h"
#include "cerberus_orb_spell.h"

REX_EXTERN(__imp__sub_85A11D38);
REX_EXTERN(__imp__sub_85A12038);

namespace skeleton_bomber_soul {
namespace {
using namespace cerberus_orb;

constexpr uint32_t kAnimBomb = 0, kAnimBlast = 1, kAnimBlank = 2;
constexpr float kForward = 3.0f, kUp = 2.5f, kGravity = float(0x16C1) / 65536.0f;
constexpr int kBlastTicks = 48, kFlightTicks = 360, kForget = 600;
constexpr uint32_t kWallA = 0x823C2468, kWallB = 0x823C2720;   // shield_rod.cpp Wall()

struct Bomb {
  uint32_t handle = 0;
  bool blast = false, ended = false, hit = false;
  int t = 0, end_t = 0;
  float x = 0, y = 0, vx = 0, vy = 0, dir = 1;
  uint32_t struck[2] = {0, 0};                       // the wrapper's +0xB8 / +0xBC at the cast
};

std::mutex g_bomb_lock;
std::unordered_map<uint32_t, Bomb> g_bombs;
std::unordered_map<uint32_t, int> g_waiting;

bool Terrain(PPCContext& ctx, uint8_t* base, float x, float y) {
  return Solid(ctx, base, kFloorPush, x, y) || Solid(ctx, base, kCeilingPush, x, y) ||
         Solid(ctx, base, kWallA, x, y) || Solid(ctx, base, kWallB, x, y);
}
}  // namespace
}  // namespace skeleton_bomber_soul

// Per-frame update (vtable slot 9; the template's 0x84211D38).
REX_EXTERN(sub_85A11D38) {
  using namespace skeleton_bomber_soul;
  const uint32_t o = ctx.r3.u32;
  const uint32_t handle = WrapperHandle(base, o);
  if (handle == 0 || handle == 0xFFFFFFFF) {            // the setup's early call: wait (cerberus_orb_spell.h)
    Float(base, o + 0x64, 0.0f);
    Float(base, o + 0x68, 0.0f);
    int waited;
    {
      std::lock_guard lock(g_bomb_lock);
      waited = ++g_waiting[o];
    }
    if (waited > 60) {
      Float(base, o + 0x320, Float(base, o + 0x32C) + 1.0f);
      __imp__sub_85A11D38(ctx, base);
      Draw(base, o, kAnimBlank, false);
    }
    return;
  }
  Bomb b;
  bool fresh = false;
  {
    std::lock_guard lock(g_bomb_lock);
    g_waiting.erase(o);
    auto it = g_bombs.find(o);
    if (it != g_bombs.end() && it->second.handle == handle) b = it->second;
    else {
      b.handle = handle;
      const float dir = Float(base, o + 0x324);
      b.dir = (dir == 1.0f || dir == -1.0f) ? dir : 1.0f;
      b.x = Float(base, o + 0x5C) + b.dir * 16.0f;
      b.y = Float(base, o + 0x60) - 40.0f;
      b.vx = b.dir * kForward;
      b.vy = -kUp;
      if (const uint32_t w = Wrapper(base, o)) { b.struck[0] = Read(base, w + 0xB8); b.struck[1] = Read(base, w + 0xBC); }
      fresh = true;
      REXLOG_INFO("[bomb-soul] cast {:08X} (handle {:08X}, owner {:08X}) at ({:.0f}, {:.0f}) facing {:.0f}", o, handle,
                  Owner(base, o), b.x, b.y, b.dir);
    }
  }
  if (fresh) {
    Float(base, o + 0x5C, b.x);
    Float(base, o + 0x60, b.y);
  }
  if (b.ended) {                                         // the template ends and destroys it
    Float(base, o + 0x64, 0.0f);
    Float(base, o + 0x68, 0.0f);
    Float(base, o + 0x320, Float(base, o + 0x32C) + 1.0f);
    __imp__sub_85A11D38(ctx, base);
    Draw(base, o, kAnimBlank, false);
    std::lock_guard lock(g_bomb_lock);
    if (++b.end_t > kForget) g_bombs.erase(o); else g_bombs[o] = b;
    return;
  }
  const float frame = float(ctx.f1.f64);
  const float dt = frame > 0 && frame < 1 ? frame : 1.0f / 60;
  ++b.t;
  if (!b.blast) {
    if (const uint32_t w = Wrapper(base, o)) {
      const uint32_t s0 = Read(base, w + 0xB8), s1 = Read(base, w + 0xBC);
      if (s0 != b.struck[0] || s1 != b.struck[1]) {
        b.hit = true;
        REXLOG_INFO("[bomb-soul] {:08X} touched {:08X} {:08X}", o, s0, s1);
      }
    }
    b.x += b.vx; b.y += b.vy; b.vy += kGravity;
    const float ahead = b.vx >= 0 ? 4.0f : -4.0f;
    if (b.hit || Terrain(ctx, base, b.x, b.y + 4.0f) || Terrain(ctx, base, b.x + ahead, b.y) ||
        Terrain(ctx, base, b.x, b.y - 4.0f)) {
      b.blast = true; b.t = 0;
      REXLOG_INFO("[bomb-soul] {:08X} explodes at ({:.0f}, {:.0f}) ({})", o, b.x, b.y, b.hit ? "hit" : "terrain");
    } else if (b.t >= kFlightTicks) {
      b.ended = true;
    }
  } else if (b.t >= kBlastTicks) {
    b.ended = true;
  }
  if (b.ended) Draw(base, o, kAnimBlank, false);
  else {
    MoveTo(base, o, b.x, b.y, dt);
    if (b.blast) { Float(base, o + 0x64, 0.0f); Float(base, o + 0x68, 0.0f); }
    Draw(base, o, b.blast ? kAnimBlast : kAnimBomb, b.dir > 0);   // the art faces left
  }
  std::lock_guard lock(g_bomb_lock);
  g_bombs[o] = b;
}

// Slot 16 (the template's "end now", called when the shot hits): a flying bomb explodes
// instead; an exploding one keeps exploding. Anything else ends as the template does.
REX_EXTERN(sub_85A12038) {
  using namespace skeleton_bomber_soul;
  const uint32_t o = ctx.r3.u32;
  {
    std::lock_guard lock(g_bomb_lock);
    auto it = g_bombs.find(o);
    if (it != g_bombs.end() && !it->second.ended) {
      if (!it->second.blast) it->second.hit = true;
      return;
    }
  }
  __imp__sub_85A12038(ctx, base);
}
