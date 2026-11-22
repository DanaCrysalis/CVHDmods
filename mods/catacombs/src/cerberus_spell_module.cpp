// Charlotte's Lightning Orb (learningset 26): the module dllshotlearncm068 (R. Zombie soul's code,
// modding/tools/cerberus_soul.py). The behaviour is shared: cerberus_orb_spell.h.
#include "../generated/dllshotlearncm068/harmonyrecomp_init.h"
#include "cerberus_orb_spell.h"

REX_EXTERN(__imp__sub_85911D38);

// Per-frame update (vtable slot 9; the template's 0x84211D38).
REX_EXTERN(sub_85911D38) {
  static constexpr cerberus_orb::Module kModule{8, 26, "cerb-spell"};
  cerberus_orb::Update(ctx, base, kModule, [](PPCContext& c, uint8_t* b) { __imp__sub_85911D38(c, b); });
}
