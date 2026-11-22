#pragma once
#include <limits>
#include "hod_guest.h"  // hod::IsHurtRecord (core/runtime, header only)
#include "hurt_record_guest.h"
namespace harmony::nathan {
// Enemy hurt boxes from the exe's registration record in guest memory
// (hurt_record_guest.h; its address is in Nathan's player block). Walking the
// collision manager's lists from here raced the threads rebuilding them, and
// the old 0x10 test missed ordinary bodies (40000009) and sleeping enemies
// (40000008: the Treant and Man-Eating Plant until approached; runs 217-219).
// The list walk is kept only for the frame after a reset clears the address.
static_assert(kSummonContacts+kSummonContactCount*kSummonContactBytes<=hurt_record::kNathanPointer &&
              hurt_record::kNathanPointer+4<=kSize,"hurt record pointer overlaps Nathan's state");
struct DssTarget {uint32_t handle=0;float x=0,y=0;};
inline DssTarget FindDssTarget(uint8_t* base,uint32_t player,float x,float y,uint32_t wanted=0) {
  DssTarget best;float distance=400*400;
  const auto record=Read(base,player+hurt_record::kNathanPointer);
  if(hurt_record::Valid(base,record)) {
    hurt_record::ForEachFresh(base,record,[&](const hurt_record::Box& b){
      if(wanted && wanted!=b.handle)return;
      const auto enemy=Entity(base,b.handle);
      if(!enemy || !(Read(base,enemy+8)&4) || base[enemy+23] || !std::isfinite(b.x) || !std::isfinite(b.y))return;
      const float d=(b.x-x)*(b.x-x)+(b.y-y)*(b.y-y);if(d<distance){distance=d;best={b.handle,b.x,b.y};}
    });
    return best;
  }
  const auto manager=Read(base,0x8291D918);
  if(!manager)return best;const auto first=Read(base,manager+4),end=Read(base,manager+8);
  if(!first || end<first || end-first>128*4)return best;
  for(auto at=first;at<end;at+=4) {
    const auto level=Read(base,at);if(!level)continue;
    for(unsigned group:{32u,48u,64u}) {
      const auto begin=Read(base,level+group+4),last=Read(base,level+group+8);
      if(!begin || last<begin || last-begin>8192*4)continue;
      for(auto i=begin;i<last;i+=4) {
        const auto r=Read(base,i);if(!r || !hod::IsHurtRecord(Read(base,r+4)))continue;
        const auto handle=Read(base,r+20),enemy=Entity(base,handle),shape=Read(base,r+12);
        if(!enemy || !(Read(base,enemy+8)&4) || base[enemy+23] || !shape || Read(base,shape+4)!=1 || (wanted && wanted!=handle))continue;
        const float tx=(Float(base,shape+8)+Float(base,shape+16))*.5f,ty=(Float(base,shape+12)+Float(base,shape+20))*.5f;
        if(!std::isfinite(tx)||!std::isfinite(ty))continue;
        const float d=(tx-x)*(tx-x)+(ty-y)*(ty-y);if(d<distance){distance=d;best={handle,tx,ty};}
      }
    }
  }
  return best;
}
inline Projectile DssShot(float x,float y,float vx,float vy,unsigned resource,unsigned phase,float power,uint32_t element,float life=1.5f) {
  Projectile p;p.kind=kProjShot;p.x=x;p.y=y;p.vx=vx;p.vy=vy;p.life=life;p.period=4/kCotmHz;p.power=power;p.element=element;
  p.first=FxArt(resource,phase);p.half_size=HalfSize(8,8);p.flags=kDieOnHit;return p;
}
inline bool CastOtherApollo(PPCContext& ctx,uint8_t* base,uint32_t player,DssState& s) {
  constexpr unsigned counts[]={1,1,1,5,6,1,1,1,8,1};
  const auto owner=Owner(base,player);const auto a=s.attribute;
  if(!owner || a>=10 || !ProjectileRoom(base,player,counts[a]) || !SpendMp(base,player,s.Cost()))return false;
  const float x=Float(base,owner+0x8D4),y=Float(base,owner+0x8D8),dir=FacingSign(base,owner),power=ProjectilePower(ctx,base,player,1);
  for(unsigned i=0;i<counts[a];++i) {
    auto p=DssShot(x+dir*18,y-26,dir*120,0,50+a,0,power,s.Element(),2);
    switch(a) {
      case 1:p.kind=kProjSpawner;p.vx=dir*65;p.vy=-110;p.period=.2f;p.angle=0;p.timing=1;p.life=2;break;
      case 2:p.flags=0;p.vx=dir*220;p.timing=2;p.life=1.7f;break;
      case 3:p.kind=kProjField;p.x=x+dir*(18+24*i);p.y=y;p.vx=0;p.next_hit=.15f;p.period=1;p.life=.7f;p.power=power*1.3f;break;
      case 4:p.x=x-100+40*i;p.y=y-140-12*(i%2);p.vx=dir*20;p.vy=240;p.life=1;p.power=power*1.3f;break;
      case 5:p.kind=kProjField;p.vx=0;p.life=4;p.period=.3f;p.power=power*.25f;p.flags=0;break;
      case 6:p.kind=kProjSpawner;p.timing=6;p.vx=dir*25;p.period=.3f;p.life=3;p.power=power*.5f;p.flags=0;break;
      case 7:p.kind=kProjHoming;p.life=3;p.power=power*.6f;p.flags=32;p.period=.25f;break;
      case 8:p.x=x-100+28*i;p.y=y-140;p.vx=dir*50;p.vy=240;p.life=1;p.power=power*1.4f;break;
      case 9:p.kind=kProjHoming;p.vx=dir*90;p.life=4;p.power=power*4;p.flags=kDieOnHit;break;
    }
    if(kApolloPassThrough[a])p.flags&=~kDieOnHit;
    AddProjectile(base,player,p);
  }
  s.enabled=1;s.pulse_time=0;s.fade_remaining=0;s.cast_remaining=DssSeconds(kApolloBody);
  Float(base,player+kProjControl+48,s.cast_remaining);Write(base,player+kProjControl+52,0);return true;
}
inline void OtherMelee(PPCContext& ctx,uint8_t* base,uint32_t player,const DssState& s,float dt) {
  const auto owner=Owner(base,player);if(!owner)return;
  const auto a=s.attribute;const float dir=FacingSign(base,owner),x=Float(base,owner+0x8D4),y=Float(base,owner+0x8D8);
  const float elapsed=Float(base,player+kProjControl+12)+dt;Float(base,player+kProjControl+12,elapsed);
  unsigned stage=Read(base,player+kProjControl+20);
  if(s.action==kActionMars) {
    const unsigned threshold=a==1?6:a==3?48:a==9?80:16;
    const unsigned hits=a==5?2:a==7?4:1;
    if(a==7 && stage>0 && Read(base,player+kAllState+140)<=stage)return;
    if(stage>=hits || elapsed<(threshold+stage*(a==7?14:7))/kCotmHz)return;
    Write(base,player+kProjControl+20,stage+1);
    const float power=MeleePower(ctx,base,player,kMarsPower[a]);
    if(a==9) {auto p=DssShot(x+dir*30,y-26,dir*6*kCotmHz,0,39,0,power,s.Element(),1);AddProjectile(base,player,p);return;}
    const float charge=a==6?1+std::min(3.0f,Float(base,player+kAllState+80)):1;
    const float reach=a==2?70:a==8?105:a==6?45*charge:40;
    NativeHit(ctx,base,player,x+dir*reach*.5f,y-(MarsPose(base,player)==1?20:34),int(reach*.5f),a==8?28:24,
      power*charge,s.Element(),0xFF,0,kProjTag,0xFFFFFFFFu);
    if(a==3) {NativeHit(ctx,base,player,x,y-4,160,8,power,0,0xFF,0,kProjTag,0xFFFFFFFFu);}
    return;
  }
  if(a==7 || stage || elapsed<16/kCotmHz)return;
  Write(base,player+kProjControl+20,1);
  const unsigned count=a==1||a==2||a==4?3:a==9?8:1;
  for(unsigned i=0;i<count;++i) {
    float vx=dir*120,vy=0;unsigned phase=0;
    if(count==3)vy=(float(i)-1)*45;
    // Behavior follows the user's CotM testing (2026-11-11) and the reference
    // video: which shots pass through is the generated kDianaPassThrough row.
    if(a==9){const float angle=i*6.283185307f/8;vx=std::cos(angle)*110;vy=std::sin(angle)*110;phase=2;} // tight ring of eight
    if(a==4){vx=dir*(70+35.0f*i);vy=-(150+20.0f*i);}                // rocks lobbed in arcs
    if(a==5){vx=dir*110;vy=-150;phase=3;}                           // one lobbed blob
    auto p=DssShot(x+dir*45,y-(MarsPose(base,player)==1?14:26),vx,vy,40+a,phase,ProjectilePower(ctx,base,player,a==9?2:1),s.Element(),a==1?.65f:1.5f);
    if(a==2){p.vx*=.6f;p.vy*=.6f;p.life=2;}
    if(a==3){p.kind=kProjGround;p.y=y-4;p.vx=dir*130;p.life=1.8f;}
    if(a==4)p.timing=0xB0;                                          // gravity
    if(a==5){p.timing=0xB0;p.flags|=32;p.period=8/kCotmHz;p.power*=.5f;p.life=3;} // sticks, then hits quickly
    if(a==6){p.vx=dir*300;p.power*=2;}
    if(a==8){p.kind=kProjHoming;p.life=3;p.period=.2f;p.power*=.6f;}
    if(a==9)p.life=.45f;                                            // gone after a short distance
    p.flags=kDianaPassThrough[a] ? p.flags&~kDieOnHit : p.flags|kDieOnHit;
    AddProjectile(base,player,p);
  }
}
inline void EnsureDssActor(uint8_t* base,uint32_t player,unsigned kind,unsigned attribute,unsigned art,float x,float y,float power,uint32_t element,unsigned count=1) {
  unsigned owned=0;for(unsigned i=0;i<kProjCount;++i){auto p=LoadProjectile(base,ProjAddress(player,i));owned+=p.kind==kind && p.timing==attribute;}
  for(unsigned i=owned;i<count;++i){Projectile p;p.kind=kind;p.x=x;p.y=y;p.power=power;p.element=element;p.timing=attribute;p.first=art;p.angle=6.283185307f*i/count;p.half_size=HalfSize(12,12);AddProjectile(base,player,p);}
}
inline void PlutoFrame(PPCContext&,uint8_t*,uint32_t,const DssState&,float);
inline void HolyBarrier(uint8_t*,uint32_t);
inline void AllDssFrame(PPCContext& ctx,uint8_t* base,uint32_t player,const DssState& s,uint32_t held,uint32_t pressed,float dt) {
  if(!(dt>0 && dt<=.1f))dt=1.0f/60;
  for(unsigned off:{48u,52u,56u})Float(base,player+kAllState+off,std::fmax(0.0f,Float(base,player+kAllState+off)-dt));
  const auto owner=Owner(base,player);if(!owner)return;
  const float x=Float(base,owner+0x8D4),y=Float(base,owner+0x8D8),power=ProjectilePower(ctx,base,player,1);const auto a=s.attribute;
  const bool active=ActiveDss(base,player,s)&&Alive(base,player)&&s.cast_remaining<=0;
  if(active && s.action==kActionMars && s.attribute==7 && (held&kAttackButton) && !(Read(base,player+kAllState+76)&kAttackButton))
    Write(base,player+kAllState+140,std::min(4u,Read(base,player+kAllState+140)+1));
  if(active && s.action==kActionJupiter && a!=0) {
    if(a==1)EnsureDssActor(base,player,kProjAllOrbit,a,FxArt(21),x,y-26,power*.25f,s.Element(),4);
    if(a==8)HolyBarrier(base,player);
    if(a==5||a==8||a==9)EnsureDssActor(base,player,kProjAllOrbit,a,FxArt(20+a),x,y-26,power*(a==9?2:a==5?.25f:.6f),s.Element());
    if(a==2 && !(held&3) && std::abs(x-Float(base,player+kAllState+64))<.01f && std::abs(y-Float(base,player+kAllState+68))<.01f) {
      const float t=Float(base,player+kAllState+60)+dt;if(t>=1){const auto st=Read(base,player+88);SummonHeal(ctx,base,player,std::max(1.0f,std::floor((Float(base,st+16)+Float(base,st+28))*.01f)));Float(base,player+kAllState+60,t-1);}else Float(base,player+kAllState+60,t);
    } else Float(base,player+kAllState+60,0);
    if(a==9 && !replaying){const float t=Float(base,player+kAllState+72)+dt;if(t>=1){const auto st=Read(base,player+88);Float(base,st+4,std::max(1.0f,Float(base,st+4)-std::max(1.0f,(Float(base,st+16)+Float(base,st+28))*.01f)));Float(base,player+kAllState+72,t-1);}else Float(base,player+kAllState+72,t);}
  }
  if(active && s.action==kActionSaturn && a!=0)EnsureDssActor(base,player,kProjAllFamiliar,a,FxArt(70+a),x,y-40,power*.5f,s.Element());
  if(active && s.action==kActionDiana && a==7 && WhipState(base,player) && Read(base,player+584)>=191 && Float(base,player+kAllState+56)<=0 && SpendMp(base,player,s.Cost())) {
    auto p=DssShot(x,y-24,0,0,47,0,power,0x400,.25f);p.kind=kProjField;p.flags=0;p.period=.2f;AddProjectile(base,player,p);Float(base,player+kAllState+56,.25f);
  }
  PlutoFrame(ctx,base,player,s,dt);
  Write(base,player+kAllState+76,held);Float(base,player+kAllState+64,x);Float(base,player+kAllState+68,y);
}
inline void ExtendedMotion(PPCContext& ctx,uint8_t* base,uint32_t player,Projectile& p,unsigned,const DssState& s,float dt) {
  const auto owner=Owner(base,player);if(!owner)return;
  const float x=Float(base,owner+0x8D4),y=Float(base,owner+0x8D8),dir=FacingSign(base,owner);
  const bool active=ActiveDss(base,player,s)&&s.cast_remaining<=0;
  if(p.kind==kProjAllOrbit) {
    if(!active || s.action!=kActionJupiter || s.attribute!=p.timing){p.kind=kProjNone;return;}
    p.angle+=7*dt;const float radius=p.timing==1?28:p.timing==5?24:0;
    p.x=x+std::cos(p.angle)*radius;p.y=y-26+std::sin(p.angle)*radius;
    p.period=p.timing==5?.3f:.2f;return;
  }
  if(p.kind==kProjHoming||p.kind==kProjSticky) {
    auto target=FindDssTarget(base,player,p.x,p.y,p.kind==kProjSticky?p.timing:0);
    if(p.kind==kProjSticky){if(target.handle){p.x=target.x;p.y=target.y;}else p.life=std::min(p.life,p.age+.2f);return;}
    if(target.handle){const float dx=target.x-p.x,dy=target.y-p.y,length=std::max(1.0f,std::sqrt(dx*dx+dy*dy));const float speed=140;p.vx+=(dx/length*speed-p.vx)*std::min(1.0f,6*dt);p.vy+=(dy/length*speed-p.vy)*std::min(1.0f,6*dt);}
    p.x+=p.vx*dt;p.y+=p.vy*dt;return;
  }
  if(p.kind==kProjGround) {
    float nx=p.x+p.vx*dt,ny=p.y;
    if(SweepTerrain(ctx,base,p.x,p.y,nx,ny,4,3)){p.kind=kProjNone;return;}
    p.x=nx;for(unsigned n=0;n<8 && !SolidTerrain(ctx,base,p.x,p.y+4);++n)p.y+=1;
    for(unsigned n=0;n<8 && SolidTerrain(ctx,base,p.x,p.y);++n)p.y-=1;return;
  }
  if(p.kind==kProjSpawner) {
    if(p.timing==1) {
      const float x0=p.x,y0=p.y;p.vy+=200*dt;p.x+=p.vx*dt;p.y+=p.vy*dt;
      // Bursts on its timer, on the first enemy it touches, or on terrain.
      if(SweepTerrain(ctx,base,x0,y0,p.x,p.y,6,6)){p.x=x0;p.y=y0;p.age=std::fmax(p.age,.75f);}
      if(p.age>=.75f){for(unsigned i=0;i<8;++i){const float a=i*6.283185307f/8;auto shot=DssShot(p.x,p.y,std::cos(a)*150,std::sin(a)*150,51,3+i%3,p.power,0x200,.8f);AddProjectile(base,player,shot);}p.kind=kProjNone;}
    } else if(p.timing==6) {
      p.x+=p.vx*dt;if(p.angle<=p.age){p.angle=p.age+.4f;for(unsigned i=0;i<4;++i){const float a=i*6.283185307f/4;auto shot=DssShot(p.x,p.y,std::cos(a)*130,std::sin(a)*130,56,2,p.power,0,.7f);AddProjectile(base,player,shot);}}
    }
    return;
  }
  if(p.kind==kProjShot && p.timing==0xB0)p.vy+=400*dt;
  if(p.kind==kProjShot && p.first==FxArt(52)) {
    p.angle+=dt;if(p.angle>.12f){p.angle=0;auto leaf=DssShot(p.x,p.y,0,20,52,1,p.power*.3f,0,.6f);leaf.flags=0;leaf.period=.2f;AddProjectile(base,player,leaf);}
    return;
  }
  if(p.kind!=kProjAllFamiliar)return;
  const auto a=p.timing;if(!active || s.action!=kActionSaturn || s.attribute!=a){p.kind=kProjNone;return;}
  auto target=FindDssTarget(base,player,p.x,p.y);const auto held=Read(base,player+kAllState+76);
  const bool spinning=WhipState(base,player)&&Read(base,player+584)>=191;
  const bool auto_attack=a==1||a==3||a==5||a==7;
  const bool attack=target.handle && (a!=5 || ((target.x-x)*dir<0 && std::abs(target.x-x)<60 && std::abs(target.y-y)<60)) && (auto_attack || (a==6||a==8||a==9?spinning:bool(held&kAttackButton)));
  p.period=0;
  if(attack && p.angle<=p.age && SpendMp(base,player,s.Cost())) {
    p.angle=.65f;p.age=0;p.first=FxArt(70+a,1);
    if(a==1||a==3||a==5||a==7){p.vx=1;p.period=.2f;}
    else {const float dx=target.x-p.x,dy=target.y-p.y,len=std::max(1.0f,std::sqrt(dx*dx+dy*dy));
      auto shot=DssShot(p.x,p.y,dx/len*180,dy/len*180,70+a,a==9?9:a==8?2:a==6?2:2,p.power,s.Element());
      if(a==9){shot.power*=1+std::min(3.0f,s.hold_time);shot.first=FxArt(79,s.hold_time<.75f?9:s.hold_time<1.5f?4:s.hold_time<2.25f?6:8);}if(kSaturnPassThrough[a])shot.flags&=~kDieOnHit;AddProjectile(base,player,shot);}
  }
  if(p.age>.5f)p.first=FxArt(70+a);
  float tx=x-dir*28,ty=y-42;
  if(p.vx && p.age<.35f && target.handle){if(a!=5){tx=target.x;ty=target.y;}p.period=.2f;}else p.vx=0;
  const float blend=1-std::pow(.94f,dt*kCotmHz);p.x+=(tx-p.x)*blend;p.y+=(ty-p.y)*blend;
  p.flags=(p.flags&~kFaceLeft)|(dir<0?kFaceLeft:0);
}
inline bool ActivePluto(uint8_t* base,uint32_t player,unsigned attr) {const auto s=Load(base,player);return s.action==kActionPluto && s.attribute==attr && ActiveDss(base,player,s)&&Alive(base,player);}
inline unsigned SkeletonFrame(uint8_t* base,uint32_t player,unsigned ordinary) {
  if(!ActivePluto(base,player,9) || Load(base,player).cast_remaining>0)return ordinary;
  const float age=Float(base,player+kAllState+96);
  if(WhipState(base,player))return AllSequenceFrame(FxSequence(99,Read(base,player+584)==188?4:1),age,false);
  const auto state=Read(base,player+572);if(state>=11&&state<=16)return AllSequenceFrame(FxSequence(99),0);
  return AllSequenceFrame(FxSequence(99),Read(base,player+kAllState+76)&3?Load(base,player).pulse_time:0);
}
inline bool ActivePluto(uint8_t* base,uint32_t player,unsigned attr);
inline void AdjustDssInput(uint8_t* base,uint32_t player,const DssState& s,uint32_t held,uint32_t& native_held,uint32_t& native_pressed,float dt) {
  // Skeleton (Pluto + Black Dog) throws a bone per press and has no whip: the
  // game sees attack only on the press, so holding it never starts the
  // hold-to-spin (whose whip hit object would hit while the whip is hidden).
  if(s.action==kActionPluto && s.attribute==9 && ActivePluto(base,player,9))
    native_held=(native_held&~kAttackButton)|(native_pressed&kAttackButton);
  const bool wind=s.action==kActionMars&&s.attribute==6&&s.enabled&&Alive(base,player);
  auto charging=Read(base,player+kAllState+132);
  if(!wind){Write(base,player+kAllState+132,0);return;}
  if(held&kAttackButton){
    if(!charging){charging=1;Float(base,player+kAllState+80,0);}
    Float(base,player+kAllState+80,std::min(3.0f,Float(base,player+kAllState+80)+dt));
    native_held&=~kAttackButton;native_pressed&=~kAttackButton;
  } else if(charging){charging=0;native_held|=kAttackButton;native_pressed|=kAttackButton;}
  Write(base,player+kAllState+132,charging);
}
// A swing arms the Skeleton's bone (+100: 1 bone, 2 big bone) and the Pluto
// shadow. One throw in 16 is the big bone: the owner rolls it here, and a
// copy is told the result (big: 0/1) so every machine throws the same bone.
// Returns whether a big bone was armed.
inline bool RecordDssSwing(uint8_t* base,uint32_t player,int big=-1) {
  Write(base,player+kAllState+140,1);
  if(ActivePluto(base,player,3)){Float(base,player+kAllState+84,0);Write(base,player+kAllState+88,1);}
  if(!ActivePluto(base,player,9)) return false;
  if(big<0) {
    const auto owner=Owner(base,player);
    unsigned random=Read(base,player+kAllState+184);if(!random)random=0x9E3779B9u^(owner?Read(base,owner+4):1u);
    random^=random<<13;random^=random>>17;random^=random<<5;Write(base,player+kAllState+184,random);
    big=(random&15)==0;
  }
  Float(base,player+kAllState+96,0);Write(base,player+kAllState+100,big?2:1);
  return big!=0;
}
inline void PlutoFrame(PPCContext& ctx,uint8_t* base,uint32_t player,const DssState& s,float dt) {
  const auto owner=Owner(base,player);if(!owner)return;
  const float x=Float(base,owner+0x8D4),y=Float(base,owner+0x8D8),dir=FacingSign(base,owner);
  if(ActivePluto(base,player,9)) {
    const float age=Float(base,player+kAllState+96)+dt;Float(base,player+kAllState+96,age);
    if(Read(base,player+kAllState+100)&&age>=15/kCotmHz){
      // The big bone (armed by RecordDssSwing) is CotM's resource 99 frame 61,
      // phase 5: its own art and a hit area to match, fatal damage, and it
      // carries on through enemies instead of breaking on the first.
      const bool big=Read(base,player+kAllState+100)==2;
      auto bone=DssShot(x+dir*16,y-24,dir*160,-115,99,big?5:2,big?9999:ProjectilePower(ctx,base,player,1),0,2);bone.timing=0xB0;
      if(big){bone.half_size=HalfSize(30,14);bone.flags&=~kDieOnHit;}
      AddProjectile(base,player,bone);Write(base,player+kAllState+100,0);
    }
  } else Write(base,player+kAllState+100,0);
  if(ActivePluto(base,player,3)) {
    if(!Read(base,player+kAllState+116)){for(unsigned i=0;i<48;++i){const auto at=player+kShadowHistory+i*16;Float(base,at,x);Float(base,at+4,y);Write(base,at+8,Read(base,player+kAllState+92));Write(base,at+12,dir<0);}Write(base,player+kAllState+116,1);}
    auto index=Read(base,player+kAllState+112)%48;const auto at=player+kShadowHistory+index*16;
    Float(base,at,x);Float(base,at+4,y);Write(base,at+8,Read(base,player+kAllState+92));Write(base,at+12,dir<0);
    Write(base,player+kAllState+112,(index+1)%48);
    const float age=Float(base,player+kAllState+84)+dt;Float(base,player+kAllState+84,age);
    if(Read(base,player+kAllState+88) && age>=24/kCotmHz){
      const auto delayed=player+kShadowHistory+((index+48-8)%48)*16;
      NativeHit(ctx,base,player,Float(base,delayed)+dir*36,Float(base,delayed+4)-24,36,12,MeleePower(ctx,base,player,1),0,0xFF,0,kProjTag,0xFFFFFFFFu);Write(base,player+kAllState+88,0);
    }
  } else {Write(base,player+kAllState+88,0);Write(base,player+kAllState+116,0);}
}
// Pluto + Serpent: a second subweapon follows each one Nathan throws. The
// local player detects the throw (its MP drop with B held) and returns the
// crash family it threw (7 = none); every machine draws the extra the same way.
inline void AdditionalSubweaponShot(PPCContext&,uint8_t*,uint32_t,unsigned);
inline unsigned AdditionalSubweapon(PPCContext& ctx,uint8_t* base,uint32_t player,uint32_t held,float before_mp) {
  if(!ActivePluto(base,player,1) || !(held&0x10))return 7;
  const auto st=Read(base,player+88);if(!st || Float(base,st+8)>=before_mp)return 7;
  const auto owner=Owner(base,player),eq=owner?Read(base,owner+0x9C8):0;if(!eq)return 7;
  const unsigned slot=held&8?11:held&4?9:held&3?10:8;
  const auto family=CrashFamily(Read(base,eq+slot*4));if(family>=7||family==3)return 7;
  AdditionalSubweaponShot(ctx,base,player,family);
  return family;
}
inline void AdditionalSubweaponShot(PPCContext& ctx,uint8_t* base,uint32_t player,unsigned family) {
  const auto owner=Owner(base,player);if(!owner || family>=7 || family==3)return;
  const float dir=FacingSign(base,owner);auto p=DssShot(Float(base,owner+0x8D4)+dir*20,Float(base,owner+0x8D8)-26,dir*200,0,40,0,ProjectilePower(ctx,base,player,1),0,1.5f);
  constexpr unsigned art[]={kArtCrashKnife,kArtCrashAxe,kArtCrashHoly,kArtCrashCross,kArtCrashRock,kArtCrashBible,kArtCrashJavelin};p.first=art[family];
  if(family==1){p.vy=-200;p.timing=0xB0;}if(family==2){p.vy=90;p.element=0x800;}if(family==4){p.kind=kProjRock;}if(family==5){p.kind=kProjCrashOrbit;p.vx=48;p.element=0x800;}
  AddProjectile(base,player,p);
}
// Native walking speed is (1+(boots+penalty)*.01)*base. Equipment resolves
// boots at stats+388 by best value and penalties at stats+392 by worst value,
// so boots never stack. The DSS pairs join those same rules, only while the
// two native readers run; the equipment result itself is left untouched.
constexpr float kPlutoGriffinBoots=100,kJupiterCockatricePenalty=-50;
class DssSpeedScope {
 public:
  DssSpeedScope(uint8_t* base,uint32_t state):base_(base) {
    const auto player=Read(base,state+4);
    const auto stats=Read(base,state+8);
    if(!player||!stats)return;
    const auto s=Load(base,player);
    if(!ActiveDss(base,player,s)||!Alive(base,player))return;
    if(s.action==kActionPluto&&s.attribute==6) Apply(stats+388,std::max(Float(base,stats+388),kPlutoGriffinBoots));
    else if(s.action==kActionJupiter&&s.attribute==4) Apply(stats+392,std::min(Float(base,stats+392),kJupiterCockatricePenalty));
  }
  ~DssSpeedScope(){if(field_)Float(base_,field_,saved_);}
  DssSpeedScope(const DssSpeedScope&)=delete;
  DssSpeedScope& operator=(const DssSpeedScope&)=delete;
 private:
  void Apply(uint32_t field,float value){field_=field;saved_=Float(base_,field);Float(base_,field,value);}
  uint8_t* base_;
  uint32_t field_=0;
  float saved_=0;
};

inline void HolyBarrier(uint8_t* base,uint32_t player) {
  const auto owner=Owner(base,player),manager=Read(base,0x8291D9F0);if(!owner||!manager)return;
  const auto first=Read(base,manager+0xAC),end=Read(base,manager+0xB0);if(!first||end<first||end-first>65536*16)return;
  const float x=Float(base,owner+0x8D4),y=Float(base,owner+0x8D8)-26;
  for(auto at=first;at<end;at+=16){const auto entity=Read(base,at+4);if(!entity)continue;
    const auto flags=Read(base,entity+8);if(!(flags&16) || (flags&(2|4)) || base[entity+23])continue;
    const float dx=Float(base,entity+0x2C)-x,dy=Float(base,entity+0x30)-y;
    if(std::isfinite(dx)&&std::isfinite(dy)&&dx*dx+dy*dy<=32*32)base[entity+23]=1;
  }
}

}
