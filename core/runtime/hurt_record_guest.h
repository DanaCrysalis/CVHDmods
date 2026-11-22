#pragma once
// Enemy hurt boxes in guest memory, shared between the exe and Nathan's
// module (harmonyrecomp_dllTest12), which cannot link to exe functions.
//
// Writer: mods/familiars/src/alucard_familiar.cpp's ObserveHurtShape, run as
// a core collision-shape observer of the hook hub (823C4C40, under the
// collision lock). Readers walk the
// table instead of the collision manager's lists, which other game threads
// rebuild while the player update runs (runs 217-219).
//
// Nathan finds the table through his own player block: the word at
// kNathanPointer, after the summon contacts, holds its guest address. The exe
// rewrites it every player update (ResetProjectiles clears that area).
//
// Table: kHeaderBytes header (+0 kMagic, +4 kEntries), then kEntries entries
// of kEntryBytes: +0 sequence (odd while being written), +4 handle, +8 time
// (steady clock, ms), +12 region, +16 shape kind, +20/+24 centre x/y,
// +28/+32 left/top, +36/+40 right/bottom.
#include <atomic>
#include <bit>
#include <chrono>
#include <cstdint>
#include <rex/memory/utils.h>

namespace harmony::hurt_record {
constexpr uint32_t kMagic = 0x48555254;  // "HURT"
constexpr uint32_t kEntries = 512, kEntryBytes = 48, kHeaderBytes = 16;
constexpr uint32_t kBytes = kHeaderBytes + kEntries * kEntryBytes;
constexpr uint32_t kFreshMs = 100;       // a box counts as live this long after its registration
constexpr uint32_t kNathanPointer = 8176;

struct Box {
  uint32_t handle = 0, region = 0, kind = 1;
  float x = 0, y = 0, x0 = 0, y0 = 0, x1 = 0, y1 = 0;
};

inline uint32_t NowMs() {
  using namespace std::chrono;
  return uint32_t(duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());
}
inline uint32_t Load(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
inline void Store(uint8_t* base, uint32_t a, uint32_t v) { rex::memory::store_and_swap<uint32_t>(base + a, v); }
inline float LoadFloat(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Load(base, a)); }
inline void StoreFloat(uint8_t* base, uint32_t a, float v) { Store(base, a, std::bit_cast<uint32_t>(v)); }

inline void Init(uint8_t* base, uint32_t table) {
  for (uint32_t i = 0; i < kBytes; i += 4) Store(base, table + i, 0);
  Store(base, table + 4, kEntries);
  std::atomic_thread_fence(std::memory_order_release);
  Store(base, table, kMagic);
}
inline bool Valid(uint8_t* base, uint32_t table) {
  return table >= 0x10000 && !(table & 3) && Load(base, table) == kMagic && Load(base, table + 4) == kEntries;
}

// One writer at a time (the exe holds its own lock around this).
inline void WriteEntry(uint8_t* base, uint32_t table, unsigned index, const Box& b, uint32_t time_ms) {
  const uint32_t e = table + kHeaderBytes + index * kEntryBytes;
  const uint32_t sequence = Load(base, e);
  Store(base, e, sequence | 1);
  std::atomic_thread_fence(std::memory_order_release);
  Store(base, e + 4, b.handle); Store(base, e + 8, time_ms);
  Store(base, e + 12, b.region); Store(base, e + 16, b.kind);
  StoreFloat(base, e + 20, b.x); StoreFloat(base, e + 24, b.y);
  StoreFloat(base, e + 28, b.x0); StoreFloat(base, e + 32, b.y0);
  StoreFloat(base, e + 36, b.x1); StoreFloat(base, e + 40, b.y1);
  std::atomic_thread_fence(std::memory_order_release);
  Store(base, e, (sequence | 1) + 1);
}

// Calls f(box) for every box registered within kFreshMs. An entry being
// rewritten during the read is skipped.
template <class F>
inline void ForEachFresh(uint8_t* base, uint32_t table, F&& f) {
  if (!Valid(base, table)) return;
  const uint32_t now = NowMs();
  for (uint32_t i = 0; i < kEntries; ++i) {
    const uint32_t e = table + kHeaderBytes + i * kEntryBytes;
    const uint32_t before = Load(base, e);
    if (!before || (before & 1)) continue;
    std::atomic_thread_fence(std::memory_order_acquire);
    Box b;
    b.handle = Load(base, e + 4);
    const uint32_t time = Load(base, e + 8);
    b.region = Load(base, e + 12); b.kind = Load(base, e + 16);
    b.x = LoadFloat(base, e + 20); b.y = LoadFloat(base, e + 24);
    b.x0 = LoadFloat(base, e + 28); b.y0 = LoadFloat(base, e + 32);
    b.x1 = LoadFloat(base, e + 36); b.y1 = LoadFloat(base, e + 40);
    std::atomic_thread_fence(std::memory_order_acquire);
    // Signed age: the writer may stamp an entry just after this read began.
    if (Load(base, e) != before || !b.handle || int32_t(now - time) > int32_t(kFreshMs)) continue;
    f(b);
  }
}
}  // namespace harmony::hurt_record
