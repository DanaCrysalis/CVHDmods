#pragma once
// hod-mods hook hub: one owner for every guest function that more than one mod
// needs, and the runtime on/off switch of each mod.
//
// ReXGlue links exactly one definition per guest function (REX_EXTERN). Before
// the hub, the first mod to hook a function owned it and called the others by
// name, so no mod could be left out or switched off on its own. Now
// core/runtime/hod_overrides.cpp defines those overrides once and runs a chain of
// handlers that the mods register at start-up:
//
//   handler[0] -> handler[1] -> ... -> the game's own function (__imp__sub_...)
//
// A handler receives `next` and decides where the rest of the chain runs:
// before its own work, after it, around it, or not at all (to consume the call).
// Handlers are sorted by `order`, lowest first (outermost). A handler that does
// `next(ctx, base); Work();` with a LOWER order therefore does its work LATER
// than one with a higher order; every registration in the mods states its order
// on purpose, so the combined behaviour matches the shipped builds.
//
// Handlers of a mod that is switched off (Enabled() below) are skipped, so the
// chain behaves as if the mod were not compiled in.
#include <cstdint>
#include <mutex>

struct PPCContext;

namespace hod {

// Runtime features. A repo section (mods/<name>) owns one or more of these.
enum class Mod : uint8_t {
  kCore = 0,     // core/runtime: collision lock, crash guard, shared hurt-box feed
  kShieldRod,    // mods/shield-rod        package 19
  kFamiliars,    // mods/familiars         package 21
  kRefectio,     // mods/glyphs            package 20
  kArmaCustos,   // mods/glyphs            Catacombs package 10
  kNathan,       // mods/nathan            package 17
  kCatacombs,    // mods/catacombs         package 10 (code lives in its own modules)
  kCount
};

// "shield-rod", "familiars", ... (the ids used in hod_native_mods.txt and mods.json).
const char* ModId(Mod mod);
// Compiled into this exe (its CMake option was on).
bool Compiled(Mod mod);
// Compiled in and switched on for this run (see hod_mods.cpp for the rules).
bool Enabled(Mod mod);

// Shared guest functions. Address, native role and the mods that use each one
// are listed in core/hooks.json (the same table drives the CMake rewrites).
enum class Hook : uint8_t {
  kSpawnEvent,       // 8244CA98 player spawn event (online carrier kind 11)
  kColliderPrepare,  // 824823A0 attack collider prepare phase
  kColliderAttack,   // 824827F0 attack collider attack phase
  kShapeRegister,    // 823C4C40 collision shape registration (runs under the collision lock)
  kEnemyHp,          // 82246DF0 enemy HP transaction
  kPlayerUpdate,     // 8244FFF8 player update, f1 = frame seconds
  kSkillFactory,     // 82487EF8 skill factory (kind, index, owner handle, ...)
  kSkillPreload,     // 8248A690 skill preload when equipped (kind, index)
  kOwnerDraw,        // 824476B8 owner draw (body and afterimages)
  kPhysicalDefense,  // 82451AA8 physical DEF -> f1
  kStatusSummary,    // 8245D9A0 status/equipment screen summary (character, out)
  kIncomingDamage,   // 8244BF10 incoming damage or heal
  kAttackValue,      // 82452658 STR/attack value getter -> f1
  kCount
};
const char* HookName(Hook hook);
uint32_t HookAddress(Hook hook);

// The rest of a chain. Calling it runs the remaining enabled handlers and then
// the game's own function. Calling it more than once runs them again.
class Next {
 public:
  constexpr Next(Hook hook, uint16_t index) : hook_(hook), index_(index) {}
  void operator()(PPCContext& ctx, uint8_t* base) const;

 private:
  Hook hook_;
  uint16_t index_;
};

using Handler = void (*)(PPCContext& ctx, uint8_t* base, const Next& next);

// Adds a handler (call from a static initializer; see HOD_HOOK). Returns true.
bool Register(Hook hook, Mod mod, int order, Handler handler, const char* name);

// Every collision shape the game registers (823C4C40), called with the
// collision lock held, after the game's own registration. `original` is the
// context as it entered the call (r3 shape, r4 flags, r5 region, r6 source,
// r7 owner, lr caller), `handle` the owning entity handle, `result` the game's
// return value (0xFFFFFFFF = refused).
using ShapeObserver = void (*)(const PPCContext& original, uint8_t* base, uint32_t handle, uint32_t result);
bool RegisterShapeObserver(Mod mod, int order, ShapeObserver observer, const char* name);

// Runs a hook's chain (what the hub's override of that guest function does).
void Dispatch(Hook hook, PPCContext& ctx, uint8_t* base);
// The game's function at the end of a chain (hod_overrides.cpp sets the real
// ones; the Nathan test harness sets stand-ins).
using Original = void (*)(PPCContext& ctx, uint8_t* base);
bool SetOriginal(Hook hook, Original original);
// Calls the registered shape observers (from the 823C4C40 chain's end).
void RunShapeObservers(const PPCContext& original, uint8_t* base, uint32_t handle, uint32_t result);

// The lock around every collision list mutation and traversal (823C4C40,
// 823C5098). Enemies register shapes on several game threads; mod code that
// reads collision lists takes this lock too.
std::recursive_mutex& CollisionLock();

}  // namespace hod

#define HOD_JOIN2(a, b) a##b
#define HOD_JOIN(a, b) HOD_JOIN2(a, b)
// HOD_HOOK(kOwnerDraw, kShieldRod, 50, DrawSpells);
#define HOD_HOOK(hook, mod, order, fn)                                                       \
  [[maybe_unused]] static const bool HOD_JOIN(hod_hook_registered_, __LINE__) =              \
      ::hod::Register(::hod::Hook::hook, ::hod::Mod::mod, order, &fn, #fn)
#define HOD_SHAPE_OBSERVER(mod, order, fn)                                                   \
  [[maybe_unused]] static const bool HOD_JOIN(hod_shape_registered_, __LINE__) =             \
      ::hod::RegisterShapeObserver(::hod::Mod::mod, order, &fn, #fn)

// First statement of a mod's own (unshared) override: when the mod is off,
// run the game's function unchanged.
#define HOD_PASS_IF_OFF(mod, original)                \
  if (!::hod::Enabled(::hod::Mod::mod)) {             \
    original(ctx, base);                              \
    return;                                           \
  }
