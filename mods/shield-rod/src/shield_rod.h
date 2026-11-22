#pragma once
#include <cstdint>

struct PPCContext;

// Shield Rod (Alucard, package 19). Its hooks register with the hub
// (core/runtime/hod_hooks.h) from shield_rod.cpp; nothing else calls into it.
namespace harmony::shield_rod {
constexpr uint32_t kHitTag = 0x53524B4E;  // collider +0x190: a Shield Rod spell's attack area ("SRKN")

// Incoming damage (8244BF10 chain): true cancels the hit (Alucard Shield).
bool Incoming(PPCContext& ctx, uint8_t* base, uint32_t owner);
// Flat DEF to add to an owner's physical DEF (Leather Shield spell, 82451AA8 chain).
float DefenseBonus(uint8_t* base, uint32_t owner);
// Detached spell art, once after the 824476B8 owner draw (including echoes).
void Draw(const PPCContext& original, uint8_t* base, uint32_t body);
// Attack phase of a collider tagged kHitTag (824827F0 chain).
void ResolveHit(PPCContext& ctx, uint8_t* base, uint32_t hit);
// Status/equipment summary (8245D9A0 chain, after the native).
void Summary(PPCContext& ctx, uint8_t* base, uint32_t character, uint32_t out);
}
