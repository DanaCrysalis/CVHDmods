#pragma once
#include "nathan_card_swap_guest.h"
#include "nathan_audio_guest.h"
#include "nathan_uranus_assets.h"
namespace harmony::nathan {
constexpr unsigned kSummonData=1280,kSummonSprite=1344,kSummonSpriteBytes=192;
constexpr float kSummonHalfWidth=160,kSummonHalfHeight=90;
constexpr uint32_t kSummonParticleTag=0x44535355,kSummonContactTag=0x44535343;
constexpr unsigned kSummonContacts=7856,kSummonContactCount=8,kSummonContactBytes=40;
static_assert(kSummonContacts+kSummonContactCount*kSummonContactBytes<=kSize);
inline void ResetSummon(uint8_t* base,uint32_t player) {
  const auto generation=Read(base,player+1308)+1;
  std::memset(base+player+kSummonData,0,64);Write(base,player+1308,generation);
  std::memset(base+player+kSummonContacts,0,kSummonContactCount*kSummonContactBytes);
}
inline bool Summoning(uint8_t* base,uint32_t player,const DssState& s) {
  return s.action==kActionUranus && s.cast_remaining>0 && ActiveDss(base,player,s) && Alive(base,player);
}
inline void BeginSummon(PPCContext&,uint8_t* base,uint32_t player,const DssState&) {
  ResetSummon(base,player);const auto owner=Owner(base,player);
  Float(base,player+1280,Float(base,owner+0x8D4));
  Float(base,player+1284,Float(base,owner+0x8D8));
}
inline void AnchorSummon(uint8_t* base,uint32_t player) {
  const auto owner=Owner(base,player);if (!owner) return;
  Float(base,owner+0x8D4,Float(base,player+1280));
  Float(base,owner+0x8DC,Float(base,player+1280));
  Float(base,owner+0x8EC,Float(base,player+1280));
  Float(base,owner+0x8D8,Float(base,player+1284));
  Float(base,owner+0x8E0,Float(base,player+1284));
  Float(base,owner+0x8F0,Float(base,player+1284));
}
template<size_t N> inline unsigned PoseFrame(const SummonPose (&poses)[N],unsigned tick,bool loop=false) {
  unsigned total=0;for (auto p:poses) total+=p.ticks;
  if (loop && total) tick%=total;
  for (auto p:poses) {if(tick<p.ticks) return p.frame;tick-=p.ticks;}
  return poses[N-1].frame;
}
inline unsigned SummonBody(const DssState& s) {
  const float elapsed=s.pulse_time;
  if (elapsed<.5f) return PoseFrame(kSummonEnter,unsigned(elapsed*kCotmHz));
  if (s.cast_remaining<.5f) return PoseFrame(kSummonExit,unsigned((.5f-s.cast_remaining)*kCotmHz));
  return PoseFrame(kSummonFloat,unsigned((elapsed-.5f)*kCotmHz),true);
}
// Draw-only levitation: combat/anchoring continue using the native owner.
inline float SummonLift(const DssState& s) {
  const float u=std::fmax(0.0f,std::fmin(1.0f,std::fmin(s.pulse_time,s.cast_remaining)/.5f));
  return 60*u*u*(3-2*u);
}
inline unsigned SummonBackdrop(const DssState& s) {
  return s.attribute==8 && s.pulse_time>=.35f && s.pulse_time<5.2f ? kSummonBeamFrame : 0;
}
inline unsigned SummonEffect(const DssState& s) {
  if (s.pulse_time<0 || s.attribute>=10 || s.pulse_time>=kSummonEffectFrames/kCotmHz) return 0;
  return kSummonEffects[s.attribute]+std::min(kSummonEffectFrames-1,unsigned(s.pulse_time*kCotmHz));
}
// Native attack collider, with an allocation-local vtable. It owns no player
// pointers and is reclaimed by the normal entity manager, including room exit.
constexpr unsigned kSummonColliderBytes=832,kSummonColliderTable=512;
inline bool SummonCollider(uint8_t* base,uint32_t p) {return p && Read(base,p)==p+kSummonColliderTable;}
constexpr uint32_t kProjTag=0x44535350; // collider +0x190: spawned by the projectile pool
inline float NativeStrength(PPCContext& ctx,uint8_t* base,uint32_t player) {
  PPCContext str=ctx;str.r3.u64=player;
  rex::runtime::ResolveIndirectFunction(0x836D3670)(str,base);
  return float(str.f1.f64);
}
// Damage sources, in HoD's own terms. A bare stat is not an attack value:
// native damage is (attack - DEF/2) * (256 - DEF)/256 with a floor of 1
// (82227B70), so STR 7 alone always produced 1.
//  - Magic (projectiles, familiars, shields, summons, Item Crash): the native
//    skill rule from 82533878, P + (P/64 + 0.25) * INT. P is the Hunter Whip's
//    collection-scaled ATK (8245D178) times the pair's own multiplier and its
//    pair level. INT is 824526D0, so Venus/Griffin and gear both count.
//  - Melee (Mars weapons, the Pluto shadow): the whip's native physical
//    attack, 824519C8 = ATK + (ATK/64 + 0.25) * STR + bonuses.
constexpr uint32_t kWhipIndex=kWhip-0x33; // weapon row of item 0xC4
inline float WhipAttack(PPCContext& ctx,uint8_t* base,uint32_t player) {
  const auto owner=Owner(base,player);if(!owner)return 0;
  PPCContext call=ctx;call.r3.u64=Read(base,owner+0x92C);call.r4.u64=kWhipIndex;
  rex::runtime::ResolveIndirectFunction(0x8245D178)(call,base);
  return float(call.f1.f64);
}
inline float NativeIntellect(PPCContext& ctx,uint8_t* base,uint32_t player) {
  const auto owner=Owner(base,player);if(!owner)return 0;
  PPCContext call=ctx;call.r3.u64=owner;
  rex::runtime::ResolveIndirectFunction(0x824526D0)(call,base);
  return float(call.f1.f64);
}
inline float MagicPower(PPCContext& ctx,uint8_t* base,uint32_t player,float scale) {
  const float p=WhipAttack(ctx,base,player)*scale*PairDamage(base,player);
  const float intellect=std::fmax(0.0f,NativeIntellect(ctx,base,player));
  const float power=p+(p/64+.25f)*intellect;
  return std::isfinite(power) ? std::fmax(1.0f,std::floor(power)) : 1.0f;
}
inline float MeleePower(PPCContext& ctx,uint8_t* base,uint32_t player,float scale) {
  const auto owner=Owner(base,player);if(!owner)return 1;
  PPCContext call=ctx;call.r3.u64=owner;call.r4.u64=kWhipIndex;
  rex::runtime::ResolveIndirectFunction(0x824519C8)(call,base);
  const float power=float(call.f1.f64)*scale*PairDamage(base,player);
  return std::isfinite(power) ? std::fmax(1.0f,std::floor(power)) : 1.0f;
}
inline uint32_t NativeHit(PPCContext& ctx,uint8_t* base,uint32_t player,float x,float y,int half_width,int half_height,
                      float damage,uint32_t element,uint32_t attribute,uint32_t wave,uint32_t tag=0,uint32_t slot=0) {
  const auto owner=Owner(base,player);if(!owner) return 0;
  const auto heap=Read(base,0x828F57A4);if(!heap) return 0;
  PPCContext call=ctx;call.r3.u64=heap;call.r4.u64=kSummonColliderBytes;call.r5.u64=0;
  rex::runtime::ResolveIndirectFunction(0x825FC4B0)(call,base);
  const auto hit=call.r3.u32;if(!hit) return 0;
  std::memset(base+hit,0,kSummonColliderBytes);
  call=ctx;call.r3.u64=hit;call.r4.u64=0;call.r5.u64=Read(base,owner+4);call.r6.u64=12;
  rex::runtime::ResolveIndirectFunction(0x82481D60)(call,base);
  std::memcpy(base+hit+kSummonColliderTable,base+0x821EA0F0,0x90);
  Write(base,hit,hit+kSummonColliderTable);
  Write(base,hit+kSummonColliderTable+0x24,0x825F4170); // no sprite post-update
  Write(base,hit+kSummonColliderTable+0x80,0x825F4170); // contact handled with its native pair
  Write(base,hit+kSummonColliderTable+0x1C,0x824827F0); // attack-resolution phase
  Write(base,hit+kSummonColliderTable+0x78,0x825F4170);
  Float(base,hit+0x2C,x);Float(base,hit+0x30,y);
  Float(base,hit+0x44,0);Float(base,hit+0x48,0); // velocity, not a second position
  Float(base,hit+0x110,damage);
  Float(base,hit+0x114,1);
  Write(base,hit+0xB0,(Read(base,hit+0xB0)&0xC0000000u)|2|0x40|element);
  Write(base,hit+0x180,attribute);Write(base,hit+0x184,wave);
  Write(base,hit+0x190,tag);Write(base,hit+0x194,slot);
  Float(base,hit+0x188,0);Write(base,hit+0x18C,0);
  // Native rectangle input is signed left/top/right/bottom offsets.
  Write(base,hit+0x1A0,uint32_t(-half_width));Write(base,hit+0x1A4,uint32_t(-half_height));
  Write(base,hit+0x1A8,half_width);Write(base,hit+0x1AC,half_height);
  return hit;
}
inline unsigned SummonTickIndex(const DssState& s) {
  return std::min(kSummonEffectFrames-1,unsigned(std::fmax(0.0f,s.pulse_time)*kCotmHz));
}
inline const SummonParticle* FindSummonParticle(const DssState& s,unsigned id) {
  if(s.attribute>=10 || s.pulse_time<0 || s.pulse_time>=kSummonEffectFrames/kCotmHz)return nullptr;
  const auto tick=kSummonTicks[s.attribute][SummonTickIndex(s)];
  for(unsigned n=0;n<tick.count;++n) {const auto& p=kSummonParticles[tick.first+n];if(p.id==id)return &p;}
  return nullptr;
}
inline void SummonParticleHit(PPCContext& ctx,uint8_t* base,uint32_t player,const DssState& s,const SummonParticle& p) {
  constexpr float power[10]={1.0f,1.0f,1.12f,1.12f,1.10f,.71f,.84f,1.32f,0,.22f};
  // NativeHit's allocator can fail; discover the new actor through a return
  // value instead of assuming an address or keeping raw owner pointers.
  const int cx=(p.left+p.right)/2,cy=(p.top+p.bottom)/2;
  const auto hit=NativeHit(ctx,base,player,Float(base,player+1280)+cx,Float(base,player+1284)+cy,1,1,
    MagicPower(ctx,base,player,power[s.attribute]),kMercuryElements[s.attribute],s.attribute,p.id,kSummonParticleTag);
  if(!hit)return;
  Write(base,hit+kSummonColliderTable+0x1C,0x824823A0);Write(base,hit+kSummonColliderTable+0x24,0x824827F0);
  Write(base,hit+0x198,Read(base,player+1308));
  Float(base,hit+0x114,12/kCotmHz);base[hit+0x9F]=uint8_t(0xD0+p.id%32);
  Write(base,hit+0x1A0,p.left-cx);Write(base,hit+0x1A4,p.top-cy);Write(base,hit+0x1A8,p.right-cx);Write(base,hit+0x1AC,p.bottom-cy);
  Write(base,player+1292,Read(base,player+1292)+1);
}
inline float SummonHeal(PPCContext& ctx,uint8_t* base,uint32_t player,float requested) {
  const auto owner=Owner(base,player),st=Read(base,player+88);
  // A copy's HP is its owner's: the owner's machine heals and HoD syncs it.
  if(replaying || !owner || !st || !Alive(base,player) || !(requested>0)) return 0;
  requested*=PairHealing(base,player); // every caller is a DSS combo heal
  const float maximum=Float(base,st+16)+Float(base,st+28),before=Float(base,st+4);
  const float after=std::fmin(maximum,before+requested),gained=after-before;
  if(!(gained>0)) return 0;
  Float(base,st+4,after);
  // HP can be fractional after poison, so a real recovery never displays 0.
  PPCContext popup=ctx;popup.r3.u64=owner;popup.r4.u64=0;popup.r5.s64=-int32_t(std::ceil(gained));
  // Native HP-recovery convention: negative amount -> green number, owner
  // positions and stacks the digits above the character automatically.
  rex::runtime::ResolveIndirectFunction(0x82454000)(popup,base);
  return gained;
}
inline unsigned ContactPose(float age) {
  unsigned ticks=unsigned(std::fmax(0.0f,age)*kCotmHz);
  for(unsigned n=0;n<7;++n){if(ticks<kBlackDogAura[n].ticks)return n;ticks-=kBlackDogAura[n].ticks;}
  return 7;
}
inline void SummonContact(uint8_t* base,uint32_t player,uint32_t target,const DssState& s) {
  unsigned slot=kSummonContactCount;
  for(unsigned n=0;n<kSummonContactCount;++n) {
    const auto at=player+kSummonContacts+n*kSummonContactBytes;
    if(Read(base,at)==target && ContactPose(s.pulse_time-Float(base,at+12))<7)return;
    if(!Read(base,at) || ContactPose(s.pulse_time-Float(base,at+12))==7)slot=n;
  }
  const auto entity=Entity(base,target);if(slot==kSummonContactCount || !entity)return;
  const auto at=player+kSummonContacts+slot*kSummonContactBytes;
  Write(base,at,target);Float(base,at+4,Float(base,entity+64));Float(base,at+8,Float(base,entity+68)-20);
  Float(base,at+12,s.pulse_time);Write(base,at+16,1);
}
inline void UpdateSummon(PPCContext& ctx,uint8_t* base,uint32_t player,const DssState& s) {
  const unsigned due=s.pulse_time<1 ? 0 : std::min(4u,unsigned(s.pulse_time));
  unsigned done=Read(base,player+1288);
  while(done<due) {
    if(done==0) {constexpr unsigned sounds[10]={350,351,352,350,350,353,353,354,352,354};Sound(ctx,base,player,sounds[s.attribute]);}
    if(s.attribute==8) {
      if(done==0) {const auto st=Read(base,player+88);const float maximum=Float(base,st+16)+Float(base,st+28);
        const float amount=std::floor(maximum*.16f);
        SummonHeal(ctx,base,player,amount);
        // Allies: HoD heals other players the way Charlotte's Heal does, with
        // an ordinary player attack record whose damage is negative. Enemy
        // damage (82227B70) rejects negative attacks; another player's hurt
        // query (8244B018 -> 8244BF10) turns it into 8244E268 healing on the
        // machine that owns that player. Nathan's own query skips records he
        // owns, so he is not healed twice.
        const float allies=std::ceil(amount*PairHealing(base,player));
        if(allies>0) NativeHit(ctx,base,player,Float(base,player+1280),Float(base,player+1284)-40,
                               int(kSummonHalfWidth),int(kSummonHalfHeight),-allies,0,s.attribute,done);}
    }
    Write(base,player+1288,++done);
  }
  if(s.attribute==8)return;
  const unsigned now=SummonTickIndex(s),last=Read(base,player+1312);
  // Spawn from this visible tick, without replaying offscreen catch-up hits
  // after stalls. A particle owns one moving native collider until it ends.
  if(Read(base,player+1316) && last==now)return;
  auto previous=s;previous.pulse_time=(last+.25f)/kCotmHz;
  const auto tick=kSummonTicks[s.attribute][now];
  for(unsigned n=0;n<tick.count;++n) {
    const auto& p=kSummonParticles[tick.first+n];
    if(!Read(base,player+1316) || !FindSummonParticle(previous,p.id))SummonParticleHit(ctx,base,player,s,p);
  }
  Write(base,player+1312,now);Write(base,player+1316,1);
  if(s.attribute==9)for(unsigned n=0;n<kSummonContactCount;++n) {
    const auto at=player+kSummonContacts+n*kSummonContactBytes,target=Read(base,at);
    if(!target || ContactPose(s.pulse_time-Float(base,at+12))>=7)continue;
    const auto enemy=Entity(base,target);if(!enemy){Write(base,at,0);continue;}
    Float(base,at+4,Float(base,enemy+64));Float(base,at+8,Float(base,enemy+68)-20);
    if(Read(base,at+16)) {
      const auto hit=NativeHit(ctx,base,player,Float(base,at+4),Float(base,at+8),1,1,MagicPower(ctx,base,player,.22f),kMercuryElements[9],9,n,kSummonContactTag);
      if(hit) {
        Write(base,hit+0x198,Read(base,player+1308));Float(base,hit+0x19C,Float(base,at+12));
        Float(base,hit+0x114,12/kCotmHz);base[hit+0x9F]=uint8_t(0xF0+n);
        Write(base,hit+kSummonColliderTable+0x1C,0x824823A0);Write(base,hit+kSummonColliderTable+0x24,0x824827F0);
      }
      if(hit)Write(base,at+16,0);
    }
  }
}
}
