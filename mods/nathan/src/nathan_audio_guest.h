#pragma once
#include "nathan_dss_guest.h"
#include <cstdio>
#include <cstring>

namespace harmony::nathan {
constexpr uint32_t kAudioState=884, kAudioBytes=68;
inline void InitSounds(uint8_t* base,uint32_t player) {
  std::memset(base+player+kAudioState,0,kAudioBytes);
  Write(base,player+1024,0);Write(base,player+1028,0);
  std::memset(base+player+1032,0,24);
  std::memset(base+player+1060,0,28); // DEF, selected palette and effect diagnostics
  std::memcpy(base+player+952,"\\data\\sound\\VX_NATHN",21);
  std::memcpy(base+player+984,"\\data\\sound\\VXJ_NATHN",22);
}
inline bool AirState(uint32_t state) { return state>=11 && state<=16; }
inline void Sound(PPCContext& ctx,uint8_t* base,uint32_t player,unsigned id) {
  const auto owner=Owner(base,player);
  if (!owner) return;
  const auto state=player+kAudioState, name=state+32;
  std::snprintf(reinterpret_cast<char*>(base+name),32,"VX_NAT_S%03u",id);
  PPCContext audio_ctx=ctx; // guest audio call must not clobber the player call
  audio_ctx.r3.u64=name;
  audio_ctx.r4.s64=int32_t(Float(base,owner+0x8EC));
  audio_ctx.r5.s64=int32_t(Float(base,owner+0x8F0));
  audio_ctx.r6.u64=1;
  auto& audio_context=audio_ctx;
  // The existing game helper handles cue lookup, language, position, category
  // volume and voice lifetime. Keep all audio in the normal game mixer.
  rex::runtime::ResolveIndirectFunction(0x82239218)(audio_context,base);
  Write(base,state+20,id);Write(base,state+24,Read(base,state+24)+1);
  Write(base,state+28,audio_ctx.r3.u32);
}
inline void SwingSound(PPCContext& ctx,uint8_t* base,uint32_t player) {
  // CotM's 0806DE0C table has three grunts, each with two silent choices.
  const auto at=player+kAudioState+16;
  const auto count=Read(base,at);Write(base,at,count+1);
  if (count%3==0) Sound(ctx,base,player,418+(count/3)%3);
}
inline void FrameSounds(PPCContext& ctx,uint8_t* base,uint32_t player) {
  const auto at=player+kAudioState,stats=Read(base,player+88);
  const auto state=Read(base,player+572),motion=Read(base,player+584);
  const auto hp=stats ? Float(base,stats+4) : 0;
  const auto old_motion=Read(base,at), old_state=Read(base,at+4);
  const auto old_hp=Float(base,at+8);
  const bool ready=Read(base,at+12)!=0;
  Write(base,at,motion);Write(base,at+4,state);Float(base,at+8,hp);Write(base,at+12,1);
  if (!ready) return;
  if (hp<=0 && old_hp>0) { Sound(ctx,base,player,106);return; }
  if (hp<old_hp && hp>0) {
    // CotM's impact SFX 104 is separate from Nathan's knockback voice.
    // 0806C1BC/0806C298 call 0806DE38 -> table 080E0ADA {421,422}.
    const auto count=Read(base,player+1048);Write(base,player+1048,count+1);
    Sound(ctx,base,player,421+count%2);
  }
  if (hp<=0) return;
  if (state!=old_state && state==11 && !AirState(old_state)) Sound(ctx,base,player,101);
  else if (state!=old_state && state==12) Sound(ctx,base,player,102);
  else if (AirState(old_state) && ((state>=1 && state<=9)||state==23||state==24)) Sound(ctx,base,player,103);
  // CotM 08064396..080643BA repeats sound 108 every eight game ticks.
  // Use elapsed time, so held spins never queue a sound on every render frame.
  float spin_time=Float(base,player+948);
  if ((state==23 || state==24) && (motion==191 || motion==192)) {
    if (motion!=old_motion) spin_time=0;
    float dt=Float(base,player+564);
    if (!(dt>0 && dt<=0.1f)) dt=1.0f/60;
    spin_time-=dt;
    if (spin_time<=0) { Sound(ctx,base,player,108);spin_time+=8.0f/kCotmHz; }
  } else spin_time=0;
  Float(base,player+948,spin_time);
  if (motion!=old_motion && motion<268) {
    const auto slot=Read(base,0x836C1DD0+motion*8);
    if (slot==7) Sound(ctx,base,player,120);
    else if (slot==24) Sound(ctx,base,player,105);
  }
}
}
