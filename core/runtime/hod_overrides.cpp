// The hub's overrides: the one definition of each shared guest function
// (see hod_hooks.h), the collision lock around the collision lists, and the
// collision crash guard every mod relies on.
#include "../generated/default/harmonyrecomp_init.h"
#include "hod_hooks.h"
#include "hod_guest.h"
#include <rex/logging.h>
#include <atomic>
#include <mutex>

REX_EXTERN(__imp__sub_8244CA98);
REX_EXTERN(__imp__sub_824823A0);
REX_EXTERN(__imp__sub_824827F0);
REX_EXTERN(__imp__sub_823C4C40);
REX_EXTERN(__imp__sub_823C5098);
REX_EXTERN(__imp__sub_823C4EC8);
REX_EXTERN(__imp__sub_82246DF0);
REX_EXTERN(__imp__sub_8244FFF8);
REX_EXTERN(__imp__sub_82487EF8);
REX_EXTERN(__imp__sub_8248A690);
REX_EXTERN(__imp__sub_824476B8);
REX_EXTERN(__imp__sub_82451AA8);
REX_EXTERN(__imp__sub_8245D9A0);
REX_EXTERN(__imp__sub_8244BF10);
REX_EXTERN(__imp__sub_82452658);

namespace {
using hod::Hook;

// 823C4C40 under the collision lock, then the registered observers (still
// under the lock). The handle is the owning entity's when the owner is a live
// entity (flag 4), else the source's, as the mods have always keyed targets.
void ShapeRegisterOriginal(PPCContext& ctx, uint8_t* base) {
  const PPCContext original = ctx;
  const auto source = ctx.r6.u32, owner = ctx.r7.u32;
  std::lock_guard guard(hod::CollisionLock());
  const auto owner_entity = hod::EntityOf(base, owner);
  const auto handle = owner_entity && (hod::Read32(base, owner_entity + 8) & 4) ? owner : source;
  __imp__sub_823C4C40(ctx, base);
  hod::RunShapeObservers(original, base, handle, ctx.r3.u32);
}

#define HOD_ORIGINAL(hook, address)                                                  \
  void hook##Original(PPCContext& c, uint8_t* b) { __imp__sub_##address(c, b); }    \
  [[maybe_unused]] const bool hook##_wired = hod::SetOriginal(Hook::k##hook, &hook##Original)

HOD_ORIGINAL(SpawnEvent, 8244CA98);
HOD_ORIGINAL(ColliderPrepare, 824823A0);
HOD_ORIGINAL(ColliderAttack, 824827F0);
HOD_ORIGINAL(EnemyHp, 82246DF0);
HOD_ORIGINAL(PlayerUpdate, 8244FFF8);
HOD_ORIGINAL(SkillFactory, 82487EF8);
HOD_ORIGINAL(SkillPreload, 8248A690);
HOD_ORIGINAL(OwnerDraw, 824476B8);
HOD_ORIGINAL(PhysicalDefense, 82451AA8);
HOD_ORIGINAL(StatusSummary, 8245D9A0);
HOD_ORIGINAL(IncomingDamage, 8244BF10);
HOD_ORIGINAL(AttackValue, 82452658);
[[maybe_unused]] const bool shape_wired = hod::SetOriginal(Hook::kShapeRegister, &ShapeRegisterOriginal);
}  // namespace

REX_EXTERN(sub_8244CA98) { hod::Dispatch(Hook::kSpawnEvent, ctx, base); }
REX_EXTERN(sub_824823A0) { hod::Dispatch(Hook::kColliderPrepare, ctx, base); }
REX_EXTERN(sub_824827F0) { hod::Dispatch(Hook::kColliderAttack, ctx, base); }
REX_EXTERN(sub_823C4C40) { hod::Dispatch(Hook::kShapeRegister, ctx, base); }
REX_EXTERN(sub_82246DF0) { hod::Dispatch(Hook::kEnemyHp, ctx, base); }
REX_EXTERN(sub_8244FFF8) { hod::Dispatch(Hook::kPlayerUpdate, ctx, base); }
REX_EXTERN(sub_82487EF8) { hod::Dispatch(Hook::kSkillFactory, ctx, base); }
REX_EXTERN(sub_8248A690) { hod::Dispatch(Hook::kSkillPreload, ctx, base); }
REX_EXTERN(sub_824476B8) { hod::Dispatch(Hook::kOwnerDraw, ctx, base); }
REX_EXTERN(sub_82451AA8) { hod::Dispatch(Hook::kPhysicalDefense, ctx, base); }
REX_EXTERN(sub_8245D9A0) { hod::Dispatch(Hook::kStatusSummary, ctx, base); }
REX_EXTERN(sub_8244BF10) { hod::Dispatch(Hook::kIncomingDamage, ctx, base); }
REX_EXTERN(sub_82452658) { hod::Dispatch(Hook::kAttackValue, ctx, base); }

// Collision list traversal: the same lock as registration.
REX_EXTERN(sub_823C5098) {
  std::lock_guard guard(hod::CollisionLock());
  __imp__sub_823C5098(ctx, base);
}

// Native collision filtering is shared by players, enemies and custom attacks.
// A stale/sentinel list entry is not a request: reject it before the game's
// filter reads candidate+0x10 (a Medusa Shield cast faulted on candidate 0x21).
REX_EXTERN(sub_823C4EC8) {
  const auto first = ctx.r3.u32, second = ctx.r4.u32;
  if (!hod::GuestAddress(first) || !hod::GuestAddress(second)) {
    static std::atomic<unsigned> rejected{0};
    if (rejected.fetch_add(1, std::memory_order_relaxed) < 8)
      REXLOG_WARN("[hod] rejected invalid collision request: {:08X}, {:08X}", first, second);
    ctx.r3.u64 = 0;
    return;
  }
  __imp__sub_823C4EC8(ctx, base);
}
