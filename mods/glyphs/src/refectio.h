#pragma once
#include <cstdint>

struct PPCContext;

// Refectio glyph for Shanoa (package 20, mods/glyphs/tools/refectio.py).
namespace harmony::refectio {
// After the owner's body draw (824476B8 chain): the cast rings and the
// rising wisps of this owner's Refectio, if any.
void Draw(const PPCContext& original, uint8_t* base, uint32_t owner);
}
