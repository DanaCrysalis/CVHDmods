#pragma once
// Tackle state shared by Nathan's module (nathan_tackle_guest.h) and the
// executable's collider handler (nathan_dss_damage.cpp). Lives in Nathan's
// player extension, after the Pluto subweapon copies (4096 + 50 * 70).
namespace harmony::nathan {
constexpr unsigned kTackle=7680;  // +0 state (1 dashing move, 2 refused), +4 wave, +8 direction, +12 dash flag
constexpr uint32_t kTackleTag=0x5441434B; // collider +0x190: the tackle's own attack area
inline bool TackleDashing(uint8_t* base,uint32_t player,uint32_t wave) {
  return player && Read(base,player+kTackle)==1 && Read(base,player+kTackle+12)==1 && Read(base,player+kTackle+4)==wave;
}
}
