// Soma's Cerberus soul (soul 117): the module dllshotsoulcm068 (R. Zombie soul's code,
// modding/tools/cerberus_soul.py). The behaviour is shared: cerberus_orb_spell.h.
#include "../generated/dllshotsoulcm068/harmonyrecomp_init.h"
#include "cerberus_orb_spell.h"

REX_EXTERN(__imp__sub_85891D38);

// Per-frame update (vtable slot 9; the template's 0x84211D38).
REX_EXTERN(sub_85891D38) {
  static constexpr cerberus_orb::Module kModule{0, 117, "cerb-soul"};
  cerberus_orb::Update(ctx, base, kModule, [](PPCContext& c, uint8_t* b) { __imp__sub_85891D38(c, b); });
}
