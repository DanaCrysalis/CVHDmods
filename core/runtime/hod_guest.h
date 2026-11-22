#pragma once
// Small guest-memory facts shared by several mods (header only, no state).
#include <cstdint>
#include <rex/memory/utils.h>

namespace hod {

inline uint32_t Read32(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }

// A pointer the collision code may follow: mapped, word aligned, not a sentinel.
constexpr bool GuestAddress(uint32_t p) { return p >= 0x10000 && p < 0xE0000000u && !(p & 3); }

// Entity handle -> object, through the entity manager's handle table.
inline uint32_t EntityOf(uint8_t* base, uint32_t handle) {
  const auto manager = Read32(base, 0x8291D9F0);
  if (!manager || !handle) return 0;
  const auto table = Read32(base, manager + 0xAC);
  if (!table) return 0;
  const auto end = Read32(base, manager + 0xB0);
  const uint32_t offset = (handle & 0xFFFF) << 4;
  if (end < table || end - table > 65536 * 16 || end - table < 16 || offset > end - table - 16) return 0;
  const auto entry = table + offset;
  return Read32(base, entry) == handle ? Read32(base, entry + 4) : 0;
}

// Enemy hurt-box record flags (collision record +4): 0x8 can be hit (a
// sleeping enemy registers only 0x40000008), 0x1 body, 0x10 guard geometry,
// 0x2 an attack.
constexpr bool IsHurtRecord(uint32_t flags) { return (flags & 0x18) && !(flags & 2); }

// Native short-lived attack rectangles (as Nathan's summons, Shield Rod
// spells and familiar hits spawn them): word 0 points 512 bytes into the
// object; a mod's tag sits at +0x190.
constexpr uint32_t kColliderTable = 512;
inline bool AttackCollider(uint8_t* base, uint32_t p) { return p && Read32(base, p) == p + kColliderTable; }
inline uint32_t ColliderTag(uint8_t* base, uint32_t p) { return Read32(base, p + 0x190); }

// Skill factory 82487EF8 called from the hand-item launcher (8246FB18 ->
// 824881C8): lr is this address and r6 is launcher + 0x48.
constexpr uint32_t kGlyphLauncherReturn = 0x8246FC40;

}  // namespace hod
