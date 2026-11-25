// Shanoa glyph pack, exe side (test builds, HARMONYRECOMP_POISONWORM; user, 2026-11-24).
//
// Cubus blocks are terrain. 823C31D8(map, x, y) is the stage's tile-attribute lookup: the u16
// cell of the 16 px grid at map +20 (low byte = attribute, high byte = room; 0x03 = solid,
// 0x01 = one-way ledge), overridden by a byte layer at map +24 when that is non-zero. Every
// terrain query sits on it: the floor push-out 823C2D80, the wall and ceiling queries, and
// the player's own ground checks (824xxxxx call 823C31D8 directly as well as 823C2D80). So
// when the stage says a cell is empty and a landed Cubus block fills it, this reports 0x03:
// players, enemies and items stand on it, walk into it and bump their heads on it exactly as
// on a stage tile, with the game's own push-out rules.
//
// Test 3 (2026-11-24) showed why the first version (an 823C2D80 override that only answered
// the push) was not enough: Shanoa's ground logic also reads the attribute and saw empty air;
// she was pushed up while inside a stack but never landed on top.
//
// Blocks land on tile tops (stage floors and other blocks), so each one is exactly one cell;
// the cell test uses the block's centre. The blocks come from the Cubus module through the
// guest table this file allocates and publishes (shanoa_glyph_guest.h). The calls inside
// shard 16 are made indirect by CMakeLists.txt so this override sees every call.
#include "../generated/default/harmonyrecomp_init.h"
#include "shanoa_glyph_guest.h"
#include <rex/logging.h>
#include <rex/system/xmemory.h>
#include <atomic>
#include <cmath>
#include <mutex>

REX_EXTERN(__imp__sub_823C31D8);
#include "shield_rod.h"

// Scutum's guard slot (shanoa_glyph_guest.h): after the native guard start every frame, a
// fresh holder entry for this owner sets owner +0xA64, so PAMA carries it to the other players.
namespace {
std::atomic<uint32_t> g_scutum{0};
std::once_flag g_scutum_made;
void ScutumGuardSlot(PPCContext&, uint8_t* base, uint32_t owner) {
  using namespace harmony::shanoa_guest;
  std::call_once(g_scutum_made, [base] {
    const uint32_t raw = REX_KERNEL_MEMORY()->SystemHeapAlloc(kScutumBytes + 15);
    const uint32_t t = raw ? (raw + 15) & ~15u : 0;
    if (!t) return;
    ScutumInit(base, t);
    Publish(kScutumVar, t);
    g_scutum = t;
    REXLOG_INFO("[scutum] holder table at {:08X}, published as {}", t, kScutumVar);
  });
  int32_t slot;
  if (owner && ScutumFind(base, g_scutum, owner, slot)) Store(base, owner + kGuardSlot, uint32_t(slot));
}
struct RegisterScutum { RegisterScutum() { harmony::shield_rod::SetGuardSlotHook(&ScutumGuardSlot); } } g_register_scutum;
}  // namespace

namespace {
using namespace harmony::shanoa_guest;
constexpr uint32_t kSolid = 0x03;
std::atomic<uint32_t> g_table{0};
std::once_flag g_made;
std::atomic<int> g_logged{0};

uint32_t Table(uint8_t* base) {
  std::call_once(g_made, [base] {
    const uint32_t raw = REX_KERNEL_MEMORY()->SystemHeapAlloc(kCubusBytes + 15);
    const uint32_t t = raw ? (raw + 15) & ~15u : 0;
    if (!t) { REXLOG_WARN("[cubus] no guest memory for the block table"); return; }
    CubusInit(base, t);
    Publish(kCubusVar, t);
    g_table = t;
    REXLOG_INFO("[cubus] block table at {:08X} ({} entries), published as {}", t, kCubusEntries, kCubusVar);
  });
  return g_table;
}

int Cell(int32_t v) { return v >= 0 ? v >> 4 : -((15 - v) >> 4); }

// Is the 16 px cell holding (x, y) filled by a landed block?
bool BlockCell(uint8_t* base, uint32_t t, int32_t x, int32_t y, float& bx, float& by) {
  if (!CubusValid(base, t)) return false;
  const uint32_t now = harmony::hurt_record::NowMs();
  const int cx = Cell(x), cy = Cell(y);
  for (uint32_t i = 0; i < kCubusEntries; ++i) {
    const uint32_t e = t + kCubusHeader + i * kCubusEntry;
    if (!Load(base, e) || int32_t(now - Load(base, e + 16)) > int32_t(kCubusFreshMs)) continue;
    bx = (LoadF(base, e + 4) + LoadF(base, e + 8)) * 0.5f;
    by = LoadF(base, e + 12) + kCubusDepth * 0.5f;
    if (Cell(int32_t(std::floor(bx))) == cx && Cell(int32_t(std::floor(by))) == cy) return true;
  }
  return false;
}
}  // namespace

REX_EXTERN(sub_823C31D8) {
  const int32_t x = ctx.r4.s32, y = ctx.r5.s32;
  const uint32_t table = Table(base);
  __imp__sub_823C31D8(ctx, base);
  if ((ctx.r3.u32 & 0xFF) != 0 || !table) return;
  float bx, by;
  if (BlockCell(base, table, x, y, bx, by)) {
    ctx.r3.u64 = kSolid;
    // The block's own probes sit on its centre column; anything else is a walker (Shanoa).
    if (std::fabs(float(x) - bx) > 2.0f && g_logged.fetch_add(1) < 30)
      REXLOG_INFO("[cubus] tile query ({}, {}) inside the block at ({:.0f}, {:.0f}): solid", x, y, bx, by);
  }
}
