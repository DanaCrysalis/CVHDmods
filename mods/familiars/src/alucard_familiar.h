#pragma once
#include <cstdint>
#include "hod_guest.h"

struct PPCContext;

// Alucard's familiar cards (package 21, mods/familiars/tools/alucard_familiars.py).
// Every entry point below is called from the hook hub registrations at the end
// of alucard_familiar.cpp (core/runtime/hod_hooks.h).
namespace harmony::alucard_familiar {
// Collider +0x190 of a familiar's attack area ("FMLG"). Nathan's 824827F0
// override (and the Shield Rod bridge) hand these to ResolveHit.
constexpr uint32_t kHitTag = 0x464D4C47;
void ResolveHit(PPCContext& ctx, uint8_t* base, uint32_t hit);
// Collision prepare phase of the same colliders (824823A0 override in shield_rod.cpp).
void PrepareHit(PPCContext& ctx, uint8_t* base, uint32_t hit);
// An enemy lost `damage` HP to one of these hits (82246DF0 observer in shield_rod.cpp).
void Landed(PPCContext& ctx, uint8_t* base, uint32_t hit, float damage);
// Every player update (8244FFF8 override in refectio.cpp), every machine.
void Frame(PPCContext& ctx, uint8_t* base, uint32_t owner, double seconds);
// Each enemy hurt shape the game registers (823C4C40 override in
// shield_rod.cpp, under its collision lock, any flags): the familiars target
// from the enemy hurt shapes among these.
void ObserveHurtShape(uint8_t* base, uint32_t handle, uint32_t shape, uint32_t flags, uint32_t region, uint32_t caller);
// Collision record flags of an enemy hurt box: see hod::IsHurtRecord.
using hod::IsHurtRecord;
// Nathan's player block gets the guest hurt-box table's address (every player update).
void PublishHurtRecord(uint8_t* base, uint32_t owner);
// Every player spawn event (8244CA98 override in shield_rod.cpp): a remote
// Alucard's Sword Brothers cast.
void SpawnEvent(PPCContext& ctx, uint8_t* base);
// After the owner's body draw (824476B8 overrides), like shield_rod::Draw.
void Draw(const PPCContext& original, uint8_t* base, uint32_t body);
}
