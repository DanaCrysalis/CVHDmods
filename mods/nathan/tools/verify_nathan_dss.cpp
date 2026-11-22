// Execute the actual native DSS wrappers against a sparse guest address space.
// Original game functions are stubs: checks cover the integration's field
// offsets, allocation size, per-player state, input, MP, animation routing,
// STR results and shared weapon flags, without launching the game.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <vector>
#include <string>
#include <utility>
#include <rex/ppc/context.h>
#include "hod_hooks.h"
#include "nathan_audio_guest.h"
#include "nathan_card_swap_guest.h"
#include "nathan_dss_menu.h"
#include "nathan_uranus_guest.h"
#include "nathan_progress_guest.h"
#include "nathan_projectiles_guest.h"
#include "nathan_tackle_state.h"
#include "nathan_tackle_assets.h"
#include "nathan_dss_balance.h"
using namespace harmony::nathan;

REX_EXTERN(VerifySummon_8224E4E8);REX_EXTERN(VerifySummon_8224AE48);
REX_EXTERN(sub_836D0000); REX_EXTERN(sub_836D00F8); REX_EXTERN(sub_836D11B8);
REX_EXTERN(sub_836D36B8);REX_EXTERN(sub_836D3790);
REX_EXTERN(sub_82451AA8);REX_EXTERN(sub_8245D9A0);REX_EXTERN(sub_823C90C0);REX_EXTERN(sub_8245BCA8);REX_EXTERN(sub_8244E3C8);
REX_EXTERN(sub_836D1FC8); REX_EXTERN(sub_836DBEF8); REX_EXTERN(sub_836D3670);
REX_EXTERN(sub_8246F5C0);REX_EXTERN(sub_8246C408); REX_EXTERN(sub_836D1358); REX_EXTERN(sub_836D1378);
REX_EXTERN(sub_824476B8); REX_EXTERN(sub_823D2648);
REX_EXTERN(sub_82412880);
REX_EXTERN(sub_823D7170);REX_EXTERN(sub_825BFF28);
REX_EXTERN(__imp__sub_82412880) {ctx.r3.u64=Read(base,ctx.r3.u32+(0x38+12)*4);ctx.r4.u64=0;sub_823D2648(ctx,base);}
std::vector<unsigned> draw_palettes;
std::vector<std::pair<float,unsigned>> draw_blends;
unsigned character_draw_frame=12;
std::vector<unsigned> draw_material_palettes;
std::vector<std::pair<uint32_t,uint32_t>> draws;
std::vector<std::pair<float,float>> draw_scales;
struct DrawPlace {int x,y,pivot_x,pivot_y;};
std::vector<DrawPlace> draw_places;
REX_EXTERN(__imp__sub_823D2648) { draw_blends.emplace_back(Float(base,ctx.r3.u32+80),base[ctx.r3.u32+140]); {const auto s=ctx.r3.u32;draw_places.push_back({int32_t(ctx.r5.u32),int32_t(ctx.r6.u32),int16_t(uint16_t(base[s+116]<<8|base[s+117])),int16_t(uint16_t(base[s+118]<<8|base[s+119]))});} draw_palettes.push_back(base[ctx.r3.u32+0x55]);const auto resource=Read(base,ctx.r3.u32+12);draw_material_palettes.push_back(resource?Read(base,resource+0x24):0);draws.emplace_back(ctx.r3.u32,ctx.r4.u32);draw_scales.emplace_back(Float(base,ctx.r3.u32+0x28),Float(base,ctx.r3.u32+0x2C));ctx.r3.u64=0xD00D; }
REX_EXTERN(__imp__sub_824476B8) {
  const auto owner=ctx.r3.u32,body=Read(base,owner+0x2C);
  // 825AE620: the draw position is the truncated owner+64/+68 world position.
  ctx.r5.u64=uint32_t(int32_t(Float(base,owner+64)));ctx.r6.u64=uint32_t(int32_t(Float(base,owner+68)));
  ctx.r3.u64=body;ctx.r4.u64=character_draw_frame;sub_823D2648(ctx,base);
  if (owner==0x30000) { // nested draw must restore the previous character scope
    ctx.r3.u64=0xB0000;sub_824476B8(ctx,base);
    ctx.r3.u64=body;ctx.r4.u64=character_draw_frame;sub_823D2648(ctx,base);
    ctx.r3.u64=0xD0000;ctx.r4.u64=12;sub_823D2648(ctx,base); // unrelated effect
  }
}
REX_EXTERN(__imp__sub_8246F5C0) {}
REX_EXTERN(sub_824699B8);REX_EXTERN(sub_82469D18);
REX_EXTERN(sub_823D31C8);REX_EXTERN(sub_823D4098);
uint32_t started_clip=0,queried_clip=0;
REX_EXTERN(__imp__sub_824699B8) {ctx.r4.u64=0;sub_823D31C8(ctx,base);}
REX_EXTERN(__imp__sub_82469D18) {ctx.r4.u64=0;sub_823D4098(ctx,base);}
REX_EXTERN(__imp__sub_823D31C8) {started_clip=ctx.r4.u32;}
REX_EXTERN(__imp__sub_823D4098) {queried_clip=ctx.r4.u32;}
constexpr uint32_t P=0x10000,S=0x20000,O=0x30000,E=0x40000,I=0x50000;
constexpr uint32_t ST=0x60000,T=O+0x74,W=0x70000,M=0x80000,REG=0x90000;
constexpr uint32_t ownerHandle=0xABCD1234,weaponHandle=0xABCD4321;
REX_EXTERN(sub_8246D8E8);
REX_EXTERN(sub_82452658);REX_EXTERN(sub_8244BF10);REX_EXTERN(sub_8245D008);
unsigned normal_hits=0,mastery_award=1;
REX_EXTERN(__imp__sub_82452658) {ctx.f1.f64=100;}
REX_EXTERN(__imp__sub_8244BF10) {++normal_hits;ctx.r3.u64=0;}
REX_EXTERN(__imp__sub_8245D008) {
  if(ctx.r4.u32==1 && ctx.r5.u32<50) {
    const auto save=Inventory(ctx,base),at=save+MasteryOffset(ctx.r5.u32);
    Write(base,at,std::min(99999u,Read(base,at)+mastery_award));
  }
}
REX_EXTERN(sub_824827F0);REX_EXTERN(sub_82484918);
int checks=0,last_check=0,frame_origin=0;uint8_t* diagnostic_base=nullptr;
LONG CALLBACK HarnessException(EXCEPTION_POINTERS* e) {
  if(e->ExceptionRecord->ExceptionCode==EXCEPTION_ACCESS_VIOLATION){
    std::fprintf(stderr,"Access violation after check line %d (#%d), guest offset %llx\n",last_check,checks,(unsigned long long)e->ExceptionRecord->ExceptionInformation[1]-(unsigned long long)diagnostic_base);std::fprintf(stderr,"Frame origin %d, action %u attr %u state %u MP %g\n",frame_origin,Read(diagnostic_base,P+1056),Read(diagnostic_base,P+1016),Read(diagnostic_base,P+572),Float(diagnostic_base,S+8));std::fflush(stderr);
  }
  return EXCEPTION_CONTINUE_SEARCH;
}
#define CHECK(x) do { ++checks;last_check=__LINE__; if (!(x)) { std::printf("FAILED line %d: %s\n",__LINE__,#x); std::fflush(stdout); std::abort(); } } while(0)

REX_EXTERN(__imp__sub_836D1948) { Write(base,ctx.r3.u32+88,S); }
REX_EXTERN(__imp__sub_836D00F8) {}
REX_EXTERN(__imp__sub_836D11B8) {
  for (uint32_t n=187;n<=192;++n) Write(base,ctx.r4.u32+n*8,n==188?17:n==191?28:n==192?29:16);
}
float native_step_x=0,native_step_y=0;
REX_EXTERN(__imp__sub_836D1FC8) {
  Float(base,S+320,Float(base,S+328));Float(base,S+324,Float(base,S+332));
  Float(base,S+328,Float(base,S+328)+native_step_x);Float(base,S+332,Float(base,S+332)+native_step_y);
  CHECK(!(Read(base,I)&(kRb|kY)) && !(Read(base,I+4)&(kRb|kY)));
  if(Read(base,0x10000+kSwapHeld)) CHECK(!(Read(base,I)&kDirections) && !(Read(base,I+4)&kDirections));
}
REX_EXTERN(sub_836DC9A0);REX_EXTERN(sub_836D7C50);
float native_walk_speed=0,native_stop_speed=0;
static float NativeBootsFormula(uint8_t* base,uint32_t state) {
  const auto stats=Read(base,state+8);return 1+(Float(base,stats+388)+Float(base,stats+392))*.01f;
}
REX_EXTERN(__imp__sub_836DC9A0) {native_walk_speed=NativeBootsFormula(base,ctx.r3.u32);}
REX_EXTERN(__imp__sub_836D7C50) {const auto state=ctx.r3.u32;sub_836DC9A0(ctx,base);native_stop_speed=NativeBootsFormula(base,state);}
REX_EXTERN(__imp__sub_836DBEF8) { Write(base,Read(base,ctx.r3.u32+4)+584,ctx.r4.u32); }
REX_EXTERN(__imp__sub_836D3670) { ctx.f1.f64=100; }
REX_EXTERN(__imp__sub_836D36B8) { ctx.f1.f64=103; }
REX_EXTERN(__imp__sub_836D3790) { ctx.f1.f64=107; }
REX_EXTERN(__savefpr_28) {}
REX_EXTERN(__restfpr_28) {}
float armor_defense=200,defense_buff=0;
REX_EXTERN(sub_8245AA88) {ctx.f1.f64=armor_defense;}
REX_EXTERN(sub_82452ED0) {ctx.f1.f64=defense_buff;}
REX_EXTERN(__imp__sub_8245D9A0) {
  const auto out=ctx.r4.u32;
  Float(base,out+0x10,100);Float(base,out+0x14,80);Float(base,out+0x18,203);Float(base,out+0x1C,100);Float(base,out+0x20,103);Float(base,out+0x24,109);Float(base,out+0x2C,107);
}
REX_EXTERN(__imp__sub_823C90C0) { ctx.r3.u64=0x12345678; }
float heart_gain=5;double added_mp=0;
REX_EXTERN(__imp__sub_8244E3C8) {
  added_mp=ctx.f1.f64;
  const auto player=Read(base,ctx.r3.u32+0x924),stats=Read(base,player+88);
  Float(base,stats+8,std::clamp(Float(base,stats+8)+float(added_mp),0.0f,Float(base,stats+20)+Float(base,stats+32)));
}
REX_EXTERN(__imp__sub_8245BCA8) {
  ctx.r3.u64=0x30000;ctx.f1.f64=heart_gain;sub_8244E3C8(ctx,base);
}
REX_EXTERN(__imp__sub_8246D8E8) {ctx.r3.u64=0x178000;}
REX_EXTERN(__imp__sub_8246C408) { ctx.r3.u64=0x800000C0; }
std::vector<unsigned> audio_ids;
void Audio(PPCContext& ctx,uint8_t* base) {
  unsigned id=0;std::sscanf(reinterpret_cast<const char*>(base+ctx.r3.u32),"VX_NAT_S%u",&id);
  CHECK(id && ctx.r6.u32==1);audio_ids.push_back(id);ctx.r3.u64=123;
}
void Allocate(PPCContext& ctx,uint8_t*) { CHECK(ctx.r3.u32==kSize);ctx.r3.u64=P; }
// Native 8244CA98 stand-in: records Nathan's announced spawn events.
struct SpawnCall {uint32_t owner,id,kind,sub,tag_a,tag_b,sp;};
std::vector<SpawnCall> spawn_calls;
void SpawnEvent(PPCContext& ctx,uint8_t* base) {
  CHECK(ctx.r1.u32%16==0 && Read(base,ctx.r1.u32+0x5C)==0 && Read(base,ctx.r1.u32+0x6C)==0);
  spawn_calls.push_back({ctx.r3.u32,ctx.r4.u32,ctx.r5.u32,ctx.r6.u32,ctx.r9.u32,ctx.r10.u32,ctx.r1.u32});
}
// Nathan's spawn-event and collider-prepare handlers are reached through the
// real hook hub (core/runtime/hod_hub.cpp), ending in stand-in originals:
// the spawn event's game function does nothing here; a prepare call that
// reaches the game's function was not consumed by Nathan.
bool prepare_reached_game=false;
void SpawnThroughHub(PPCContext& ctx,uint8_t* base) {hod::Dispatch(hod::Hook::kSpawnEvent,ctx,base);}
bool PrepareThroughHub(PPCContext& ctx,uint8_t* base) {prepare_reached_game=false;hod::Dispatch(hod::Hook::kColliderPrepare,ctx,base);return !prepare_reached_game;}
using SpawnEventHook=void(*)(PPCContext&,uint8_t*);SpawnEventHook registered_spawn_hook=&SpawnThroughHub;
using PrepareHitHook=bool(*)(PPCContext&,uint8_t*);PrepareHitHook registered_prepare_hook=&PrepareThroughHub;
constexpr uint32_t APP=0x100000,SAVE=APP+0x1018;
uint32_t soul_slots[200]={},soul_permissions[200]={};
void GameData(PPCContext& ctx,uint8_t*) {ctx.r3.u64=APP;}
// Stand-ins for the native attack sources. Whip ATK 100 and INT 0 keep the
// magic rule at 100 x scale, the same figures the STR 100 fixture gave.
float test_whip_attack=100,test_int=0;unsigned whip_attack_calls=0,physical_attack_calls=0;
uint32_t last_attack_character=0;
void TestWhipAttack(PPCContext& ctx,uint8_t*) {CHECK(ctx.r4.u32==kWhipIndex);++whip_attack_calls;last_attack_character=ctx.r3.u32;ctx.f1.f64=test_whip_attack;}
void TestIntellect(PPCContext& ctx,uint8_t*) {ctx.f1.f64=test_int;}
// 824519C8 is ATK + (ATK/64 + 0.25) x STR; the fixture returns hooked STR so
// melee figures stay comparable and still pass through the STR override.
void TestPhysicalAttack(PPCContext& ctx,uint8_t* base) {CHECK(ctx.r4.u32==kWhipIndex);++physical_attack_calls;ctx.r3.u64=Read(base,ctx.r3.u32+0x924);sub_836D3670(ctx,base);}
void LocalActor(PPCContext& ctx,uint8_t*) {ctx.r3.u64=ownerHandle;}
void FxResourceReady(PPCContext& ctx,uint8_t* base) {Write(base,ctx.r3.u32+12,0x17A000);Write(base,0x17A024,0x17B000);ctx.r3.u64=1;}
void NormalHunter(PPCContext& ctx,uint8_t*) {ctx.r3.u64=0;}
void TotalCon(PPCContext& ctx,uint8_t* base) {const auto s=Read(base,ctx.r3.u32+88);ctx.f1.f64=Float(base,s+104)+Float(base,s+240);}
void ExtraCon(PPCContext& ctx,uint8_t* base) {ctx.f1.f64=Float(base,Read(base,ctx.r3.u32+88)+84);}
void SoulSlot(PPCContext& ctx,uint8_t*) {const auto i=ctx.r3.u32-0x673;ctx.r3.u64=i<200?soul_slots[i]:0;}
void Permission(PPCContext& ctx,uint8_t*) {const auto i=ctx.r3.u32-0x673;ctx.r3.u64=i<200 && ctx.r4.u32==12?soul_permissions[i]:0;}
REX_EXTERN(sub_823C4E00);REX_EXTERN(sub_82454000);REX_EXTERN(sub_823C2340);
REX_EXTERN(__savegprlr_29) {} REX_EXTERN(__restgprlr_29) {}
float test_floor=300,test_wall=100000;
REX_EXTERN(sub_823C3F30) {ctx.r3.u64=0;}
REX_EXTERN(sub_823C31D8) {ctx.r3.u64=(ctx.r4.s32>=test_wall || ctx.r5.s32>=test_floor)?8:0;}

unsigned area_resolves=0,heal_numbers=0;int last_heal=0;
unsigned area_submits=0,fallback_ticks=0,fallback_contacts=0;uint32_t next_hit=0x120000;
REX_EXTERN(__imp__sub_824827F0) {++fallback_ticks;}
REX_EXTERN(__imp__sub_82484918) {++fallback_contacts;}
REX_EXTERN(sub_823C3150) {ctx.r3.u64=7;}
REX_EXTERN(sub_823C4C40) {
  const auto rect=ctx.r3.u32,hit=ctx.r6.u32;
  CHECK(SummonCollider(base,hit));CHECK(Read(base,rect+4)==1);
  CHECK(Float(base,rect+8)==Float(base,hit+0x2C)+int32_t(Read(base,hit+0x1A0)) && Float(base,rect+12)==Float(base,hit+0x30)+int32_t(Read(base,hit+0x1A4)));
  CHECK(Float(base,rect+16)==Float(base,hit+0x2C)+int32_t(Read(base,hit+0x1A8)) && Float(base,rect+20)==Float(base,hit+0x30)+int32_t(Read(base,hit+0x1AC)));
  CHECK(ctx.r8.u32>0 && ctx.r7.u32==ownerHandle);
  CHECK((ctx.r4.u32&0x40000002)==0x40000002);
  constexpr uint32_t manager=0x150000,levels=0x151000,level=0x152000,array=0x153000,request=0x154000;
  Write(base,0x8291D918,manager);Write(base,manager+4,levels);Write(base,levels+7*4,level);
  Write(base,level+0x24,array);Write(base,level+0x28,array+4);
  Write(base,level+0x34,array);Write(base,level+0x38,array+4);Write(base,array,request);
  Write(base,request+4,ctx.r4.u32);Write(base,request+0x10,hit);Write(base,request+0x14,ctx.r7.u32);Write(base,request+0x18,ctx.r8.u32);
  ++area_submits;ctx.r3.u64=(ctx.r4.u32&0xC0000000u)|(7u<<22);

}
uint32_t probe_struck=0;unsigned area_probes=0;
REX_EXTERN(sub_823C5098) {
  CHECK(ctx.r3.u32==0x150000 && ctx.r5.u32==0x154000);
  const auto request=ctx.r5.u32,hit=Read(base,request+0x10);
  if(ctx.r6.u32==(0x40000000u|0x20u|2u)) { // overlap probe: reports the first volume, runs no callbacks
    CHECK(ctx.r4.u32==hit+0x1D0);++area_probes;
    Write(base,ctx.r4.u32,probe_struck);Write(base,ctx.r4.u32+4,probe_struck?request:0);
    ctx.r3.u64=probe_struck?1:0;return;
  }
  CHECK(ctx.r6.u32==3);
  CHECK(ctx.r4.u32==hit+0x1C0 && Read(base,request+0x18)>0);
  CHECK(Read(base,hit+kSummonColliderTable+0x1C)==0x824827F0 || Read(base,hit+kSummonColliderTable+0x1C)==0x824823A0);
  CHECK(Read(base,hit+kSummonColliderTable+0x24)==0x825F4170 || Read(base,hit+kSummonColliderTable+0x24)==0x824827F0);
  CHECK(Float(base,hit+0x44)==0 && Float(base,hit+0x48)==0);
  ++area_resolves;ctx.r3.u64=1;
}
REX_EXTERN(sub_825A7F70) {
  CHECK(ctx.r3.u32==O+0xB8C && ctx.r4.s32<0 && ctx.r5.u32==0);
  ++heal_numbers;last_heal=-ctx.r4.s32;
}
void ColliderHeap(PPCContext& ctx,uint8_t*) {CHECK(ctx.r4.u32==kSummonColliderBytes);ctx.r3.u64=next_hit;next_hit+=0x1000;}
void ColliderCtor(PPCContext& ctx,uint8_t* base) {
  CHECK(ctx.r4.u32==0 && ctx.r5.u32==ownerHandle && ctx.r6.u32==12);
  Write(base,ctx.r3.u32+4,ctx.r3.u32);Write(base,ctx.r3.u32+0xA4,ctx.r5.u32);Write(base,ctx.r3.u32+0xB0,0x40000002);
}
// Tackle stand-ins: Simon's command answer, his state 37 and the native
// interrupt checks, plus the command state's "return to neutral" entry.
REX_EXTERN(sub_836D4638);REX_EXTERN(sub_836D16C8);REX_EXTERN(sub_836D17A8);REX_EXTERN(sub_836D18B8);
unsigned simon_command_calls=0,simon_enter=0,simon_update=0,simon_exit=0,tackle_ends=0;
uint8_t tackle_interrupt=0,tackle_airborne=0;
REX_EXTERN(__imp__sub_836D4638) {++simon_command_calls;Write(base,ctx.r5.u32,9);Write(base,ctx.r6.u32,0xFFFFFFFFu);}
REX_EXTERN(__imp__sub_836D16C8) {++simon_enter;}
REX_EXTERN(__imp__sub_836D17A8) {++simon_update;}
REX_EXTERN(__imp__sub_836D18B8) {++simon_exit;}
REX_EXTERN(sub_836DC760) {ctx.r3.u64=tackle_interrupt;}
REX_EXTERN(sub_836DC8B0) {ctx.r3.u64=tackle_airborne;}
void TackleNeutral(PPCContext&,uint8_t*) {++tackle_ends;}
unsigned tackle_list_adds=0;uint32_t tackle_list_last=0;
REX_EXTERN(__imp__sub_823ED2E0) {}
// Native footer: kind 3, nothing shown (the wrapper must take over for cards only).
REX_EXTERN(__imp__sub_823E4AB0) {Write(base,ctx.r4.u32,77);Write(base,ctx.r5.u32,88);base[ctx.r6.u32]=0;base[ctx.r7.u32]=0;ctx.r3.u64=3;}
REX_EXTERN(sub_823E4AB0);
REX_EXTERN(sub_823ED2E0);
std::vector<std::pair<uint32_t,std::string>> martial_rows_set;
void MartialRowText(PPCContext& ctx,uint8_t* base) {CHECK(ctx.r5.u32==1);martial_rows_set.push_back({ctx.r3.u32,std::string(reinterpret_cast<char*>(base+ctx.r4.u32))});}
std::vector<uint32_t> list_items;
void TackleListAdd(PPCContext& ctx,uint8_t*) {CHECK(ctx.r5.u32==1);list_items.push_back(ctx.r4.u32);if(ctx.r4.u32==0x8B8){++tackle_list_adds;tackle_list_last=ctx.r3.u32;}}
namespace rex::runtime { PPCFunc* ResolveIndirectFunction(uint32_t va) { if(va==0x80000120)return &TackleNeutral;if(va==0x80000124)return &MartialRowText;if(va==0x82459868)return &TackleListAdd;if(va==0x8245D178)return &TestWhipAttack;if(va==0x824526D0)return &TestIntellect;if(va==0x824519C8)return &TestPhysicalAttack;if(va==0x823D2520)return &FxResourceReady;if(va==0x823C2340)return &sub_823C2340;if(va==0x823C4E00)return &sub_823C4E00;if(va==0x82454000)return &sub_82454000;if(va==0x825FC4B0)return &ColliderHeap;if(va==0x82481D60)return &ColliderCtor;if(va==0x836D3670)return &sub_836D3670;if(va==0x80000108)return &NormalHunter;if(va==0x8000010C)return &TotalCon;if(va==0x80000110)return &ExtraCon;if (va==0x82223348) return &GameData;if(va==0x8245CCE8)return &LocalActor;if(va==0x82451AA8)return &sub_82451AA8;if(va==0x823C96C8) return &SoulSlot;if(va==0x823C98B0)return &Permission;if (va==0x82239218) return &Audio;if(va==0x8244CA98)return &SpawnEvent; CHECK(va==0x80000100); return &Allocate; } }

int main() {
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
  auto* base=static_cast<uint8_t*>(VirtualAlloc(nullptr,0x100000000ull,MEM_RESERVE,PAGE_READWRITE));
  diagnostic_base=base;AddVectoredExceptionHandler(1,HarnessException);
  CHECK(base);
  CHECK(VirtualAlloc(base+0x10000,0x190000,MEM_COMMIT,PAGE_READWRITE));
  CHECK(VirtualAlloc(base+0x82910000,0x10000,MEM_COMMIT,PAGE_READWRITE));
  CHECK(VirtualAlloc(base+0x836C0000,0x10000,MEM_COMMIT,PAGE_READWRITE));
  CHECK(VirtualAlloc(base+0x836F0000,0x10000,MEM_COMMIT,PAGE_READWRITE));
  for (uint32_t n=187;n<=192;++n) Write(base,0x836C1DD0+n*8,n==188?17:n==191?28:n==192?29:16);
  CHECK(VirtualAlloc(base+0x82100000,0x100000,MEM_COMMIT,PAGE_READWRITE));
  Float(base,0x82102FDC,1);Float(base,0x821030C4,0);Float(base,0x82103838,.5f);Float(base,0x821C8AF0,.01f);
  Write(base,kVtable+42*4,0x80000108);Write(base,kVtable+197*4,0x8000010C);Write(base,kVtable+179*4,0x80000110);
  Float(base,S+104,6);
  Write(base,0x836C1DD0+3*8,1);
  Float(base,0x836C1DCC,1); // module constant: Simon's natural MP regeneration
  DWORD old_protect=0;
  CHECK(VirtualProtect(base+0x836C0000,0x10000,PAGE_READONLY,&old_protect));
  PPCContext ctx{};ctx.fpscr.InitHost();ctx.r1.u64=0x180000;
  ctx.r3.u64=0x80000100;ctx.r4.u64=0x80000104;sub_836D0000(ctx,base);
  CHECK(ctx.r3.u32==P && Read(base,P)==kVtable && !Load(base,P).enabled);
  CHECK(Read(base,0x836F1334)==0x80000104);
  Write(base,0x8291D9F0,M);Write(base,M+0xAC,REG);
  Write(base,REG+(ownerHandle&0xFFFF)*16,ownerHandle);Write(base,REG+(ownerHandle&0xFFFF)*16+4,O);
  Write(base,REG+(weaponHandle&0xFFFF)*16,weaponHandle);Write(base,REG+(weaponHandle&0xFFFF)*16+4,W);
  Write(base,O+8,2); // Native player entity type flag.
  Write(base,O+0x930,1); // control type 1: this machine's player (online copies are not)
  Write(base,P+60,1);Write(base,O+0x924,P);Write(base,O+0x9C8,E); // real live context index, NOT owner handle
  Write(base,E,kWhip);Write(base,E+48,kMercury);Write(base,E+52,kSalamander);Write(base,E+0x50,weaponHandle);
  Write(base,W+0x88,0x91);Write(base,W+0x8C,1);Write(base,W+0x2C,ownerHandle);
  Write(base,P+0x60,ST);Write(base,ST+12,I);Write(base,ST+4,P);
  Float(base,S+4,100);Float(base,S+8,6);
  ctx.r3.u64=P;ctx.r4.u64=T;sub_836D11B8(ctx,base);
  CHECK(Load(base,P).motion_table==T && Read(base,T+187*8)==16);
  auto frame=[&](uint32_t buttons,int call_line=__builtin_LINE()) { frame_origin=call_line; Write(base,I,buttons);Write(base,I+4,buttons);ctx.r3.u64=P;sub_836D1FC8(ctx,base);CHECK(Read(base,I)==buttons && Read(base,I+4)==buttons); };
  auto swing=[&](uint32_t motion) {ctx.r3.u64=ST;ctx.r4.u64=motion;sub_836DBEF8(ctx,base);};
  auto damage=[&]() {ctx.r3.u64=W;sub_8246C408(ctx,base);CHECK(ctx.r3.u32&0x80000000);return ctx.r3.u32&0xFFFF;};
  frame(0x200);CHECK(!Load(base,P).enabled); // LB/backdash is not RB/personal skill
  frame(kRb);CHECK(Load(base,P).enabled && Float(base,S+8)==6);
  frame(kRb);CHECK(Load(base,P).enabled); // held button must not toggle repeatedly
  ctx.r3.u64=P;sub_836D3670(ctx,base);CHECK(std::abs(ctx.f1.f64-105)<0.001);
  Write(base,P+572,23);Write(base,P+608,0);swing(187);
  CHECK(Float(base,S+8)==4 && Read(base,T+187*8)==31 && damage()==0x1C0);
  Write(base,P+608,6); // real shared-code reset while the paid attack is still held
  for(int n=0;n<120;++n) { swing(191);frame(0); }
  CHECK(Float(base,S+8)==4 && Load(base,P).Fire()); // rotation has no repeated cost
  CHECK(Read(base,T+191*8)==33); // held rotation keeps the fire variant
  frame(kRb);CHECK(!Load(base,P).enabled && Read(base,T+191*8)==28 && damage()==0xC0);
  frame(0);frame(kRb);swing(188);
  CHECK(Float(base,S+8)==2 && Read(base,T+188*8)==32 && damage()==0x1C0);
  frame(0);swing(189);CHECK(Float(base,S+8)==0 && Load(base,P).Fire());
  CHECK(damage()==0x1C0); // final paid swing keeps its effect at exactly zero MP
  swing(187);CHECK(Float(base,S+8)==0 && !Load(base,P).enabled && damage()==0xC0);
  frame(0);frame(kRb);CHECK(!Load(base,P).enabled); // insufficient MP cannot enable
  Float(base,S+8,4);frame(0);frame(kRb);swing(187);
  Write(base,E+52,0);frame(0);CHECK(!Load(base,P).enabled && damage()==0xC0);
  Write(base,E+52,kSalamander);frame(kRb);CHECK(Load(base,P).enabled);
  Float(base,S+4,0);frame(0);CHECK(!Load(base,P).enabled && damage()==0xC0);
  Float(base,S+4,100);Float(base,S+8,4);frame(kRb);CHECK(Load(base,P).enabled);
  Float(base,S+0x2C,1.5); // native base 1.0 plus a 0.5 equipment bonus
  ctx.r3.u64=P;sub_836D00F8(ctx,base);CHECK(!Load(base,P).enabled && !Load(base,P).motion_table);
  CHECK(Float(base,S+0x2C)==1.5f+kMpRegenPerSecond-1 && kMpRegenPerSecond==2); // regenerates like Yoko and Charlotte
  ctx.r3.u64=P;sub_836D3670(ctx,base);CHECK(ctx.f1.f64==100);
  // Real airborne playback: the air whip stays in jump/fall states, then
  // changes to grounded motion 187 on landing without starting a new swing.
  ctx.r3.u64=P;ctx.r4.u64=T;sub_836D11B8(ctx,base);
  auto airborne=Load(base,P);airborne.enabled=1;Save(base,P,airborne);
  Float(base,S+8,6);Write(base,P+572,11);Write(base,P+608,0);swing(189);
  CHECK(Float(base,S+8)==4 && Read(base,T+189*8)==36);
  Write(base,P+608,6);
  for (unsigned air_state : {11u,12u,13u,14u,15u,16u}) {
    Write(base,P+572,air_state);frame(0);
    CHECK(Load(base,P).Fire() && Read(base,T+189*8)==36 && damage()==0x1C0);
    CHECK(Float(base,S+8)==4);
  }
  Write(base,P+572,23);Write(base,P+584,187);frame(0);
  CHECK(Load(base,P).Fire() && Read(base,T+187*8)==31 && Float(base,S+8)==4);
  Write(base,P+572,1);Write(base,P+584,2);frame(0);
  CHECK(!Load(base,P).Fire() && damage()==0xC0);
  Write(base,P+572,16);swing(189);frame(0);
  CHECK(Float(base,S+8)==2 && Load(base,P).Fire()); // next air swing pays once
  Write(base,P+584,239);frame(0);
  CHECK(!Load(base,P).Fire() && damage()==0xC0); // another aerial action ends it
  // Wrong generation, another character, a different weapon, or removed card
  // must never receive Nathan's fire flag.
  ctx.r3.u64=P;ctx.r4.u64=T;sub_836D11B8(ctx,base);
  auto state=Load(base,P);state.enabled=state.paid_swing=1;Save(base,P,state);
  Write(base,P,0x83000000);CHECK(damage()==0xC0);Write(base,P,kVtable);
  Write(base,W+0x88,0x8F);CHECK(damage()==0xC0);Write(base,W+0x88,0x91);
  Write(base,REG+(ownerHandle&0xFFFF)*16,ownerHandle+0x10000);CHECK(Paired(base,P));
  CHECK(damage()==0xC0);
  Write(base,O+0x924,P+0x1000);CHECK(!Paired(base,P));
  // Palette transitions preserve canonical frame identity and static idle updates.
  DssState visual{};visual.enabled=1;visual.motion_table=T;
  Write(base,O+0x924,P);Write(base,O+0x2C,0xA0000);
  Write(base,0xB0000+0x2C,0xC0000);Write(base,P+28,42);
  unsigned lowest=kGoldLevels,highest=0;
  for (int n=0;n<256;++n) {
    visual.Frame(false,true,true,18,false,kPulseSeconds/256);
    lowest=std::min(lowest,visual.Level());highest=std::max(highest,visual.Level());
    auto f=visual.BodyFrame(12);CHECK(visual.BodyFrame(f)==f);
    Save(base,P,visual);draws.clear();draw_palettes.clear();ctx.r3.u64=O;sub_824476B8(ctx,base);
    CHECK(f==12 && draw_palettes[0]==visual.PaletteOffset(12));
    CHECK(draw_palettes[1]==0 && draw_palettes[2]==visual.PaletteOffset(12) && draw_palettes[3]==0);
    CHECK(base[0xA0000+0x55]==0 && Read(base,P+1072)==visual.PaletteOffset(12));
    CHECK(draws.size()==4 && ctx.r3.u32==0xD00D);
    CHECK(draws[0].first==0xA0000 && draws[0].second==f);
    CHECK(draws[1].first==0xC0000 && draws[1].second==12);
    CHECK(draws[2].first==0xA0000 && draws[2].second==f);
    CHECK(draws[3].first==0xD0000 && draws[3].second==12);
    CHECK(Read(base,P+28)==42); // preserve the animation-event field
    CHECK(Read(base,P+872)==f && Read(base,P+876)==12 && Read(base,P+880)==2);
    ctx.r3.u64=0xA0000;ctx.r4.u64=12;sub_823D2648(ctx,base);
    CHECK(draws.back().second==12); // scope never escapes the character render
  }
  CHECK(lowest==0 && highest==kGoldLevels);
  // Mixed-palette frames retain identity; only body gets a shader offset,
  // with an independently drawn clipped effect layer in native colors.
  unsigned mixed=0;while(mixed<kBaseFrames && kBodyEffects[mixed]==0xFFFFFFFFu)++mixed;
  CHECK(mixed<kBaseFrames);character_draw_frame=mixed;
  visual.enabled=1;visual.cast_remaining=visual.fade_remaining=0;visual.pulse_time=kPulseSeconds/4;
  Save(base,P,visual);base[0xA0000+0x55]=7;draws.clear();draw_palettes.clear();
  ctx.r3.u64=O;sub_824476B8(ctx,base);
  CHECK(draws[0].second==mixed && draw_palettes[0]==kCostumePalette+visual.PaletteOffset(mixed));
  CHECK(draws[1].first==P+kSummonSprite && draws[1].second==kBodyEffects[mixed] && draw_palettes[1]==0);
  CHECK(base[0xA0000+0x55]==7);
  base[0xA0000+0x55]=0;character_draw_frame=12;
  visual.previous_rb=0;visual.Frame(true,true,true,18,false);
  CHECK(!visual.enabled && visual.fade_remaining==kFadeSeconds && visual.Level()==kWhiteLevels);
  for (int n=0;n<40;++n) visual.Frame(false,true,true,18,false);
  CHECK(visual.BodyFrame(12)==12 && visual.fade_remaining==0);
  DssState cast{};cast.Frame(true,true,true,18,false);
  CHECK(cast.cast_remaining==kCastSeconds && cast.Level()==0);
  for (int n=0;n<int(std::ceil(kCastSeconds*60))+2;++n) cast.Frame(false,true,true,18,false);
  CHECK(cast.enabled && cast.cast_remaining==0);
  // Native sound calls are scoped to Nathan and preserve caller registers.
  ctx.r3.u64=P;ctx.r4.u64=0;sub_836D1358(ctx,base);
  CHECK(std::strcmp(reinterpret_cast<const char*>(base+ctx.r3.u32),"\\data\\sound\\VX_NATHN")==0);
  ctx.r3.u64=P;ctx.r4.u64=1;sub_836D1358(ctx,base);
  CHECK(std::strcmp(reinterpret_cast<const char*>(base+ctx.r3.u32),"\\data\\sound\\VXJ_NATHN")==0);
  ctx.r3.u64=P;ctx.r4.u64=6;sub_836D1378(ctx,base);CHECK(ctx.r3.u32==0);
  InitSounds(base,P);audio_ids.clear();Float(base,S+4,100);
  Write(base,P+572,1);Write(base,P+584,2);FrameSounds(ctx,base,P);
  CHECK(audio_ids.empty());
  Write(base,P+572,11);Write(base,P+584,28);FrameSounds(ctx,base,P);
  CHECK(audio_ids.size()==1 && audio_ids.back()==101);
  FrameSounds(ctx,base,P);CHECK(audio_ids.size()==1);
  Write(base,P+572,12);FrameSounds(ctx,base,P);CHECK(audio_ids.back()==102);
  Write(base,P+572,16);FrameSounds(ctx,base,P);CHECK(audio_ids.size()==2);
  Write(base,P+572,1);Write(base,P+584,2);FrameSounds(ctx,base,P);CHECK(audio_ids.back()==103);
  Float(base,S+4,90);FrameSounds(ctx,base,P);CHECK(audio_ids.back()==421);
  auto count=audio_ids.size();FrameSounds(ctx,base,P);CHECK(audio_ids.size()==count);
  Float(base,S+4,0);FrameSounds(ctx,base,P);CHECK(audio_ids.back()==106);
  count=audio_ids.size();FrameSounds(ctx,base,P);CHECK(audio_ids.size()==count);
  Float(base,S+4,100);InitSounds(base,P);audio_ids.clear();
  Write(base,P+572,1);Write(base,P+584,2);FrameSounds(ctx,base,P);
  Write(base,P+572,23);Write(base,P+584,191);FrameSounds(ctx,base,P);
  CHECK(audio_ids==std::vector<unsigned>({108}));
  for(int i=0;i<7;++i) FrameSounds(ctx,base,P);
  CHECK(audio_ids.size()==1);
  FrameSounds(ctx,base,P);CHECK(audio_ids.size()==2 && audio_ids.back()==108);
  Write(base,P+584,2);Write(base,P+572,1);
  for(int i=0;i<20;++i) FrameSounds(ctx,base,P);
  CHECK(audio_ids.size()==2 && Float(base,P+948)==0);
  InitSounds(base,P);audio_ids.clear();
  for (int i=0;i<9;++i) SwingSound(ctx,base,P);
  CHECK(audio_ids==std::vector<unsigned>({418,419,420}));
  CHECK(Read(base,P+904)==420 && Read(base,P+908)==3 && Read(base,P+912)==123);
  // All ten native Mercury combinations: selection, MP, STR, geometry,
  // collision flags, exact-zero final swing, cancellation and healing.
  Write(base,REG+(ownerHandle&0xFFFF)*16,ownerHandle);
  Write(base,O+0x924,P);Write(base,P,kVtable);Write(base,P+88,S);
  Write(base,O+0x9C8,E);Write(base,E,kWhip);Write(base,E+48,kMercury);
  Write(base,0xD0000+72,weaponHandle);
  Write(base,W+0x88,0x91);Write(base,W+0x8C,1);
  for (unsigned attr=0;attr<10;++attr) {
    InitSounds(base,P);Save(base,P,{});Write(base,P+852,T);
    Write(base,E+52,kSalamander+attr);
    Float(base,S+4,100);Float(base,S+16,200);Float(base,S+28,300);
    Float(base,S+8,kMercuryMp[attr]*2);Write(base,S+308,0);
    Write(base,P+572,1);Write(base,P+584,2);
    frame(0);frame(kRb);
    CHECK(Load(base,P).enabled && Load(base,P).attribute==attr);
    ctx.r3.u64=P;sub_836D3670(ctx,base);
    CHECK(std::abs(ctx.f1.f64-100*kMercuryStrength[attr])<.001);
    for (unsigned pose=0;pose<3;++pose) {
      Float(base,S+8,kMercuryMp[attr]);Write(base,P+572,pose==2?11:pose==1?24:23);
      swing(187+pose);
      CHECK(Float(base,S+8)==0 && Load(base,P).Fire());
      CHECK(Read(base,T+(187+pose)*8)==kMercurySlots[attr][pose]);
      CHECK(damage()==(0xC0|kMercuryElements[attr]));
      ctx.r3.u64=0xD0000;sub_824699B8(ctx,base);
      CHECK(started_clip==2+attr*3+pose);
      ctx.r3.u64=0xD0000;sub_82469D18(ctx,base);
      CHECK(queried_clip==started_clip);
      // Scope ends immediately: an unrelated weapon retains its clip.
      ctx.r4.u64=0;sub_823D31C8(ctx,base);CHECK(started_clip==0);
    }
    CHECK(Float(base,S+4)==(attr==8?115:100));
    swing(187);CHECK(!Load(base,P).enabled && Float(base,S+8)==0);
    CHECK(damage()==0xC0);
    // Changing an attribute cannot carry an already paid effect into another.
    Float(base,S+8,100);Write(base,P+572,1);Write(base,P+584,2);
    frame(0);frame(kRb);Write(base,E+52,kSalamander+(attr+1)%10);frame(0);
    CHECK(!Load(base,P).enabled && damage()==0xC0);
  }
  // Unicorn uses max HP including equipment bonuses, caps healing, and never
  // heals from a failed swing. A 1-HP minimum covers low maximum HP.
  Write(base,E+52,kSalamander+8);Save(base,P,{});Write(base,P+852,T);
  auto mercury_numbers=heal_numbers;
  Float(base,S+8,2*kMercuryMp[8]);Float(base,S+4,499);frame(0);frame(kRb);swing(187);
  CHECK(Float(base,S+4)==500 && heal_numbers==mercury_numbers+1 && last_heal==1);
  swing(187);CHECK(Float(base,S+4)==500 && heal_numbers==mercury_numbers+1); // full HP: no number
  Float(base,S+4,200);swing(187);CHECK(Float(base,S+4)==200 && heal_numbers==mercury_numbers+1);
  Float(base,S+16,50);Float(base,S+28,0);Float(base,S+4,20);Float(base,S+8,20);
  frame(0);frame(kRb);swing(187);CHECK(Float(base,S+4)==21 && heal_numbers==mercury_numbers+2 && last_heal==1);
  // Native hit actor receives hold damage falloff and loses its elemental
  // flag immediately when RB disables DSS during an already spawned swing.
  Write(base,W+60,0xE0000);Write(base,W+64,0xE0004);Write(base,0xE0000,0xF0000);
  Write(base,P+1024,0x800000C0);Write(base,P+1028,100);
  for (unsigned attr : {6u,7u}) {
    Write(base,E+52,kSalamander+attr);DssState h{};h.enabled=h.paid_swing=1;h.attribute=attr;h.hold_time=.1f;h.motion_table=T;Save(base,P,h);
    RefreshWhip(base,P);CHECK(Read(base,0xF0000+364)==(attr==6?63:1));
    CHECK(Read(base,0xF0000+176)==(0x800000C0|kMercuryElements[attr]));
    h.Disable();Save(base,P,h);RefreshWhip(base,P);CHECK(Read(base,0xF0000+176)==0x800000C0);
  }
  // Card Swap: owned inventory only, menu-equivalent category/permission,
  // wraparound, single press per hold, opposite inputs and persistence.
  InitSounds(base,P);Save(base,P,{});Write(base,P+852,T);
  Write(base,O+0x924,P);Write(base,O+0x9C8,E);
  Write(base,E,kWhip);Write(base,E+4,kCardSwap);Write(base,E+32,0x614);Write(base,E+36,0x610);
  Write(base,E+48,kMercury);Write(base,E+52,kSalamander);
  Float(base,S+4,100);Write(base,S+308,0);Write(base,P+572,1);Write(base,P+584,2);
  soul_slots[90]=12;soul_permissions[90]=1;
  for(unsigned i=91;i<=100;++i) {soul_slots[i]=13;soul_permissions[i]=1;}
  for(auto item : {kMercury,kSalamander,kSalamander+2,kSalamander+9})base[SAVE+0x3E8+item]=0x13;
  // Owned foreign passive and unowned Nathan cards must be skipped.
  soul_slots[20]=13;soul_permissions[20]=0;base[SAVE+0x3E8+0x673+20]=0x13;
  CHECK(!CardSwapInput(ctx,base,P,8));CHECK(Read(base,E+52)==kSalamander);
  CHECK(CardSwapInput(ctx,base,P,kY));CHECK(Read(base,P+kSwapHeld)==1);
  CardSwapInput(ctx,base,P,kY|8);CHECK(Read(base,E+52)==kSalamander+2);
  for(int n=0;n<120;++n)CardSwapInput(ctx,base,P,kY|8);
  CHECK(Read(base,E+52)==kSalamander+2);
  CardSwapInput(ctx,base,P,kY);CardSwapInput(ctx,base,P,kY|8);
  CHECK(Read(base,E+52)==kSalamander+9);
  CardSwapInput(ctx,base,P,kY);CardSwapInput(ctx,base,P,kY|8);
  CHECK(Read(base,E+52)==kSalamander);
  CardSwapInput(ctx,base,P,kY);CardSwapInput(ctx,base,P,kY|4);
  CHECK(Read(base,E+52)==kSalamander+9);
  CHECK(Read(base,SAVE+0x28+11*60+13*4)==kSalamander+9);
  CardSwapInput(ctx,base,P,kY);CardSwapInput(ctx,base,P,kY|12);
  CHECK(Read(base,E+52)==kSalamander+9); // opposite directions cancel
  CardSwapInput(ctx,base,P,kY);CardSwapInput(ctx,base,P,kY|2);
  CHECK(Read(base,E+48)==kMercury); // one owned Action Card is a stable cycle
  // Future action cards join through the native classifier, without a new
  // hardcoded cycle list. Not-owned and wrong-character records stay out.
  soul_slots[102]=soul_slots[103]=12;soul_permissions[102]=soul_permissions[103]=1;
  base[SAVE+0x3E8+0x673+102]=0x13;
  CardSwapInput(ctx,base,P,kY);CardSwapInput(ctx,base,P,kY|2);
  CHECK(Read(base,E+48)==kVenus && kVenus==0x673+102);
  CHECK(Read(base,SAVE+0x28+11*60+12*4)==kVenus);
  CHECK(CardArt(kMercury,false)==kCardArtFirst);
  for(unsigned i=0;i<10;++i) {
    CHECK(CardArt(kSalamander+i,true)==kCardArtFirst+20+2*i+1);
    CHECK(CardArt(kSalamander+i,false)==0);
  }
  CHECK(CardArt(kVenus,false)==kCardArtFirst+2 && CardArt(kVenus,true)==0);
  Float(base,S+8,100);frame(0);frame(kRb);swing(187);
  CHECK(Load(base,P).enabled && Float(base,S+8)<100 && damage()==0xC0);
  ctx.r3.u64=P;sub_836D3670(ctx,base);CHECK(ctx.f1.f64==141);
  CardSwapInput(ctx,base,P,kY);CardSwapInput(ctx,base,P,kY|1);
  CHECK(Read(base,E+48)==kMercury);
  Save(base,P,{});Write(base,P+852,T);
  // Every new owned Action Card cycles with its full-art frame, persists,
  // and really casts at the adapted MP costs. Direct casts reach the native
  // hit allocator and terrain globals, so those exist for this loop.
  CHECK(VirtualAlloc(base+0x828F0000,0x10000,MEM_COMMIT,PAGE_READWRITE));
  const auto cycling_level=Read(base,0x8291D918);
  Write(base,0x8291D918,0x150000);Write(base,0x828F57A4,0x1234);Write(base,O+4,ownerHandle); // empty enemy list
  for(unsigned i=0;i<9;++i) {
    soul_slots[102+i]=12;soul_permissions[102+i]=1;
    base[SAVE+0x3E8+kVenus+i]=0x13;
  }
  for(unsigned i=0;i<9;++i) {
    CardSwapInput(ctx,base,P,kY);CardSwapInput(ctx,base,P,kY|2);
    CHECK(Read(base,E+48)==kVenus+i);
    CHECK(CardArt(kVenus+i,false)==kCardArtFirst+2+2*i);
    CHECK(Read(base,SAVE+0x28+11*60+12*4)==kVenus+i);
    Float(base,S+8,100);frame(0);frame(kRb);swing(187);
    CHECK(damage()==0xC0);
  }
  Write(base,0x8291D918,cycling_level);
  CardSwapInput(ctx,base,P,kY);CardSwapInput(ctx,base,P,kY|2);
  CHECK(Read(base,E+48)==kMercury);
  // Regression from the actual equipment screen: Y is secondary WEPN slot
  // 1; slots 8..11 are B / Up+B / Right+B / Down+B, not Y variations.
  Write(base,E+4,0);Write(base,E+32,0x6D8);Write(base,E+36,0x6D8);
  Write(base,E+40,0x612);Write(base,E+44,0x611);
  CardSwapInput(ctx,base,P,0);
  CHECK(kYEquipmentSlot==1 && Read(base,E+4)==kCardSwap && kCardSwap==0xC5);
  CHECK(Read(base,E+32)==0x614 && Read(base,E+36)==0x610);
  CHECK(Read(base,E+40)==0x612 && Read(base,E+44)==0x611);
  CHECK(Read(base,SAVE+0x28+11*60+1*4)==kCardSwap);
  CHECK(Read(base,SAVE+0x28+11*60+8*4)==0x614);
  CHECK(Read(base,SAVE+0x28+11*60+9*4)==0x610);
  Write(base,E+32,0x60F);Write(base,E+36,0x612);CardSwapInput(ctx,base,P,0);
  CHECK(Read(base,E+32)==0x60F && Read(base,E+36)==0x612); // preserve genuine B choices
  // Empty inventories leave the selected cards intact; no grants occur.
  CHECK(CycleCard(ctx,base,0,kMercury,12,1)==kMercury);
  // Holding Y consumes direction inputs but leaves the caller's complete
  // input block restored after the original character update.
  Write(base,E+52,kSalamander);frame(kY|8);
  CHECK(Read(base,E+52)==kSalamander+2 && Read(base,I)==(kY|8));
  frame(0);CHECK(!Read(base,P+kSwapHeld));
  // Card art is drawn on an isolated instance, never tinted by the gold pulse
  // or reflected with Nathan's body. Original body cache/transform is intact.
  Write(base,E+52,kSalamander+2);Write(base,P+kSwapHeld,1);
  Write(base,O+0x2C,0xA0000);base[0xA0000+0x1C]=1;Write(base,0xA0000+0xA0,0xDADADA);
  Float(base,0xA0000+0x28,2);Float(base,0xA0000+0x2C,3);
  draws.clear();draw_scales.clear();ctx.r3.u64=O;sub_824476B8(ctx,base);
  for(unsigned i=0;i<draws.size();++i) if(draws[i].first==P+kCardSprite) {
    CHECK(draw_scales[i].first==1 && draw_scales[i].second==1.5f);
  }
  CHECK(Float(base,0xA0000+0x28)==2 && Float(base,0xA0000+0x2C)==3);
  unsigned card_draws=0;
  for(auto [sprite,frame_index]:draws) if(sprite==P+kCardSprite) {
    ++card_draws;CHECK(frame_index==CardArt(kMercury,false)||frame_index==CardArt(kSalamander+2,true));
  }
  CHECK(card_draws==4 && Read(base,0xA0000+0xA0)==0xDADADA && base[0xA0000+0x1C]==1);
  CHECK(Read(base,P+kCardSprite+0xA0)==0 && !base[P+kCardSprite+0x1C]);
  CHECK(Read(base,P+kCardSprite+0x78)==6 && Float(base,P+kCardSprite+0x60)==60000); // own render list, above the body's
  Float(base,S+4,0);CHECK(!CardSwapInput(ctx,base,P,kY));
  CHECK(!Read(base,P+kSwapHeld) && !Read(base,P+kSwapDirections));
  Float(base,S+4,100);InitSounds(base,P);audio_ids.clear();
  Write(base,P+572,1);FrameSounds(ctx,base,P);
  Float(base,S+4,90);FrameSounds(ctx,base,P);CHECK(audio_ids.back()==421);
  Float(base,S+4,80);FrameSounds(ctx,base,P);CHECK(audio_ids.back()==422);
  // Venus: all seven supported pairs, disabled pairs, timed drain, no swing
  // charge/element, final defense including gear, native INT/LCK rounding.
  Float(base,S+4,100);Write(base,S+308,0);Write(base,E+48,kVenus);
  const double expected_str[10]={112,100,100,100,100,100,100,100,71,141};
  const double expected_def[10]={203,253.75,203,203,203,203,203,203,406,101.5};
  for(unsigned attr=0;attr<10;++attr) {
    Save(base,P,{});Write(base,P+852,T);Write(base,E+52,kSalamander+attr);
    Float(base,S+8,100);Write(base,P+572,1);Write(base,P+584,2);Float(base,P+564,1.0f/60);
    frame(0);frame(kRb);
    CHECK(bool(Load(base,P).enabled)==VenusAvailable(attr));
    const float expected_mp=VenusAvailable(attr)?100-Load(base,P).Drain()/60:100;
    CHECK(std::abs(Float(base,S+8)-expected_mp)<.0001);
    ctx.r3.u64=P;sub_836D3670(ctx,base);CHECK(ctx.f1.f64==expected_str[attr]);
    ctx.r3.u64=O;sub_82451AA8(ctx,base);CHECK(std::abs(ctx.f1.f64-(attr==3 ? 203*(1+CardBonus(base,P)) : expected_def[attr]))<.001);
    ctx.r3.u64=P;sub_836D36B8(ctx,base);CHECK(ctx.f1.f64==(attr==6?128:103));
    ctx.r3.u64=P;sub_836D3790(ctx,base);CHECK(ctx.f1.f64==(attr==2?133:107));
    ctx.r3.u64=0;ctx.r4.u64=0x110000;sub_8245D9A0(ctx,base);
    CHECK(std::abs(Float(base,0x110000+0x18)-(attr==3 ? 203*(1+CardBonus(base,P)) : expected_def[attr]))<.001);
    CHECK(Float(base,0x110000+0x1C)==expected_str[attr]);
    CHECK(Float(base,0x110000+0x20)==(attr==6?128:103));
    CHECK(Float(base,0x110000+0x24)==109); // CON is never mistaken for INT
    CHECK(Float(base,0x110000+0x2C)==(attr==2?133:107));
    float mp=Float(base,S+8);swing(187);CHECK(Float(base,S+8)==mp && damage()==0xC0 && !Load(base,P).Fire());
    if(VenusAvailable(attr)) {
      // Real wrappers must drain the same amount at 30 and 60 updates/sec.
      for(unsigned hz : {30u,60u}) {
        Float(base,S+8,100);Float(base,P+564,1.0f/hz);
        for(unsigned n=0;n<hz;++n) frame(0);
        CHECK(std::abs(Float(base,S+8)-(100-Load(base,P).Drain()))<.001);
      }
      frame(kRb);CHECK(!Load(base,P).enabled && Load(base,P).fade_remaining>0);
      ctx.r3.u64=P;sub_836D3670(ctx,base);CHECK(ctx.f1.f64==100);
      ctx.r3.u64=O;sub_82451AA8(ctx,base);CHECK(ctx.f1.f64==203);
    }
  }
  // Heart pickups apply native gear bonuses first; only positive heart MP
  // is doubled, and native max-MP clamping still runs exactly once.
  Save(base,P,{});Write(base,P+852,T);Write(base,E+52,kSalamander+5);
  Float(base,P+564,1.0f/60);Float(base,S+8,50);Float(base,S+20,100);Float(base,S+32,20);
  frame(0);frame(kRb);Write(base,W+0x68,ownerHandle);
  for(float amount : {1.0f,5.0f,12.5f}) {
    heart_gain=amount;Float(base,S+8,50);ctx.r3.u64=W;sub_8245BCA8(ctx,base);
    CHECK(added_mp==amount*2 && Float(base,S+8)==50+amount*2);
  }
  Float(base,S+8,115);heart_gain=5;ctx.r3.u64=W;sub_8245BCA8(ctx,base);
  CHECK(added_mp==10 && Float(base,S+8)==120);
  Float(base,S+8,50);ctx.r3.u64=O;ctx.f1.f64=7;sub_8244E3C8(ctx,base);
  CHECK(added_mp==7 && Float(base,S+8)==57); // potion/regen outside heart scope
  heart_gain=-5;ctx.r3.u64=W;sub_8245BCA8(ctx,base);CHECK(added_mp==-5);
  frame(0);frame(kRb);heart_gain=5;ctx.r3.u64=W;sub_8245BCA8(ctx,base);CHECK(added_mp==5);
  // Running out of MP, dying, removing cards or swapping Actions immediately
  // cancels the boost and never carries Venus into Mercury's whip profiles.
  for(unsigned reason=0;reason<4;++reason) {
    Write(base,E+48,kVenus);Write(base,E+52,kSalamander);Float(base,S+4,100);Float(base,S+8,50);
    Save(base,P,{});Write(base,P+852,T);frame(0);frame(kRb);
    CHECK(Load(base,P).enabled);
    if(reason==0) Float(base,S+8,.001f);
    if(reason==1) Float(base,S+4,0);
    if(reason==2) Write(base,E+52,0);
    if(reason==3) Write(base,E+48,kMercury);
    frame(0);CHECK(!Load(base,P).enabled && !Load(base,P).Fire());
    ctx.r3.u64=P;sub_836D3670(ctx,base);CHECK(ctx.f1.f64==100);
  }
  // Another character cannot receive the shared defense or heart effect.
  Float(base,S+4,100);Write(base,E+48,kVenus);Write(base,E+52,kSalamander+5);
  Save(base,P,{});Write(base,P+852,T);Float(base,S+8,50);frame(0);frame(kRb);
  Write(base,0xA8000+42*4,0x80000108);Write(base,0xA8000+197*4,0x8000010C);Write(base,0xA8000+179*4,0x80000110);
  Write(base,P,0xA8000);heart_gain=5;ctx.r3.u64=W;sub_8245BCA8(ctx,base);CHECK(added_mp==5);
  ctx.r3.u64=O;sub_82451AA8(ctx,base);CHECK(ctx.f1.f64==203);Write(base,P,kVtable);
  // Real original DEF routine includes armor, CON/2 and Protect-like buffs.
  // The Venus multiplier applies once to the complete native result.
  Write(base,P,kVtable);Write(base,E+48,kVenus);Write(base,E+52,kSalamander+1);
  Float(base,S+4,100);Float(base,S+8,100);Save(base,P,{});Write(base,P+852,T);frame(0);frame(kRb);
  armor_defense=70;Float(base,S+104,30);Float(base,S+240,6);Float(base,S+84,4);
  Float(base,O+0xB68,1);defense_buff=20;
  ctx.r3.u64=O;sub_82451AA8(ctx,base);
  CHECK(std::abs(ctx.f1.f64-135)<.0001); // (70 + (30+6+4)/2) * 1.2 * 1.25
  CHECK(std::abs(Float(base,P+1064)-108)<.0001 && std::abs(Float(base,P+1068)-135)<.0001);
  frame(0);frame(kRb);ctx.r3.u64=O;sub_82451AA8(ctx,base);CHECK(std::abs(ctx.f1.f64-108)<.0001);
  armor_defense=200;defense_buff=0;Float(base,S+104,6);Float(base,S+240,0);Float(base,S+84,0);
  // Attribute descriptions select exactly one pair, including disabled and
  // future actions, with no effect on other items or missing game state.
  Write(base,SAVE+0x28+11*60,kWhip);
  for(unsigned action=0;action<10;++action) {
    Write(base,SAVE+0x28+11*60+48,action ? kVenus+action-1 : kMercury);
    for(unsigned attr=0;attr<10;++attr) {
      ctx.r3.u64=kSalamander+attr;sub_823C90C0(ctx,base);
      CHECK(ctx.r3.u32==0x440E0000+20+action*10+attr);
    }
  }
  ctx.r3.u64=kVenus;sub_823C90C0(ctx,base);CHECK(ctx.r3.u32==0x12345678);
  Write(base,SAVE+0x28+11*60+48,0);ctx.r3.u64=kSalamander;sub_823C90C0(ctx,base);CHECK(ctx.r3.u32==0x12345678);
  Write(base,SAVE+0x28+11*60,0);ctx.r3.u64=kSalamander;sub_823C90C0(ctx,base);CHECK(ctx.r3.u32==0x12345678);
  // Menu footer: Attribute Cards show their pair's LV (copies averaged,
  // rounded down) and MP (0 hides it); Action Cards, other items and other
  // states keep the native one. Item Crash shows the B subweapon's crash cost.
  {
    constexpr uint32_t L=0x180000,Rv=0x180004,SL=0x180008,SR=0x180009;
    auto footer=[&](uint32_t item){ctx.r3.u64=item;ctx.r4.u64=L;ctx.r5.u64=Rv;ctx.r6.u64=SL;ctx.r7.u64=SR;sub_823E4AB0(ctx,base);return unsigned(ctx.r3.u32);};
    Write(base,SAVE+0x28+11*60,kWhip);
    for(unsigned action=0;action<10;++action) {
      const uint32_t a=action ? kVenus+action-1 : kMercury;
      Write(base,SAVE+0x28+11*60+48,a);
      for(unsigned attr=0;attr<10;++attr) {
        Write(base,SAVE+0x28+11*60+52,kSalamander+attr);
        base[SAVE+0x3E8+a]=0x30;base[SAVE+0x3E8+kSalamander+attr]=0x63;  // 3 and 6 copies: 4.5 -> LV 4
        Write(base,SAVE+0x28+11*60+32,0);
        CHECK(footer(kSalamander+attr)==1 && Read(base,L)==4 && base[SL]==1);
        CHECK(Read(base,Rv)==kPairMenuMp[action*10+attr] && base[SR]==(kPairMenuMp[action*10+attr]!=0));
        CHECK(footer(a)==3 && Read(base,L)==77 && base[SL]==0 && base[SR]==0);  // Action Card: native
        base[SAVE+0x3E8+kSalamander+attr]=0xF3;  // copies cap at 9: (3+9)/2 = 6
        CHECK(footer(kSalamander+attr)==1 && Read(base,L)==6);
        base[SAVE+0x3E8+a]=0;base[SAVE+0x3E8+kSalamander+attr]=0;
        CHECK(footer(kSalamander+attr)==1 && Read(base,L)==1);  // pair level is at least 1
      }
    }
    CHECK(kPairMenuMp[90]==0);
    // Item Crash: the equipped B subweapon's crash cost; none (or no crash) hides MP.
    Write(base,SAVE+0x28+11*60+48,kVenus+8);Write(base,SAVE+0x28+11*60+52,kSalamander);
    for(uint32_t sub=0x60F;sub<=0x614;++sub) {
      Write(base,SAVE+0x28+11*60+32,sub);
      CHECK(footer(kSalamander)==1 && Read(base,Rv)==unsigned(kCrashCost[sub-0x60F]) && base[SR]==1);
    }
    Write(base,SAVE+0x28+11*60+32,0x61B);CHECK(footer(kSalamander)==1 && Read(base,Rv)==unsigned(kCrashCost[6]) && base[SR]==1);
    Write(base,SAVE+0x28+11*60+32,0);CHECK(footer(kSalamander)==1 && Read(base,Rv)==0 && base[SR]==0);
    Write(base,SAVE+0x28+11*60+52,kSalamander+5);CHECK(footer(kSalamander+5)==1 && base[SR]==0);  // Pluto + Manticore
    CHECK(footer(0x6D8)==3 && Read(base,L)==77 && base[SL]==0);              // retired row: native
    CHECK(footer(kWhip)==3 && base[SR]==0);                                    // not a card
    Write(base,SAVE+0x28+11*60+52,kSalamander);Write(base,SAVE+0x28+11*60,0);
    CHECK(footer(kSalamander)==3 && Read(base,Rv)==88);                       // not Nathan's loadout
  }
  // Uranus is a direct, one-shot cast: exact cost, no toggle/stat buff,
  // no repeated payment while RB is held, and all ten pairs selectable.
  CHECK(VirtualAlloc(base+0x828F0000,0x10000,MEM_COMMIT,PAGE_READWRITE));
  Write(base,0x8291D918,0x1234);Write(base,0x828F57A4,0x1234);Write(base,O+4,ownerHandle);
  Write(base,E+48,0x6E0);Write(base,P+572,1);Write(base,P+584,2);
  Float(base,O+0x8D4,500);Float(base,O+0x8D8,300);Float(base,S+16,1000);Float(base,S+28,0);
  for(unsigned attr=0;attr<10;++attr) {
    Save(base,P,{});Write(base,P+852,T);Write(base,E+52,kSalamander+attr);
    ResetSummon(base,P);Float(base,S+4,100);Float(base,S+8,kUranusCost[attr]-.5f);
    frame(0);frame(kRb);CHECK(!Load(base,P).enabled);
    frame(0);Float(base,S+8,kUranusCost[attr]);frame(kRb);
    CHECK(Load(base,P).enabled && Load(base,P).action==kActionUranus && Float(base,S+8)==0);
    CHECK(audio_ids.back()==349 && !Load(base,P).Fire() && Load(base,P).Level()==0);
    ctx.r3.u64=P;sub_836D3670(ctx,base);CHECK(ctx.f1.f64==100);
    CHECK(Float(base,P+1280)==500 && Float(base,P+1284)==300);
    for(unsigned n=0;n<30;++n)frame(kRb);
    CHECK(Load(base,P).enabled && Float(base,S+8)==0);
    CHECK(SummonBody(Load(base,P))>=kSummonFloat[0].frame);
    auto spell=Load(base,P);spell.pulse_time=1.01f;spell.cast_remaining=4.49f;Save(base,P,spell);
    draws.clear();draw_places.clear();draw_blends.clear();ctx.r3.u64=O;sub_824476B8(ctx,base);
    const auto body_index=attr==8 && SummonBackdrop(spell)?1u:0u;
    CHECK(draws[body_index].second==SummonBody(spell));
    CHECK(draw_places[body_index].y==int(Float(base,O+68))-60);
    if(SummonBackdrop(spell)){CHECK(draws[0].second==kSummonBeamFrame);CHECK(draw_places[0].y==int(Float(base,O+68)));}
    bool beast=false;for(auto [sprite,f]:draws)if(sprite==P+kSummonSprite && f!=kSummonBeamFrame){CHECK(f==SummonEffect(spell) || f==kSummonCores[attr][SummonTickIndex(spell)].frame);beast=true;}CHECK(beast);
    for(unsigned n=0;n<draws.size();++n)if(draws[n].first==P+kSummonSprite && draws[n].second!=kSummonBeamFrame)CHECK(draw_blends[n].first==.75f && draw_blends[n].second==0);
    auto visual=spell;visual.pulse_time=0;CHECK(SummonLift(visual)==0);
    visual.pulse_time=.25f;CHECK(std::abs(SummonLift(visual)-30)<.001);
    visual.pulse_time=2;visual.cast_remaining=.25f;CHECK(std::abs(SummonLift(visual)-30)<.001);
    visual.cast_remaining=0;CHECK(SummonLift(visual)==0);
    for(unsigned tick=0;tick<kSummonEffectFrames;++tick){visual.pulse_time=(tick+.1f)/kCotmHz;CHECK(SummonEffect(visual)==kSummonEffects[attr]+tick);}
    visual.pulse_time=kSummonSeconds;CHECK(!SummonEffect(visual));
    const auto numbers_before=heal_numbers;const auto previous_hit=next_hit;UpdateSummon(ctx,base,P,spell);
    CHECK(Read(base,P+1288)==1);CHECK(Float(base,S+8)==0);
    if(attr==8) {
      // Nathan is healed directly; allies get one native negative-damage rectangle over the summon area.
      CHECK(Float(base,S+4)==260 && heal_numbers==numbers_before+1 && last_heal==160);
      CHECK(next_hit==previous_hit+0x1000 && SummonCollider(base,previous_hit) && Float(base,previous_hit+0x110)==-160);
      CHECK(Float(base,previous_hit+0x2C)==500 && Float(base,previous_hit+0x30)==260 && Read(base,previous_hit+0x1A8)==uint32_t(kSummonHalfWidth));
    }
    else {
      const auto tick=kSummonTicks[attr][SummonTickIndex(spell)];
      CHECK(next_hit==previous_hit+0x1000*tick.count && Read(base,P+1292)>=tick.count);
      const auto hit=previous_hit;
      if(tick.count) {
        CHECK(SummonCollider(base,hit));
        const auto& geometry=kSummonParticles[tick.first];CHECK(Float(base,hit+0x2C)==500+(geometry.left+geometry.right)/2 && Float(base,hit+0x30)==300+(geometry.top+geometry.bottom)/2);
        CHECK((Read(base,hit+0xB0)&0xFFFF)==(0x42|kMercuryElements[attr]));
        CHECK(Float(base,hit+0x114)==12/kCotmHz && base[hit+0x9F]>=0xD0);
        const auto before=area_submits;ctx.r3.u64=hit;ctx.f1.f64=1.0/60;
        CHECK(registered_prepare_hook && registered_prepare_hook(ctx,base));
        CHECK(area_submits==before+1);ctx.r3.u64=hit;sub_824827F0(ctx,base);CHECK(area_resolves==area_submits);
        ctx.r3.u64=hit;sub_824827F0(ctx,base);CHECK(area_submits==before+1 && area_resolves==area_submits);
        // Same actor follows the current visible sprite and survives longer
        // than the old 120ms rectangle; a stale cast is rejected immediately.
        for(unsigned n=0;n<10;++n){ctx.r3.u64=hit;registered_prepare_hook(ctx,base);ctx.r3.u64=hit;sub_824827F0(ctx,base);}CHECK(!base[hit+0x17]);
        Write(base,hit+0x198,Read(base,P+1308)-1);ctx.r3.u64=hit;registered_prepare_hook(ctx,base);CHECK(base[hit+0x17]);Write(base,hit+0x198,Read(base,P+1308));base[hit+0x17]=0;
      }
      if(attr==9) {
        const unsigned pair=0x170000,a=pair+0x40,b=pair+0x80;
        Write(base,pair,a);Write(base,pair+4,b);base[pair+12]=base[pair+13]=0;
        Write(base,a+0x10,hit);Write(base,b+4,0x10);Write(base,b+0x14,0xCAFE);
        ctx.r3.u64=hit;ctx.r5.u64=pair;sub_82484918(ctx,base);CHECK(Float(base,S+4)==110);
        ctx.r3.u64=hit;ctx.r5.u64=pair;sub_82484918(ctx,base);CHECK(Float(base,S+4)==110);
        Write(base,b+0x10,0x123);ctx.r3.u64=hit;ctx.r5.u64=pair;sub_82484918(ctx,base);CHECK(Float(base,S+4)==110);
        Write(base,b+0x14,0xCAFF);base[pair+12]=1;ctx.r3.u64=hit;ctx.r5.u64=pair;sub_82484918(ctx,base);CHECK(Float(base,S+4)==110);
        base[pair+12]=0;ctx.r3.u64=hit;ctx.r5.u64=pair;sub_82484918(ctx,base);CHECK(Float(base,S+4)==120);
      }
    }
    spell.pulse_time=4.1f;spell.cast_remaining=1.4f;Save(base,P,spell);UpdateSummon(ctx,base,P,spell);
    CHECK(Read(base,P+1288)==4 && (attr==8 ? Read(base,P+1292)==0 : Read(base,P+1292)>0));
    if(attr==8)CHECK(Float(base,S+4)==260 && next_hit==previous_hit+0x1000); // one heal and one ally rectangle, not four
    spell.cast_remaining=.001f;Save(base,P,spell);frame(kRb);CHECK(!Load(base,P).enabled);
    frame(kRb);CHECK(!Load(base,P).enabled); // fresh press required after finishing
  }
  // Black Dog's source aura phases attach to a real generation-checked
  // enemy handle; their collider moves and expires with the visible aura.
  {
    auto spell=Load(base,P);spell.action=kActionUranus;spell.attribute=9;spell.enabled=1;spell.cast_remaining=3;spell.pulse_time=2;Save(base,P,spell);
    BeginSummon(ctx,base,P,spell);
    constexpr unsigned target=0xABCD0004,enemy=0x178000;
    const auto table=Read(base,M+0xAC);Write(base,table+64,target);Write(base,table+68,enemy);Float(base,enemy+64,510);Float(base,enemy+68,285);
    SummonContact(base,P,target,spell);const auto before=next_hit;UpdateSummon(ctx,base,P,spell);
    unsigned aura=0;for(auto h=before;h<next_hit;h+=0x1000)if(Read(base,h+0x190)==kSummonContactTag)aura=h;
    CHECK(aura && Float(base,aura+0x114)==12/kCotmHz);
    Float(base,enemy+64,525);spell.pulse_time+=.05f;Save(base,P,spell);UpdateSummon(ctx,base,P,spell);
    ctx.r3.u64=aura;CHECK(registered_prepare_hook(ctx,base));CHECK(Float(base,aura+0x2C)==525 && !base[aura+0x17]);
    spell.pulse_time+=1;Save(base,P,spell);ctx.r3.u64=aura;registered_prepare_hook(ctx,base);CHECK(base[aura+0x17]);
    spell.enabled=0;spell.cast_remaining=0;Save(base,P,spell);
  }
  // Recovery popup shows the actual capped gain, and never reports a heal
  // at full HP. It runs the game's real owner-popup wrapper above.
  Float(base,S+4,990);Float(base,S+16,1000);Float(base,S+28,0);
  auto number_count=heal_numbers;CHECK(SummonHeal(ctx,base,P,160)==10);
  CHECK(last_heal==10 && heal_numbers==number_count+1 && Float(base,S+4)==1000);
  CHECK(SummonHeal(ctx,base,P,160)==0 && heal_numbers==number_count+1);
  // Menu/card changes and RB in the same update must still pay the cast
  // cost even when a different DSS combination was enabled beforehand.
  DssState before_swap{};before_swap.enabled=1;before_swap.motion_table=T;
  Save(base,P,before_swap);Write(base,E+48,0x6E0);Write(base,E+52,kSalamander);
  Float(base,S+8,kUranusCost[0]);frame(kRb);CHECK(Load(base,P).enabled && Float(base,S+8)==0);
  // Shared collider callbacks still delegate all unrelated objects.
  ctx.r3.u64=W;sub_824827F0(ctx,base);CHECK(fallback_ticks==1);
  ctx.r3.u64=W;sub_82484918(ctx,base);CHECK(fallback_contacts>=1);
  // Chapter 7 boulders resolve as entities but have no player component.
  // Leave low guest memory uncommitted: the old callback faults on 0x43.
  {
    const auto saved_state=Load(base,P);
    const auto saved_action=Read(base,E+48),saved_attribute=Read(base,E+52);
    const uint32_t hazard=0x160000,collider=0x161000,handle=0x12340003;
    Write(base,REG+(handle&0xFFFF)*16,handle);
    Write(base,REG+(handle&0xFFFF)*16+4,hazard);
    Write(base,hazard+8,0);Write(base,collider+0xA4,handle);
    for(const uint32_t bogus : {0x43u,0x3E396E52u}) {
      Write(base,hazard+0x924,bogus);
      const auto before=fallback_contacts;
      ctx.r3.u64=collider;ctx.r5.u64=0;sub_82484918(ctx,base);
      CHECK(fallback_contacts==before+1);
    }
    // Player-owned attacks still observe Pluto/Unicorn's no-contact behavior.
    Write(base,collider+0xA4,ownerHandle);Write(base,P+852,T);Write(base,E,kWhip);Write(base,O+0x9C8,E);
    Write(base,E+48,0x6E1);Write(base,E+52,kSalamander+8);
    DssState pluto{};pluto.motion_table=T;pluto.enabled=1;pluto.action=kActionPluto;pluto.attribute=8;
    Save(base,P,pluto);Float(base,S+4,100);
    CHECK(Entity(base,ownerHandle)==O);CHECK(Read(base,O+8)&2);CHECK(Action(base,P)==kActionPluto);CHECK(Attribute(base,P)==8);CHECK(Alive(base,P));CHECK(ActivePluto(base,P,8));
    const auto before=fallback_contacts;
    ctx.r3.u64=collider;sub_82484918(ctx,base);CHECK(fallback_contacts==before);
    pluto.enabled=0;Save(base,P,pluto);
    ctx.r3.u64=collider;sub_82484918(ctx,base);CHECK(fallback_contacts==before+1);
    Save(base,P,saved_state);Write(base,E+48,saved_action);Write(base,E+52,saved_attribute);
  }
  // Shared callbacks must not interpret an enemy/hazard's +0x924 as a
  // player pointer, including a valid-looking pointer to another object.
  {
    const uint32_t hazard=0x164000,collider=0x165000,component=0x166000;
    const uint32_t pair=0x167000,a=pair+0x40,b=pair+0x80,handle=0x12340004;
    const auto saved_weapon_owner=Read(base,W+0x2C);
    Write(base,REG+(handle&0xFFFF)*16,handle);
    Write(base,REG+(handle&0xFFFF)*16+4,hazard);
    Write(base,component+72,weaponHandle);Write(base,W+0x2C,handle);
    Write(base,hazard+0x2C,0); // no sprite: FacingSign uses its default
    CHECK(PlayerComponent(base,0)==0);
    CHECK(PlayerComponent(base,O)==P);
    // Only the entity header is mapped: even reading +0x924 would fault.
    CHECK(VirtualAlloc(base+0x1A0000,0x1000,MEM_COMMIT,PAGE_READWRITE));
    Write(base,0x1A0FF8,8);
    CHECK(PlayerComponent(base,0x1A0FF0)==0);
    for(uint32_t flags : {0u,8u}) for(uint32_t bogus : {0u,0x43u,0x3E396E52u,P}) {
      Write(base,hazard+8,flags);Write(base,hazard+0x924,bogus);
      CHECK(PlayerComponent(base,hazard)==0);
      CHECK(FacingSign(base,hazard)==1);
      ctx.r3.u64=hazard;sub_82452658(ctx,base);CHECK(ctx.f1.f64==100);
      const auto hits=normal_hits;
      ctx.r3.u64=hazard;ctx.f1.f64=10;ctx.r9.u64=0;sub_8244BF10(ctx,base);
      CHECK(normal_hits==hits+1);
      ctx.r3.u64=handle;ctx.r4.u64=0;ctx.r5.u64=0;sub_8245D008(ctx,base);
      ctx.r3.u64=W;sub_8246C408(ctx,base);CHECK(ctx.r3.u32==0x800000C0);
      ctx.r3.u64=W;sub_8246F5C0(ctx,base);
      ctx.r3.u64=component;sub_824699B8(ctx,base);CHECK(started_clip==0);
      ctx.r3.u64=component;sub_82469D18(ctx,base);CHECK(queried_clip==0);
      // A summon whose owner no longer resolves to a player is retired.
      Write(base,collider,collider+kSummonColliderTable);
      Write(base,collider+0xA4,handle);base[collider+0x17]=0;
      ctx.r3.u64=collider;sub_824827F0(ctx,base);CHECK(base[collider+0x17]==1);
      // Both pooled-projectile and Black Dog recovery contact branches.
      Write(base,pair,a);Write(base,pair+4,b);base[pair+12]=base[pair+13]=0;
      Write(base,collider+4,123);Write(base,a+0x10,123);
      Write(base,b+4,0x10);Write(base,b+0x14,456);
      for(uint32_t tag : {kProjTag,0u}) {
        Write(base,collider+0x190,tag);Write(base,collider+0x180,9);
        std::memset(base+collider+0x2A0,0,32*4);
        const auto before=fallback_contacts;
        ctx.r3.u64=collider;ctx.r5.u64=pair;sub_82484918(ctx,base);
        CHECK(fallback_contacts==before+1);
      }
    }
    // Null components on players and stale generation handles are benign.
    Write(base,hazard+8,2);Write(base,hazard+0x924,0);
    CHECK(PlayerComponent(base,hazard)==0);
    CHECK(Entity(base,handle+0x10000)==0);
    Write(base,collider+0xA4,handle+0x10000);base[collider+0x17]=0;
    ctx.r3.u64=collider;sub_824827F0(ctx,base);CHECK(base[collider+0x17]==1);
    Write(base,W+0x2C,saved_weapon_owner);
  }
  // Collected cards count distinct inventory entries, not stack quantities.
  ResetProgress(base,P);Float(base,S+4,100);Write(base,P+572,1);Write(base,P+584,3);
  Write(base,P+852,T);Float(base,P+564,.1f);Write(base,I,2);
  for(unsigned i=0;i<10;++i)base[SAVE+0x3E8+kSalamander+i]=0xF3;
  base[SAVE+0x3E8+kMercury]=0xF3;for(unsigned i=0;i<9;++i)base[SAVE+0x3E8+kVenus+i]=0xF3;
  Write(base,SAVE+kNathanTimeOffset,3600);ProgressFrame(ctx,base,P,2);
  CHECK(Read(base,P+1536)==20 && std::abs(TimeBonus(base,P)-.1f)<.00001);
  // Pair level: average of both equipped cards' copies, each capped at 9.
  CHECK(PairLevelFor(1,1)==1 && PairLevelFor(9,9)==9 && PairLevelFor(15,15)==9 && PairLevelFor(1,9)==5 && PairLevelFor(0,0)==1 && PairLevelFor(2,3)==2.5f);
  CHECK(PairLevel(base,P)==9); // equipped Uranus + Salamander, 15 copies each
  CHECK(PairDamage(base,P)==kPairDamageAtMax && PairHealing(base,P)==kPairHealingAtMax);
  CHECK(std::abs(PairBonus(base,P,1.25f)-(1+.25f*kPairBonusAtMax))<.00001 && PairBonus(base,P,.5f)==.5f && PairBonus(base,P,1)==1);
  base[SAVE+0x3E8+0x6E0]=0x33;base[SAVE+0x3E8+kSalamander]=0x73;ProgressFrame(ctx,base,P,2);CHECK(PairLevel(base,P)==5);
  CHECK(std::abs(PairDamage(base,P)-(1+(kPairDamageAtMax-1)*.5f))<.00001);
  Float(base,P+kPairLevel,0);CHECK(PairLevel(base,P)==1 && PairDamage(base,P)==1); // before the first update
  {
    Float(base,S+4,100);Float(base,P+kPairLevel,9);const auto heals=heal_numbers;
    CHECK(SummonHeal(ctx,base,P,50)==50*kPairHealingAtMax && last_heal==int(50*kPairHealingAtMax) && heal_numbers==heals+1);
    Float(base,P+kPairLevel,1);const float low=ProjectilePower(ctx,base,P,10);
    Float(base,P+kPairLevel,9);const float high=ProjectilePower(ctx,base,P,10);
    CHECK(low>1 && std::abs(high-std::floor(low*kPairDamageAtMax))<=kPairDamageAtMax);
    // Magic power is HoD's skill rule: P + (P/64 + 0.25) x INT, with
    // P = whip ATK x pair multiplier x pair level. STR plays no part.
    Write(base,O+0x92C,12);whip_attack_calls=0;
    Float(base,P+kPairLevel,1);test_whip_attack=64;test_int=32;
    CHECK(ProjectilePower(ctx,base,P,1)==64+(1+.25f)*32 && whip_attack_calls==1 && last_attack_character==12);
    CHECK(ProjectilePower(ctx,base,P,.5f)==32+(.5f+.25f)*32);
    Float(base,P+kPairLevel,9);CHECK(ProjectilePower(ctx,base,P,1)==64*kPairDamageAtMax+(kPairDamageAtMax+.25f)*32);
    test_int=-5;Float(base,P+kPairLevel,1);CHECK(ProjectilePower(ctx,base,P,1)==64); // a negative INT never reduces P
    test_whip_attack=0;test_int=0;CHECK(ProjectilePower(ctx,base,P,1)==1);            // floor of 1
    test_whip_attack=100;test_int=0;
    // Melee power is the whip's native physical attack, scaled the same way.
    physical_attack_calls=0;
    Float(base,P+kPairLevel,1);CHECK(MeleePower(ctx,base,P,1.1f)==110 && physical_attack_calls==1);
    Float(base,P+kPairLevel,9);CHECK(MeleePower(ctx,base,P,1.1f)==std::floor(110*kPairDamageAtMax));
    // The Mercury whip scales inside STR with the pair level.
    DssState whip{};whip.enabled=1;whip.motion_table=T;whip.action=kActionMercury;whip.attribute=0;
    Write(base,E+48,kMercury);Write(base,E+52,kSalamander);Save(base,P,whip);
    Float(base,P+kPairLevel,1);const float str1=NativeStrength(ctx,base,P);
    Float(base,P+kPairLevel,9);const float str9=NativeStrength(ctx,base,P);
    CHECK(std::abs(str9-str1*kPairDamageAtMax)<.01f);
    // Venus STR is a stat bonus: Black Dog 141% grows to 182%; Unicorn's 71% stays.
    DssState idle{};idle.motion_table=T; // the harness owner link lives in the state
    Save(base,P,idle);const float plain=NativeStrength(ctx,base,P);
    whip.action=kActionVenus;whip.attribute=9;Write(base,E+48,kVenus);Write(base,E+52,kSalamander+9);Save(base,P,whip);
    CHECK(NativeStrength(ctx,base,P)==std::floor(plain*(100+41*kPairBonusAtMax)/100));
    whip.attribute=8;Write(base,E+52,kSalamander+8);Save(base,P,whip);
    CHECK(NativeStrength(ctx,base,P)==std::floor(plain*71/100.0));
    Save(base,P,idle);Write(base,E+48,0x6E0);Write(base,E+52,kSalamander);
  }
  // Back to one copy of every card so later exact checks run at level 1.
  for(unsigned i=0;i<10;++i)base[SAVE+0x3E8+kSalamander+i]=0x13;
  base[SAVE+0x3E8+kMercury]=0x13;for(unsigned i=0;i<9;++i)base[SAVE+0x3E8+kVenus+i]=0x13;
  Float(base,S+4,100);ProgressFrame(ctx,base,P,2);CHECK(PairLevel(base,P)==1 && Read(base,P+1536)==20);
  DssState bonus{};bonus.enabled=1;bonus.motion_table=T;bonus.action=kActionVenus;bonus.attribute=3;
  Write(base,E+48,kVenus);Write(base,E+52,kSalamander+3);Save(base,P,bonus);
  ctx.r3.u64=O;sub_82451AA8(ctx,base);CHECK(std::abs(ctx.f1.f64-284.2)<.001);
  bonus.attribute=7;Write(base,E+52,kSalamander+7);Save(base,P,bonus);
  ctx.r3.u64=O;sub_82452658(ctx,base);CHECK(std::abs(ctx.f1.f64-140)<.001);
  ctx.r3.u64=0;ctx.r4.u64=0x110000;sub_8245D9A0(ctx,base);CHECK(std::abs(Float(base,0x110010)-140)<.001);
  bonus.action=kActionPluto;bonus.attribute=4;Write(base,E+48,0x6E1);Write(base,E+52,kSalamander+4);Save(base,P,bonus);
  ctx.r3.u64=O;sub_82451AA8(ctx,base);CHECK(std::abs(ctx.f1.f64-223.3)<.001);
  Float(base,P+1540,1000000);CHECK(std::abs(TimeBonus(base,P)-.2f)<.00001);
  bonus.attribute=7;Write(base,E+52,kSalamander+7);Save(base,P,bonus);
  ctx.r3.u64=O;sub_82452658(ctx,base);CHECK(std::abs(ctx.f1.f64-120)<.001);
  bonus.enabled=0;Save(base,P,bonus);ctx.r3.u64=O;sub_82452658(ctx,base);CHECK(ctx.f1.f64==100);
  // Exactly +20%, including fractional awards and separate skill carries.
  bonus.enabled=1;bonus.attribute=2;Save(base,P,bonus);Write(base,E+52,kSalamander+2);
  Write(base,SAVE+MasteryOffset(0),0);Write(base,SAVE+MasteryOffset(1),0);mastery_award=1;
  for(unsigned n=0;n<10;++n){ctx.r3.u64=ownerHandle;ctx.r4.u64=1;ctx.r5.u64=n%2;sub_8245D008(ctx,base);}
  CHECK(Read(base,SAVE+MasteryOffset(0))==6 && Read(base,SAVE+MasteryOffset(1))==6);
  Write(base,SAVE+MasteryOffset(0),99998);mastery_award=5;
  ctx.r3.u64=ownerHandle;ctx.r4.u64=1;ctx.r5.u64=0;sub_8245D008(ctx,base);CHECK(Read(base,SAVE+MasteryOffset(0))==99999);
  // Walking grants 1 XP per minute to each distinct equipped subweapon.
  bonus.action=kActionVenus;bonus.attribute=4;Write(base,E+48,kVenus);Write(base,E+52,kSalamander+4);Save(base,P,bonus);
  Write(base,E+8*4,0x60F);Write(base,E+9*4,0x60F);Write(base,E+10*4,0x610);Write(base,E+11*4,0);
  base[SAVE+0x3E8+0x60F]=base[SAVE+0x3E8+0x610]=0x13;
  Write(base,SAVE+MasteryOffset(0),0);Write(base,SAVE+MasteryOffset(1),0);Float(base,P+1548,0);
  for(unsigned n=0;n<601;++n){Float(base,O+0x8D4,Float(base,O+0x8D4)+1);ProgressFrame(ctx,base,P,2);}
  CHECK(Read(base,SAVE+MasteryOffset(0))==1 && Read(base,SAVE+MasteryOffset(1))==1);
  for(unsigned n=0;n<601;++n)ProgressFrame(ctx,base,P,2);
  CHECK(Read(base,SAVE+MasteryOffset(0))==1); // wall/idle doesn't earn XP
  // Moving shield ignores enemy hit transactions, but allows healing and idle hits.
  bonus.action=kActionJupiter;bonus.attribute=6;Save(base,P,bonus);Write(base,E+48,0x6DA);Write(base,E+52,kSalamander+6);
  Float(base,O+0x8D4,Float(base,O+0x8D4)+1);ProgressFrame(ctx,base,P,2);Write(base,I,2);
  const auto hit_count=normal_hits;ctx.r3.u64=O;ctx.f1.f64=50;sub_8244BF10(ctx,base);CHECK(normal_hits==hit_count && ctx.r3.s64==-1);
  ctx.r3.u64=O;ctx.f1.f64=-10;sub_8244BF10(ctx,base);CHECK(normal_hits==hit_count+1);
  ProgressFrame(ctx,base,P,2);ctx.r3.u64=O;ctx.f1.f64=50;sub_8244BF10(ctx,base);CHECK(normal_hits==hit_count+2);
  const auto live_body=Read(base,O+0x2C);base[live_body+0x55]=7;
  Write(base,P+kSwapHeld,1);draw_palettes.clear();draws.clear();ctx.r3.u64=O;sub_824476B8(ctx,base);
  CHECK(draw_palettes[0]==96 && base[live_body+0x55]==7);
  for(unsigned i=0;i<draws.size();++i)if(draws[i].first==P+kCardSprite || draws[i].first==P+kSummonSprite)CHECK(draw_palettes[i]==0);
  base[live_body+0x55]=0;
  // Native Color 8 routes only Nathan's body/preview into the costume bank.
  const unsigned preview_menu=0x175000,manager=0x176000,records=0x110000;
  Write(base,0x8291D968,manager);Write(base,manager+4,records);Write(base,manager+8,records+13*0x328);
  Write(base,records+12*0x328,12);Write(base,preview_menu+0x138,12);
  Write(base,preview_menu+(0x38+12)*4,0xD0000);base[0xD0000+0x55]=7;
  draw_palettes.clear();ctx.r3.u64=preview_menu;sub_82412880(ctx,base);
  CHECK(draw_palettes.back()==96 && base[0xD0000+0x55]==7);
  Write(base,records+12*0x328,11);draw_palettes.clear();ctx.r3.u64=preview_menu;sub_82412880(ctx,base);CHECK(draw_palettes.back()==7);
  // Menu/player-list portraits can render with no character draw scope.
  // Use the real native FNV-1 and palette lookup, not stubbed UV results.
  constexpr unsigned portrait=0x16A000,resource=0x16B000,palette=0x16C000,texture=0x16D000,uv=0x16E000,name=0x16F000;
  std::memcpy(base+name,"p_nathan",9);
  ctx.r3.u64=uv+4;ctx.r4.u64=name;sub_825BFF28(ctx,base);
  CHECK(Read(base,uv+4)==0x854D90C4u);
  Write(base,portrait+8,Read(base,uv+4));Write(base,portrait+0xC,resource);
  Write(base,resource+0x24,palette);Write(base,palette+8,texture);Write(base,texture+0x28,0xCAFEBABE);
  Float(base,0x821BDD38,16);Float(base,0x821DF924,1.0f/4096);
  for(unsigned color=0;color<8;++color) {
    base[portrait+0x55]=color;ctx.r3.u64=portrait;ctx.r4.u64=uv;sub_823D7170(ctx,base);
    CHECK(ctx.r3.u32==0xCAFEBABE && base[portrait+0x55]==color);
    CHECK(Float(base,uv)==float(color==7?96:color)/256);
  }
  // Other character/resource color 8 and already remapped Nathan stay intact.
  Write(base,portrait+8,0xDEADBEEF);base[portrait+0x55]=7;
  ctx.r3.u64=portrait;ctx.r4.u64=uv;sub_823D7170(ctx,base);CHECK(Float(base,uv)==7.0f/256 && base[portrait+0x55]==7);
  Write(base,portrait+8,0x854D90C4u);base[portrait+0x55]=96;
  ctx.r3.u64=portrait;ctx.r4.u64=uv;sub_823D7170(ctx,base);CHECK(Float(base,uv)==96.0f/256 && base[portrait+0x55]==96);
  Write(base,portrait+0xC,0);base[portrait+0x55]=7;
  ctx.r3.u64=portrait;ctx.r4.u64=uv;sub_823D7170(ctx,base);CHECK(ctx.r3.u32==0 && Float(base,uv)==0 && base[portrait+0x55]==7);
  #include "verify_nathan_salamander.inc"
  #include "verify_nathan_all_dss.inc"
  #include "verify_nathan_tackle.inc"
  #include "verify_nathan_online.inc"
  // Real enemy repeat immunity: the old one-second key permits one hit;
  // the production particle interval permits repeated hits, and independent
  // particle keys do not suppress one another or the ordinary whip.
  CHECK(VirtualAlloc(base+0x1B0000,0x10000,MEM_COMMIT,PAGE_READWRITE));
  {
    constexpr unsigned pair=0x1B0000,attack=pair+64,policy=pair+128,timers=pair+256,entries=pair+512,owners=pair+2048;
    Float(base,0x821030C4,0);Float(base,0x821D8F38,10);Float(base,0x82103A2C,1);
    const auto manager=Read(base,0x8291D9F0),old_table=Read(base,manager+0xAC);
    Write(base,manager+0xAC,pair+4096);Write(base,pair,attack);Write(base,policy+24,timers);
    Write(base,timers+4,entries);Write(base,timers+12,entries+1024);
    Write(base,attack+4,0x40000042);Write(base,attack+16,0);Write(base,attack+40,0xD0);
    for(unsigned mode=0;mode<2;++mode) {
      Write(base,timers+8,entries);Float(base,attack+28,mode?12/kCotmHz:1);unsigned accepted=0;
      for(unsigned f=0;f<60;++f) {
        ctx.r3.u64=timers;ctx.f1.f64=1.0/60;VerifySummon_8224AE48(ctx,base);
        ctx.r3.u64=pair;ctx.r4.u64=policy;ctx.r5.u64=owners;VerifySummon_8224E4E8(ctx,base);accepted+=ctx.r3.u32!=0;
      }
      CHECK(accepted==(mode?5u:1u));
    }
    Write(base,timers+8,entries);
    for(unsigned n=0;n<16;++n) {
      Write(base,attack+40,0xD0+n);ctx.r3.u64=pair;ctx.r4.u64=policy;ctx.r5.u64=owners;VerifySummon_8224E4E8(ctx,base);CHECK(ctx.r3.u32==1);
      ctx.r3.u64=pair;ctx.r4.u64=policy;ctx.r5.u64=owners;VerifySummon_8224E4E8(ctx,base);CHECK(ctx.r3.u32==0);
    }
    Write(base,manager+0xAC,old_table);
  }
  VirtualFree(base,0,MEM_RELEASE);
  std::printf("Passed %d native DSS wrapper checks.\n",checks);
}


// The hook hub as the exe has it (core/runtime/hod_overrides.cpp), for the
// chains Nathan's handlers join; every mod counts as switched on.
namespace hod {
const char* ModId(Mod) { return "harness"; }
bool Compiled(Mod) { return true; }
bool Enabled(Mod) { return true; }
}
REX_EXTERN(__imp__sub_82451AA8);REX_EXTERN(__imp__sub_8245D9A0);REX_EXTERN(__imp__sub_824476B8);
REX_EXTERN(__imp__sub_824827F0);REX_EXTERN(__imp__sub_8244BF10);REX_EXTERN(__imp__sub_82452658);
namespace {
void SpawnGame(PPCContext&,uint8_t*) {}
void PrepareGame(PPCContext&,uint8_t*) {prepare_reached_game=true;}
void DefenseGame(PPCContext& c,uint8_t* b) {__imp__sub_82451AA8(c,b);}
void SummaryGame(PPCContext& c,uint8_t* b) {__imp__sub_8245D9A0(c,b);}
void DrawGame(PPCContext& c,uint8_t* b) {__imp__sub_824476B8(c,b);}
void AttackGame(PPCContext& c,uint8_t* b) {__imp__sub_824827F0(c,b);}
void IncomingGame(PPCContext& c,uint8_t* b) {__imp__sub_8244BF10(c,b);}
void ValueGame(PPCContext& c,uint8_t* b) {__imp__sub_82452658(c,b);}
const bool harness_wired=hod::SetOriginal(hod::Hook::kSpawnEvent,&SpawnGame)&&hod::SetOriginal(hod::Hook::kColliderPrepare,&PrepareGame)&&
  hod::SetOriginal(hod::Hook::kPhysicalDefense,&DefenseGame)&&hod::SetOriginal(hod::Hook::kStatusSummary,&SummaryGame)&&
  hod::SetOriginal(hod::Hook::kOwnerDraw,&DrawGame)&&hod::SetOriginal(hod::Hook::kColliderAttack,&AttackGame)&&
  hod::SetOriginal(hod::Hook::kIncomingDamage,&IncomingGame)&&hod::SetOriginal(hod::Hook::kAttackValue,&ValueGame);
}
REX_EXTERN(sub_82451AA8) {hod::Dispatch(hod::Hook::kPhysicalDefense,ctx,base);}
REX_EXTERN(sub_8245D9A0) {hod::Dispatch(hod::Hook::kStatusSummary,ctx,base);}
REX_EXTERN(sub_824476B8) {hod::Dispatch(hod::Hook::kOwnerDraw,ctx,base);}
REX_EXTERN(sub_824827F0) {hod::Dispatch(hod::Hook::kColliderAttack,ctx,base);}
REX_EXTERN(sub_8244BF10) {hod::Dispatch(hod::Hook::kIncomingDamage,ctx,base);}
REX_EXTERN(sub_82452658) {hod::Dispatch(hod::Hook::kAttackValue,ctx,base);}
