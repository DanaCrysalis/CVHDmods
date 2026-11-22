#pragma once
// Nathan's Martial Art: Tackle.
//
// Input and dispatch are native. Simon's module registers one command
// (down, down-forward, forward + attack; pattern 836C2630, handler state 37).
// The shared matcher (82449A40) asks player vtable entry 268 what the
// command is; Simon answers "weapon skill" (type 9), which fired his VK shot.
// Nathan answers "Martial Art" (type 10) with his own row, global Martial Art
// kTackleArt (martialartsset_dlc17.dat, built by nathan_cards.py), so the
// game reads its MP cost from that row and lists it under Martial Arts.
// Entry 89 then stores the row index at player+0x16C and requests state 37,
// whose enter/update/exit are taken over here for that index only.
//
// The dash: Nathan's CotM tackle animation (body slot kTackleSlot via motion
// kTackleMotion) and the slide's own physics fields (movement object +0x150
// velocity X, +0x158 acceleration X, walk speed +0x13C with boots +0x18C), so
// walls stop him as they stop a slide. He passes through enemies like any
// HoD player. One native attack area per tackle follows him during the dash
// (nathan_dss_damage.cpp re-submits it each frame, like the whip's own hit
// object); his normal hurtbox is untouched, so an enemy the tackle does not
// kill first can still hurt him.
#include "nathan_tackle_assets.h"
#include "nathan_tackle_state.h"
#include "nathan_dss_balance.h"
namespace harmony::nathan {
constexpr uint32_t kMartialArtType=10,kTackleCommand=0;
constexpr float kTackleBrakeWalks=6;  // the slide's own deceleration (836C1D74)

// The Martial Arts menu lists owned Martial Art items. In a level the pause
// menu reads the actor's own item lists (owner+0x9CC, 823E81D4), which
// 82458FE0 fills from the save when the actor is created (82459288 walks
// items 0x8AD + index and adds owned ones through 82459868). Nathan knows the
// Tackle from the start: on his first update in a level, give the save one
// copy if it has none, and add it to that level's actor lists the same way.
// The row's mask keeps it Nathan-only.
constexpr uint32_t kTackleItem=0x8AD+kTackleArt;
constexpr unsigned kTackleGranted=kTackle+16;
// Nathan's starting items (decided November 12): one Mercury and one
// Salamander (his starting equipment), the locked Card Swap on Y, and the
// Tackle. The definition only equips the cards; Card Swap cycles through
// owned cards, so an unowned starter would be lost on the first swap. Each is
// made owned (count 1) only when the save has none; collected copies are
// never changed.
constexpr uint32_t kStartingItems[]={kMercury,kSalamander,kCardSwap,kTackleItem};
inline void GrantOwned(PPCContext& ctx,uint8_t* base,uint32_t save,uint32_t owner,uint32_t item) {
  // Low nibble bit 0 is "acquired": the Martial Arts list (823FCB38) shows
  // only items with it; the game's own entries carry 0x3 (like the cards).
  const auto at=save+0x3E8+item;const uint8_t was=base[at];
  const uint8_t want=uint8_t((was>>4 ? was&0xF0 : 0x10)|(was&0x0F)|3);
  if(was==want) return;
  base[at]=want;
  if(was>>4) return;   // already counted in the lists built from the save
  if(const auto lists=Read(base,owner+0x9CC)) {
    PPCContext add=ctx;add.r3.u64=lists;add.r4.u64=item;add.r5.u64=1;
    rex::runtime::ResolveIndirectFunction(0x82459868)(add,base);
  }
}
inline void GrantTackle(PPCContext& ctx,uint8_t* base,uint32_t player) {
  if(Read(base,player+kTackleGranted)) return;
  const auto save=Inventory(ctx,base),owner=Owner(base,player);
  if(!save || !owner) return;
  Write(base,player+kTackleGranted,1);
  for(const auto item:kStartingItems) GrantOwned(ctx,base,save,owner,item);
}
inline bool TackleIndex(uint8_t* base,uint32_t player) {return player && Read(base,player+0x16C)==kTackleArt;}
inline float TackleWalkSpeed(uint8_t* base,uint32_t movement) {
  return Float(base,movement+0x13C)*(1+Float(base,movement+0x18C)*.01f);
}
inline void TackleVelocity(uint8_t* base,uint32_t movement,float vx) {
  Float(base,movement+0x150,vx);Float(base,movement+0x158,0);
}
// The generic command state's own way out (Simon's state 37 does the same):
// stop, then the state's vtable entry 4 returns the player to neutral.
inline void EndTackle(PPCContext& ctx,uint8_t* base,uint32_t state) {
  const auto player=Read(base,state+4),movement=Read(base,state+8);
  if(movement) TackleVelocity(base,movement,0);
  if(player) {Write(base,player+kTackle,0);Write(base,player+kTackle+12,0);}
  PPCContext call=ctx;call.r3.u64=state;
  rex::runtime::ResolveIndirectFunction(Read(base,Read(base,state)+0x10))(call,base);
}
inline void BeginTackle(PPCContext& ctx,uint8_t* base,uint32_t state) {
  const auto player=Read(base,state+4),movement=Read(base,state+8),owner=Owner(base,player);
  Write(base,player+0x134,0);
  if(movement) TackleVelocity(base,movement,0);
  Write(base,player+kTackle+12,0);
  // The matcher passes the row's MP cost (player+0x178); nothing native pays it.
  const float cost=Float(base,player+0x178);
  if(!SpendMp(base,player,cost>0 ? cost : kTackleMp)) {Write(base,player+kTackle,2);return;}
  Write(base,player+0x248,kTackleMotion);base[player+7]=1;base[player+8]=1;
  Write(base,player+kTackle,1);
  Write(base,player+kTackle+4,Read(base,player+kTackle+4)+1);
  // Native facing, as the slide reads it (vtable +0x288 = player+0x250; 1 = left).
  // The body sprite's mirror flag is not yet current on the command frame.
  (void)owner;Float(base,player+kTackle+8,Read(base,player+0x250)==1 ? -1.0f : 1.0f);
  Sound(ctx,base,player,105); // CotM dash
}
// Returns false when the tackle ended this frame.
inline bool UpdateTackle(PPCContext& ctx,uint8_t* base,uint32_t state) {
  const auto player=Read(base,state+4),movement=Read(base,state+8),owner=Owner(base,player);
  if(Read(base,player+kTackle)!=1 || !movement || !owner) {EndTackle(ctx,base,state);return false;}
  // Native interrupts first (damage, losing the ground), as the slide does.
  PPCContext check=ctx;check.r3.u64=state;sub_836DC760(check,base);
  if(check.r3.u8) {EndTackle(ctx,base,state);return false;}
  check=ctx;check.r3.u64=state;sub_836DC8B0(check,base);
  if(check.r3.u8) {EndTackle(ctx,base,state);return false;}
  const float t=Float(base,player+0x238),dt=Float(base,player+0x234),dir=Float(base,player+kTackle+8);
  if(t>=kTackleSeconds) {EndTackle(ctx,base,state);return false;}
  const float walk=TackleWalkSpeed(base,movement);
  const bool dashing=t>=kTackleWindupSeconds && t<kTackleWindupSeconds+kTackleDashSeconds;
  if(t<kTackleWindupSeconds) TackleVelocity(base,movement,0);
  else if(dashing) TackleVelocity(base,movement,dir*walk*kTackleSpeedWalks);
  else {
    const float step=kTackleBrakeWalks*walk*(dt>0 && dt<=.1f ? dt : 1.0f/60);
    TackleVelocity(base,movement,dir*std::fmax(0.0f,std::fabs(Float(base,movement+0x150))-step));
  }
  if(dashing && !Read(base,player+kTackle+12)) {
    // One attack area for the whole dash; the collider handler moves it.
    NativeHit(ctx,base,player,Float(base,owner+0x8D4)+dir*kTackleAhead,Float(base,owner+0x8D8)-24,kTackleHalfWidth,kTackleHalfHeight,
              MeleePower(ctx,base,player,kTacklePower),0,10,Read(base,player+kTackle+4),kTackleTag,Read(base,player+kTackle+4));
  }
  Write(base,player+kTackle+12,dashing ? 1 : 0);
  return true;
}
}
