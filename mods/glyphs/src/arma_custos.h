#pragma once
#include <cstdint>

struct PPCContext;

// Arma Custos glyph for Shanoa (Catacombs package 10, mods/glyphs/tools/arma_custos.py):
// a timed STR buff with Cerberus's third head drawn above her while it runs.
namespace harmony::arma_custos {
// The skill factory / preload (kind, index) for this glyph (hub chains, end of arma_custos.cpp).
bool Handles(uint32_t kind, uint32_t index);
void Cast(PPCContext& ctx, uint8_t* base, uint32_t handle, uint32_t level, uint32_t launcher);
void Preload(PPCContext& ctx, uint8_t* base);
// Every player update (8244FFF8 chain).
void Frame(PPCContext& ctx, uint8_t* base, uint32_t owner, double seconds);
// After the owner's body draw (824476B8 chain).
void Draw(const PPCContext& original, uint8_t* base, uint32_t owner);
// STR to add to the game's STR total (82452658 chain) for this owner.
double StrengthBonus(uint8_t* base, uint32_t owner);
// Status screen summary (8245D9A0 chain): add the buff to its STR and ATK.
void Summary(PPCContext& ctx, uint8_t* base, uint32_t character, uint32_t out);
}
