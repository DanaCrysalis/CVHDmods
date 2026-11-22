// Strong overrides of Nathan's generated weak functions. Originals remain
// available as __imp__sub_*; codegen can be rerun without losing this module.
#include "../generated/dlltest12/harmonyrecomp_init.h"
#include "nathan_audio_guest.h"
#include "nathan_card_swap_guest.h"
#include "nathan_uranus_guest.h"
#include "nathan_progress_guest.h"
#include "nathan_projectiles_guest.h"
#include "nathan_tackle_guest.h"

using namespace harmony::nathan;

namespace {
// Online co-op, owner side (see LocalPlayer in nathan_dss_guest.h): announce
// an event as a native replicate-only spawn event (8244CA98 kind 11 / sub 1).
// HoD queues it for the other machines only for the local player in a
// network game; in single player it does nothing. The callee reads three
// stack arguments, so it gets a fresh zeroed frame below the live stack.
void Announce(PPCContext& ctx,uint8_t* base,uint32_t player,uint32_t id) {
  const auto owner=Owner(base,player);
  if(!owner || !LocalPlayer(base,player)) return;
  PPCContext call=ctx;
  const uint32_t sp=(ctx.r1.u32-0x400)&~15u;
  std::memset(base+sp,0,0x100);
  call.r1.u64=sp;call.r3.u64=owner;call.r4.u64=id&0xFFFF;call.r5.u64=11;call.r6.u64=1;
  call.r7.u64=0;call.r8.u64=0;call.r9.u64=kNetTagA;call.r10.u64=kNetTagB;call.f1.f64=0;
  rex::runtime::ResolveIndirectFunction(0x8244CA98)(call,base);
}
// Once per update of the local Nathan: the DSS state (pair and pair level, or
// off) whenever it changes and every 2 s while on (a copy that missed it
// catches up; the copy ignores a repeat), and the attack button while DSS is
// on (familiars, the Mars combo and charge follow it on every machine).
// Uranus is not repeated: its "on" starts the summon.
void AnnounceFrame(PPCContext& ctx,uint8_t* base,uint32_t player,uint32_t held,float dt) {
  const auto s=Load(base,player);
  const bool on=s.enabled && !s.Direct() && s.attribute<10 && ActiveDss(base,player,s);
  const unsigned level=std::clamp(unsigned(PairLevel(base,player)),1u,kCardCopyCap);
  const auto state=on ? NetId(kNetOn,s.action,s.attribute,level) : NetId(kNetOff);
  float resend=Float(base,player+kNet+96)-(dt>0 && dt<=.1f ? dt : 1.0f/60);
  if(state!=Read(base,player+kNet+92) || (on && s.action!=kActionUranus && resend<=0)) {
    Announce(ctx,base,player,state);Write(base,player+kNet+92,state);resend=2;
  }
  Float(base,player+kNet+96,resend);
  const uint32_t attack=on && (held&kAttackButton) ? 1 : 0;
  if(attack!=Read(base,player+kNet+100)) {Announce(ctx,base,player,NetId(kNetAttack,0,0,attack));Write(base,player+kNet+100,attack);}
}
// Copy side: apply the events its owner announced, in order, with no MP spent
// (ReplayScope). Returns the owner's attack button for this update (held, and
// the press itself once) in place of input the copy does not have.
struct NetInput {uint32_t held=0,pressed=0;};
NetInput ReceiveEvents(PPCContext& ctx,uint8_t* base,uint32_t player) {
  const ReplayScope replay(true);
  const auto written=Read(base,player+kNet);
  auto read=Read(base,player+kNet+4);
  if(written-read>kNetQueue) read=written-kNetQueue;
  for(;read!=written;++read) {
    const auto id=Read(base,player+kNet+8+(read%kNetQueue)*4);
    const unsigned type=id>>12&15,a=id>>8&15,b=id>>4&15,c=id&15;
    auto s=Load(base,player);
    auto pair=[&]{Write(base,player+kNet+72,a<=kActionNeptune ? a : kActionUnavailable);Write(base,player+kNet+76,b<10 ? b : 10);};
    switch(type) {
      case kNetOn:
        pair();Float(base,player+kNet+80,c>=1 && c<=kCardCopyCap ? float(c) : 1);
        if(!(s.enabled && s.action==a && s.attribute==b)) {
          s.Select(b,a);s.enabled=1;s.pulse_time=0;s.fade_remaining=0;
          s.cast_remaining=a==kActionUranus ? kSummonSeconds : kCastSeconds;
        }
        Save(base,player,s);break;
      case kNetOff:
        s.Disable();Save(base,player,s);Write(base,player+kNet+84,0);Write(base,player+kNet+88,0);break;
      case kNetCast:
        pair();s.Select(b,a);
        if(DirectCast(ctx,base,player,s)) Sound(ctx,base,player,300);
        Save(base,player,s);break;
      case kNetSwing:
        RecordDssSwing(base,player,(c&2) ? 1 : 0);
        if((c&1) && s.enabled && s.action==a && s.attribute==b) {
          s.paid_swing=1;s.hold_time=0;Save(base,player,s);
          SwingProjectile(ctx,base,player,s);
        }
        SwingSound(ctx,base,player);break;
      case kNetAttack:
        if((c&1) && !Read(base,player+kNet+84)) Write(base,player+kNet+88,1);
        Write(base,player+kNet+84,c&1);break;
      case kNetSubweapon:
        AdditionalSubweaponShot(ctx,base,player,c);break;
    }
  }
  Write(base,player+kNet+4,read);
  NetInput input;
  if(Read(base,player+kNet+84)) input.held=kAttackButton;
  if(Read(base,player+kNet+88)) {input.pressed=kAttackButton;input.held|=kAttackButton;Write(base,player+kNet+88,0);}
  return input;
}
}

// Tackle Martial Art (see nathan_tackle_guest.h). Entry 268: Simon's only
// command (index 0) is answered as Nathan's Martial Art instead of the VK shot.
REX_EXTERN(sub_836D4638) {
  if(ctx.r4.u32==kTackleCommand && ctx.r5.u32 && ctx.r6.u32) {
    Write(base,ctx.r6.u32,kTackleArt);Write(base,ctx.r5.u32,kMartialArtType);return;
  }
  __imp__sub_836D4638(ctx,base);
}
// State 37 (the command state): enter / update / exit, for Nathan's row only.
REX_EXTERN(sub_836D16C8) {
  const auto player=Read(base,ctx.r3.u32+4);
  if(!TackleIndex(base,player)) {__imp__sub_836D16C8(ctx,base);return;}
  const ReplayScope replay(!LocalPlayer(base,player));  // a copy's dash was paid by its owner
  BeginTackle(ctx,base,ctx.r3.u32);
}
REX_EXTERN(sub_836D17A8) {
  const auto state=ctx.r3.u32,player=Read(base,state+4);
  if(!TackleIndex(base,player)) {__imp__sub_836D17A8(ctx,base);return;}
  const ReplayScope replay(!LocalPlayer(base,player));
  UpdateTackle(ctx,base,state);
}
REX_EXTERN(sub_836D18B8) {
  const auto player=Read(base,ctx.r3.u32+4);
  if(player) {Write(base,player+kTackle,0);Write(base,player+kTackle+12,0);}
  __imp__sub_836D18B8(ctx,base);
}

REX_EXTERN(sub_836D0000) {
  const uint32_t alloc=ctx.r3.u32;
  Write(base,0x836F1330,alloc); Write(base,0x836F1334,ctx.r4.u32);
  if (!alloc) { ctx.r3.u64=0; return; }
  ctx.r3.u64=kSize;
  REX_CALL_INDIRECT_FUNC(alloc);
  if (!ctx.r3.u32) return;
  const auto player=ctx.r3.u32;
  __imp__sub_836D1948(ctx,base);
  Save(base,player,{}); ResetSummon(base,player); ResetProgress(base,player); InitSounds(base,player);
  ResetProjectiles(base,player); ResetNet(base,player);
  Write(base,player,kVtable);
  ctx.r3.u64=player;
}

// Natural MP regeneration is stats +0x2C (MP per second), which this native
// init sets from the module constant 836C1DCC (1.0, Simon's rate). Nathan
// regenerates like Yoko and Charlotte: the base is raised by the difference,
// so any equipment bonus already in the field is kept.
constexpr uint32_t kNativeMpRegen=0x836C1DCC;
REX_EXTERN(sub_836D00F8) {
  const auto regen_player=ctx.r3.u32;
  InitSounds(base,ctx.r3.u32);
  ResetSummon(base,ctx.r3.u32);
  ResetProjectiles(base,ctx.r3.u32);
  Save(base,ctx.r3.u32,{}); // each level/life starts with DSS disabled
  ResetNet(base,ctx.r3.u32); // and with nothing announced or replayed
  Write(base,ctx.r3.u32+kTackleGranted,0); // grant check once per level (GrantTackle)
  __imp__sub_836D00F8(ctx,base);
  const auto stats=Read(base,regen_player+88);
  if(stats) Float(base,stats+0x2C,Float(base,stats+0x2C)+kMpRegenPerSecond-Float(base,kNativeMpRegen));
}

REX_EXTERN(sub_836D11B8) {
  const auto player=ctx.r3.u32, table=ctx.r4.u32;
  __imp__sub_836D11B8(ctx,base);
  auto s=Load(base,player); s.motion_table=table; Save(base,player,s);
  Animations(base,s); // caller owns a persistent per-player copy at entity+0x74
}

REX_EXTERN(sub_836D1FC8) {
  const auto player=ctx.r3.u32, stats=Read(base,player+88);
  // The local Nathan reads its buttons, pays and announces; a copy of another
  // machine's Nathan replays what that machine announced (ReplayScope: no MP,
  // no self-heal; no save access at all).
  const bool local=LocalPlayer(base,player);
  const ReplayScope replay(!local);
  if(local) {PPCContext grant=ctx;GrantTackle(grant,base,player);}
  const auto standing=Read(base,player+0x60);
  const auto input=local && standing ? Read(base,standing+12) : 0;
  uint32_t held=input ? Read(base,input) : 0;
  uint32_t pressed=input ? Read(base,input+4) : 0;
  const float frame_dt=Float(base,player+564);
  auto s=Load(base,player);
  const bool was_enabled=s.enabled;
  const auto previous_action=s.action,previous_attribute=s.attribute;
  const bool was_casting=s.cast_remaining>0;
  if(!local) {
    const auto net=ReceiveEvents(ctx,base,player);held=net.held;pressed=net.pressed;
    s=Load(base,player);
  }
  bool swapping=false;
  if(local) swapping=CardSwapInput(ctx,base,player,held);
  else {Write(base,player+kSwapHeld,0);Write(base,player+kSwapDirections,0);}
  s.Select(Attribute(base,player),Action(base,player));
  const auto state=Read(base,player+572);
  const bool summon_state=s.action!=kActionUranus || (state>=1 && state<=16);
  const bool direct_edge=local && !swapping && (held&kRb) && !s.previous_rb;
  // A copy's MP is its owner's business: it only turns off when told to.
  s.Frame(local && !swapping && (held&kRb)!=0,Paired(base,player) && summon_state,Alive(base,player),
          local ? (stats ? Float(base,stats+8) : 0) : 1e9f,WhipState(base,player),frame_dt);
  if (local && stats && s.enabled && TimedAction(s.action)) {
    float mp=Float(base,stats+8);
    s.DrainMana(mp,frame_dt);
    Float(base,stats+8,mp);
  }
  if(s.Direct() && direct_edge && Paired(base,player) && Alive(base,player) && !WhipState(base,player) && state>=1 && state<=16 && DirectCast(ctx,base,player,s))
    Announce(ctx,base,player,NetId(kNetCast,s.action,s.attribute));
  const auto motion=Read(base,player+584);
  if (s.Fire() && (motion==191 || motion==192)) {
    s.hold_time+=frame_dt>0 && frame_dt<=.1f ? frame_dt : 1.0f/60;
  } else if(s.action==kActionSaturn && Read(base,player+584)>=191 && WhipState(base,player))s.hold_time+=frame_dt;else s.hold_time=0;
  const bool summon=s.action==kActionUranus && s.enabled;
  const bool casting=s.cast_remaining>0 && (summon || (state>=1 && state<=9));
  const bool started=s.enabled && (!was_enabled || previous_action!=s.action || previous_attribute!=s.attribute);
  if (started && summon && stats) {
    if(local) Float(base,stats+8,std::fmax(0.0f,Float(base,stats+8)-s.Cost()));
    BeginSummon(ctx,base,player,s);
  }
  if (summon) UpdateSummon(ctx,base,player,s);
  const bool thrown=false; // direct casts consume RB only
  if (!swapping) SaturnShot(ctx,base,player,s,pressed,frame_dt);
  Save(base,player,s); Animations(base,s);
  if (started) Sound(ctx,base,player,summon ? 349 : 300);
  if (was_casting!=(s.cast_remaining>0) && state>=1 && state<=9) {
    // Switch only on cast entry/exit; palette pulses never restart clips.
    // The inherited motion setter uses these same two byte flags.
    base[player+7]=1; base[player+8]=1;
  }
  // RB belongs to DSS on Nathan; suppress any inherited personal-skill action.
  if (input) {
    const auto consumed=kRb|kY|(swapping ? kDirections : 0)|(thrown ? kAttackButton : 0);
    auto native_held=casting?0:held&~consumed,native_pressed=casting?0:pressed&~consumed;
    if(!swapping)AdjustDssInput(base,player,s,held,native_held,native_pressed,frame_dt);
    Write(base,input,native_held);Write(base,input+4,native_pressed);
  }
  // Levitation uses dedicated ROM frames. Keep the native update running
  // for damage, status timers and recovery, while anchoring the cast position.
  const float subweapon_mp=stats?Float(base,stats+8):0;
  Write(base,player+kAllState+176,ActivePluto(base,player,5));
  __imp__sub_836D1FC8(ctx,base);
  Write(base,player+kAllState+176,0);
  if(local && !swapping) {
    const auto family=AdditionalSubweapon(ctx,base,player,held,subweapon_mp);
    if(family<7) Announce(ctx,base,player,NetId(kNetSubweapon,0,0,family));
  }
  if (summon && Alive(base,player)) AnchorSummon(base,player);
  ProgressFrame(ctx,base,player,held);
  RefreshWhip(base,player);
  AllDssFrame(ctx,base,player,Load(base,player),swapping?0:held,swapping?0:pressed,frame_dt);
  UpdateProjectiles(ctx,base,player,Load(base,player),frame_dt);
  FrameSounds(ctx,base,player);
  if (input) {
    Write(base,input,held); Write(base,input+4,pressed);
  }
  if(local) AnnounceFrame(ctx,base,player,swapping?0:held,frame_dt);
}

REX_EXTERN(sub_836DBEF8) {
  const auto state=ctx.r3.u32, motion=ctx.r4.u32;
  const auto player=Read(base,state+4);
  // A copy's swings arrive as its owner's Swing events (ReceiveEvents).
  if (player && motion>=187 && motion<=190 && LocalPlayer(base,player)) {
    const bool big=RecordDssSwing(base,player);
    auto s=Load(base,player);
    s.Select(Attribute(base,player),Action(base,player));
    const auto stats=Read(base,player+88);
    float mp=stats ? Float(base,stats+8) : 0;
    bool paid=false;
    if ((s.action!=kActionDiana || ProjectileRoom(base,player)) && s.Swing(Paired(base,player),Alive(base,player),mp)) {
      paid=true;
      Float(base,stats+8,mp);
      SwingProjectile(ctx,base,player,s);
      if (s.action==kActionMercury && s.attribute==8) { // Mercury + Unicorn restores 1% max HP per paid swing.
        const float maxhp=Float(base,stats+16)+Float(base,stats+28);
        SummonHeal(ctx,base,player,std::fmax(1.0f,std::floor(maxhp/100)));
      }
    }
    Save(base,player,s); Animations(base,s);
    SwingSound(ctx,base,player);
    if(s.enabled && s.attribute<10) Announce(ctx,base,player,NetId(kNetSwing,s.action,s.attribute,(paid?1:0)|(big?2:0)));
  }
  // Motions 191/192 are held rotations: no per-frame/per-hit mana charge.
  __imp__sub_836DBEF8(ctx,base);
}

// The only two native readers of the boots speed fields. D7C50 reaches C9A0
// through its own update, so the scope must stay safe when nested.
REX_EXTERN(sub_836DC9A0) {
  const DssSpeedScope speed(base,ctx.r3.u32);
  __imp__sub_836DC9A0(ctx,base);
}
REX_EXTERN(sub_836D7C50) {
  const DssSpeedScope speed(base,ctx.r3.u32);
  __imp__sub_836D7C50(ctx,base);
}

REX_EXTERN(sub_836D3670) {
  const auto player=ctx.r3.u32;
  __imp__sub_836D3670(ctx,base); // STR, including the original game's buffs
  const auto s=Load(base,player);
  if ((s.action==kActionMercury || s.action==kActionVenus) && ActiveDss(base,player,s) && Alive(base,player)) {
    // Venus STR is a stat boost (bonus part grows); the Mercury whip is
    // combo damage (whole multiplier grows with the pair level).
    ctx.f1.f64=s.action==kActionVenus
      ? std::floor(ctx.f1.f64*PairPercent(base,player,kVenusStrength[s.attribute])/100.0)
      : double(float(ctx.f1.f64*s.Strength()*PairDamage(base,player)));
  }
}

REX_EXTERN(sub_836D36B8) {
  const auto player=ctx.r3.u32;
  __imp__sub_836D36B8(ctx,base); // INT with equipment and native buffs
  const auto s=Load(base,player);
  if (ActiveVenus(base,player,s) && s.attribute==6) ctx.f1.f64=std::floor(ctx.f1.f64*PairBonus(base,player,1.25f));
}

REX_EXTERN(sub_836D3790) {
  const auto player=ctx.r3.u32;
  __imp__sub_836D3790(ctx,base); // LCK feeds the normal item-drop calculation
  const auto s=Load(base,player);
  if (ActiveVenus(base,player,s) && s.attribute==2) ctx.f1.f64=std::floor(ctx.f1.f64*PairBonus(base,player,1.25f));
}


// Bank paths live in Nathan's allocated player extension. Guest module data
// is read-only; the loader can retain either path safely for async loading.
REX_EXTERN(sub_836D1358) {
  ctx.r3.u64=ctx.r3.u32+(ctx.r4.u8 ? 984 : 952);
}
// Damage/death voice events are emitted once from the actual HP transition.
// Suppress the inherited Simon voice callback to avoid a second character.
REX_EXTERN(sub_836D1378) { ctx.r3.u64=0; }
