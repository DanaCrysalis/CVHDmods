// Online co-op: the local Nathan announces (nathan_dss.cpp Announce /
// AnnounceFrame), another machine's copy replays (ReceiveNathanEvent in
// nathan_dss_damage.cpp queues, ReceiveEvents in nathan_dss.cpp applies).
{
  auto count=[&](unsigned type){unsigned n=0;for(const auto& c:spawn_calls)n+=c.id>>12==type;return n;};
  auto last=[&](unsigned type){uint32_t id=0;for(const auto& c:spawn_calls)if(c.id>>12==type)id=c.id;return id;};
  CHECK(registered_spawn_hook);

  // --- The local Nathan announces through the native replicate-only event.
  begin_pair(0,0);Float(base,S+8,5000);Write(base,P+kNet+92,NetId(kNetOff));Write(base,P+kNet+100,0);spawn_calls.clear();
  frame(kRb);CHECK(Load(base,P).enabled);
  const unsigned level=std::clamp(unsigned(PairLevel(base,P)),1u,kCardCopyCap);
  CHECK(spawn_calls.size()==1);
  {const auto& c=spawn_calls[0];
   CHECK(c.owner==O && c.kind==11 && c.sub==1 && c.tag_a==kNetTagA && c.tag_b==kNetTagB && c.id==NetId(kNetOn,kActionMercury,0,level));
   CHECK(c.sp<ctx.r1.u32 && ctx.r1.u32-c.sp>=0x400);}  // its own zeroed frame below the live stack
  for(int n=0;n<60;++n)frame(0);
  CHECK(count(kNetOn)==1);  // no repeat within 2 s
  for(int n=0;n<80;++n)frame(0);
  CHECK(count(kNetOn)==2 && last(kNetOn)==NetId(kNetOn,kActionMercury,0,level));  // resent for copies that missed it
  frame(kAttackButton);CHECK(last(kNetAttack)==NetId(kNetAttack,0,0,1));
  frame(kAttackButton);CHECK(count(kNetAttack)==1);
  frame(0);CHECK(count(kNetAttack)==2 && last(kNetAttack)==NetId(kNetAttack,0,0,0));
  Write(base,P+572,23);swing(187);
  CHECK(count(kNetSwing)==1 && last(kNetSwing)==NetId(kNetSwing,kActionMercury,0,1));  // a paid swing
  Write(base,P+572,1);Write(base,P+584,2);frame(0);frame(kRb);CHECK(!Load(base,P).enabled && last(kNetOff)==NetId(kNetOff));
  // Apollo is a cast, not a state: one Cast event per paid cast.
  begin_pair(5,0);spawn_calls.clear();Write(base,P+kNet+92,NetId(kNetOff));frame(kRb);
  CHECK(count(kNetCast)==1 && last(kNetCast)==NetId(kNetCast,kActionApollo,0) && !count(kNetOn));

  // --- Another machine's Nathan: a copy (control type 2) on this machine.
  frame(0);auto quiet=Load(base,P);quiet.enabled=0;quiet.cast_remaining=quiet.fade_remaining=0;Save(base,P,quiet);
  Write(base,O+0x930,2);ResetNet(base,P);ResetProjectiles(base,P);ResetSummon(base,P);spawn_calls.clear();
  auto deliver=[&](uint32_t id,uint32_t owner=O,uint32_t tag=kNetTagB){
    PPCContext e=ctx;e.r3.u64=owner;e.r4.u64=id;e.r5.u64=11;e.r6.u64=1;e.r9.u64=kNetTagA;e.r10.u64=tag;registered_spawn_hook(e,base);};
  CHECK(Owner(base,P)==O);CHECK(!LocalPlayer(base,P));CHECK(Action(base,P)==kActionUnavailable);CHECK(Attribute(base,P)==10);
  Float(base,S+8,7);Float(base,S+4,50);Float(base,S+16,100);Float(base,S+28,0);Write(base,P+572,1);Write(base,P+584,2);
  std::vector<uint8_t> save_before(base+SAVE,base+SAVE+0x2600);
  // The copy ignores its own (absent) buttons: attack alone changes nothing.
  frame(kAttackButton);CHECK(!Load(base,P).enabled && Float(base,S+8)==7);
  // Only Nathan events for a remote player's Nathan are queued.
  deliver(NetId(kNetOn,kActionMars,3,5),O,0x1234);CHECK(Read(base,P+kNet)==0);
  Write(base,O+0x930,1);deliver(NetId(kNetOn,kActionMars,3,5));CHECK(Read(base,P+kNet)==0);Write(base,O+0x930,2);
  Write(base,P,0x83000000);deliver(NetId(kNetOn,kActionMars,3,5));CHECK(Read(base,P+kNet)==0);Write(base,P,kVtable);
  // On: the announced pair and pair level, no MP spent, nothing announced back.
  deliver(NetId(kNetOn,kActionMars,3,5));CHECK(Read(base,P+kNet)==1);
  frame(0);
  {const auto s=Load(base,P);CHECK(s.enabled && s.action==kActionMars && s.attribute==3 && Action(base,P)==kActionMars && Attribute(base,P)==3);}
  CHECK(Float(base,P+kPairLevel)==5 && Float(base,S+8)==7 && spawn_calls.empty() && ActiveDss(base,P,Load(base,P)));
  // A repeated On (the owner's 2 s resend) does not restart the pair.
  for(int n=0;n<70;++n)frame(0);
  const float pulse=Load(base,P).pulse_time;CHECK(pulse>0);
  deliver(NetId(kNetOn,kActionMars,3,5));frame(0);CHECK(Load(base,P).enabled && Load(base,P).pulse_time>pulse);
  // Its MP is the owner's: an empty pool here never turns it off.
  Float(base,S+8,0);for(int n=0;n<10;++n)frame(0);CHECK(Load(base,P).enabled);Float(base,S+8,7);
  // Off.
  deliver(NetId(kNetOff));frame(0);CHECK(!Load(base,P).enabled);
  // A paid Mercury swing: the fire whip, without paying.
  // (The snapshot already shows the whip motion when the event arrives.)
  deliver(NetId(kNetOn,kActionMercury,0,1));frame(0);
  Write(base,P+572,23);Write(base,P+584,187);deliver(NetId(kNetSwing,kActionMercury,0,1));frame(0);
  CHECK(Load(base,P).Fire() && Float(base,S+8)==7);
  // The copy's own swing callback does nothing: swings arrive as events.
  {auto s=Load(base,P);s.paid_swing=0;Save(base,P,s);}
  Write(base,P+572,23);swing(188);CHECK(!Load(base,P).Fire() && Float(base,S+8)==7 && spawn_calls.empty());
  Write(base,P+572,1);Write(base,P+584,2);
  // Apollo cast: the bomb is thrown here too, for free.
  deliver(NetId(kNetOff));deliver(NetId(kNetCast,kActionApollo,0));frame(0);
  {bool bomb=false;for(unsigned i=0;i<kProjCount;++i)bomb|=LoadProjectile(base,ProjAddress(P,i)).kind==kProjArc;CHECK(bomb && Float(base,S+8)==7);}
  for(int n=0;n<60;++n)frame(0);ResetProjectiles(base,P);
  // Uranus + Unicorn: the summon runs here (its ally heal attack is what heals
  // this machine's player), but the copy's own HP is left to its owner.
  deliver(NetId(kNetOn,kActionUranus,8,1));frame(0);
  CHECK(Load(base,P).enabled && Load(base,P).action==kActionUranus && Float(base,S+8)==7);
  const auto heal_area=next_hit;for(int n=0;n<120;++n)frame(0);
  CHECK(Float(base,S+4)==50 && next_hit>heal_area);
  for(int n=0;n<int(kSummonSeconds*60);++n)frame(0);CHECK(!Load(base,P).enabled);  // the summon ends by itself
  // Skeleton: the owner's roll decides the bone; the copy throws that one.
  deliver(NetId(kNetOn,kActionPluto,9,1));frame(0);
  {auto s=Load(base,P);s.cast_remaining=0;Save(base,P,s);}
  deliver(NetId(kNetSwing,kActionPluto,9,2));frame(0);CHECK(Read(base,P+kAllState+100)==2);
  deliver(NetId(kNetSwing,kActionPluto,9,0));frame(0);CHECK(Read(base,P+kAllState+100)==1);
  // Jupiter + Black Dog's self-poison is the owner's HP too.
  deliver(NetId(kNetOn,kActionJupiter,9,1));frame(0);{auto s=Load(base,P);s.cast_remaining=0;Save(base,P,s);}
  for(int n=0;n<130;++n)frame(0);CHECK(Load(base,P).enabled && Float(base,S+4)==50);
  // The attack button follows the owner: held, plus the press once.
  deliver(NetId(kNetAttack,0,0,1));frame(0);CHECK(Read(base,P+kNet+84)==1 && Read(base,P+kNet+88)==0);
  deliver(NetId(kNetAttack,0,0,0));frame(0);CHECK(Read(base,P+kNet+84)==0);
  // A full queue keeps the newest events.
  for(unsigned n=0;n<kNetQueue+4;++n)deliver(NetId(kNetAttack,0,0,n&1));
  CHECK(Read(base,P+kNet)-Read(base,P+kNet+4)==kNetQueue);frame(0);CHECK(Read(base,P+kNet)==Read(base,P+kNet+4));
  // No grant, equipment, playtime, mastery or card change reached this machine's save.
  CHECK(std::equal(save_before.begin(),save_before.end(),base+SAVE) && spawn_calls.empty());
  // A new level clears what was replayed.
  ctx.r3.u64=P;sub_836D00F8(ctx,base);CHECK(Action(base,P)==kActionUnavailable && Read(base,P+kNet)==0);
  ctx.r3.u64=P;ctx.r4.u64=T;sub_836D11B8(ctx,base);
  Write(base,O+0x930,1);ResetNet(base,P);ResetProjectiles(base,P);ResetSummon(base,P);
}
