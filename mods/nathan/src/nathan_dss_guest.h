#pragma once
#include "nathan_dss_state.h"
#include <bit>
#include <algorithm>
#include <cstring>
#include <rex/memory/utils.h>

namespace harmony::nathan {
inline uint32_t Read(uint8_t* base, uint32_t address) {
  return rex::memory::load_and_swap<uint32_t>(base + address);
}
inline void Write(uint8_t* base, uint32_t address, uint32_t value) {
  rex::memory::store_and_swap<uint32_t>(base + address, value);
}
inline float Float(uint8_t* base, uint32_t address) {
  return std::bit_cast<float>(Read(base, address));
}
inline void Float(uint8_t* base, uint32_t address, float value) {
  Write(base, address, std::bit_cast<uint32_t>(value));
}
inline DssState Load(uint8_t* base, uint32_t player) {
  const uint32_t p = player + kOriginalSize;
  return {Read(base,p),Read(base,p+4),Read(base,p+8),Read(base,p+12),Float(base,p+16),Float(base,p+20),Float(base,p+24),Read(base,p+28),Read(base,p+32),Read(base,p+36),Read(base,player+1016),Float(base,player+1020),Read(base,player+1056)};
}
inline void Save(uint8_t* base, uint32_t player, const DssState& s) {
  const uint32_t p = player + kOriginalSize;
  Write(base,p,s.enabled); Write(base,p+4,s.previous_rb); Write(base,p+8,s.motion_table);
  Write(base,p+12,s.paid_swing); Float(base,p+16,s.pulse_time); Float(base,p+20,s.cast_remaining); Float(base,p+24,s.fade_remaining);
  Write(base,p+28,s.drawn_frame); Write(base,p+32,s.canonical_frame); Write(base,p+36,s.draw_count);
  Write(base,player+1016,s.attribute); Float(base,player+1020,s.hold_time);
  Write(base,player+1056,s.action);
}
inline uint32_t Entity(uint8_t* base, uint32_t handle) {
  const auto manager = Read(base,0x8291D9F0);
  if (!manager || !handle) return 0;
  const auto table = Read(base,manager+0xAC);
  if (!table) return 0;
  const auto entry = table + ((handle & 0xFFFF) << 4);
  return Read(base,entry)==handle ? Read(base,entry+4) : 0;
}
// Entity handles can resolve to enemies, hazards, or players. The component
// at +0x924 belongs only to entities with the native player type flag. Check
// that flag before even reading the component slot (other objects may be smaller).
inline uint32_t PlayerComponent(uint8_t* base, uint32_t owner) {
  return owner && (Read(base,owner+8)&2) ? Read(base,owner+0x924) : 0;
}
inline uint32_t Owner(uint8_t* base, uint32_t player) {
  // player+60 is a context/player index (1 in the verified live object),
  // not an entity handle. The motion-table callback receives owner+0x74.
  const auto table = Read(base,player+kOriginalSize+8);
  if (table<0x74) return 0;
  const auto owner = table-0x74;
  return owner && PlayerComponent(base,owner)==player ? owner : 0;
}
// Online co-op (modding/docs/NATHAN_LESSONS_FROM_SHIELD_ROD.md). Each machine
// simulates its own player; every other player is a copy rebuilt from HoD's
// snapshots. Owner +0x930 is the control type: 1 = this machine's player.
// The local Nathan alone reads buttons, pays MP, heals himself and writes the
// save; it announces what it does as native replicate-only spawn events
// (8244CA98 kind 11 / sub 1, r9/r10 "NA" "TH", the event in the 16-bit id).
// Every other machine queues them on its copy of that Nathan (kNet) and the
// copy replays them with no MP, no self-heal and no save writes. Its attack
// areas belong to the remote owner, so HoD shows their hits and numbers there
// and applies the damage only on the caster's machine.
inline bool LocalPlayer(uint8_t* base,uint32_t player) {
  const auto owner=Owner(base,player);
  return !owner || Read(base,owner+0x930)==1;
}
// Set while a copy replays: SpendMp succeeds without paying, self-heals and
// self-damage do nothing. Per thread, nested scopes keep the outer value.
inline thread_local bool replaying=false;
struct ReplayScope {
  bool previous;
  explicit ReplayScope(bool on):previous(replaying){replaying=previous||on;}
  ~ReplayScope(){replaying=previous;}
  ReplayScope(const ReplayScope&)=delete;
  ReplayScope& operator=(const ReplayScope&)=delete;
};
// Player extension block: +0 events written, +4 events read, +8 sixteen queued
// ids; copy side +72 action, +76 attribute, +80 pair level, +84 attack held,
// +88 attack press pending; owner side +92 last announced state, +96 resend
// timer, +100 attack held as last announced.
constexpr uint32_t kNet=7744,kNetBytes=104,kNetQueue=16;
constexpr uint32_t kNetTagA=0x4E41,kNetTagB=0x5448;  // "NA" "TH"
// Event id: type << 12 | a << 8 | b << 4 | c (four bits each).
//   On: a action, b attribute, c pair level   Off   Cast: a action, b attribute
//   Swing: a action, b attribute, c 1 paid | 2 big bone   Attack: c 1 held
//   Subweapon: c crash family of the extra subweapon (Pluto + Serpent)
constexpr uint32_t kNetOn=1,kNetOff=2,kNetCast=3,kNetSwing=4,kNetAttack=5,kNetSubweapon=6;
constexpr uint32_t NetId(uint32_t type,uint32_t a=0,uint32_t b=0,uint32_t c=0) {return (type&15)<<12|(a&15)<<8|(b&15)<<4|(c&15);}
inline void ResetNet(uint8_t* base,uint32_t player) {
  std::memset(base+player+kNet,0,kNetBytes);
  Write(base,player+kNet+72,kActionUnavailable);Write(base,player+kNet+76,10);Float(base,player+kNet+80,1);
}
inline void NetEnqueue(uint8_t* base,uint32_t player,uint32_t id) {
  const auto written=Read(base,player+kNet),read=Read(base,player+kNet+4);
  if(written-read>=kNetQueue) Write(base,player+kNet+4,written-kNetQueue+1);  // full: drop the oldest
  Write(base,player+kNet+8+(written%kNetQueue)*4,id&0xFFFF);Write(base,player+kNet,written+1);
}
inline uint32_t Action(uint8_t* base,uint32_t player) {
  // A copy's equipment is not kept in step with Card Swap: it uses the pair
  // its owner announced.
  if(!LocalPlayer(base,player)) return Read(base,player+kNet+72);
  const auto owner=Owner(base,player);
  const auto equipment=owner ? Read(base,owner+0x9C8) : 0;
  if (!equipment || Read(base,equipment)!=kWhip) return kActionUnavailable;
  const auto card=Read(base,equipment+48);
  return card==kMercury ? kActionMercury : card==kVenus ? kActionVenus : card==0x6E0 ? kActionUranus : card==0x6DA ? kActionJupiter : card==0x6E1 ? kActionPluto : card==0x6DC ? kActionDiana : card==0x6DD ? kActionApollo : card==0x6DF ? kActionSaturn : card==0x6DB ? kActionMars : card==0x6DE ? kActionNeptune : kActionUnavailable;
}
inline uint32_t Attribute(uint8_t* base,uint32_t player) {
  const auto action=Action(base,player);
  if (action==kActionUnavailable) return 10;
  if(!LocalPlayer(base,player)) {const auto a=Read(base,player+kNet+76);return a<10?a:10;}
  const auto equipment=Read(base,Owner(base,player)+0x9C8);
  const auto card=Read(base,equipment+52);
  const auto attribute=card>=kSalamander && card<kSalamander+10 ? card-kSalamander : 10;
  return attribute;
}
inline bool Paired(uint8_t* base, uint32_t player) { return Attribute(base,player)<10; }
inline bool ActiveDss(uint8_t* base,uint32_t player,const DssState& s) {
  return s.enabled && s.action==Action(base,player) && s.attribute<10 && s.attribute==Attribute(base,player);
}
inline bool ActivePair(uint8_t* base,uint32_t player,const DssState& s) {
  return ActiveDss(base,player,s) && s.Fire();
}
inline bool Alive(uint8_t* base, uint32_t player) {
  const auto stats = Read(base,player+88);
  return stats && Float(base,stats+4)>0 && Read(base,stats+308)==0;
}
inline bool ActiveVenus(uint8_t* base,uint32_t player,const DssState& s) {
  return s.action==kActionVenus && ActiveDss(base,player,s) && Alive(base,player);
}
inline bool WhipState(uint8_t* base, uint32_t player) {
  const auto state = Read(base,player+572);
  const auto motion = Read(base,player+584);
  // A jumping whip runs inside jump/fall states 11..16, not only the
  // dedicated grounded attack states 23..25. Keep its paid swing through
  // takeoff, falling and landing until the whip motion actually ends.
  // Shared attack code also resets kind +608 to 6 during a live paid swing.
  const bool attack_state=(state>=23 && state<=25) || (state>=11 && state<=16);
  return attack_state && motion>=187 && motion<=192;
}
inline void RefreshWhip(uint8_t* base,uint32_t player) {
  const auto owner=Owner(base,player);
  const auto equipment=owner ? Read(base,owner+0x9C8) : 0;
  const auto weapon=equipment ? Entity(base,Read(base,equipment+0x50)) : 0;
  if (!weapon || Read(base,weapon+0x88)!=0x91 || Read(base,weapon+0x8C)!=1) return;
  const auto begin=Read(base,weapon+60),end=Read(base,weapon+64);
  if (!begin || end-begin<4) return;
  const auto hit=Read(base,begin);
  if (!hit) return;
  const auto s=Load(base,player);
  if (Read(base,player+1024)) {
    Write(base,hit+176,Read(base,player+1024)|
      (ActivePair(base,player,s) && Alive(base,player) ? s.Element() : 0));
  }
  const auto damage=Read(base,player+1028);
  if (damage && ActivePair(base,player,s)) {
    float scale=1;
    if (s.hold_time>0 && s.attribute==6) scale=.63f;
    if (s.hold_time>0 && s.attribute==7) scale=.01f;
    Write(base,hit+364,std::max(1u,uint32_t(float(damage)*scale)));
  }
}
inline void Animations(uint8_t* base, const DssState& s) {
  if (!s.motion_table) return;
  const bool fire=s.Fire();
  for (uint32_t motion=0; motion<268; ++motion) {
    uint32_t slot=Read(base,0x836C1DD0+motion*8); // immutable original motion table
    if (motion>=187 && motion<=192) {
      const uint32_t normal = motion==188 ? 17 : motion==191 ? 28 : motion==192 ? 29 : 16;
      const uint32_t flame = motion==188 ? 32 : motion==191 ? 33 : motion==192 ? 34 : 31;
      slot=fire ? kMercurySlots[s.attribute<10?s.attribute:0][motion-187] : normal;
    }
    if(s.action==kActionDiana && s.attribute==5 && s.enabled && s.paid_swing && motion>=187 && motion<=192)slot=kMercurySlots[5][motion-187];
    if(s.action==kActionMars && s.enabled && s.paid_swing && motion>=187 && motion<=190) slot=kAllMarsSlots[s.attribute<10?s.attribute:0][motion==188?1:motion==189?2:0];
    if (s.action==kActionMars && s.enabled && motion>=191 && motion<=192) slot=motion==192?2:0;
    if (s.action!=kActionUranus && s.cast_remaining>0 && slot<=3) slot=kCastSlot;
    if (motion==193) slot=26; // Tackle Martial Art (kTackleMotion -> kTackleSlot, nathan_tackle_guest.h)
    Write(base,s.motion_table+motion*8,slot);
  }
}
// Pair level follows HoD's per-skill rule: copies count up to 9. A combo's
// level is the average of its two cards, refreshed by ProgressFrame each
// update and kept in the progress block (zero before the first update).
constexpr unsigned kPairLevel=1580,kCardCopyCap=9;
inline unsigned CardCopies(uint8_t* base,uint32_t save,uint32_t item) {
  return save && item<0x208B ? std::min(kCardCopyCap,unsigned(base[save+0x3E8+item]>>4)) : 0;
}
inline float PairLevelFor(unsigned action_copies,unsigned attribute_copies) {
  return std::clamp((std::min(action_copies,kCardCopyCap)+std::min(attribute_copies,kCardCopyCap))*.5f,1.0f,float(kCardCopyCap));
}
inline float PairLevel(uint8_t* base,uint32_t player) {
  const float level=Float(base,player+kPairLevel);
  return level>=1 && level<=kCardCopyCap ? level : 1;
}
// Linear from 1 at level 1 to at_max at level 9, like native L1..Lmax rows.
inline float PairGrowth(uint8_t* base,uint32_t player,float at_max) {
  return 1+(at_max-1)*(PairLevel(base,player)-1)/(kCardCopyCap-1);
}
inline float PairDamage(uint8_t* base,uint32_t player) {return PairGrowth(base,player,kPairDamageAtMax);}
inline float PairHealing(uint8_t* base,uint32_t player) {return PairGrowth(base,player,kPairHealingAtMax);}
// Only the bonus part of a stat multiplier grows; penalties stay fixed.
inline float PairBonus(uint8_t* base,uint32_t player,float multiplier) {
  return multiplier>1 ? 1+(multiplier-1)*PairGrowth(base,player,kPairBonusAtMax) : multiplier;
}
// Integer-percent form, so callers can keep the exact x*percent/100 order.
inline double PairPercent(uint8_t* base,uint32_t player,unsigned percent) {
  return percent>100 ? 100+(percent-100)*double(PairGrowth(base,player,kPairBonusAtMax)) : percent;
}
}
