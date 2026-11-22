// Included inside the actual wrapper harness so these exercise real hooks.
auto activate=[&](unsigned item) {
  next_hit=0x120000;ResetProjectiles(base,P);ResetSummon(base,P);Save(base,P,{});Write(base,P+852,T);
  Write(base,P,kVtable);Write(base,P+572,1);Write(base,P+584,2);Write(base,E+48,item);Write(base,E+52,kSalamander);
  Float(base,O+0x8D4,500);Float(base,O+0x8D8,300);Float(base,O+0x8EC,500);Float(base,O+0x8F0,300);
  Float(base,S+4,500);Float(base,S+8,500);Float(base,P+564,1.0f/60);base[live_body+0x1C]=0;Write(base,P+0x250,0);
  frame(0);if(!Load(base,P).Direct()){frame(kRb);for(unsigned i=0;i<60;++i)frame(0);CHECK(Load(base,P).enabled);}CHECK(Paired(base,P));
};
activate(0x6DA);unsigned flames=0;
for(unsigned i=0;i<kProjCount;++i) {
  auto p=LoadProjectile(base,ProjAddress(P,i));
  if(p.kind==kProjOrbit){++flames;CHECK(p.first==kArtJupiter && p.Frame()>=kJupiterFire[0].frame);}
}
CHECK(flames==2);frame(kRb);CHECK(!OwnedKind(base,P,kProjOrbit));
// Diana releases on whip extension, not on the first windup frame.
for(unsigned motion:{187u,188u,189u}) {
  activate(0x6DC);Write(base,P+572,motion==189?11:23);swing(motion);
  CHECK(Float(base,S+8)==500-kDianaMp[0] && !OwnedKind(base,P,kProjShot));
  for(unsigned i=0;i<17;++i)frame(0);
  CHECK(OwnedKind(base,P,kProjShot));auto shot=LoadProjectile(base,ProjAddress(P,0));
  CHECK(shot.first==kArtDiana && shot.vx>0 && (shot.element&kFireDamage));
  const auto mp=Float(base,S+8);for(unsigned i=0;i<6;++i)frame(0);CHECK(Float(base,S+8)==mp);
  const auto collider=next_hit-0x1000;ctx.r3.u64=collider;ctx.f1.f64=1.0/60;sub_824827F0(ctx,base);
  CHECK(Read(base,collider+0x18C)==1);
  const auto generation=shot.flags>>16;MarkProjectileHit(base,P,0,generation-1);CHECK(!(Read(base,ProjAddress(P,0)+60)&kWasHit));
  MarkProjectileHit(base,P,0,generation);frame(0);
  // Pass-through is per pair (nathan_dss_balance.json): a passing fireball
  // survives the hit and keeps flying; a stopping one becomes its impact puff.
  CHECK(Read(base,ProjAddress(P,0))==(kDianaPassThrough[0]?kProjShot:kProjPuff));
  CHECK(!(Read(base,ProjAddress(P,0)+60)&kWasHit) && bool(shot.flags&kDieOnHit)!=kDianaPassThrough[0]);
  if(kDianaPassThrough[0]) { // walls still stop it
    test_wall=LoadProjectile(base,ProjAddress(P,0)).x+6;for(unsigned i=0;i<12;++i)frame(0);
    CHECK(Read(base,ProjAddress(P,0))!=kProjShot);test_wall=100000;
  }
}
// The overlap probe marks a shot when its hit rectangle touches an enemy hurt
// volume, without depending on the contact callback being delivered.
{
  constexpr unsigned record=0x17A000;Write(base,record+0x14,0xBEEF);
  activate(0x6DC);Write(base,P+572,23);swing(187);for(unsigned i=0;i<20;++i)frame(0);
  CHECK(OwnedKind(base,P,kProjShot));
  auto collider=next_hit-0x1000;const auto probes=area_probes;
  Write(base,record+4,0x08);probe_struck=record;   // a breakable is not a hurt volume
  ctx.r3.u64=collider;ctx.f1.f64=1.0/60;sub_824827F0(ctx,base);
  CHECK(area_probes==probes+1 && !(Read(base,ProjAddress(P,0)+60)&kWasHit));
  ctx.r3.u64=collider;ctx.f1.f64=1.0/60;sub_824827F0(ctx,base);CHECK(area_probes==probes+1); // one probe per hit object
  for(unsigned i=0;i<6 && next_hit-0x1000==collider;++i)frame(0);
  CHECK(next_hit-0x1000!=collider);collider=next_hit-0x1000;
  Write(base,record+4,0x10);                       // an enemy hurt volume
  ctx.r3.u64=collider;ctx.f1.f64=1.0/60;sub_824827F0(ctx,base);
  CHECK(area_probes==probes+2 && (Read(base,ProjAddress(P,0)+60)&kWasHit));
  frame(0);CHECK(Read(base,ProjAddress(P,0))==(kDianaPassThrough[0]?kProjShot:kProjPuff));
  probe_struck=0;
}
// One command consumes one bomb; facing changes do not turn a fired shot.
for(unsigned facing:{0u,1u}) {
  activate(0x6DD);base[live_body+0x1C]=facing;Write(base,P+0x250,facing);
  frame(kRb);
  CHECK(Float(base,S+8)==500-kApolloMp[0] && OwnedKind(base,P,kProjArc));
  auto bomb=LoadProjectile(base,ProjAddress(P,0));CHECK(bomb.first==kArtBomb && (bomb.vx<0)==bool(facing));
  const auto start_x=bomb.x;for(unsigned i=0;i<45;++i)frame(0);
  auto blast=LoadProjectile(base,ProjAddress(P,0));CHECK(blast.kind==kProjBlast && blast.first==kArtBlast);
  CHECK((blast.x<start_x)==bool(facing));CHECK(Float(base,S+8)==500-kApolloMp[0]);
}
// Sword poses replace the body and whip collider for all three attack poses.
for(unsigned motion:{187u,188u,189u}) {
  activate(0x6DB);Write(base,P+572,motion==189?11:23);swing(motion);CHECK(Float(base,S+8)==500-kMarsMp[0]);
  for(unsigned i=0;i<17;++i)frame(0);
  CHECK(SalamanderBody(MarsBodyFrame(base,P,0)) && Read(base,P+kProjControl+20)==1);
  const auto sword=next_hit-0x1000;CHECK((Read(base,sword+0xB0)&kFireDamage) && Float(base,sword+0x110)==110);
  ctx.r3.u64=0xD0000;ctx.r4.u64=0;sub_824699B8(ctx,base);CHECK(started_clip==32);
  frame(kRb);CHECK(!MarsSwing(base,P,Load(base,P)) && MarsBodyFrame(base,P,0)==0);
}
// Bat's native eight-tick attack delay and MP payment at shot release.
activate(0x6DF);CHECK(OwnedKind(base,P,kProjFamiliar));
auto bat=LoadProjectile(base,ProjAddress(P,0));CHECK(bat.first==kArtBat && bat.Frame()>=kSaturnBat[0].frame);
frame(kAttackButton);CHECK(!OwnedKind(base,P,kProjShot) && Float(base,S+8)==500);
for(unsigned i=0;i<9;++i)frame(0);
CHECK(OwnedKind(base,P,kProjShot) && Float(base,S+8)==500-kSaturnMp[0]);
auto batshot=LoadProjectile(base,ProjAddress(P,1));CHECK(batshot.first==kArtBatFire);
frame(kRb);CHECK(!OwnedKind(base,P,kProjFamiliar));
// Neptune + Salamander: fire hits go through the native hit at half power
// (a 50% resistance, no healing); other damage types are untouched.
activate(0x6DE);Float(base,S+4,100);auto previous_numbers=heal_numbers;const auto hit_before=normal_hits;
ctx.r3.u64=O;ctx.r7.u64=kFireDamage;ctx.f1.f64=30;sub_8244BF10(ctx,base);
CHECK(ctx.f1.f64==15 && Float(base,S+4)==100 && normal_hits==hit_before+1 && heal_numbers==previous_numbers);
ctx.r3.u64=O;ctx.r7.u64=0x200;ctx.f1.f64=30;sub_8244BF10(ctx,base);CHECK(ctx.f1.f64==30 && normal_hits==hit_before+2);
frame(kRb);ctx.r3.u64=O;ctx.r7.u64=kFireDamage;ctx.f1.f64=30;sub_8244BF10(ctx,base);CHECK(ctx.f1.f64==30 && normal_hits==hit_before+3);
// Every eligible hunter subweapon selects its crash family, including
// Simon variants, Bible/Rock/Javelin. An empty B slot consumes no MP.
for(unsigned item:{0x60Fu,0x610u,0x611u,0x612u,0x613u,0x614u,0x61Bu,0x61Cu,0x61Du,0x61Eu,0x61Fu}) {
  activate(0x6E1);Write(base,E+32,item);const auto before=Float(base,S+8);const auto family=CrashFamily(item);
  CHECK(family<7 && BeginItemCrash(ctx,base,P));CHECK(std::abs(Float(base,S+8)-(before-kCrashCost[family]))<.001);
  frame(0);bool found=false;
  for(unsigned i=0;i<kProjCount;++i){auto p=LoadProjectile(base,ProjAddress(P,i));found|=p.kind!=kProjNone && p.kind!=kProjCrash;}
  CHECK(found);
}
activate(0x6E1);Write(base,E+32,0);const auto empty_mp=Float(base,S+8);CHECK(!BeginItemCrash(ctx,base,P) && Float(base,S+8)==empty_mp);
// Exercise the shared command through the actual player update, not only
// the crash spawner. MP includes this one frame's native timed drain.
activate(0x6E1);Write(base,E+32,0x614);
const auto crash_mp=Float(base,S+8);frame(kRb);
CHECK(OwnedKind(base,P,kProjCrash) && Float(base,P+kProjControl+48)>0);
CHECK(std::abs(crash_mp-Float(base,S+8)-kCrashCost[5])<.001);
// Real native stage query receives swept point coordinates, stopping a bomb
// at a wall before it can reach the original launch height/floor.
activate(0x6DD);test_wall=550;frame(kRb);
for(unsigned i=0;i<17;++i)frame(0);
CHECK(LoadProjectile(base,ProjAddress(P,0)).kind==kProjBlast);
CHECK(LoadProjectile(base,ProjAddress(P,0)).x<550);
test_wall=100000;
// Ricochet motion reflects from stage geometry, not an invented screen box.
activate(0x6E1);test_wall=550;Projectile rock;rock.kind=kProjRock;rock.x=530;rock.y=250;rock.vx=200;
rock.first=kArtCrashRock;rock.life=2;rock.power=1;rock.half_size=HalfSize(10,10);AddProjectile(base,P,rock);
UpdateProjectiles(ctx,base,P,Load(base,P),.1f);CHECK(LoadProjectile(base,ProjAddress(P,0)).vx<0);
test_wall=100000;

Float(base,S+4,0);frame(0);for(unsigned i=0;i<kProjCount;++i)CHECK(!Read(base,ProjAddress(P,i)));
