// Tackle Martial Art (nathan_tackle_guest.h, collider path in nathan_dss_damage.cpp).
{
  constexpr uint32_t T=0x60000,TV=0x60100;
  // Entry 268: the inherited command (index 0) becomes Nathan's Martial Art.
  const auto calls=simon_command_calls;
  ctx.r3.u64=P;ctx.r4.u64=0;ctx.r5.u64=T+0x40;ctx.r6.u64=T+0x44;sub_836D4638(ctx,base);
  CHECK(Read(base,T+0x40)==10 && Read(base,T+0x44)==kTackleArt && simon_command_calls==calls);
  ctx.r3.u64=P;ctx.r4.u64=1;ctx.r5.u64=T+0x40;ctx.r6.u64=T+0x44;sub_836D4638(ctx,base);CHECK(simon_command_calls==calls+1);
  Write(base,T,TV);Write(base,TV+0x10,0x80000120);Write(base,T+4,P);Write(base,T+8,S);
  Float(base,S+0x13C,100);Float(base,S+0x18C,0);Float(base,S+8,100);Float(base,S+4,100);Write(base,S+308,0);
  // Any other command index keeps Simon's state 37.
  Write(base,P+0x16C,25);const auto enters=simon_enter,updates=simon_update;
  ctx.r3.u64=T;sub_836D16C8(ctx,base);CHECK(simon_enter==enters+1);
  ctx.r3.u64=T;sub_836D17A8(ctx,base);CHECK(simon_update==updates+1);
  // Enter: pays the row's MP, plays motion 193 (body slot 26), starts still.
  Write(base,P+0x16C,kTackleArt);Float(base,P+0x178,kTackleMp);
  ctx.r3.u64=T;sub_836D16C8(ctx,base);
  CHECK(Float(base,S+8)==100-kTackleMp && Read(base,P+0x248)==kTackleMotion && Read(base,P+kTackle)==1 && simon_enter==enters+1);
  // Wind-up: no movement, no attack.
  const auto hits=next_hit;Float(base,P+0x234,1.0f/60);
  Float(base,P+0x238,kTackleWindupSeconds/2);ctx.r3.u64=T;sub_836D17A8(ctx,base);
  CHECK(Float(base,S+0x150)==0 && next_hit==hits);
  // Dash: walk speed x kTackleSpeedWalks in the facing direction, and exactly
  // one attack area for the whole dash, tagged with this tackle's wave.
  Float(base,P+0x238,kTackleWindupSeconds+.05f);ctx.r3.u64=T;sub_836D17A8(ctx,base);
  const float dir=Float(base,P+kTackle+8);CHECK(dir==1);
  CHECK(Float(base,S+0x150)==dir*100*kTackleSpeedWalks && Float(base,S+0x158)==0 && next_hit==hits+0x1000 && Read(base,P+kTackle+12)==1);
  const auto area=hits;CHECK(Read(base,area+0x190)==kTackleTag && Read(base,area+0x184)==Read(base,P+kTackle+4));
  CHECK(Float(base,area+0x110)>0);
  Float(base,P+0x238,kTackleWindupSeconds+.1f);ctx.r3.u64=T;sub_836D17A8(ctx,base);CHECK(next_hit==hits+0x1000);
  // While dashing the area stays alive past the normal 0.12 s collider life and follows Nathan.
  Float(base,area+0x188,.5f);ctx.r3.u64=area;ctx.f1.f64=1.0/60;base[area+0x17]=0;sub_824827F0(ctx,base);
  CHECK(base[area+0x17]==0 && Float(base,area+0x188)<.12f);
  // Recovery: brakes like the slide; the area is released.
  Float(base,P+0x238,kTackleWindupSeconds+kTackleDashSeconds+.01f);ctx.r3.u64=T;sub_836D17A8(ctx,base);
  CHECK(std::fabs(Float(base,S+0x150))<100*kTackleSpeedWalks && Read(base,P+kTackle+12)==0);
  ctx.r3.u64=area;ctx.f1.f64=1.0/60;base[area+0x17]=0;sub_824827F0(ctx,base);CHECK(base[area+0x17]==1);
  // The end of the animation returns him to neutral through the state's own entry.
  const auto ends=tackle_ends;Float(base,P+0x238,kTackleSeconds+.01f);ctx.r3.u64=T;sub_836D17A8(ctx,base);
  CHECK(tackle_ends==ends+1 && Read(base,P+kTackle)==0 && Float(base,S+0x150)==0);
  // Facing left (player+0x250 == 1) dashes left.
  Write(base,P+0x250,1);ctx.r3.u64=T;sub_836D16C8(ctx,base);Float(base,P+0x238,kTackleWindupSeconds+.05f);
  ctx.r3.u64=T;sub_836D17A8(ctx,base);CHECK(Float(base,P+kTackle+8)==-1 && Float(base,S+0x150)==-100*kTackleSpeedWalks);
  Float(base,P+0x238,kTackleSeconds+.01f);ctx.r3.u64=T;sub_836D17A8(ctx,base);Write(base,P+0x250,0);
  // Getting hit (native interrupt) ends it at once.
  ctx.r3.u64=T;sub_836D16C8(ctx,base);tackle_interrupt=1;Float(base,P+0x238,kTackleWindupSeconds+.05f);
  ctx.r3.u64=T;sub_836D17A8(ctx,base);tackle_interrupt=0;CHECK(tackle_ends==ends+3 && Read(base,P+kTackle)==0);
  // Not enough MP: nothing is paid, no motion, and the state ends.
  Float(base,S+8,5);Write(base,P+0x248,2);ctx.r3.u64=T;sub_836D16C8(ctx,base);
  CHECK(Float(base,S+8)==5 && Read(base,P+kTackle)==2 && Read(base,P+0x248)==2);
  ctx.r3.u64=T;sub_836D17A8(ctx,base);CHECK(tackle_ends==ends+4);
  // Exit always clears the tackle and keeps Simon's generic exit.
  const auto exits=simon_exit;Write(base,P+kTackle,1);ctx.r3.u64=T;sub_836D18B8(ctx,base);
  CHECK(Read(base,P+kTackle)==0 && simon_exit==exits+1);
  Write(base,P+0x16C,0);Float(base,S+8,100);
  // First update of a level grants the Martial Art item once (the menu lists
  // owned ones), keeping the inventory byte's low nibble, and adds it to the
  // actor's own item lists (owner+0x9CC) that the in-level pause menu reads.
  const auto save=APP+0x1018,at=save+0x3E8+0x8AD+kTackleArt;
  const auto table=Load(base,P).motion_table;CHECK(table!=0);
  Write(base,O+0x9CC,0x70000);const auto adds=tackle_list_adds;
  base[at]=0x03;ctx.r3.u64=P;sub_836D00F8(ctx,base);ctx.r3.u64=P;ctx.r4.u64=table;sub_836D11B8(ctx,base);
  CHECK(base[at]==0x03 && Read(base,P+kTackle+16)==0);
  frame(0);CHECK(base[at]==0x13 && tackle_list_adds==adds+1 && tackle_list_last==0x70000);
  frame(0);CHECK(base[at]==0x13 && tackle_list_adds==adds+1);
  // Already owned but not marked acquired (the earlier build's 0x10): gains
  // the acquired bits, keeps its count, and is not added twice.
  ctx.r3.u64=P;sub_836D00F8(ctx,base);ctx.r3.u64=P;ctx.r4.u64=table;sub_836D11B8(ctx,base);
  base[at]=0x10;frame(0);CHECK(base[at]==0x13 && tackle_list_adds==adds+1);
  // Already acquired: untouched.
  ctx.r3.u64=P;sub_836D00F8(ctx,base);ctx.r3.u64=P;ctx.r4.u64=table;sub_836D11B8(ctx,base);
  base[at]=0x27;frame(0);CHECK(base[at]==0x27 && tackle_list_adds==adds+1 && Read(base,P+kTackle+16)==1);
  // Fresh save: one Mercury, one Salamander, Card Swap and the Tackle become
  // owned and enter the actor's lists; existing counts are never changed.
  for(const auto item:{0x6CDu,0x6CEu,0xC5u,0x8B8u}) base[save+0x3E8+item]=0;
  base[save+0x3E8+0x6CF]=0x53; // a collected card stays as it is
  list_items.clear();ctx.r3.u64=P;sub_836D00F8(ctx,base);ctx.r3.u64=P;ctx.r4.u64=table;sub_836D11B8(ctx,base);frame(0);
  for(const auto item:{0x6CDu,0x6CEu,0xC5u,0x8B8u}) CHECK(base[save+0x3E8+item]==0x13);
  CHECK(base[save+0x3E8+0x6CF]==0x53 && list_items==std::vector<uint32_t>({0x6CD,0x6CE,0xC5,0x8B8}));
  base[save+0x3E8+0x6CD]=0x93;ctx.r3.u64=P;sub_836D00F8(ctx,base);ctx.r3.u64=P;ctx.r4.u64=table;sub_836D11B8(ctx,base);frame(0);
  CHECK(base[save+0x3E8+0x6CD]==0x93);
  Write(base,O+0x9CC,0);
  // Martial Arts page: Nathan's entry (here the second) gets the input row on
  // both of its text widgets: down, down-forward, forward + the configured
  // whip-attack button (save model byte 0; 2 = X). Other entries are untouched.
  {
    constexpr uint32_t page=0x61000,widget_a=0x62000,widget_b=0x62100,label_a=0x62200,label_b=0x62300,vt=0x62400;
    Write(base,page+0xB8,2);Write(base,page+0xC4,0x8B4);Write(base,page+0xC8,0x8AD+kTackleArt);
    Write(base,0x821D34B4+4,3);Write(base,0x821D356C+4,4);
    Write(base,page+3*4,widget_a);Write(base,page+4*4,widget_b);
    Write(base,widget_a+0x10,widget_a+0x20);Write(base,widget_a+0x20,label_a);
    Write(base,widget_b+0x10,widget_b+0x20);Write(base,widget_b+0x20,label_b);
    Write(base,label_a,vt);Write(base,label_b,vt);Write(base,vt+8,0x80000124);
    base[save]=2;martial_rows_set.clear();ctx.r1.u64=0x7F000;
    ctx.r3.u64=page;sub_823ED2E0(ctx,base);
    CHECK(martial_rows_set.size()==2 && martial_rows_set[0].first==label_a && martial_rows_set[1].first==label_b);
    CHECK(martial_rows_set[0].second=="345X" && martial_rows_set[1].second=="345X");
    base[save]=3;martial_rows_set.clear();ctx.r3.u64=page;sub_823ED2E0(ctx,base);CHECK(martial_rows_set[0].second=="345Y");
    Write(base,page+0xC8,0x8B4);martial_rows_set.clear();ctx.r3.u64=page;sub_823ED2E0(ctx,base);CHECK(martial_rows_set.empty());
  }
}
