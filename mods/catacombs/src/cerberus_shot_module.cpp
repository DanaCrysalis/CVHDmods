// Cerberus's projectiles (test builds only; CMake HARMONYRECOMP_POISONWORM): the shot
// module dllshotCm068 = Legion's falling body (dllshotRegionHuman) rebased to 0x85800000,
// shot ID 0x4068, sprite p_Cm068s.opd (modding/tools/cerberus_shot.py, cerberus_art.py).
//
// Every shot is a puppet. The boss (cerberus_module.cpp) runs CotM's projectile logic
// and fires a request whose +0x18 (this object's +0x21C) is the address of a row in its
// puppet table | the row number. Each row is 32 bytes, big-endian: float x, float y,
// u32 animation (0xFFFFFFFF: remove the shot), u32 flags (bit 0: mirrored), float
// rotation (radians, layer +0x50), float x scale (+0x38), float y scale (+0x3C). The shot
// follows its row every frame by velocity (the exe moves shots by +0x64/+0x68 px/s; the
// body's own gravity and walking never run). Hit boxes come from the frame shown, so a
// piece only hurts while it shows a boxed frame (the damaging beam, the orbs, the bolts).
#include "../generated/dllshotcm068/harmonyrecomp_init.h"
#include <rex/logging.h>
#include <rex/memory/utils.h>
#include <atomic>
#include <bit>
#include <cstdint>
#include <mutex>
#include <unordered_map>

REX_EXTERN(__imp__sub_85811AB8);
REX_EXTERN(__imp__sub_85811D40);

namespace cerberus_shot {
namespace {
uint32_t Read(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
void Write(uint8_t* base, uint32_t a, uint32_t v) { rex::memory::store_and_swap<uint32_t>(base + a, v); }
float Float(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Read(base, a)); }
void Float(uint8_t* base, uint32_t a, float v) { Write(base, a, std::bit_cast<uint32_t>(v)); }

constexpr uint32_t kRemove = 0xFFFFFFFF;
// The orbs and bolts are no longer these puppets: Cerberus fires them as Lightning Orb
// shots (dllshotLearnCm068, cerberus_orb_spell.h), which Charlotte's guard can learn from.
std::mutex g_lock;
std::unordered_map<uint32_t, uint32_t> g_rows;     // shot -> its row's address
std::atomic<int> g_logged{0};

// As the small worms draw: the body sprite +0x258 shows; the setup's extra layers hidden.
void Draw(uint8_t* base, uint32_t o, uint32_t anim, bool mirrored, uint32_t row) {
  if (const uint32_t s = Read(base, o + 0x258)) {
    base[s + 0x29] = 1;
    // Legion's laser (dllshotRegionLaser 0x83911FA4 / 0x839123B8) stretches its layers
    // with +0x38/+0x3C and turns them with +0x50.
    Float(base, s + 0x50, Float(base, row + 16));
    Float(base, s + 0x38, Float(base, row + 20));
    Float(base, s + 0x3C, Float(base, row + 24));
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
}  // namespace
}  // namespace cerberus_shot

// Setup (slot 4): a puppet takes its row; anything else stays Legion's body.
REX_EXTERN(sub_85811AB8) {
  using namespace cerberus_shot;
  const uint32_t o = ctx.r3.u32;
  __imp__sub_85811AB8(ctx, base);
  const uint32_t marker = Read(base, o + 0x21C);
  if (marker < 0x10000) return;
  const uint32_t row = (marker & ~0xFFu) + (marker & 0xFF) * 32;
  {
    std::lock_guard lock(g_lock);
    g_rows[o] = row;
  }
  Float(base, o + 0x64, 0.0f);
  Float(base, o + 0x68, 0.0f);
  const uint32_t anim = Read(base, row + 8);
  if (anim != kRemove) Draw(base, o, anim, Read(base, row + 12) & 1, row);
  if (g_logged.fetch_add(1) < 40)
    REXLOG_INFO("[cerb] shot {:08X} row {:08X} anim {} at ({:.0f}, {:.0f})", o, row, int32_t(anim),
                Float(base, o + 0x5C), Float(base, o + 0x60));
}

// Update (slot 9): follow the row; removed rows end the shot (state 4: the body's update
// destroys it through vtable +0x158).
REX_EXTERN(sub_85811D40) {
  using namespace cerberus_shot;
  const uint32_t o = ctx.r3.u32;
  uint32_t row = 0;
  {
    std::lock_guard lock(g_lock);
    auto it = g_rows.find(o);
    if (it != g_rows.end()) row = it->second;
  }
  if (!row) { __imp__sub_85811D40(ctx, base); return; }
  const uint32_t anim = Read(base, row + 8);
  if (anim == kRemove) {
    {
      std::lock_guard lock(g_lock);
      g_rows.erase(o);
    }
    Float(base, o + 0x64, 0.0f);
    Float(base, o + 0x68, 0.0f);
    Write(base, o + 0x324, 4);
    __imp__sub_85811D40(ctx, base);
    return;
  }
  const float frame = float(ctx.f1.f64);
  const float dt = frame > 0 && frame < 1 ? frame : 1.0f / 60;
  Float(base, o + 0x64, (Float(base, row + 0) - Float(base, o + 0x5C)) / dt);
  Float(base, o + 0x68, (Float(base, row + 4) - Float(base, o + 0x60)) / dt);
  Draw(base, o, anim, Read(base, row + 12) & 1, row);
}
