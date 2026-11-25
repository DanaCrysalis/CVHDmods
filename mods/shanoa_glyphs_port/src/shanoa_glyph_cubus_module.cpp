// Cubus (glyph 11, module dllshotGlyphCubus at 0x85C80000): "drops a block that can be
// stood upon, stacked, fades quickly" (user, 2026-11-24). OoE art ram10: 0 the block
// (OoE hitbox 16x16), animations: 0 block, 1 crumble (0-6), 2 block (frame 7, whose 48x0 box
// looks like OoE's platform edge), 3 crumble (7-13), 4 the flash it forms from (14-20).
//
// Cast: the block forms (animation 4) in front of her on the 16 px tile grid, then falls
// until it lands on a floor or on another Cubus block (so they stack), stays kStayTicks,
// crumbles (animation 1) and ends. A block whose support goes (the one under it crumbles)
// falls again and keeps the time it had already stayed (user, 2026-11-24). Falling onto an enemy hits it (the block's box; glyph power
// + INT, strike).
//
// Standing on it (user, test 2): every landed block is put in the exe's Cubus table
// (shanoa_glyph_guest.h) each frame, and the exe's tile-attribute override
// (shanoa_glyph_bridge.cpp, 823C31D8) reports its 16 px cell as a solid tile (0x03) to every
// terrain query, so walkers stand on it, bump into it and push out of it as on stage tiles
// (test 3: answering only the floor push left Shanoa unable to land on it). It leaves the table
// when it starts to fall again or to crumble. (The first landing on the stage still logs the
// stage's push value on a floor's top row, -1 in test 3; nothing uses it now.)
#include "../generated/dllshotglyphcubus/harmonyrecomp_init.h"
#include "shanoa_glyph_shot.h"

REX_EXTERN(__imp__sub_85C91D38);
REX_EXTERN(__imp__sub_85C92038);

namespace cubus {
namespace {
using namespace shanoa_glyph;
using namespace shanoa_glyphs;
constexpr Glyph kGlyph{3, kCubusIndex, "cubus", kCubusBlank};
constexpr uint32_t kBlockAnim = 0, kCrumbleAnim = 1, kFlashAnim = 4;
constexpr int kFlashTicks = 14, kStayTicks = 150, kCrumbleTicks = 14, kMaxFallTicks = 240;
constexpr float kGravity = 0.4f, kMaxFall = 8.0f, kHalf = 8.0f, kTile = 16.0f;
constexpr float kForward = 24.0f, kUp = 8.0f;

struct Block { float x, y; bool landed; };
std::mutex g_block_lock;
std::unordered_map<uint32_t, Block> g_blocks;           // module object -> block

// The top of whatever is under (x, bottom): another landed block's top, if any.
bool BlockBelow(uint32_t self, float x, float bottom, float& top) {
  std::lock_guard lock(g_block_lock);
  for (const auto& [o, b] : g_blocks) {
    if (o == self || !b.landed || std::fabs(b.x - x) >= kTile) continue;
    const float t = b.y - kHalf;
    if (bottom >= t && bottom <= t + kTile) { top = t; return true; }
  }
  return false;
}

uint32_t CubusTable(uint8_t* base) {
  static std::atomic<uint32_t> table{0};
  uint32_t t = table;
  if (!harmony::shanoa_guest::CubusValid(base, t)) {
    t = harmony::shanoa_guest::Published(harmony::shanoa_guest::kCubusVar);
    if (!harmony::shanoa_guest::CubusValid(base, t)) return 0;
    table = t;
  }
  return t;
}

void Step(PPCContext& ctx, uint8_t* base, const Glyph&, uint32_t o, Shot& s, Look& look, float) {
  auto remember = [&](bool landed) {
    {
      std::lock_guard lock(g_block_lock);
      if (s.ended) g_blocks.erase(o); else g_blocks[o] = Block{s.x, s.y, landed};
    }
    if (const uint32_t table = CubusTable(base)) {   // standable while landed
      if (landed && !s.ended) harmony::shanoa_guest::CubusPut(base, table, o, s.x - kHalf, s.x + kHalf, s.y - kHalf);
      else harmony::shanoa_guest::CubusRemove(base, table, o);
    }
  };
  switch (s.phase) {
    case 0:                                             // forms in front of her
      if (s.t == 0) {
        float cx, cy;
        if (OwnerCentre(base, s, cx, cy)) { s.x = cx + s.dir * kForward; s.y = cy - kUp; }
        s.x = std::floor(s.x / kTile) * kTile + kHalf;  // on the tile grid, so blocks stack
      }
      look.anim = kFlashAnim;
      if (s.t >= kFlashTicks) { s.phase = 1; s.t = -1; s.vy = 0; s.aux = 0; }
      remember(false);
      return;
    case 1: {                                           // falls
      look.anim = kBlockAnim;
      s.vy = std::min(s.vy + kGravity, kMaxFall);
      float top = 0;
      bool landed = false, on_stage = false;
      for (int px = 0; px < int(std::ceil(s.vy)) && !landed; ++px) {
        if (BlockBelow(o, s.x, s.y + kHalf + 1, top)) { s.y = top - kHalf; landed = true; }
        else if (Floor(ctx, base, s.x, s.y + kHalf + 1)) landed = on_stage = true;
        else s.y += 1.0f;
      }
      if (on_stage) {                                   // measure the stage's push on a floor's top row
        const uint32_t table = CubusTable(base);
        if (table && !harmony::shanoa_guest::Load(base, table + 8)) {
          const float fx = std::floor(s.x), fy = s.y + kHalf + 1;
          const int32_t top_row = int32_t(cerberus_orb::Guest(ctx, base, kFloorPush, uint32_t(int32_t(fx)), uint32_t(int32_t(fy))));
          const int32_t below = int32_t(cerberus_orb::Guest(ctx, base, kFloorPush, uint32_t(int32_t(fx)), uint32_t(int32_t(fy) + 4)));
          if (top_row < 0) harmony::shanoa_guest::Store(base, table + 8, uint32_t(top_row));
          REXLOG_INFO("[cubus] stage floor push at its top row {} (4 px deeper {}); block tops will match", top_row, below);
        }
      }
      if (landed || s.t >= kMaxFallTicks) {
        REXLOG_INFO("[cubus] {:08X} landed at ({:.0f}, {:.0f})", o, s.x, s.y);
        s.phase = 2; s.t = s.aux - 1; s.vy = 0;
      }
      remember(landed);
      return;
    }
    case 2: {                                           // stays while something holds it up
      look.anim = kBlockAnim;
      float top = 0;
      if (!BlockBelow(o, s.x, s.y + kHalf + 1, top) && !Floor(ctx, base, s.x, s.y + kHalf + 1)) {
        REXLOG_INFO("[cubus] {:08X} lost its support at ({:.0f}, {:.0f}); falls again", o, s.x, s.y);
        s.aux = s.t; s.phase = 1; s.t = -1; s.vy = 0;
        remember(false);
        return;
      }
      if (s.t >= kStayTicks) { s.phase = 3; s.t = -1; remember(false); return; }
      remember(true);
      return;
    }
    default:                                            // crumbles
      look.anim = kCrumbleAnim;
      if (s.t >= kCrumbleTicks) s.ended = true;
      remember(false);
      return;
  }
}
}  // namespace
}  // namespace cubus

REX_EXTERN(sub_85C91D38) { shanoa_glyph::Update(ctx, base, cubus::kGlyph, __imp__sub_85C91D38, cubus::Step); }
REX_EXTERN(sub_85C92038) { shanoa_glyph::EndRequest(ctx, base, __imp__sub_85C92038); }
