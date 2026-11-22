#pragma once
// Pool of moving DSS objects kept in Nathan's own allocation: shots, thrown
// bombs, orbiting shields and familiars. Each draws through his body sprite
// and deals damage by spawning HoD's normal short-lived attack rectangles, so
// enemy defenses, status, feedback and kill credit all stay native.
#include "nathan_uranus_guest.h"
namespace harmony::nathan {
enum ProjectileKind : uint32_t {kProjNone,kProjShot,kProjArc,kProjBlast,kProjOrbit,kProjFamiliar,kProjPuff,kProjCrash,kProjCrashOrbit,kProjRock,kProjHoming,kProjSticky,kProjField,kProjGround,kProjAllFamiliar,kProjAllOrbit,kProjSpawner};
constexpr unsigned kProjData=1728,kProjCount=16,kProjBytes=64;
constexpr unsigned kProjControl=kProjData+kProjCount*kProjBytes;
static_assert(kProjControl+64==2816 && kSize>=4096);
constexpr unsigned kFxLookupSprite=2816,kFxResource=3008,kAllState=3136,kShadowHistory=3328;
constexpr uint32_t kDieOnHit=1,kWasHit=2,kFaceLeft=4;
constexpr uint32_t kAttackButton=0x20,kLeftButton=1,kRightButton=2,kUpButton=4,kDownButton=8;
// Animation identities are independent of OPD frame indices. All timelines
// use original CotM ticks, including nonuniform bat wing/attack timings.
enum ProjectileArt : uint32_t {kArtDiana,kArtJupiter,kArtBomb,kArtBlast,kArtBat,kArtBatAttack,kArtBatFire,kArtImpact,kArtCrashKnife,kArtCrashAxe,kArtCrashHoly,kArtCrashCross,kArtCrashRock,kArtCrashBible,kArtCrashJavelin};
template<size_t N> inline unsigned DssFrame(const DssPose (&poses)[N],float age,bool loop=true) {
  unsigned tick=unsigned(std::max(0.0f,age)*kCotmHz),total=0;for(auto p:poses)total+=p.ticks;
  if(loop && total)tick%=total;
  for(auto p:poses){if(tick<p.ticks)return p.frame;tick-=p.ticks;}
  return poses[N-1].frame;
}
template<size_t N> constexpr float DssSeconds(const DssPose (&poses)[N]) {unsigned total=0;for(auto p:poses)total+=p.ticks;return total/kCotmHz;}
inline unsigned AllSequenceFrame(unsigned sequence,float age,bool loop=true) {
  if(sequence>=std::size(kAllSequences))return 0;
  const auto s=kAllSequences[sequence];if(!s.count)return 0;
  unsigned tick=unsigned(std::max(0.0f,age)*kCotmHz);if(loop && s.ticks)tick%=s.ticks;
  for(unsigned n=0;n<s.count;++n){const auto p=kAllPoses[s.offset+n];if(tick<p.ticks)return p.frame;tick-=p.ticks;}
  return kAllPoses[s.offset+s.count-1].frame;
}
inline unsigned FxSequence(unsigned resource,unsigned phase=0){return resource>=10 && resource<101?kAllFx[resource-10][std::min(phase,15u)]:0;}
inline unsigned FxArt(unsigned resource,unsigned phase=0){return 0x80000000u|FxSequence(resource,phase);}
inline unsigned ArtFrame(unsigned art,float age) {
  if(art&0x80000000u)return AllSequenceFrame(art&0x7FFFFFFFu,age);
  switch(art) {
    case kArtJupiter:return DssFrame(kJupiterFire,age);
    case kArtBomb:return DssFrame(kApolloBomb,age);
    case kArtBlast:return DssFrame(kApolloBlast,age,false);
    case kArtBat:return DssFrame(kSaturnBat,age);
    case kArtBatAttack:return DssFrame(kSaturnBatAttack,age,false);
    case kArtBatFire:return DssFrame(kSaturnFire,age);
    case kArtCrashKnife:return DssFrame(kCrashKnife,age);
    case kArtCrashAxe:return DssFrame(kCrashAxe,age);
    case kArtCrashHoly:return DssFrame(kCrashHoly,age);
    case kArtCrashCross:return DssFrame(kCrashCross,age);
    case kArtCrashRock:return DssFrame(kCrashRock,age);
    case kArtCrashBible:return DssFrame(kCrashBible,age);
    case kArtCrashJavelin:return DssFrame(kCrashJavelin,age);
    case kArtImpact:return DssFrame(kFireImpact,age,false);
    default:return DssFrame(kDianaFire,age);
  }
}

struct Projectile {
  uint32_t kind=kProjNone;
  float x=0,y=0,vx=0,vy=0,age=0,life=0,next_hit=0,period=0,power=0,angle=0;
  uint32_t element=0,half_size=0,first=0,timing=0,flags=0;   // timing reserved for a native actor handle
  float HalfWidth() const {return float(half_size>>16);}
  float HalfHeight() const {return float(half_size&0xFFFF);}
  uint32_t Frame() const {
    return ArtFrame(first,age);
  }
};
inline uint32_t ProjAddress(uint32_t player,unsigned i) {return player+kProjData+i*kProjBytes;}
inline Projectile LoadProjectile(uint8_t* base,uint32_t a) {
  Projectile p;
  p.kind=Read(base,a);p.x=Float(base,a+4);p.y=Float(base,a+8);p.vx=Float(base,a+12);p.vy=Float(base,a+16);
  p.age=Float(base,a+20);p.life=Float(base,a+24);p.next_hit=Float(base,a+28);p.period=Float(base,a+32);
  p.power=Float(base,a+36);p.angle=Float(base,a+40);p.element=Read(base,a+44);p.half_size=Read(base,a+48);
  p.first=Read(base,a+52);p.timing=Read(base,a+56);p.flags=Read(base,a+60);
  return p;
}
inline void SaveProjectile(uint8_t* base,uint32_t a,const Projectile& p) {
  Write(base,a,p.kind);Float(base,a+4,p.x);Float(base,a+8,p.y);Float(base,a+12,p.vx);Float(base,a+16,p.vy);
  Float(base,a+20,p.age);Float(base,a+24,p.life);Float(base,a+28,p.next_hit);Float(base,a+32,p.period);
  Float(base,a+36,p.power);Float(base,a+40,p.angle);Write(base,a+44,p.element);Write(base,a+48,p.half_size);
  Write(base,a+52,p.first);Write(base,a+56,p.timing);Write(base,a+60,p.flags);
}
// Clears the pool and everything after it, except the online block (kNet):
// a copy keeps its owner's announced pair through death and revive.
inline void ResetProjectiles(uint8_t* base,uint32_t player) {
  std::memset(base+player+kProjData,0,kNet-kProjData);
  std::memset(base+player+kNet+kNetBytes,0,kSize-kNet-kNetBytes);
}
inline bool ProjectileRoom(uint8_t* base,uint32_t player,unsigned required=1) {
  unsigned count=0;for(unsigned i=0;i<kProjCount;++i)count+=!Read(base,ProjAddress(player,i));
  return count>=required;
}
inline bool AddProjectile(uint8_t* base,uint32_t player,Projectile p) {
  for(unsigned i=0;i<kProjCount;++i) if(!Read(base,ProjAddress(player,i))) {
    auto gen=(Read(base,player+kProjControl+32)+1)&0xFFFFu;if(!gen)gen=1;
    Write(base,player+kProjControl+32,gen);p.flags=(p.flags&0xFFFFu)|(gen<<16);
    if(p.vx<0)p.flags|=kFaceLeft;
    SaveProjectile(base,ProjAddress(player,i),p);return true;
  }
  return false;
}
// Native facing (player vtable +0x288 reads player+0x250; 1 = left), as the
// slide uses it. The body sprite's mirror flag lags a frame behind, so casts
// made on the button press (Apollo, Item Crash) used to fire backwards.
inline float FacingSign(uint8_t* base,uint32_t owner) {
  const auto player=PlayerComponent(base,owner);
  if(player) return Read(base,player+0x250)==1 ? -1.0f : 1.0f;
  const auto body=owner ? Read(base,owner+0x2C) : 0;
  return body && base[body+0x1C] ? -1.0f : 1.0f;
}
inline uint32_t HalfSize(unsigned w,unsigned h) {return w<<16|h;}
inline float ProjectilePower(PPCContext& ctx,uint8_t* base,uint32_t player,float scale) {
  return MagicPower(ctx,base,player,scale);
}
inline bool SpendMp(uint8_t* base,uint32_t player,float cost) {
  if(replaying) return true;  // a copy's casts were paid on its owner's machine
  const auto stats=Read(base,player+88);
  if(!stats) return false;
  const float mp=Float(base,stats+8);
  if(mp<cost) return false;
  Float(base,stats+8,mp-cost);
  return true;
}
inline Projectile FireShot(float x,float y,float direction,float speed,float power,uint32_t element) {
  Projectile p;
  p.kind=kProjShot;p.x=x;p.y=y;p.vx=direction*speed;p.life=1.6f;p.period=4.0f/kCotmHz;p.power=power;p.element=element;
  p.half_size=HalfSize(10,10);p.first=kArtDiana;p.flags=kDieOnHit;
  return p;
}
// Diana: the paid whip swing also throws a projectile.
inline void SwingProjectile(PPCContext& ctx,uint8_t* base,uint32_t player,const DssState& s) {
  const auto owner=Owner(base,player);
  if(!owner) return;
  if(s.action==kActionMars || s.action==kActionDiana) {
    Float(base,player+kProjControl+12,0);Write(base,player+kProjControl+20,0);
  }
}
inline bool BeginItemCrash(PPCContext&,uint8_t*,uint32_t);
inline bool CastOtherApollo(PPCContext&,uint8_t*,uint32_t,DssState&);
inline void OtherMelee(PPCContext&,uint8_t*,uint32_t,const DssState&,float);
inline void ExtendedMotion(PPCContext&,uint8_t*,uint32_t,Projectile&,unsigned,const DssState&,float);
// One rising RB edge performs one paid cast. No armed/toggle state, no
// directional command, and holding RB cannot repeat after recovery ends.
inline bool DirectCast(PPCContext& ctx,uint8_t* base,uint32_t player,DssState& s) {
  const auto owner=Owner(base,player);
  if(!owner || s.cast_remaining>0 || !s.Direct() || s.attribute>=10)return false;
  if(s.action==kActionPluto) {
    if(!BeginItemCrash(ctx,base,player))return false;
    s.cast_remaining=.5f;Write(base,player+kProjControl+52,1);
  } else if(s.attribute!=0) {
    return CastOtherApollo(ctx,base,player,s);
  } else {
    if(!ProjectileRoom(base,player) || !SpendMp(base,player,s.Cost()))return false;
    const float dir=FacingSign(base,owner);Projectile p;
    p.kind=kProjArc;p.x=Float(base,owner+0x8D4)+dir*16;p.y=Float(base,owner+0x8D8)-30;
    p.vx=dir*(2.5f*kCotmHz);p.vy=-5*kCotmHz;p.life=1.5f;p.power=ProjectilePower(ctx,base,player,1.5f);p.element=s.Element();
    p.half_size=HalfSize(10,10);p.first=kArtBomb;AddProjectile(base,player,p);
    s.cast_remaining=DssSeconds(kApolloBody);Write(base,player+kProjControl+52,0);
  }
  s.enabled=1;s.pulse_time=0;s.fade_remaining=0;
  Float(base,player+kProjControl+48,s.cast_remaining);return true;
}
inline bool OwnedKind(uint8_t* base,uint32_t player,uint32_t kind) {
  for(unsigned i=0;i<kProjCount;++i) if(Read(base,ProjAddress(player,i))==kind) return true;
  return false;
}
// Saturn: the familiar shoots when Nathan attacks; each shot is paid for.
inline void SaturnShot(PPCContext& ctx,uint8_t* base,uint32_t player,const DssState& s,uint32_t pressed,float dt) {
  const auto c=player+kProjControl+8;
  if(!(dt>0 && dt<=.1f)) dt=1.0f/60;
  const float cooldown=std::fmax(0.0f,Float(base,c)-dt);
  Float(base,c,cooldown);
  const auto owner=Owner(base,player);
  if(!owner || s.action!=kActionSaturn || !s.enabled || s.attribute!=0 || s.cast_remaining>0 || cooldown>0 || !(pressed&kAttackButton)) return;
  for(unsigned i=0;i<kProjCount;++i) {
    const auto p=LoadProjectile(base,ProjAddress(player,i));
    if(p.kind!=kProjFamiliar) continue;
    if(ProjectileRoom(base,player) && (replaying || Float(base,Read(base,player+88)+8)>=s.Cost())) {
      auto bat=p;bat.first=kArtBatAttack;bat.age=0;bat.flags|=8;SaveProjectile(base,ProjAddress(player,i),bat);
      Float(base,c,32.0f/kCotmHz);
    }
    return;
  }
}
inline void Puff(Projectile& p) {
  if(p.first>=kArtCrashKnife){p.kind=kProjNone;return;}
  p.kind=kProjPuff;p.age=0;p.life=.33f;p.vx=p.vy=0;p.first=kArtImpact;p.flags&=0xFFFF0004u;p.period=0;
}
inline void Blast(Projectile& p) {
  p.kind=kProjBlast;p.age=0;p.life=20.0f/kCotmHz;p.vx=p.vy=0;p.first=kArtBlast;p.flags&=0xFFFF0004u;
  p.period=1;p.next_hit=0;p.half_size=HalfSize(16,16);
}
// CotM's four shared subweapons retain their recognizable Item Crashes.
// Bible, Ricochet Rock and Javelin are explicit HoD extensions. The selected
// normal B slot chooses the family; classic Simon variants use that family.
inline unsigned CrashFamily(uint32_t item) {
  if(item>=0x60F && item<=0x614)return item-0x60F;
  switch(item){case 0x61B:return 6;case 0x61C:return 3;case 0x61D:return 2;case 0x61E:return 1;case 0x61F:return 0;default:return 7;}
}
inline bool BeginItemCrash(PPCContext& ctx,uint8_t* base,uint32_t player) {
  const auto owner=Owner(base,player),eq=owner?Read(base,owner+0x9C8):0;
  const auto family=eq?CrashFamily(Read(base,eq+8*4)):7;
  if(family>=7 || !ProjectileRoom(base,player,9) || OwnedKind(base,player,kProjCrash) || !SpendMp(base,player,kCrashCost[family]))return false;
  Projectile p;p.kind=kProjCrash;p.x=Float(base,owner+0x8D4);p.y=Float(base,owner+0x8D8);
  p.life=family==0?2:family==2?2.5f:.05f;p.first=family;p.power=ProjectilePower(ctx,base,player,1.5f);
  p.vx=FacingSign(base,owner);AddProjectile(base,player,p);return true;
}
inline void CrashWave(uint8_t* base,uint32_t player,Projectile& controller) {
  const auto f=controller.first;const bool rapid=f==0 || f==2;
  if(controller.next_hit>controller.age)return;
  if(!rapid && controller.next_hit>0)return;
  const auto wave=unsigned(controller.angle++);
  controller.next_hit=controller.age+(f==0?4/kCotmHz:.3f);
  const unsigned count=f==0?1:f==2?3:f==3?3:f==5?4:f==6?5:8;
  for(unsigned i=0;i<count;++i) {
    if(!ProjectileRoom(base,player))break;
    Projectile p;p.kind=kProjShot;p.life=1.5f;p.period=4/kCotmHz;p.power=controller.power;
    p.x=controller.x;p.y=controller.y-26;p.vx=controller.vx*240;p.half_size=HalfSize(12,8);
    switch(f) {
      case 0:p.first=kArtCrashKnife;p.vx=controller.vx*8*kCotmHz;p.y+=float(int(wave%3)-1)*6;p.life=.7f;p.flags=kDieOnHit;p.half_size=HalfSize(17,4);break;
      case 1: {const float a=i*6.283185307f/count;p.first=kArtCrashAxe;p.vx=std::cos(a)*150;p.vy=std::sin(a)*150;p.half_size=HalfSize(14,14);break;}
      case 2:p.first=kArtCrashHoly;p.x=controller.x-100+float((i*79+wave*29)%200);p.y=controller.y-120;p.vx=0;p.vy=190;p.life=.7f;p.element=0x800;p.half_size=HalfSize(12,14);break;
      case 3:p.first=kArtCrashCross;p.x+=float(int(i)-1)*70;p.y-=20;p.vx=0;p.vy=-55;p.life=2;p.flags=16;p.element=0x800;p.half_size=HalfSize(22,22);break;
      case 4: {const float a=i*6.283185307f/count;p.kind=kProjRock;p.first=kArtCrashRock;p.vx=std::cos(a)*200;p.vy=std::sin(a)*200;p.life=2.5f;p.angle=controller.y;p.half_size=HalfSize(12,12);break;}
      case 5:p.kind=kProjCrashOrbit;p.first=kArtCrashBible;p.vx=70;p.angle=i*6.283185307f/count;p.life=2.5f;p.element=0x800;p.half_size=HalfSize(12,12);break;
      case 6:p.first=kArtCrashJavelin;p.y+=float(int(i)-2)*18;p.vx=controller.vx*280;p.life=1;p.half_size=HalfSize(48,6);break;
    }
    AddProjectile(base,player,p);
  }
}
inline bool MarsSwing(uint8_t* base,uint32_t player,const DssState& s) {
  return Read(base,player+584)<191 && s.action==kActionMars && s.paid_swing && ActiveDss(base,player,s) && WhipState(base,player) && Alive(base,player);
}
inline unsigned MarsPose(uint8_t* base,uint32_t player) {
  const auto motion=Read(base,player+584);return motion==188?1:motion==189?2:0;
}
inline unsigned MarsBodyFrame(uint8_t* base,uint32_t player,unsigned canonical) {
  const auto special=Float(base,player+kProjControl+48);const auto state=Load(base,player);
  const bool crash=Read(base,player+kProjControl+52)!=0;
  if(special>0 && Alive(base,player) && ActiveDss(base,player,state) && state.action==(crash?kActionPluto:kActionApollo))return Read(base,player+kProjControl+52)?DssFrame(kCrashBody,.5f-special,false):DssFrame(kApolloBody,DssSeconds(kApolloBody)-special,false);
  if(Load(base,player).action==kActionMars && Load(base,player).attribute==6 && Read(base,player+kAllState+132))return AllSequenceFrame(kAllBody[112-94][0],0,false);
  if(!MarsSwing(base,player,Load(base,player)))return canonical;
  const auto age=Float(base,player+kProjControl+12);
  if(Load(base,player).attribute>0) {const auto a=Load(base,player).attribute;constexpr unsigned rows[]={91,94,97,100,103,106,109,115,118,121};return AllSequenceFrame(kAllBody[rows[a]+MarsPose(base,player)-94][0],age,false);}
  switch(MarsPose(base,player)) {
    case 1:return DssFrame(kMarsBody1,age,false);
    case 2:return DssFrame(kMarsBody2,age,false);
    default:return DssFrame(kMarsBody0,age,false);
  }
}
inline unsigned MarsEffectFrame(uint8_t* base,uint32_t player) {
  const auto age=Float(base,player+kProjControl+12);
  const auto s=Load(base,player);if(s.attribute==6){const auto level=std::min(3u,unsigned(Float(base,player+kAllState+80)/.75f));if(Read(base,player+kAllState+132))return kWindChargeFrames[level];const unsigned t=unsigned(age*kCotmHz),phase=t<14?0:t<20?1:t<28?2:3;const auto pose=MarsPose(base,player);return kWindSlashes[pose==1?2:pose==2?1:0][level][phase];}
  if(s.attribute>0) {const auto pose=MarsPose(base,player);return AllSequenceFrame(FxSequence(30+s.attribute,s.attribute==9?(pose==1?3:pose==2?2:1):(pose==1?2:pose==2?1:0)),age,false);}
  switch(MarsPose(base,player)) {
    case 1:return DssFrame(kMarsFire1,age,false);
    case 2:return DssFrame(kMarsFire2,age,false);
    default:return DssFrame(kMarsFire0,age,false);
  }
}
inline void UpdateSalamander(PPCContext& ctx,uint8_t* base,uint32_t player,const DssState& s,float dt) {
  if(!(dt>0 && dt<=.1f))dt=1.0f/60;
  Float(base,player+kProjControl+48,std::fmax(0.0f,Float(base,player+kProjControl+48)-dt));
  Float(base,player+kProjControl+24,std::fmax(0.0f,Float(base,player+kProjControl+24)-dt));
  const bool diana=s.action==kActionDiana && s.paid_swing && ActiveDss(base,player,s) && WhipState(base,player);
  if(s.attribute>0 && (MarsSwing(base,player,s) || diana)){OtherMelee(ctx,base,player,s,dt);return;}
  if(!MarsSwing(base,player,s) && !diana)return;
  const auto age=Float(base,player+kProjControl+12)+dt;Float(base,player+kProjControl+12,age);
  if(age>=16.0f/kCotmHz && !Read(base,player+kProjControl+20)) {
    const auto owner=Owner(base,player);const float dir=FacingSign(base,owner);
    const bool crouch=MarsPose(base,player)==1;
    if(diana) {
      auto fire=FireShot(Float(base,owner+0x8D4)+dir*48,Float(base,owner+0x8D8)-(crouch?14:26),dir,2*kCotmHz,
        ProjectilePower(ctx,base,player,1),s.Element());
      if(kDianaPassThrough[0])fire.flags&=~kDieOnHit; // still stopped by walls
      AddProjectile(base,player,fire);
      Write(base,player+kProjControl+20,1);return;
    }
    NativeHit(ctx,base,player,Float(base,owner+0x8D4)+dir*20,Float(base,owner+0x8D8)-(crouch?25:40),40,24,
      MeleePower(ctx,base,player,1.10f),kFireDamage,0xFF,0,kProjTag,0xFFFFFFFFu);
    Write(base,player+kProjControl+20,1);
  }
}
// Native point-vs-stage query used by the game's own projectile updater
// 824823A0 -> 823C2340. It handles solid/slope tiles and dynamic stage shapes.
inline bool SolidTerrain(PPCContext& ctx,uint8_t* base,float x,float y) {
  if(!Read(base,0x8291D918))return false;
  return NativeQuery(ctx,base,0x823C2340,uint32_t(int32_t(std::floor(x))),uint32_t(int32_t(std::floor(y))))!=0;
}
inline bool SweepTerrain(PPCContext& ctx,uint8_t* base,float oldx,float oldy,float& x,float& y,float hw,float hh) {
  const float dx=x-oldx,dy=y-oldy;const unsigned steps=std::max(1u,unsigned(std::ceil(std::max(std::abs(dx),std::abs(dy))/4)));
  float safe_x=oldx,safe_y=oldy;
  for(unsigned n=1;n<=steps;++n) {
    const float nx=oldx+dx*n/steps,ny=oldy+dy*n/steps;
    if(SolidTerrain(ctx,base,nx,ny) || SolidTerrain(ctx,base,nx-hw,ny) || SolidTerrain(ctx,base,nx+hw,ny) ||
       SolidTerrain(ctx,base,nx,ny-hh) || SolidTerrain(ctx,base,nx,ny+hh)) {x=safe_x;y=safe_y;return true;}
    safe_x=nx;safe_y=ny;
  }
  return false;
}
inline void UpdateProjectiles(PPCContext& ctx,uint8_t* base,uint32_t player,const DssState& s,float dt) {
  UpdateSalamander(ctx,base,player,s,dt);
  const auto owner=Owner(base,player);
  if(!owner) return;
  if(!Alive(base,player)) {ResetProjectiles(base,player);return;}
  if(!(dt>0 && dt<=.1f)) dt=1.0f/60;
  const float ox=Float(base,owner+0x8D4),oy=Float(base,owner+0x8D8),facing=FacingSign(base,owner);
  const bool shield=s.cast_remaining<=0 && ActiveDss(base,player,s) && s.action==kActionJupiter && s.attribute==0;
  const bool familiar=s.cast_remaining<=0 && ActiveDss(base,player,s) && s.action==kActionSaturn && s.attribute==0;
  if(shield && !OwnedKind(base,player,kProjOrbit)) {
    for(unsigned i=0;i<2;++i) {
      Projectile p;
      p.kind=kProjOrbit;p.x=ox;p.y=oy-26;p.period=16.0f/kCotmHz;p.power=ProjectilePower(ctx,base,player,1);p.angle=float(i)*3.14159265f;
      p.element=s.Element();p.half_size=HalfSize(8,8);p.first=kArtJupiter;
      AddProjectile(base,player,p);
    }
  }
  if(familiar && !OwnedKind(base,player,kProjFamiliar)) {
    Projectile p;
    p.kind=kProjFamiliar;p.x=ox-facing*26;p.y=oy-44;p.first=kArtBat;
    AddProjectile(base,player,p);
  }
  for(unsigned i=0;i<kProjCount;++i) {
    const auto a=ProjAddress(player,i);
    auto p=LoadProjectile(base,a);
    if(p.kind==kProjNone) continue;
    if((p.kind==kProjOrbit && !shield) || (p.kind==kProjFamiliar && !familiar)) {Write(base,a,kProjNone);continue;}
    p.age+=dt;
    if(p.flags&kWasHit) {
      p.flags&=~kWasHit;
      if(p.kind==kProjSpawner && p.timing==1) p.age=std::fmax(p.age,.75f); // Apollo + Serpent: the orb bursts into shards on contact
      else if(p.flags&kDieOnHit) {
        if(p.kind==kProjArc) Blast(p); else Puff(p);
        SaveProjectile(base,a,p);
        continue;
      }
    }
    ExtendedMotion(ctx,base,player,p,i,s,dt);
    if(p.kind==kProjNone){SaveProjectile(base,a,p);continue;}
    switch(p.kind) {
      case kProjArc:
        p.vy=std::fmin(8*kCotmHz,p.vy+.25f*kCotmHz*kCotmHz*dt);
        {const float x=p.x,y=p.y;p.x+=p.vx*dt;p.y+=p.vy*dt;
        if(SweepTerrain(ctx,base,x,y,p.x,p.y,6,6)){Blast(p);Sound(ctx,base,player,322);}}
        break;
      case kProjShot: {
        const float x=p.x,y=p.y;p.x+=p.vx*dt;p.y+=p.vy*dt;
        if((p.first==kArtDiana || p.first==kArtBatFire || (p.flags&kDieOnHit)) &&
          SweepTerrain(ctx,base,x,y,p.x,p.y,std::min(8.0f,p.HalfWidth()),std::min(6.0f,p.HalfHeight())))Puff(p);
        break;
      }
      case kProjOrbit: {
        p.angle+=6.283185307f/256*kCotmHz*dt;
        const unsigned tick=unsigned(p.age*kCotmHz)%512;
        const float radius=24+float(tick<256?tick:512-tick)/16;
        const float blend=1-std::pow(.875f,dt*kCotmHz);
        p.x+=(ox+std::cos(p.angle)*radius-p.x)*blend;p.y+=(oy-26+std::sin(p.angle)*radius-p.y)*blend;break;
      }
      case kProjFamiliar: {
        if(p.first==kArtBatAttack && p.age>=32.0f/kCotmHz){p.first=kArtBat;p.age=0;}
        p.flags=(p.flags&~kFaceLeft)|(facing<0?kFaceLeft:0);
        constexpr float offsets[16][2]={{-36,-36},{-24,-48},{-48,-24},{-12,-12},{-24,-36},{-24,-12},{-36,-48},{-12,-24},{-48,-48},{-36,-12},{-12,-36},{-48,-12},{-36,-24},{-12,-48},{-48,-36},{-24,-24}};
        p.angle+=dt;const auto n=unsigned(p.angle*kCotmHz/64)%16;
        const float blend=1-std::pow(31.0f/32,dt*kCotmHz);
        p.x+=(ox+facing*offsets[n][0]-p.x)*blend;p.y+=(oy+offsets[n][1]-p.y)*blend;
        if((p.flags&8) && p.age>=8.0f/kCotmHz) {
          p.flags&=~8u;
          if(ProjectileRoom(base,player) && SpendMp(base,player,s.Cost())) {
            auto shot=FireShot(p.x,p.y,facing,3*kCotmHz,ProjectilePower(ctx,base,player,.5f),s.Element());
            shot.first=kArtBatFire;shot.half_size=HalfSize(7,7);if(kSaturnPassThrough[0])shot.flags&=~kDieOnHit;AddProjectile(base,player,shot);
          }
        }
        break;
      }
      case kProjCrash:CrashWave(base,player,p);break;
      case kProjCrashOrbit:p.angle+=4*dt;p.x=ox+std::cos(p.angle)*p.vx;p.y=oy-26+std::sin(p.angle)*p.vx;break;
      case kProjRock:
        {float x=p.x+p.vx*dt,y=p.y;
        if(SweepTerrain(ctx,base,p.x,p.y,x,y,10,10))p.vx=-p.vx;p.x=x;
        x=p.x;y=p.y+p.vy*dt;
        if(SweepTerrain(ctx,base,p.x,p.y,x,y,10,10))p.vy=-p.vy;p.y=y;}
        break;
      default: break;
    }
    if(p.life>0 && p.age>=p.life) {
      if(p.kind==kProjArc) {Blast(p);Sound(ctx,base,player,322);SaveProjectile(base,a,p);continue;}
      Write(base,a,kProjNone);
      continue;
    }
    if(p.period>0) {
      p.next_hit-=dt;
      if(p.next_hit<=0) {
        p.next_hit=p.period;
        float hx=p.x,hy=p.y;int hw=int(p.HalfWidth()),hh=int(p.HalfHeight());const auto drawn=p.Frame();
        if(drawn>=kAllDssFirst && drawn<kAllDssEnd){const auto b=kAllBounds[drawn-kAllDssFirst];const float facing=p.flags&kFaceLeft?-1:1;
          hx+=(b[0]+b[2])*.5f*facing;hy+=(b[1]+b[3])*.5f;hw=std::min(160,std::max(1,(b[2]-b[0])/2));hh=std::min(90,std::max(1,(b[3]-b[1])/2));}
        NativeHit(ctx,base,player,hx,hy,hw,hh,p.power,p.element,0xFF,p.flags>>16,kProjTag,i);
      }
    }
    SaveProjectile(base,a,p);
  }
}
inline void MarkProjectileHit(uint8_t* base,uint32_t player,uint32_t slot,uint32_t generation,uint32_t target=0) {
  if(slot>=kProjCount) return;
  const auto a=ProjAddress(player,slot);
  if(Read(base,a) && (Read(base,a+60)>>16)==generation) {if(Read(base,a+60)&32){auto p=LoadProjectile(base,a);p.kind=kProjSticky;p.timing=target;p.flags&=~(kWasHit|kDieOnHit);p.vx=p.vy=0;SaveProjectile(base,a,p);}else Write(base,a+60,Read(base,a+60)|kWasHit);}
}
}

#include "nathan_dss_combinations.h"
