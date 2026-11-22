#pragma once
#include "nathan_card_swap_guest.h"
namespace harmony::nathan {
constexpr unsigned kProgress=1536,kProgressBytes=192,kMasteryCarry=1600;
constexpr unsigned kNathanTimeOffset=0x2474+12*4,kMasteryBase=0x98E*4;
inline void ResetProgress(uint8_t* base,uint32_t player) {std::memset(base+player+kProgress,0,kProgressBytes);}
inline bool ActiveProgress(uint8_t* base,uint32_t player,const DssState& s) {return ActiveDss(base,player,s) && Alive(base,player);}
inline float CardBonus(uint8_t* base,uint32_t player) {return std::min(20u,Read(base,player+1536))*.02f;}
inline float TimeBonus(uint8_t* base,uint32_t player) {return std::min(20u,unsigned(std::max(0.0f,Float(base,player+1540)+Float(base,player+1544))/360))*.01f;}
inline float AttackBonus(uint8_t* base,uint32_t player,const DssState& s) {
  if(!ActiveProgress(base,player,s) || s.attribute!=7) return 1;
  return PairBonus(base,player,s.action==kActionVenus ? 1+CardBonus(base,player) : s.action==kActionPluto ? 1+TimeBonus(base,player) : 1);
}
inline float DssDefense(uint8_t* base,uint32_t player,const DssState& s) {
  if(s.action==kActionVenus) return PairBonus(base,player,s.attribute==3 ? 1+CardBonus(base,player) : s.Defense());
  return PairBonus(base,player,s.action==kActionPluto && s.attribute==4 ? 1+TimeBonus(base,player) : 1);
}
inline bool MovingShield(uint8_t* base,uint32_t player) {
  if(!player || Read(base,player)!=kVtable || !(Read(base,player+1564)&1)) return false;
  const auto s=Load(base,player);const auto state=Read(base,player+0x60),input=state?Read(base,state+12):0;
  const auto horizontal=input ? Read(base,input)&3 : 0;
  return s.action==kActionJupiter && s.attribute==6 && ActiveProgress(base,player,s) && horizontal && horizontal!=3;
}
inline unsigned MasteryOffset(unsigned local) {return kMasteryBase+(11*50+local)*4;}
inline void WalkingMastery(uint8_t* base,uint32_t player,uint32_t save,uint32_t equipment) {
  uint32_t seen[4]={};unsigned count=0;
  for(unsigned slot=8;slot<12;++slot) {
    const auto item=Read(base,equipment+slot*4);
    if(item<0x60F || item>=0x60F+50 || !Owned(base,save,item)) continue;
    bool duplicate=false;for(unsigned i=0;i<count;++i) duplicate|=seen[i]==item;
    if(duplicate) continue;seen[count++]=item;
    const auto address=save+MasteryOffset(item-0x60F);
    Write(base,address,std::min(99999u,Read(base,address)+1));
    Write(base,player+1572,Read(base,player+1572)+1);
  }
}
inline void ProgressFrame(PPCContext& ctx,uint8_t* base,uint32_t player,uint32_t held) {
  const auto owner=Owner(base,player);if(!owner) return;
  // A copy's card counts, playtime and mastery live in its owner's save, not
  // this machine's: it takes the pair level its owner announced.
  if(!LocalPlayer(base,player)) {
    const float level=Float(base,player+kNet+80);
    Float(base,player+kPairLevel,level>=1 && level<=kCardCopyCap ? level : 1);
    return;
  }
  const auto save=Inventory(ctx,base),equipment=Read(base,owner+0x9C8);
  const auto x=Float(base,owner+0x8D4),y=Float(base,owner+0x8D8);
  const auto state=Read(base,player+572),motion=Read(base,player+584);
  float dt=Float(base,player+564);if(!(dt>0 && dt<=.1f)) dt=0;
  const bool initialized=Read(base,player+1576)!=0;
  const float dx=std::abs(x-Float(base,player+1556)),dy=std::abs(y-Float(base,player+1560));
  const bool moving=initialized && Alive(base,player) && (held&3) && (held&3)!=3 && state>=1 && state<=16 && dx>.01f && dx<16 && dy<16;
  const bool walking=moving && state<=9 && motion<268 && Read(base,0x836C1DD0+motion*8)==1;
  Write(base,player+1564,(moving?1:0)|(walking?2:0));
  Float(base,player+1556,x);Float(base,player+1560,y);
  if(!initialized) {Write(base,player+1576,1);Float(base,player+1540,save?float(Read(base,save+kNathanTimeOffset)):0);}
  if(Alive(base,player)) Float(base,player+1544,Float(base,player+1544)+dt);
  // Native playtime can be flushed while a stage is running. Absorb only
  // increases beyond the baseline+elapsed total, never count it twice.
  if(save && float(Read(base,save+kNathanTimeOffset))>Float(base,player+1540)+Float(base,player+1544))
    Float(base,player+1540,float(Read(base,save+kNathanTimeOffset))-Float(base,player+1544));
  unsigned cards=0;if(save) {cards+=Owned(base,save,kMercury);for(unsigned i=0;i<10;++i) cards+=Owned(base,save,kSalamander+i);for(unsigned i=0;i<9;++i) cards+=Owned(base,save,kVenus+i);}
  Write(base,player+1536,cards);
  Float(base,player+kPairLevel,equipment ? PairLevelFor(CardCopies(base,save,Read(base,equipment+48)),CardCopies(base,save,Read(base,equipment+52))) : 1);
  const auto s=Load(base,player);
  if(walking && save && equipment && s.action==kActionVenus && s.attribute==4 && ActiveProgress(base,player,s)) {
    float elapsed=Float(base,player+1548)+dt;
    while(elapsed>=60) {WalkingMastery(base,player,save,equipment);elapsed-=60;}
    Float(base,player+1548,elapsed);
  }
}
}
