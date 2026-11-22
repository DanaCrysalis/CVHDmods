#pragma once
#include "nathan_dss_guest.h"
#include "nathan_card_swap_assets.h"
#include <vector>
#include <cstring>
namespace harmony::nathan {
constexpr uint32_t kCardSwap=0xC5,kY=0x40,kDirections=0xF;
constexpr unsigned kYEquipmentSlot=1,kBEquipmentSlot=8;
constexpr uint32_t kSwapHeld=1032,kSwapDirections=1036,kSwapCount=1040,kSwapLast=1044,kCardDrawCount=1052;
constexpr uint32_t kCardSprite=1088,kCardSpriteBytes=192;
inline uint32_t NativeQuery(PPCContext& ctx,uint8_t* base,uint32_t function,uint32_t arg,uint32_t arg2=0) {
  PPCContext query=ctx;query.r3.u64=arg;query.r4.u64=arg2;
  rex::runtime::ResolveIndirectFunction(function)(query,base);
  return query.r3.u32;
}
inline uint32_t Inventory(PPCContext& ctx,uint8_t* base) {
  // 823CAC80: GameData +1018 is the native 3B00 save model; its +3E8
  // inventory bytes store owned quantity in the upper nibble.
  const auto game=NativeQuery(ctx,base,0x82223348,0);
  return game ? game+0x1018 : 0;
}
inline bool Owned(uint8_t* base,uint32_t save,uint32_t item) {
  return save && item<0x208B && (base[save+0x3E8+item]>>4)!=0;
}
inline uint32_t CycleCard(PPCContext& ctx,uint8_t* base,uint32_t save,uint32_t current,unsigned slot,int direction) {
  std::vector<uint32_t> cards;
  for (uint32_t index=0;index<200;++index) {
    const auto item=0x673+index;
    if (!Owned(base,save,item)) continue;
    // Use the same classifier and character permission check as equipment.
    // Future owned Action/Attribute cards therefore join the cycle naturally.
    if (!NativeQuery(ctx,base,0x823C98B0,item,12)) continue;
    if (NativeQuery(ctx,base,0x823C96C8,item)!=slot) continue;
    cards.push_back(item);
  }
  if (cards.empty()) return current;
  const auto at=std::find(cards.begin(),cards.end(),current);
  if (at==cards.end()) return direction>0 ? cards.front() : cards.back();
  const auto index=int(at-cards.begin());
  return cards[(index+direction+int(cards.size()))%int(cards.size())];
}
inline void EquipCard(uint8_t* base,uint32_t player,uint32_t equipment,uint32_t save,unsigned slot,uint32_t item) {
  if (Read(base,equipment+slot*4)==item) return;
  Write(base,equipment+slot*4,item);
  // Persist through the game's own in-memory loadout/save model. File I/O
  // remains with the game's normal save flow, never an external live edit.
  if (save) Write(base,save+0x28+11*15*4+slot*4,item);
  Write(base,player+kSwapCount,Read(base,player+kSwapCount)+1);
  Write(base,player+kSwapLast,item);
}
inline bool CardSwapInput(PPCContext& ctx,uint8_t* base,uint32_t player,uint32_t held) {
  const auto owner=Owner(base,player);
  const auto equipment=owner ? Read(base,owner+0x9C8) : 0;
  if (!equipment) {Write(base,player+kSwapHeld,0);Write(base,player+kSwapDirections,0);return false;}
  // Definition disables changing this slot; enforce its invariant for old
  // saves and runtime loadouts as well, just as the fixed Hunter Whip.
  // Slots 8..11 are B, Up+B, Right+B and Down+B. Remove only the
  // obsolete SOUL item placed there by the previous builds.
  constexpr uint32_t defaults[4]={0x614,0x610,0x612,0x611};
  for (unsigned i=0;i<4;++i) {
    const auto slot=8+i;
    if (Read(base,equipment+slot*4)==0x6D8)
      EquipCard(base,player,equipment,Inventory(ctx,base),slot,defaults[i]);
  }
  if (Read(base,equipment+kYEquipmentSlot*4)!=kCardSwap)
    EquipCard(base,player,equipment,Inventory(ctx,base),kYEquipmentSlot,kCardSwap);
  const bool show=(held&kY) && Alive(base,player);
  Write(base,player+kSwapHeld,show);
  const auto dirs=show ? held&kDirections : 0;
  const auto edge=dirs&~Read(base,player+kSwapDirections);
  Write(base,player+kSwapDirections,dirs);
  if (!show || !edge) return show;
  const auto save=Inventory(ctx,base);
  if (!save) return show;
  const int horizontal=(dirs&3)==3 ? 0 : (edge&2 ? 1 : 0)-(edge&1 ? 1 : 0);
  const int vertical=(dirs&12)==12 ? 0 : (edge&8 ? 1 : 0)-(edge&4 ? 1 : 0);
  if (horizontal) EquipCard(base,player,equipment,save,12,
    CycleCard(ctx,base,save,Read(base,equipment+48),12,horizontal));
  if (vertical) EquipCard(base,player,equipment,save,13,
    CycleCard(ctx,base,save,Read(base,equipment+52),13,vertical));
  return show;
}
// CotM ROM illustration order: ten Action Cards, then ten Attribute Cards.
// Each illustration has a left (even) and right (odd) placement frame.
inline uint32_t CardArt(uint32_t item,bool attribute) {
  if (attribute && item>=kSalamander && item<kSalamander+10)
    return kCardArtFirst+20+2*(item-kSalamander)+1;
  if (!attribute && item==kMercury) return kCardArtFirst;
  if (!attribute && item>=kVenus && item<kVenus+9)
    return kCardArtFirst+2+2*(item-kVenus);
  return 0;
}
}
