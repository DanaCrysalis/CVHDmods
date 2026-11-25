#pragma once
// Data the exe and the Shanoa glyph modules share in guest memory (user, 2026-11-24). Shot
// modules are their own host DLLs and cannot link to exe code, so, as Nathan's module reads
// the enemy hurt boxes (hurt_record_guest.h), they read tables the exe allocates. The exe
// publishes each table's guest address in a process environment variable; the modules read
// it with GetEnvironmentVariableA (live, unlike the CRT's getenv copy).
//
//   HARMONY_HURT_RECORD  enemy hurt boxes (hurt_record_guest.h), written by
//                        alucard_familiar.cpp from Shield Rod's 823C4C40 override.
//   HARMONY_CUBUS_TABLE  Cubus blocks standing in the stage (below). The Cubus module writes
//                        them; the exe's floor push-out override (shanoa_glyph_bridge.cpp,
//                        823C2D80) reports their tops as floor, so players, enemies and
//                        items stand on them.
//
// Cubus table: +0 kCubusMagic, +4 kCubusEntries, +8 the stage's floor push on a floor's top row
// (s32, measured by the Cubus module; 0 = not yet), +12 0, then entries of 16 bytes:
// +0 owner (the Cubus shot's module object; 0 = free), +4 left x, +8 right x, +12 top y
// (floats, world px), +16 time (steady clock ms). An entry is live while its owner refreshes it
// (a shot that vanishes without crumbling, e.g. on a stage change, stops counting by itself).
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <rex/memory/utils.h>
#include "hurt_record_guest.h"   // NowMs (one steady clock for the exe and the modules)

// kernel32 (declared here instead of <windows.h>, whose macros clash with game code names).
extern "C" __declspec(dllimport) int __stdcall SetEnvironmentVariableA(const char* name, const char* value);
extern "C" __declspec(dllimport) unsigned long __stdcall GetEnvironmentVariableA(const char* name, char* buffer,
                                                                                unsigned long size);

namespace harmony::shanoa_guest {
constexpr char kHurtRecordVar[] = "HARMONY_HURT_RECORD";
constexpr char kCubusVar[] = "HARMONY_CUBUS_TABLE";
constexpr char kScutumVar[] = "HARMONY_SCUTUM_TABLE";
constexpr uint32_t kCubusMagic = 0x43554255;   // "CUBU"
constexpr uint32_t kCubusEntries = 64, kCubusHeader = 16, kCubusEntry = 20;
constexpr uint32_t kCubusFreshMs = 250;          // an entry its owner stopped refreshing is ignored
constexpr uint32_t kCubusBytes = kCubusHeader + kCubusEntries * kCubusEntry;
constexpr float kCubusDepth = 16.0f;            // the block's height: a foot inside it is pushed up to the top

inline void Publish(const char* name, uint32_t guest) {
  char text[16];
  std::snprintf(text, sizeof text, "%08X", guest);
  SetEnvironmentVariableA(name, text);
}
inline uint32_t Published(const char* name) {
  char text[16] = {};
  const unsigned long n = GetEnvironmentVariableA(name, text, sizeof text);
  return n && n < sizeof text ? uint32_t(std::strtoul(text, nullptr, 16)) : 0;
}

inline uint32_t Load(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
inline void Store(uint8_t* base, uint32_t a, uint32_t v) { rex::memory::store_and_swap<uint32_t>(base + a, v); }
inline float LoadF(uint8_t* base, uint32_t a) { const uint32_t v = Load(base, a); float f; std::memcpy(&f, &v, 4); return f; }
inline void StoreF(uint8_t* base, uint32_t a, float f) { uint32_t v; std::memcpy(&v, &f, 4); Store(base, a, v); }

inline bool CubusValid(uint8_t* base, uint32_t t) {
  return t >= 0x10000 && !(t & 3) && Load(base, t) == kCubusMagic && Load(base, t + 4) == kCubusEntries;
}
inline void CubusInit(uint8_t* base, uint32_t t) {
  for (uint32_t i = 0; i < kCubusBytes; i += 4) Store(base, t + i, 0);
  Store(base, t + 4, kCubusEntries);
  Store(base, t, kCubusMagic);
}
// Writer (the Cubus module): put or refresh this owner's block; returns false when full.
inline bool CubusPut(uint8_t* base, uint32_t t, uint32_t owner, float x0, float x1, float top) {
  if (!CubusValid(base, t)) return false;
  uint32_t free_at = 0;
  for (uint32_t i = 0; i < kCubusEntries; ++i) {
    const uint32_t e = t + kCubusHeader + i * kCubusEntry;
    const uint32_t o = Load(base, e);
    if (o == owner) {
      StoreF(base, e + 4, x0); StoreF(base, e + 8, x1); StoreF(base, e + 12, top);
      Store(base, e + 16, harmony::hurt_record::NowMs());
      return true;
    }
    if ((!o || int32_t(harmony::hurt_record::NowMs() - Load(base, e + 16)) > int32_t(kCubusFreshMs)) && !free_at) free_at = e;
  }
  if (!free_at) return false;
  StoreF(base, free_at + 4, x0); StoreF(base, free_at + 8, x1); StoreF(base, free_at + 12, top);
  Store(base, free_at + 16, harmony::hurt_record::NowMs());
  Store(base, free_at, owner);
  return true;
}
inline void CubusRemove(uint8_t* base, uint32_t t, uint32_t owner) {
  if (!CubusValid(base, t)) return;
  for (uint32_t i = 0; i < kCubusEntries; ++i) {
    const uint32_t e = t + kCubusHeader + i * kCubusEntry;
    if (Load(base, e) == owner) Store(base, e, 0);
  }
}
// Reader (the exe): the top of the block whose body holds (x, y), if any.
inline bool CubusAt(uint8_t* base, uint32_t t, float x, float y, float& top) {
  if (!CubusValid(base, t)) return false;
  const uint32_t now = harmony::hurt_record::NowMs();
  for (uint32_t i = 0; i < kCubusEntries; ++i) {
    const uint32_t e = t + kCubusHeader + i * kCubusEntry;
    if (!Load(base, e) || int32_t(now - Load(base, e + 16)) > int32_t(kCubusFreshMs)) continue;
    const float x0 = LoadF(base, e + 4), x1 = LoadF(base, e + 8), tp = LoadF(base, e + 12);
    if (x >= x0 && x < x1 && y >= tp && y < tp + kCubusDepth) { top = tp; return true; }
  }
  return false;
}
// Scutum holders (test builds): +0 kScutumMagic, +4 kScutumEntries, +8/+12 0, then entries
// of 12 bytes: +0 owner (the player entity; 0 = free), +4 weapon slot (s32), +8 time (ms). The
// Scutum module (on the owner's own machine) refreshes its entry every frame while the shield
// is up; the exe's guard-slot hook (shanoa_glyph_bridge.cpp, after 82450658) writes that slot
// to owner +0xA64, the guard slot HoD sends to the other players in PAMA (+0x47), so their
// copies of the shield stay up as long as it is held. Guard status 11 is never set: no stance,
// and attacks stay free (user, 2026-11-24).
constexpr uint32_t kScutumMagic = 0x53435554;  // "SCUT"
constexpr uint32_t kScutumEntries = 8, kScutumHeader = 16, kScutumEntry = 12, kScutumFreshMs = 150;
constexpr uint32_t kScutumBytes = kScutumHeader + kScutumEntries * kScutumEntry;
constexpr uint32_t kGuardSlot = 0xA64;          // owner: guard slot (-1 none), sent as PAMA +0x47
inline bool ScutumValid(uint8_t* base, uint32_t t) {
  return t >= 0x10000 && !(t & 3) && Load(base, t) == kScutumMagic && Load(base, t + 4) == kScutumEntries;
}
inline void ScutumInit(uint8_t* base, uint32_t t) {
  for (uint32_t i = 0; i < kScutumBytes; i += 4) Store(base, t + i, 0);
  Store(base, t + 4, kScutumEntries);
  Store(base, t, kScutumMagic);
}
inline void ScutumPut(uint8_t* base, uint32_t t, uint32_t owner, int32_t slot) {
  if (!ScutumValid(base, t)) return;
  const uint32_t now = harmony::hurt_record::NowMs();
  uint32_t free_at = 0;
  for (uint32_t i = 0; i < kScutumEntries; ++i) {
    const uint32_t e = t + kScutumHeader + i * kScutumEntry;
    const uint32_t o = Load(base, e);
    if (o == owner) { Store(base, e + 4, uint32_t(slot)); Store(base, e + 8, now); return; }
    if ((!o || int32_t(now - Load(base, e + 8)) > int32_t(kScutumFreshMs)) && !free_at) free_at = e;
  }
  if (!free_at) return;
  Store(base, free_at + 4, uint32_t(slot)); Store(base, free_at + 8, now); Store(base, free_at, owner);
}
inline void ScutumRemove(uint8_t* base, uint32_t t, uint32_t owner) {
  if (!ScutumValid(base, t)) return;
  for (uint32_t i = 0; i < kScutumEntries; ++i) {
    const uint32_t e = t + kScutumHeader + i * kScutumEntry;
    if (Load(base, e) == owner) Store(base, e, 0);
  }
}
inline bool ScutumFind(uint8_t* base, uint32_t t, uint32_t owner, int32_t& slot) {
  if (!ScutumValid(base, t)) return false;
  const uint32_t now = harmony::hurt_record::NowMs();
  for (uint32_t i = 0; i < kScutumEntries; ++i) {
    const uint32_t e = t + kScutumHeader + i * kScutumEntry;
    if (Load(base, e) == owner && int32_t(now - Load(base, e + 8)) <= int32_t(kScutumFreshMs)) {
      slot = int32_t(Load(base, e + 4));
      return true;
    }
  }
  return false;
}
}  // namespace harmony::shanoa_guest
