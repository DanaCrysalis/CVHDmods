#include <cstring>
// Shared weapon flag getter. 8246F5C0 calls this BEFORE copying the result to
// the live whip hit object's +0xB0 flags. Keep faction/status flags intact and
// add the same mapped fire bit as the native fire weapons for a paid swing.
#include "../generated/default/harmonyrecomp_init.h"
#include "nathan_card_swap_guest.h"
#include <string_view>
#include "nathan_uranus_guest.h"
#include "nathan_progress_guest.h"
#include "nathan_projectiles_guest.h"
#include "nathan_tackle_state.h"
#include "nathan_dss_balance.h"
#include "nathan_dss_menu.h"
#include "hod_guest.h"
#include "hod_hooks.h"
#ifdef NATHAN_VERIFY_HARNESS  // modding/tools/verify_nathan_dss.py: no logger linked
#define NATHAN_ONLINE_LOG(...) ((void)0)
#else
#include <rex/logging.h>
#define NATHAN_ONLINE_LOG(...) REXLOG_INFO(__VA_ARGS__)
#endif
using namespace harmony::nathan;

// Online co-op, receiving side (see LocalPlayer in nathan_dss_guest.h). Every
// player spawn event passes 8244CA98 (the hub's chain; Nathan's handler runs
// first). A Nathan event (kind 11 / sub 1, "NA" "TH") for another
// machine's Nathan is queued on this machine's copy of him; Nathan's own
// update replays it. The native call then continues (a no-op for kind 11/1).
namespace {
const char* NetName(uint32_t type) {
  switch(type){case kNetOn:return "DSS on";case kNetOff:return "DSS off";case kNetCast:return "cast";
    case kNetSwing:return "swing";case kNetAttack:return "attack button";case kNetSubweapon:return "extra subweapon";default:return "unknown event";}
}
void ReceiveNathanEvent(PPCContext& ctx,uint8_t* base) {
  const auto owner=ctx.r3.u32;
  if(!owner || ctx.r5.u32!=11 || ctx.r6.s32!=1 || (ctx.r9.u32&0xFFFF)!=kNetTagA || (ctx.r10.u32&0xFFFF)!=kNetTagB) return;
  const auto player=PlayerComponent(base,owner);
  if(!player || Read(base,player)!=kVtable || Read(base,owner+0x930)==1) return;
  const auto id=ctx.r4.u32&0xFFFF;
  NetEnqueue(base,player,id);
  const unsigned type=id>>12&15;
  if(type!=kNetAttack && type!=kNetSwing && !(type==kNetOn && Read(base,player+kNet+72)==(id>>8&15) && Read(base,player+kNet+76)==(id>>4&15)))
    NATHAN_ONLINE_LOG("[nathan] online player {} {}: action {} attribute {} value {}",Read(base,owner+0x938),NetName(type),id>>8&15,id>>4&15,id&15);
}
bool PrepareSummonParticle(PPCContext& ctx,uint8_t* base) {
  const auto hit=ctx.r3.u32;
  if(!SummonCollider(base,hit))return false;
  const auto tag=Read(base,hit+0x190);
  if(tag!=kSummonParticleTag && tag!=kSummonContactTag)return false;
  const auto owner=Entity(base,Read(base,hit+0xA4)),player=PlayerComponent(base,owner);
  if(!player || Read(base,player)!=kVtable || Read(base,hit+0x198)!=Read(base,player+1308)) {base[hit+0x17]=1;return true;}
  const auto s=Load(base,player);
  if(!Summoning(base,player,s)){base[hit+0x17]=1;return true;}
  if(tag==kSummonParticleTag) {
    const auto p=FindSummonParticle(s,Read(base,hit+0x184));
    if(!p){base[hit+0x17]=1;return true;}
    const int cx=(p->left+p->right)/2,cy=(p->top+p->bottom)/2;
    Float(base,hit+0x2C,Float(base,player+1280)+cx);Float(base,hit+0x30,Float(base,player+1284)+cy);
    Write(base,hit+0x1A0,p->left-cx);Write(base,hit+0x1A4,p->top-cy);Write(base,hit+0x1A8,p->right-cx);Write(base,hit+0x1AC,p->bottom-cy);
  } else {
    const auto slot=Read(base,hit+0x184);if(slot>=kSummonContactCount){base[hit+0x17]=1;return true;}
    const auto at=player+kSummonContacts+slot*kSummonContactBytes;
    const auto pose=ContactPose(s.pulse_time-Float(base,at+12));
    if(!Read(base,at) || Float(base,at+12)!=Float(base,hit+0x19C) || pose>=7){base[hit+0x17]=1;return true;}
    const float x=Float(base,at+4),y=Float(base,at+8);
    const float dx=x-Float(base,player+1280),dy=y-Float(base,player+1284);
    if(dx < -160 || dx>160 || dy < -180 || dy>12){base[hit+0x17]=1;return true;}
    Float(base,hit+0x2C,x);Float(base,hit+0x30,y);
    const auto& b=kBlackDogAuraBounds[pose];
    Write(base,hit+0x1A0,std::max(b[0],int(std::ceil(-160-dx))));Write(base,hit+0x1A4,std::max(b[1]-1,int(std::ceil(-181-dy))));
    Write(base,hit+0x1A8,std::min(b[2],int(std::floor(160-dx))));Write(base,hit+0x1AC,std::min(b[3]-1,int(std::floor(11-dy))));
  }
  PPCContext area=ctx;area.r3.u64=hit;area.r4.u64=hit+0x1A0;
  __imp__sub_82484180(area,base);Write(base,hit+0x18C,1);
  return true;
}
void SpawnEventHandler(PPCContext& ctx,uint8_t* base,const hod::Next& next) {ReceiveNathanEvent(ctx,base);next(ctx,base);}
void ColliderPrepareHandler(PPCContext& ctx,uint8_t* base,const hod::Next& next) {if(PrepareSummonParticle(ctx,base))return;next(ctx,base);}
}

// Physical DEF used by incoming damage: armor + CON/2, then native buffs.
// Shared with the Shield Rod (Leather Shield spell: +20 DEF, any character
// whose owner cast it; only Alucard can).
static void PhysicalDefense(PPCContext& ctx,uint8_t* base,const hod::Next& next) {
  const auto owner=ctx.r3.u32,player=PlayerComponent(base,owner);
  next(ctx,base);
  if (!player || Read(base,player)!=kVtable) return;
  const auto s=Load(base,player);
  if (ActiveProgress(base,player,s) && (s.action==kActionVenus || s.action==kActionPluto)) {
    Write(base,player+1060,Read(base,player+1060)+1);
    Float(base,player+1064,float(ctx.f1.f64));
    ctx.f1.f64*=DssDefense(base,player,s);
    Float(base,player+1068,float(ctx.f1.f64));
  }
}

// Status/equipment screens build a separate stat summary, rather than using
// the battle getter. Apply the same effects to its temporary output only.
static void StatusSummary(PPCContext& ctx,uint8_t* base,const hod::Next& next) {
  const auto character=ctx.r3.u32,out=ctx.r4.u32;
  next(ctx,base);
  if (!out || (character!=0 && character!=12)) return;
  const auto handle=NativeQuery(ctx,base,0x8245CCE8,0);
  const auto owner=Entity(base,handle),player=PlayerComponent(base,owner);
  if (!player || Read(base,player)!=kVtable) return;
  const auto s=Load(base,player);
  if (!ActiveProgress(base,player,s)) return;
  Float(base,out+0x18,Float(base,out+0x18)*DssDefense(base,player,s));
  Float(base,out+0x10,Float(base,out+0x10)*AttackBonus(base,player,s));
  Float(base,out+0x14,Float(base,out+0x14)*AttackBonus(base,player,s));
  if(s.action!=kActionVenus) return;
  Float(base,out+0x1C,float(std::floor(double(Float(base,out+0x1C))*PairPercent(base,player,kVenusStrength[s.attribute])/100)));
  if (s.attribute==6) Float(base,out+0x20,float(std::floor(Float(base,out+0x20)*1.25)));
  if (s.attribute==2) Float(base,out+0x2C,float(std::floor(Float(base,out+0x2C)*1.25)));
}

namespace {
thread_local uint32_t heart_owner=0;
struct ScopedHeart {
  uint32_t previous=heart_owner;
  explicit ScopedHeart(uint32_t owner) {heart_owner=owner;}
  ~ScopedHeart() {heart_owner=previous;}
};
}

// Only the native heart-item path enters this scope. Potions, passive MP
// regeneration, damage absorption and other MP gains must remain unchanged.
REX_EXTERN(sub_8245BCA8) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_8245BCA8);
  const auto owner=Entity(base,Read(base,ctx.r3.u32+0x68));
  ScopedHeart scope(owner);
  __imp__sub_8245BCA8(ctx,base);
}
REX_EXTERN(sub_8244E3C8) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_8244E3C8);
  const auto owner=ctx.r3.u32;
  if (owner && owner==heart_owner && ctx.f1.f64>0) {
    const auto player=PlayerComponent(base,owner);
    if (player && Read(base,player)==kVtable) {
      const auto s=Load(base,player);
      if (ActiveVenus(base,player,s) && s.attribute==5) ctx.f1.f64*=2;
    }
  }
  // Native MP clamp and pickup feedback see the doubled amount together.
  __imp__sub_8244E3C8(ctx,base);
}

REX_EXTERN(sub_8246C408) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_8246C408);
  const auto weapon=ctx.r3.u32;
  __imp__sub_8246C408(ctx,base);
  if (Read(base,weapon+0x88)!=0x91 || Read(base,weapon+0x8C)!=1) return;
  const auto owner=Entity(base,Read(base,weapon+0x2C));
  if (!owner) return;
  const auto player=PlayerComponent(base,owner);
  if (!player || Read(base,player)!=kVtable || !ActivePair(base,player,Load(base,player)) ||
      !Paired(base,player) || !Alive(base,player)) return;
  Write(base,player+1024,ctx.r3.u32);
  ctx.r3.u64=ctx.r3.u32|Load(base,player).Element();
}

namespace {
struct DrawTarget { uint32_t body=0, player=0; bool palette=false; };
thread_local DrawTarget draw_target;
struct ScopedDrawTarget {
  DrawTarget previous=draw_target;
  explicit ScopedDrawTarget(DrawTarget next) { draw_target=next; }
  ~ScopedDrawTarget() { draw_target=previous; }
};
}

// Character rendering resolves the clip's step AFTER the player update. Scope
// only Nathan's own sprite instance, so weapons, effects and other players
// never inherit his palette. No animation cursor or frame event is changed.
static void OwnerDraw(PPCContext& ctx,uint8_t* base,const hod::Next& next) {
  const auto owner=ctx.r3.u32;
  const auto player=PlayerComponent(base,owner);
  DrawTarget target{};
  if (player && Read(base,player)==kVtable && Owner(base,player)==owner)
    target={Read(base,owner+0x2C),player,true};
  ScopedDrawTarget scope(target);
  next(ctx,base);
}

// Character Select renders one sprite eight times, with native row offsets
// 0..7. Scope only Nathan's preview; normal character previews stay native.
REX_EXTERN(sub_82412880) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_82412880);
  const auto menu=ctx.r3.u32,index=Read(base,menu+0x138),manager=Read(base,0x8291D968);
  DrawTarget target{};
  if(manager && index<32) {
    const auto first=Read(base,manager+4),end=Read(base,manager+8);
    const auto record=first+index*0x328;
    if(first && record<end && Read(base,record)==12)
      target={Read(base,menu+(index+0x38)*4),0,true};
  }
  ScopedDrawTarget scope(target);
  __imp__sub_82412880(ctx,base);
}

// Player-list/menu portraits bypass the character draw scope. Both sprite
// paths share this palette lookup. Sprite +8 is native basename FNV-1:
// 825BFF28("p_nathan") = 854D90C4. Match the resource, not menu selection.
REX_EXTERN(sub_823D7170) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_823D7170);
  const auto sprite=ctx.r3.u32;
  const bool alternate=sprite && Read(base,sprite+8)==0x854D90C4u && base[sprite+0x55]==7;
  if(alternate) base[sprite+0x55]=96;
  __imp__sub_823D7170(ctx,base);
  if(alternate) base[sprite+0x55]=7;
}

// Additional FX share body geometry/textures but use the already-preloaded
// invisible weapon's independent COL. A per-player descriptor copy changes
// only its palette pointer; no shared resource or GPU palette is mutated.
static bool EffectPalette(PPCContext& ctx,uint8_t* base,uint32_t player,uint32_t sprite,uint32_t frame) {
  if(frame<kAllDssFirst || frame>=kAllDssBodyFirst)return true;
  const auto lookup=player+kFxLookupSprite;
  if(!Read(base,player+kAllState)) {
    std::memcpy(base+lookup,base+sprite,192);base[lookup]=1;
    unsigned hash=2166136261u;for(unsigned char c:std::string_view("p_wpf0")){hash*=16777619u;hash^=c;}
    Write(base,lookup+8,hash);Write(base,lookup+12,0);Write(base,lookup+0xA0,0);
    PPCContext query=ctx;query.r3.u64=lookup;
    rex::runtime::ResolveIndirectFunction(0x823D2520)(query,base);
    const auto resource=Read(base,lookup+12),palette=resource?Read(base,resource+0x24):0;
    if(!palette){Write(base,player+kAllState+4,Read(base,player+kAllState+4)+1);return false;}
    Write(base,player+kAllState,palette);
  }
  const auto resource=Read(base,sprite+12);if(!resource)return false;
  std::memcpy(base+player+kFxResource,base+resource,112);
  Write(base,player+kFxResource+0x24,Read(base,player+kAllState));Write(base,sprite+12,player+kFxResource);return true;
}
// Places a copied sprite at a world position. The draw call's r5/r6 are the
// integer world X and down-positive Y that 825AE620 takes from owner+64/+68,
// the body's real draw position (82449C30: X, and Y plus a pose offset).
// Sprite +116/+118 cannot do this: they are a mirror pivot that the transform
// (823D69E0) and the part placement (823D2648) both apply, so an X offset is
// doubled and a Y offset cancels. owner+0x8EC/0x8F0 is the body-box center
// (82448730), not the draw origin. Scaled layers (sprite mode 7..10) pass
// zoomed coordinates; their zoom is the ratio the body scale was raised by.
constexpr float kCardDepth=60000;
constexpr uint32_t kCardList=6; // render list for the Card Swap cards (body: 3; 7..10 zoomed)
static void PlaceAt(PPCContext& draw,uint8_t* base,uint32_t owner,uint32_t body,float x,float y) {
  float zoom=1;
  const auto mode=Read(base,body+0x78);
  if(mode>=7 && mode<=10) {const float unit=Float(base,owner+72);if(unit>0)zoom=std::abs(Float(base,body+0x28))/unit;}
  if(!std::isfinite(zoom) || zoom<=0)zoom=1;
  const float dx=(x-Float(base,owner+64))*zoom,dy=(y-Float(base,owner+68))*zoom;
  if(!std::isfinite(dx) || !std::isfinite(dy))return;
  draw.r5.u64=uint32_t(int32_t(draw.r5.u32)+int32_t(std::lround(dx)));
  draw.r6.u64=uint32_t(int32_t(draw.r6.u32)+int32_t(std::lround(dy)));
}
// Pool objects use the same sprite-copy path as summon art.
static void DrawProjectiles(const PPCContext& original,uint8_t* base,uint32_t player,uint32_t body) {
  const auto owner=Owner(base,player);
  if(!owner) return;
  const auto sprite=player+kSummonSprite;
  for(unsigned i=0;i<kProjCount;++i) {
    const auto p=LoadProjectile(base,ProjAddress(player,i));
    if(p.kind==kProjNone || p.kind==kProjCrash) continue;
    std::memcpy(base+sprite,base+body,kSummonSpriteBytes);base[sprite+0x54]=base[sprite+0x55]=0;
    Write(base,sprite+0xA0,0);base[sprite+0xA4]=1;base[sprite+0x1C]=(p.flags&kFaceLeft)?1:0;
    if(p.flags&16){Float(base,sprite+0x28,Float(base,body+0x28)*2);Float(base,sprite+0x2C,Float(base,body+0x2C)*2);}
    PPCContext draw=original;draw.r3.u64=sprite;draw.r4.u64=p.Frame();draw.r7.u64=original.r7.u32&~3u;
    PlaceAt(draw,base,owner,body,p.x,p.y);
    if(EffectPalette(draw,base,player,sprite,draw.r4.u32))__imp__sub_823D2648(draw,base);
  }
}

// This is the OPD frame DRAW call, not the player's animation-event counter.
// Both ordinary and alternate character draw paths call it after resolving
// the current clip step. Its frame argument is what the renderer consumes.
REX_EXTERN(sub_823D2648) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_823D2648);
  const auto player=draw_target.player,body=ctx.r3.u32;
  const bool nathan=player && draw_target.body==body;
  PPCContext original=ctx;
  if (nathan) {
    const auto s=Load(base,player);
    if(Summoning(base,player,s) && SummonBackdrop(s)) {
      const auto sprite=player+kSummonSprite;
      std::memcpy(base+sprite,base+body,kSummonSpriteBytes);base[sprite+0x54]=base[sprite+0x55]=0;
      Write(base,sprite+0xA0,0);base[sprite+0xA4]=1;base[sprite+0x1C]=0;
      const float alpha=std::clamp(std::min((s.pulse_time-.35f)/.55f,(5.2f-s.pulse_time)/.5f),0.0f,1.0f);
      Float(base,sprite+80,alpha*.65f);base[sprite+140]=1;
      PPCContext backdrop=original;backdrop.r8.u64=0xFFFFFFFFu;backdrop.r9.u64=0;backdrop.r3.u64=sprite;backdrop.r4.u64=SummonBackdrop(s);backdrop.r7.u64=original.r7.u32&~3u;
      __imp__sub_823D2648(backdrop,base);
    }
    const auto canonical=ctx.r4.u32;
    ctx.r4.u64=Summoning(base,player,s) ? SummonBody(s) : SkeletonFrame(base,player,MarsBodyFrame(base,player,s.BodyFrame(canonical)));
    if(Summoning(base,player,s)) {
      const auto owner=Owner(base,player);
      if(owner)PlaceAt(ctx,base,owner,body,Float(base,owner+64),Float(base,owner+68)-SummonLift(s));
    }
    Write(base,player+872,ctx.r4.u32);
    Write(base,player+876,canonical);
    Write(base,player+880,s.draw_count+1);
  }
  const auto original_resource=Read(base,body+12);
  const bool transformed=nathan && ctx.r4.u32>=kAllDssFirst && ctx.r4.u32<kAllDssBodyFirst;
  if(transformed) {Write(base,player+kAllState+188,base[body+0x55]);base[body+0x55]=0;Write(base,body+0xA0,0);base[body+0xA4]=1;}
  const auto native_palette=base[body+0x55];
  const bool alternate=draw_target.palette && draw_target.body==body && native_palette==7;
  const auto shade=nathan && !transformed ? Load(base,player).PaletteOffset(ctx.r4.u32) : 0;
  if(alternate || shade) base[body+0x55]=uint8_t((alternate ? kCostumePalette : native_palette)+shade);
  if(nathan) Write(base,player+1072,base[body+0x55]);
  if(!transformed || EffectPalette(ctx,base,player,body,ctx.r4.u32))__imp__sub_823D2648(ctx,base);
  else {
    // Resource readiness can lag the first draw. Keep Nathan visible while
    // the independent FX palette becomes available.
    ctx.r4.u64=original.r4.u32;Write(base,body+12,original_resource);
    base[body+0x55]=uint8_t(Read(base,player+kAllState+188));
    __imp__sub_823D2648(ctx,base);
  }
  if(transformed){Write(base,body+12,original_resource);base[body+0x55]=original.r3.u32==body?uint8_t(Read(base,player+kAllState+188)):0;}
  if(alternate || shade) base[body+0x55]=native_palette;
  if(nathan) {
    const auto s=Load(base,player);
    const auto selected=Summoning(base,player,s) ? SummonBody(s) : SkeletonFrame(base,player,MarsBodyFrame(base,player,s.BodyFrame(original.r4.u32)));
    if(selected<kBaseFrames && kBodyEffects[selected]!=0xFFFFFFFFu) {
      // Body tint is a shader palette offset. The clipped independent effect
      // layer keeps its native palette and exact visible-pixel priority.
      const auto sprite=player+kSummonSprite;
      std::memcpy(base+sprite,base+body,kSummonSpriteBytes);
      base[sprite+0x54]=base[sprite+0x55]=0;
      Write(base,sprite+0xA0,0);base[sprite+0xA4]=1;
      PPCContext effect=original;effect.r3.u64=sprite;effect.r4.u64=kBodyEffects[selected];
      if(EffectPalette(effect,base,player,sprite,effect.r4.u32))__imp__sub_823D2648(effect,base);
      Write(base,player+1076,Read(base,player+1076)+1);
    }
    if(Summoning(base,player,s)) {
      const auto& core=kSummonCores[s.attribute][SummonTickIndex(s)];
      if(core.frame && core.sx && core.sy) {
        const auto sprite=player+kSummonSprite,owner=Owner(base,player);
        std::memcpy(base+sprite,base+body,192);base[sprite+0x54]=base[sprite+0x55]=0;
        Write(base,sprite+0xA0,0);base[sprite+0xA4]=1;base[sprite+0x1C]=0;
        Write(base,sprite+116,0);Float(base,sprite+80,kSummonOpacity);base[sprite+140]=0;
        Float(base,sprite+0x28,std::abs(Float(base,body+0x28))*256/core.sx);
        Float(base,sprite+0x2C,std::abs(Float(base,body+0x2C))*256/core.sy);
        PPCContext effect=original;effect.r3.u64=sprite;effect.r4.u64=core.frame;effect.r7.u64=0;effect.r8.u64=0xFFFFFFFFu;effect.r9.u64=0;
        if(owner)PlaceAt(effect,base,owner,body,Float(base,player+1280)+core.x,Float(base,player+1284)+core.y);
        __imp__sub_823D2648(effect,base);
      }
    }
    const auto frame=Summoning(base,player,s) ? SummonEffect(s) : MovingShield(base,player) ? kMovingShieldFrames[unsigned(s.pulse_time*20)%3] : 0;
    if(frame) {
      const auto sprite=player+kSummonSprite;
      std::memcpy(base+sprite,base+body,kSummonSpriteBytes);base[sprite+0x54]=base[sprite+0x55]=0;
      Write(base,sprite+0xA0,0);base[sprite+0xA4]=1;base[sprite+0x1C]=0;
      PPCContext effect=original;effect.r3.u64=sprite;effect.r4.u64=frame;effect.r7.u64=original.r7.u32&~3u;
      if(Summoning(base,player,s)) {
        Write(base,sprite+116,0);Float(base,sprite+80,kSummonOpacity);base[sprite+140]=0;
        effect.r8.u64=0xFFFFFFFFu;effect.r9.u64=0;
      }
      if(EffectPalette(effect,base,player,sprite,effect.r4.u32))__imp__sub_823D2648(effect,base);
    }
    if(MarsSwing(base,player,s) || (s.action==kActionMars && s.attribute==6 && Read(base,player+kAllState+132))) {
      const auto sprite=player+kSummonSprite;std::memcpy(base+sprite,base+body,kSummonSpriteBytes);
      base[sprite+0x54]=base[sprite+0x55]=0;Write(base,sprite+0xA0,0);base[sprite+0xA4]=1;
      PPCContext effect=original;effect.r3.u64=sprite;effect.r4.u64=MarsEffectFrame(base,player);
      if(EffectPalette(effect,base,player,sprite,effect.r4.u32))__imp__sub_823D2648(effect,base);
    }
    if(Float(base,player+kProjControl+24)>0) {
      const auto sprite=player+kSummonSprite;std::memcpy(base+sprite,base+body,kSummonSpriteBytes);
      base[sprite+0x54]=base[sprite+0x55]=0;Write(base,sprite+0xA0,0);base[sprite+0xA4]=1;
      PPCContext effect=original;effect.r3.u64=sprite;effect.r4.u64=DssFrame(kNeptuneFire,.5f-Float(base,player+kProjControl+24));
      if(EffectPalette(effect,base,player,sprite,effect.r4.u32))__imp__sub_823D2648(effect,base);
    }
    if(Summoning(base,player,s) && s.attribute==9)for(unsigned n=0;n<kSummonContactCount;++n) {
      const auto at=player+kSummonContacts+n*kSummonContactBytes;
      if(!Read(base,at))continue;
      const auto pose=ContactPose(s.pulse_time-Float(base,at+12));if(pose>=7)continue;
      const auto owner=Owner(base,player),sprite=player+kSummonSprite;
      const float x=Float(base,at+4),y=Float(base,at+8),dx=x-Float(base,player+1280),dy=y-Float(base,player+1284);
      if(!owner || dx < -160 || dx>160 || dy < -180 || dy>12)continue;
      std::memcpy(base+sprite,base+body,192);base[sprite+0x54]=base[sprite+0x55]=0;
      Write(base,sprite+0xA0,0);base[sprite+0xA4]=1;base[sprite+0x1C]=0;Float(base,sprite+80,kSummonOpacity);base[sprite+140]=0;
      PPCContext effect=original;effect.r3.u64=sprite;effect.r4.u64=kBlackDogAura[pose].frame;effect.r7.u64=0;effect.r8.u64=0xFFFFFFFFu;effect.r9.u64=0;
      PlaceAt(effect,base,owner,body,x,y);__imp__sub_823D2648(effect,base);
    }
    DrawProjectiles(original,base,player,body);
    Write(base,player+kAllState+92,original.r4.u32);
    if(ActivePluto(base,player,3)) {
      const auto owner=Owner(base,player);const auto sprite=player+kSummonSprite,at=player+kShadowHistory+((Read(base,player+kAllState+112)+48-9)%48)*16;
      std::memcpy(base+sprite,base+body,192);base[sprite+0x54]=0;base[sprite+0x55]=1;Write(base,sprite+0xA0,0);base[sprite+0xA4]=1;
      base[sprite+0x1C]=Read(base,at+12)!=0;PPCContext echo=original;echo.r3.u64=sprite;echo.r4.u64=Read(base,at+8);echo.r7.u64=original.r7.u32&~3u;
      if(owner)PlaceAt(echo,base,owner,body,Float(base,at),Float(base,at+4));
      if(echo.r4.u32<kAllDssEnd)__imp__sub_823D2648(echo,base);
    }
  }
  if (!nathan || !Read(base,player+kSwapHeld) || !Alive(base,player)) return;
  const auto owner=Owner(base,player);
  const auto equipment=owner ? Read(base,owner+0x9C8) : 0;
  if (!equipment) return;
  for (unsigned side=0;side<2;++side) {
    const auto frame=CardArt(Read(base,equipment+(12+side)*4),side!=0);
    if (!frame) continue;
    // A separate sprite-instance copy prevents the native renderer's cached
    // draw packet from overwriting Nathan's already submitted body geometry.
    const auto sprite=player+kCardSprite;
    std::memcpy(base+sprite,base+body,kCardSpriteBytes);base[sprite+0x54]=base[sprite+0x55]=0;
    // Native transform 823D69E0 reads X/Y scale at +28/+2C.
    // Full 64x96 artwork, same 32x48 world size and placement as before.
    Float(base,sprite+0x28,Float(base,body+0x28)*0.5f);
    Float(base,sprite+0x2C,Float(base,body+0x2C)*0.5f);
    base[sprite+0x1C]=0; // cards stay upright when Nathan faces left
    // Draw order: depth (+0x60 -> packet +0x19C) only sorts packets within one
    // render list. The list is sprite +0x78 (82472DC8): Nathan's body draws in
    // list 3, and foreground terrain is drawn in a later list, so no depth
    // could lift copies of his body above it (seen live, November 12). The
    // cards go to the last world list (lists 7..10 are the zoomed layers), at
    // the top of its depth range.
    Write(base,sprite+0x78,kCardList);
    Float(base,sprite+0x60,kCardDepth);
    Write(base,sprite+0xA0,0);base[sprite+0xA4]=1;
    PPCContext overlay=original;overlay.r3.u64=sprite;overlay.r4.u64=frame;
    overlay.r7.u64=original.r7.u32&~3u; // direct draw flags include the body facing reflection
    __imp__sub_823D2648(overlay,base);
    Write(base,player+kCardDrawCount,Read(base,player+kCardDrawCount)+1);
  }
}

namespace {
thread_local uint32_t weapon_player=0;
struct WeaponScope {
  uint32_t previous=weapon_player;
  WeaponScope(uint8_t* base,uint32_t component) {
    weapon_player=0;
    const auto weapon=Entity(base,Read(base,component+72));
    if (!weapon || Read(base,weapon+0x88)!=0x91 || Read(base,weapon+0x8C)!=1) return;
    const auto owner=Entity(base,Read(base,weapon+0x2C));
    const auto player=PlayerComponent(base,owner);
    if (player && Read(base,player)==kVtable && (ActivePair(base,player,Load(base,player)) || (Load(base,player).action==kActionDiana && Load(base,player).attribute==5 && ActiveDss(base,player,Load(base,player))) || (Load(base,player).action==kActionMars && ActiveDss(base,player,Load(base,player))) || ActivePluto(base,player,9)) && Alive(base,player)) weapon_player=player;
  }
  ~WeaponScope() { weapon_player=previous; }
};
uint32_t WeaponClip(uint8_t* base,uint32_t clip) {
  if (!weapon_player || clip>1) return clip;
  const auto s=Load(base,weapon_player);
  if(s.action==kActionMars || (s.action==kActionPluto&&s.attribute==9))return 32; // inherited whip geometry is replaced by the sword attack
  const auto motion=Read(base,weapon_player+584);
  const unsigned pose=(motion==188 || motion==192) ? 1 : (motion==189 ? 2 : 0);
  return 2+s.attribute*3+pose;
}
}
// Scope the shared weapon animation start and collision query. Resource clips
// 0/1 remain intact for ordinary whips; 2..31 have the native DSS geometry.
REX_EXTERN(sub_824699B8) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_824699B8);
  WeaponScope scope(base,ctx.r3.u32);
  __imp__sub_824699B8(ctx,base);
}
REX_EXTERN(sub_82469D18) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_82469D18);
  WeaponScope scope(base,ctx.r3.u32);
  __imp__sub_82469D18(ctx,base);
}
REX_EXTERN(sub_823D31C8) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_823D31C8);
  ctx.r4.u64=WeaponClip(base,ctx.r4.u32);
  __imp__sub_823D31C8(ctx,base);
}
REX_EXTERN(sub_823D4098) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_823D4098);
  ctx.r4.u64=WeaponClip(base,ctx.r4.u32);
  __imp__sub_823D4098(ctx,base);
}

REX_EXTERN(sub_8246F5C0) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_8246F5C0);
  const auto weapon=ctx.r3.u32;
  __imp__sub_8246F5C0(ctx,base);
  if (Read(base,weapon+0x88)!=0x91 || Read(base,weapon+0x8C)!=1) return;
  const auto owner=Entity(base,Read(base,weapon+0x2C));
  const auto player=PlayerComponent(base,owner);
  if (!player || Read(base,player)!=kVtable) return;
  const auto begin=Read(base,weapon+60),end=Read(base,weapon+64);
  if (!begin || end-begin<4) return;
  const auto hit=Read(base,begin);
  if (hit) Write(base,player+1028,Read(base,hit+364));
  RefreshWhip(base,player);
}

// Item descriptions use the same equipped loadout model as the menu and
// Card Swap. Text stays in package-local TXRC resources for normal rendering.
REX_EXTERN(sub_823C90C0) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_823C90C0);
  const auto item=ctx.r3.u32;
  __imp__sub_823C90C0(ctx,base);
  if (item<kSalamander || item>=kSalamander+10) return;
  const auto save=Inventory(ctx,base);
  if (!save) return;
  const auto equipment=save+0x28+11*15*4;
  if (Read(base,equipment)!=kWhip) return;
  const auto action=Read(base,equipment+12*4);
  const auto selected=action==kMercury ? 0 : action>=kVenus && action<kVenus+9 ? action-kVenus+1 : 10;
  if (selected<10) ctx.r3.u64=0x440E0000u+20+selected*10+item-kSalamander;
}

// Menu description footer (every menu calls 823E4AB0 for it): r3 item,
// r4/r5 left/right value, r6/r7 show left/right; returns the layout. Kind 1
// is "LV. n" on the left and "MP n" on the right, as for hunter subweapons.
// Attribute Cards show their pair with Nathan's equipped Action Card (Action
// Cards keep the native footer: their rule text needs the room). LV is the
// pair level (average of the two cards' copies, rounded down); MP is the
// pair's cost from nathan_dss_menu.h. Item Crash (Pluto + Salamander) costs
// what the equipped B subweapon's crash costs; none equipped hides it.
REX_EXTERN(sub_823E4AB0) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_823E4AB0);
  const auto item=ctx.r3.u32,left=ctx.r4.u32,right=ctx.r5.u32,show_left=ctx.r6.u32,show_right=ctx.r7.u32;
  __imp__sub_823E4AB0(ctx,base);
  if(item<kSalamander || item>=kSalamander+10) return;
  const auto kind=ctx.r3.u64;
  PPCContext query=ctx;const auto save=Inventory(query,base);
  ctx.r3.u64=kind;
  if(!save) return;
  const auto equipment=save+0x28+11*15*4;
  if(Read(base,equipment)!=kWhip) return;
  const auto action=Read(base,equipment+48),attribute=item;
  const unsigned a=action==kMercury ? 0 : action>=kVenus && action<kVenus+9 ? action-kVenus+1 : 10;
  const unsigned b=attribute-kSalamander;
  if(a>=10) return;
  unsigned mp=kPairMenuMp[a*10+b];
  if(a==9 && b==0) {
    const auto family=CrashFamily(Read(base,equipment+8*4));
    mp=family<7 ? unsigned(kCrashCost[family]) : 0;
  }
  Write(base,left,unsigned(PairLevelFor(CardCopies(base,save,action),CardCopies(base,save,attribute))));
  base[show_left]=1;
  Write(base,right,mp);
  base[show_right]=mp!=0;
  ctx.r3.u64=1;
}

// Uranus selects this entry in its actor update / attack-resolution phase.
static void ColliderAttack(PPCContext& ctx,uint8_t* base,const hod::Next& next) {
  const auto hit=ctx.r3.u32;
  if(!SummonCollider(base,hit)) {next(ctx,base);return;}
  const auto owner=Entity(base,Read(base,hit+0xA4));
  const auto player=PlayerComponent(base,owner);
  const bool pooled=Read(base,hit+0x190)==kProjTag;
  const bool tackle=Read(base,hit+0x190)==kTackleTag;
  const bool particle=Read(base,hit+0x190)==kSummonParticleTag;
  if(!player || Read(base,player)!=kVtable) {base[hit+0x17]=1;return;}
  if(tackle) {
    // The tackle's single attack area lives exactly as long as the dash and
    // stays ahead of Nathan, re-submitted every frame like the whip's own hit
    // object, so the collision manager treats it as one attack.
    if(!Alive(base,player) || !TackleDashing(base,player,Read(base,hit+0x184))) {base[hit+0x17]=1;return;}
    Float(base,hit+0x2C,Float(base,owner+0x8D4)+Float(base,player+kTackle+8)*kTackleAhead);
    Float(base,hit+0x30,Float(base,owner+0x8D8)-24);
    Write(base,hit+0x18C,0);
    Float(base,hit+0x188,0);
  } else if(!(pooled ? Alive(base,player) : Summoning(base,player,Load(base,player)))) {base[hit+0x17]=1;return;}
  const bool contact=Read(base,hit+0x190)==kSummonContactTag;
  if((particle || contact) && (Read(base,hit+0x198)!=Read(base,player+1308) || base[hit+0x17]))return;
  const auto slot=Read(base,hit+0x194);
  if(pooled && slot<kProjCount) {
    const auto p=LoadProjectile(base,ProjAddress(player,slot));
    if(p.kind==kProjNone || p.kind==kProjPuff || p.kind==kProjFamiliar || (p.flags>>16)!=Read(base,hit+0x184)) {base[hit+0x17]=1;return;}
  }
  float dt=float(ctx.f1.f64);if(!(dt>0 && dt<=.1f)) dt=1.0f/60;
  const float age=Float(base,hit+0x188)+dt;Float(base,hit+0x188,age);
  if(!(particle || contact) && age>.12f) {base[hit+0x17]=1;return;}
  // Submit once, through HoD's normal collision manager; enemy resistance,
  // status immunity, damage feedback, kill credit and drops remain native.
  const auto prepared=Read(base,hit+0x18C);
  if((particle || contact) ? prepared==1 : !prepared) {
    Write(base,hit+0x18C,(particle || contact)?2:1);
    if(!(particle || contact)) {PPCContext area=ctx;area.r3.u64=hit;area.r4.u64=hit+0x1A0;__imp__sub_82484180(area,base);}
    const auto request=Read(base,hit+0xAC);
    if(request!=0xFFFFFFFFu) {
      // A submitted rectangle is only a collision request. Native actors then
      // explicitly resolve that request against enemy/other-player volumes.
      // Skipping this step leaves visible summons with no damage at all.
      uint32_t mask=0x40000000u;
      const auto flags=Read(base,hit+0xB0);
      if(flags&0x80000000u) {
        const auto game=NativeQuery(ctx,base,0x82223348,0);
        mask=game && Read(base,game+0xFB8)==2 ? 15 : 12;
      } else if(flags&0x40000000u) mask=3;
      std::memset(base+hit+0x1C0,0,16);
      PPCContext resolve=ctx;resolve.r3.u64=hit+0x1C0;resolve.r4.u64=request;resolve.r5.u64=mask;
      rex::runtime::ResolveIndirectFunction(0x823C4E00)(resolve,base);
      Write(base,player+1300,Read(base,player+1300)+1);
      // Enemies sit in the collision manager's neutral group and take damage
      // from their own query, so the mask-3 query above only ever matches PvP
      // opponents, and the contact callback is not a dependable signal that
      // a shot landed. Ask the game directly instead: bit 0x40000000 makes
      // 823C4E00 report the first overlapping volume without running any
      // callbacks; 0x20 selects neutral hurt volumes and 2 opposing players'.
      if(pooled && slot<kProjCount) {
        std::memset(base+hit+0x1D0,0,16);
        PPCContext probe=ctx;probe.r3.u64=hit+0x1D0;probe.r4.u64=request;probe.r5.u64=0x40000000u|0x20u|2u;
        rex::runtime::ResolveIndirectFunction(0x823C4E00)(probe,base);
        const auto struck=Read(base,hit+0x1D0);
        if(probe.r3.u32 && struck && hod::IsHurtRecord(Read(base,struck+4))) {
          MarkProjectileHit(base,player,slot,Read(base,hit+0x184),Read(base,struck+0x14));
          Write(base,player+1304,Read(base,player+1304)+1);
        }
      }
    }
  }
}
REX_EXTERN(sub_82484918) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_82484918);
  const auto hit=ctx.r3.u32,pair=ctx.r5.u32;
  const auto attacker=Entity(base,Read(base,hit+0xA4));
  // This shared callback also receives stage hazards and enemies. Only native
  // player entities (type flag 2) own the player component at +0x924; a boulder
  // has unrelated data there (0x43 in the Chapter 7 crash), not a pointer.
  const auto attacker_player=PlayerComponent(base,attacker);
  if(attacker_player && Read(base,attacker_player)==kVtable && ActivePluto(base,attacker_player,8))return;
  const bool summon=SummonCollider(base,hit);
  __imp__sub_82484918(ctx,base);
  if(summon && pair && Read(base,hit+0x190)==kProjTag && !base[pair+12] && !base[pair+13]) {
    const auto a=Read(base,pair),b=Read(base,pair+4),own=Read(base,hit+4);
    const auto struck=a && b ? (Read(base,a+0x10)==own ? b : Read(base,b+0x10)==own ? a : 0) : 0;
    const auto shooter=Entity(base,Read(base,hit+0xA4)),who=PlayerComponent(base,shooter);
    if(struck && hod::IsHurtRecord(Read(base,struck+4)) && who && Read(base,who)==kVtable) MarkProjectileHit(base,who,Read(base,hit+0x194),Read(base,hit+0x184),Read(base,struck+0x14));
    return;
  }
  if(!summon || !pair || Read(base,hit+0x180)!=9 || base[pair+12] || base[pair+13]) return;
  const auto first=Read(base,pair),second=Read(base,pair+4);
  if(!first || !second) return;
  const auto own=Read(base,hit+4);
  const auto other=Read(base,first+0x10)==own ? second : Read(base,second+0x10)==own ? first : 0;
  if(!other || !hod::IsHurtRecord(Read(base,other+4))) return; // enemy hurt geometry, not attacks or stage collision
  const auto target=Read(base,other+0x14);
  if(!target || target==Read(base,hit+0xA4)) return;
  // Native request +14 identifies the owner, so a boss's several hurtboxes
  // still grant a single recovery per wave. Contact coordinates are not IDs.
  for(unsigned i=0;i<32;++i) {
    const auto at=hit+0x2A0+i*4,seen=Read(base,at);
    if(seen==target) return;
    if(!seen) {Write(base,at,target);break;}
    if(i==31) return;
  }
  const auto owner=Entity(base,Read(base,hit+0xA4)),player=PlayerComponent(base,owner);
  if(!player || Read(base,player)!=kVtable || !Summoning(base,player,Load(base,player))) return;
  if(Read(base,hit+0x190)==kSummonParticleTag)SummonContact(base,player,target,Load(base,player));
  const auto stats=Read(base,player+88);const float maximum=Float(base,stats+16)+Float(base,stats+28);
  SummonHeal(ctx,base,player,std::fmax(1.0f,std::floor(maximum*.01f)));
  Write(base,player+1296,Read(base,player+1296)+1);
}

static void AttackValue(PPCContext& ctx,uint8_t* base,const hod::Next& next) {
  const auto owner=ctx.r3.u32,player=PlayerComponent(base,owner);
  next(ctx,base);
  if(player && Read(base,player)==kVtable) ctx.f1.f64*=AttackBonus(base,player,Load(base,player));
}
// Skip the native enemy-hit transaction before HP loss, knockback, statuses
// and impact feedback. Healing (negative power) still uses the normal path.
// A DSS heal rectangle lives for a few frames; each player takes it once.
static bool RepeatDssHeal(uint32_t owner,uint32_t source) {
  static struct {uint32_t owner,source;} seen[8];static unsigned next=0;
  for(auto& e:seen) if(e.owner==owner) {if(e.source==source) return true;e.source=source;return false;}
  seen[next++%8]={owner,source};return false;
}
static void IncomingDamage(PPCContext& ctx,uint8_t* base,const hod::Next& next) {
  const auto owner=ctx.r3.u32,player=PlayerComponent(base,owner);
  if(ctx.f1.f64<0 && ctx.r9.u32) { // r9 = handle of the attacking object
    const auto source=Entity(base,ctx.r9.u32);
    if(source && SummonCollider(base,source) && RepeatDssHeal(owner,ctx.r9.u32)) {ctx.r3.s64=0;return;}
  }
  const auto stats=player && Read(base,player)==kVtable?Read(base,player+88):0;
  const float hp_before=stats?Float(base,stats+4):0;
  const auto s=stats?Load(base,player):DssState{};
  const bool active=stats && ActiveDss(base,player,s)&&Alive(base,player)&&s.cast_remaining<=0;
  if(active && ctx.f1.f64>=0) {
    if((s.action==kActionPluto && s.attribute==8) || (s.action==kActionJupiter && s.attribute==3 && Float(base,player+kAllState+48)>0)){ctx.r3.s64=-1;return;}
    if(s.action==kActionNeptune) {
      const auto a=s.attribute;const uint32_t physical=a==2?0x20:a==3?0x40:a==6?0x80:0;
      // Every Neptune pairing is a 50% resistance to its damage type; the
      // elemental ones still flash the Neptune effect when they reduce a hit.
      if(physical && (ctx.r7.u32&physical))ctx.f1.f64*=.5;
      else if(s.Element() && (ctx.r7.u32&s.Element())) {
        ctx.f1.f64*=.5;
        if(Float(base,player+kProjControl+24)<=0)Float(base,player+kProjControl+24,.5f);
      }
    }
    if(s.action==kActionJupiter && s.attribute==4)ctx.r7.u64=ctx.r7.u32&~0x8000u;
    if(s.action==kActionJupiter && s.attribute==7)ctx.f1.f64*=.5;
    if(s.action==kActionPluto && s.attribute==9)ctx.f1.f64=1000000;
  }
  if(ctx.f1.f64>=0 && MovingShield(base,player)) {
    Write(base,player+1568,Read(base,player+1568)+1);ctx.r3.s64=-1;return;
  }
  next(ctx,base);
  if(active && s.action==kActionJupiter && s.attribute==3 && Float(base,stats+4)<hp_before)Float(base,player+kAllState+48,4);
}
// Martial Arts page: the input row under each name comes from a fixed table of
// five codes for the 11 base Martial Arts (823ED320 skips index >= 11). The
// row is a string in the menu font: '1' left, '3' down, '5' right, '7' up
// (diagonals in between, '4' down-forward), and a button glyph chosen from the
// player's button configuration (save model bytes; byte 0 is the whip attack).
// After the native page update, Nathan's Tackle gets its row the same way:
// down, down-forward, forward + whip attack, set on the entry's two text
// widgets (tables 821D34B4 / 821D356C) through their vtable entry 2.
constexpr uint32_t kMartialRowWidgets[2]={0x821D34B4u,0x821D356Cu};
constexpr uint8_t kButtonGlyph[9]={0x41,0x42,0x58,0x59,0x5F,0x60,0x5D,0x5E,0x3C};
REX_EXTERN(sub_823ED2E0) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_823ED2E0);
  const auto page=ctx.r3.u32;const PPCContext caller=ctx;
  __imp__sub_823ED2E0(ctx,base);
  const auto count=Read(base,page+0xB8);
  for(uint32_t k=0;k<count && k<5;++k) {
    if(Read(base,page+0xC4+k*4)!=0x8ADu+kTackleArt) continue;
    PPCContext query=caller;const auto save=Inventory(query,base);
    const uint8_t button=save ? base[save] : 2;
    const uint32_t text=caller.r1.u32-0x100;
    const uint8_t row[5]={'3','4','5',button<=8 ? kButtonGlyph[button] : uint8_t(' '),0};
    std::memcpy(base+text,row,sizeof row);
    for(const auto table:kMartialRowWidgets) {
      const auto widget=Read(base,page+Read(base,table+k*4)*4);if(!widget) continue;
      const auto holder=Read(base,widget+0x10);const auto label=holder ? Read(base,holder) : 0;if(!label) continue;
      PPCContext set=caller;set.r1.u64=caller.r1.u32-0x200;set.r3.u64=label;set.r4.u64=text;set.r5.u64=1;
      rex::runtime::ResolveIndirectFunction(Read(base,Read(base,label)+8))(set,base);
    }
  }
}
// Native subweapon awards already include Master Ring and the game's rate.
// Add exactly 20% of the awarded delta, carrying fractions per subweapon.
REX_EXTERN(sub_8245D008) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_8245D008);
  const auto handle=ctx.r3.u32,type=ctx.r4.u32,local=ctx.r5.u32;
  const auto owner=Entity(base,handle),player=PlayerComponent(base,owner);
  // Mastery lives in this machine's save: only for this machine's Nathan.
  const bool nathan=player && Read(base,player)==kVtable && type==1 && local<50 && LocalPlayer(base,player);
  const auto save=nathan?Inventory(ctx,base):0,address=save?save+MasteryOffset(local):0;
  const auto before=address?Read(base,address):0;
  __imp__sub_8245D008(ctx,base);
  if(!address) return;
  const auto s=Load(base,player);const auto after=Read(base,address);
  if(s.action!=kActionPluto || s.attribute!=2 || !ActiveProgress(base,player,s) || after<=before) return;
  const unsigned scaled=after-before+base[player+kMasteryCarry+local];
  const auto bonus=scaled/5;base[player+kMasteryCarry+local]=scaled%5;
  Write(base,address,std::min(99999u,after+bonus));
}

// Generic row lookup: only the Nathan currently inside its native input/state
// update can receive a discounted copy. Shared tables and other players stay
// immutable; each subweapon owns a stable allocation-local 70-byte record.
REX_EXTERN(sub_8246D8E8) {
  HOD_PASS_IF_OFF(kNathan, __imp__sub_8246D8E8);
  const auto row_size=ctx.r6.u32,index=ctx.r5.u32;
  __imp__sub_8246D8E8(ctx,base);const auto row=ctx.r3.u32;
  if(row_size!=70 || index>=50 || !row)return;
  const auto manager=Read(base,0x8291D9F0);if(!manager)return;
  const auto first=Read(base,manager+0xAC),end=Read(base,manager+0xB0);
  if(!first || end<first || end-first>65536*16)return;
  for(auto at=first;at<end;at+=16) {
    const auto owner=Read(base,at+4);if(!owner || !(Read(base,owner+8)&2))continue;
    const auto player=PlayerComponent(base,owner);
    if(!player || Read(base,player)!=kVtable || !Read(base,player+kAllState+176) || !ActivePluto(base,player,5))continue;
    const auto copy=player+4096+index*70;std::memcpy(base+copy,base+row,70);
    const unsigned cost=unsigned(base[copy+14]<<8|base[copy+15]),discounted=(cost+1)/2;
    base[copy+14]=uint8_t(discounted>>8);base[copy+15]=uint8_t(discounted);ctx.r3.u64=copy;return;
  }
}

// ---- Handlers in the shared chains (core/runtime/hod_hooks.h) -------------
// Orders: docs/HOOKS.md. Nathan's draw scope is outermost so his palette
// covers the whole owner draw; his collider handler is innermost so tagged
// colliders of other mods are taken first.
HOD_HOOK(kSpawnEvent, kNathan, 10, SpawnEventHandler);
HOD_HOOK(kColliderPrepare, kNathan, 10, ColliderPrepareHandler);
HOD_HOOK(kColliderAttack, kNathan, 30, ColliderAttack);
HOD_HOOK(kOwnerDraw, kNathan, 10, OwnerDraw);
HOD_HOOK(kPhysicalDefense, kNathan, 10, PhysicalDefense);
HOD_HOOK(kStatusSummary, kNathan, 10, StatusSummary);
HOD_HOOK(kIncomingDamage, kNathan, 20, IncomingDamage);
HOD_HOOK(kAttackValue, kNathan, 20, AttackValue);
