// Test all card selections against the real player/renderer wrappers.
CHECK(VirtualAlloc(base+0x400000,0x100000,MEM_COMMIT,PAGE_READWRITE));
Write(base,M+0xAC,0x400000);Write(base,M+0xB0,0x500000);
Write(base,0x400000+(ownerHandle&65535)*16,ownerHandle);Write(base,0x400004+(ownerHandle&65535)*16,O);
Write(base,0x400000+(weaponHandle&65535)*16,weaponHandle);Write(base,0x400004+(weaponHandle&65535)*16,W);
Write(base,O+8,2);Write(base,live_body+12,0x179000);Write(base,0x179024,0x179100);
constexpr unsigned enemy=0x17E000,enemy_handle=0xFACE0002,shape=0x17C000,request=0x17D000;
Write(base,0x400020,enemy_handle);Write(base,0x400024,enemy);Write(base,enemy+8,4);
Write(base,shape+4,1);Float(base,shape+8,560);Float(base,shape+12,240);Float(base,shape+16,580);Float(base,shape+20,280);
Write(base,request+4,0x10);Write(base,request+12,shape);Write(base,request+20,enemy_handle);
Write(base,0x8291D918,0x155000);Write(base,0x155004,0x155100);Write(base,0x155008,0x155104);Write(base,0x155100,0x155200);
Write(base,0x155224,0x155300);Write(base,0x155228,0x155304);Write(base,0x155300,request);
const auto nearest=FindDssTarget(base,P,500,270);CHECK(nearest.handle==enemy_handle && nearest.x==570 && nearest.y==260);
constexpr unsigned actions[]={kMercury,kVenus,0x6DA,0x6DB,0x6DC,0x6DD,0x6DE,0x6DF,0x6E0,0x6E1};
auto begin_pair=[&](unsigned action,unsigned attribute) {
  next_hit=0x120000;ResetProjectiles(base,P);ResetSummon(base,P);Save(base,P,{});Write(base,P+852,T);
  Write(base,P,kVtable);Write(base,E+48,actions[action]);Write(base,E+52,kSalamander+attribute);Write(base,E+32,0x60F);
  Write(base,P+572,1);Write(base,P+584,2);Float(base,S+4,500);Float(base,S+8,5000);Float(base,P+564,1.0f/60);
  Float(base,O+0x8D4,500);Float(base,O+0x8D8,300);Float(base,O+0x8EC,500);Float(base,O+0x8F0,300);base[live_body+0x1C]=0;Write(base,P+0x250,0);
  frame(0);CHECK(Paired(base,P));
};
for(unsigned action=0;action<10;++action)for(unsigned a=0;a<10;++a) {
  begin_pair(action,a);frame(kRb);auto state=Load(base,P);CHECK(state.enabled);
  if(action==5){CHECK(std::abs(Float(base,S+8)-(5000-kApolloMp[a]))<.01);for(unsigned n=0;n<8;++n)frame(kRb);CHECK(std::abs(Float(base,S+8)-(5000-kApolloMp[a]))<.01);}
  if(action==8){CHECK(Float(base,S+8)==5000-kUranusCost[a]);}
  if(action==9&&a==0){CHECK(Float(base,S+8)==5000-kCrashCost[0]);for(unsigned n=0;n<8;++n)frame(kRb);CHECK(Float(base,S+8)==5000-kCrashCost[0]);}
  if(action==3||action==4) {
    // Paid callback chooses each weapon/projectile's own timeline and cost.
    Write(base,P+572,23);swing(187);CHECK(Float(base,S+8)==5000-(action==3?kMarsMp[a]:(a==7?0:kDianaMp[a])));
    if(action==3)CHECK(Read(base,T+187*8)==kAllMarsSlots[a][0]);
  }
  // Existing palette selection must survive every action without a global mutation.
  base[live_body+0x55]=7;draws.clear();draw_material_palettes.clear();ctx.r3.u64=O;sub_824476B8(ctx,base);
  CHECK(base[live_body+0x55]==7 && Read(base,live_body+12)==0x179000);base[live_body+0x55]=0;
  Write(base,E+52,0);frame(0);CHECK(!Load(base,P).enabled);
}
// Direct RB is a rising edge. Holding it through completion cannot recast;
// another press after release can. Low MP and a full pool consume nothing.
for(unsigned a=0;a<10;++a) {
  begin_pair(5,a);frame(kRb);const auto paid=Float(base,S+8);
  auto state=Load(base,P);state.cast_remaining=.001f;Save(base,P,state);frame(kRb);CHECK(!Load(base,P).enabled && Float(base,S+8)==paid);
  frame(0);frame(kRb);CHECK(Float(base,S+8)==paid-kApolloMp[a]);
  begin_pair(5,a);Float(base,S+8,kApolloMp[a]-.5f);frame(kRb);CHECK(!Load(base,P).enabled && Float(base,S+8)==kApolloMp[a]-.5f);
}
// Every new FX draw gets the FX COL; the body retains its own descriptor.
begin_pair(2,1);auto shield=Load(base,P);shield.enabled=1;shield.cast_remaining=0;Save(base,P,shield);frame(0);
draws.clear();draw_material_palettes.clear();ctx.r3.u64=O;sub_824476B8(ctx,base);bool fx_drawn=false;
for(unsigned i=0;i<draws.size();++i)if(draws[i].second>=kAllDssFirst && draws[i].second<kAllDssBodyFirst){fx_drawn=true;CHECK(draw_material_palettes[i]==0x17B000);}
CHECK(fx_drawn && Read(base,live_body+12)==0x179000);
// The Manticore adaptation discounts a stable private record, never shared tables.
begin_pair(9,5);auto discount=Load(base,P);discount.enabled=1;Save(base,P,discount);
Write(base,P+kAllState+176,1);base[0x17800E]=0;base[0x17800F]=12;
ctx.r3.u64=0;ctx.r4.u64=0;ctx.r5.u64=1;ctx.r6.u64=70;sub_8246D8E8(ctx,base);
CHECK(ctx.r3.u32==P+4096+70 && base[ctx.r3.u32+15]==6 && base[0x17800F]==12);
Write(base,P+kAllState+176,0);ctx.r6.u64=70;ctx.r5.u64=1;sub_8246D8E8(ctx,base);CHECK(ctx.r3.u32==0x178000);
// Skeleton is a separate native body, not a costume tint, and its bone
// release replaces the inherited whip rather than adding a hidden whip hit.
begin_pair(9,9);auto skeleton=Load(base,P);skeleton.enabled=1;skeleton.cast_remaining=0;Save(base,P,skeleton);
Write(base,P+572,23);swing(187);for(unsigned n=0;n<17;++n)frame(0);
CHECK(SkeletonFrame(base,P,0)>=kAllDssFirst);bool bone=false;
for(unsigned i=0;i<kProjCount;++i){auto p=LoadProjectile(base,ProjAddress(P,i));bone|=p.timing==0xB0;}
CHECK(bone);ctx.r3.u64=0xD0000;ctx.r4.u64=0;sub_824699B8(ctx,base);CHECK(started_clip==32);
// Holding attack as the Skeleton never reaches the game (no hold-to-spin
// with a hidden whip); the press itself still does (the throw). Other pairs
// keep the held attack.
{
  uint32_t held=kAttackButton,pressed=0;AdjustDssInput(base,P,Load(base,P),kAttackButton,held,pressed,1.0f/60);CHECK(held==0);
  held=kAttackButton|kLeftButton;pressed=kAttackButton;AdjustDssInput(base,P,Load(base,P),kAttackButton,held,pressed,1.0f/60);
  CHECK(held==(kAttackButton|kLeftButton) && pressed==kAttackButton);
  DssState other=Load(base,P);other.attribute=8;held=kAttackButton;pressed=0;AdjustDssInput(base,P,other,kAttackButton,held,pressed,1.0f/60);CHECK(held==kAttackButton);
}
// One throw in 16 is the big bone: its own art (phase 5), a bigger hit area,
// fatal damage, and it does not break on the first enemy.
{
  auto next=[](uint32_t r){r^=r<<13;r^=r>>17;r^=r<<5;return r;};
  auto thrown=[&](uint32_t seed){
    ResetProjectiles(base,P);Write(base,P+kAllState+184,seed);
    const bool armed_big=RecordDssSwing(base,P);Float(base,P+kAllState+96,1);  // the swing rolls the bone
    CHECK(Read(base,P+kAllState+100)==(armed_big?2u:1u));
    PlutoFrame(ctx,base,P,Load(base,P),0);Projectile found{};
    for(unsigned i=0;i<kProjCount;++i){auto p=LoadProjectile(base,ProjAddress(P,i));if(p.timing==0xB0)found=p;}
    CHECK(found.timing==0xB0 && !Read(base,P+kAllState+100));return found;};
  uint32_t big_seed=1,small_seed=1;
  while(next(big_seed)&15)++big_seed;
  while(!(next(small_seed)&15))++small_seed;
  const auto big=thrown(big_seed),small=thrown(small_seed);
  CHECK(big.first==FxArt(99,5) && big.power==9999 && big.half_size==HalfSize(30,14) && !(big.flags&kDieOnHit));
  CHECK(small.first==FxArt(99,2) && small.power<9999 && small.half_size==HalfSize(8,8) && (small.flags&kDieOnHit));
  CHECK(FxSequence(99,5)!=FxSequence(99,2));
}
// A holy barrier deletes spawned enemy attack objects, never the enemy itself.
begin_pair(2,8);auto holy=Load(base,P);holy.enabled=1;holy.cast_remaining=0;Save(base,P,holy);
Write(base,0x400030,0xFACE0003);Write(base,0x400034,0x17F000);Write(base,0x17F008,16);Float(base,0x17F02C,500);Float(base,0x17F030,274);
frame(0);CHECK(base[0x17F017]==1 && !base[enemy+23]);
// Loss/death removes familiars and shields; changing cards stops their MP use.
Float(base,S+4,0);frame(0);for(unsigned i=0;i<kProjCount;++i)CHECK(!Read(base,ProjAddress(P,i)));

// Thunderbird charges for each discharge, without an entry-whip surcharge.
begin_pair(4,7);auto thunder=Load(base,P);thunder.enabled=1;thunder.cast_remaining=0;Save(base,P,thunder);
Write(base,P+572,23);swing(187);CHECK(Float(base,S+8)==5000);
Write(base,P+584,191);frame(kAttackButton);CHECK(Float(base,S+8)==5000-kDianaMp[7]);

// Speed pairs go through the native boots fields: best boots, worst penalty,
// no stacking with equipment, and equipment results restored afterwards.
{
  constexpr uint32_t kSpeedState=0x18F000;
  Write(base,kSpeedState+4,P);Write(base,kSpeedState+8,S);
  const auto walk=[&]{ctx.r3.u64=kSpeedState;sub_836DC9A0(ctx,base);return native_walk_speed;};
  const auto stop=[&]{ctx.r3.u64=kSpeedState;sub_836D7C50(ctx,base);return native_stop_speed;};
  struct Case{unsigned action,attribute;float boots,expected;};
  for(const Case c:{Case{9,6,0,2},Case{9,6,20,2},Case{9,6,60,2},Case{2,4,0,.5f},Case{2,4,50,1}}) {
    begin_pair(c.action,c.attribute);auto speed=Load(base,P);speed.enabled=1;speed.cast_remaining=0;Save(base,P,speed);
    Float(base,S+388,c.boots);Float(base,S+392,0);Float(base,S+4,100);
    CHECK(walk()==c.expected);CHECK(stop()==c.expected && native_walk_speed==c.expected);
    CHECK(Float(base,S+388)==c.boots && Float(base,S+392)==0);
    speed=Load(base,P);speed.Disable();Save(base,P,speed);
    CHECK(walk()==1+c.boots*.01f);
    speed.enabled=1;Save(base,P,speed);Float(base,S+4,0);
    CHECK(walk()==1+c.boots*.01f);Float(base,S+4,100);
  }
  // Other pairs, and gear penalties already worse than the card's, stay native.
  begin_pair(9,5);auto other=Load(base,P);other.enabled=1;Save(base,P,other);Float(base,S+388,50);CHECK(walk()==1.5f);
  begin_pair(2,4);auto cursed=Load(base,P);cursed.enabled=1;cursed.cast_remaining=0;Save(base,P,cursed);
  Float(base,S+388,0);Float(base,S+392,-70);CHECK(std::abs(walk()-.3f)<.0001f);
  Float(base,S+392,0);Float(base,S+388,0);
}
// Green numbers report only real recovery; poison and full HP stay silent.
{
  begin_pair(2,2);auto regen=Load(base,P);regen.enabled=1;regen.cast_remaining=0;Save(base,P,regen);
  Float(base,S+16,1000);Float(base,S+28,0);Float(base,S+4,500);Float(base,S+8,5000);Float(base,P+kAllState+60,0);
  auto numbers=heal_numbers;Float(base,P+564,1.0f/60);
  for(unsigned n=0;n<70;++n)frame(0);
  CHECK(heal_numbers==numbers+1 && last_heal==10 && Float(base,S+4)==510);
  Float(base,S+4,1000);numbers=heal_numbers;for(unsigned n=0;n<70;++n)frame(0);
  CHECK(heal_numbers==numbers && Float(base,S+4)==1000);
  begin_pair(2,9);regen=Load(base,P);regen.enabled=1;regen.cast_remaining=0;Save(base,P,regen);
  Float(base,S+4,500);Float(base,S+8,5000);Float(base,P+kAllState+72,0);numbers=heal_numbers;
  for(unsigned n=0;n<70;++n)frame(0);
  CHECK(heal_numbers==numbers && Float(base,S+4)<500);
  // Popups round fractional recovery up, so healing never displays as 0.
  Float(base,S+4,999.5f);CHECK(SummonHeal(ctx,base,P,10)==.5f && last_heal==1);
}
// All cost families fit Nathan's ordinary 100 MP pool; high-end skills can
// be used with half a bar. Numeric policy is checked independently below.
for(float cost:kUranusCost)CHECK(cost>=20 && cost<=50);
for(float cost:kDianaMp)CHECK(cost>=1 && cost<=32);
CHECK(kMercuryMp[0]==2 && kApolloMp[9]==30 && kCrashCost[3]==25);

// The actual 100-MP budget must activate every pair, not just a 5,000-MP fixture.
for(unsigned action=0;action<10;++action)for(unsigned a=0;a<10;++a){
  begin_pair(action,a);Float(base,S+8,100);frame(kRb);
  CHECK(Load(base,P).enabled && Float(base,S+8)>=0 && Float(base,S+8)<=100);
}
DssState upkeep;upkeep.action=kActionPluto;upkeep.attribute=6;
CHECK(std::abs(upkeep.Drain()-.99520684f)<.0001f);

// Pool objects are drawn at their own world position. The body draws at
// owner+64/+68 (feet X, and Y plus a pose offset); owner+0x8EC/0x8F0 is the
// body-box center and the sprite pivot (+116/+118) must stay the body's.
{
  ResetProjectiles(base,P);Save(base,P,{});Write(base,P+852,T);
  DssState quiet{};quiet.motion_table=T;Save(base,P,quiet);
  const auto body=Read(base,O+0x2C);
  base[body+116]=0;base[body+117]=3;base[body+118]=0xFF;base[body+119]=0xFE; // pivot (3,-2)
  Write(base,body+0x78,0);Float(base,body+0x28,1);Float(base,body+0x2C,1);Float(base,O+72,1);
  Float(base,O+0x8D4,500);Float(base,O+0x8D8,300);Float(base,O+64,500);Float(base,O+68,310);
  Float(base,O+0x8EC,500);Float(base,O+0x8F0,278);
  Projectile mark;mark.kind=kProjShot;mark.x=540;mark.y=274;mark.first=kArtDiana;mark.life=10;
  CHECK(AddProjectile(base,P,mark));
  const auto pool_draw=[&]{
    draws.clear();draw_places.clear();ctx.r3.u64=O;sub_824476B8(ctx,base);
    for(unsigned i=0;i<draws.size();++i)if(draws[i].first==P+kSummonSprite && draws[i].second==mark.Frame())return draw_places[i];
    CHECK(false);return DrawPlace{};
  };
  auto place=pool_draw();
  CHECK(place.x==540 && place.y==274 && place.pivot_x==3 && place.pivot_y==-2);
  // Jumping or a different body-box center must not move a flying shot.
  Float(base,O+0x8D8,240);Float(base,O+68,250);Float(base,O+0x8F0,200);
  place=pool_draw();CHECK(place.x==540 && place.y==274);
  // Left of and below Nathan, with fractional positions.
  Float(base,ProjAddress(P,0)+4,455.4f);Float(base,ProjAddress(P,0)+8,262.6f);
  place=pool_draw();CHECK(place.x==455 && place.y==263);
  // Scaled layers pass zoomed coordinates: offsets scale with the body.
  Write(base,body+0x78,7);Float(base,body+0x28,2);Float(base,body+0x2C,2);
  Float(base,ProjAddress(P,0)+4,540);Float(base,ProjAddress(P,0)+8,274);
  place=pool_draw();CHECK(place.x==500+80 && place.y==250+48);
  Write(base,body+0x78,0);Float(base,body+0x28,1);Float(base,body+0x2C,1);
  base[body+116]=base[body+117]=base[body+118]=base[body+119]=0;
  ResetProjectiles(base,P);
}
