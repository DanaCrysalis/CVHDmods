// Exercise the production Shield Rod callbacks with sparse guest memory.
// Logging and the runtime heap are stubbed; entity lifetimes are real fixtures.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <fstream>
#include <thread>
#include "../generated/default/harmonyrecomp_init.h"
#undef REXLOG_INFO
#undef REXLOG_WARN
#define REXLOG_INFO(...) ((void)0)
#define REXLOG_WARN(...) ((void)0)
struct ShieldTestMemory {uint32_t next=0x70000;uint32_t SystemHeapAlloc(uint32_t size){const auto p=next;next+=(size+15)&~15u;return p;}};
inline ShieldTestMemory shield_test_memory;
#undef REX_KERNEL_MEMORY
#define REX_KERNEL_MEMORY() (&shield_test_memory)
#include "shield_rod.cpp"
// The hook hub as the exe has it (core/runtime): Shield Rod's handlers run
// through the real chains. Every mod counts as switched on; the game
// functions at the ends of chains this file does not exercise do nothing.
#include "hod_hub.cpp"
#include "hod_overrides.cpp"
namespace hod {
const char* ModId(Mod) { return "harness"; }
bool Compiled(Mod) { return true; }
bool Enabled(Mod) { return true; }
}
REX_EXTERN(__imp__sub_8244CA98) {}
REX_EXTERN(__imp__sub_824827F0) {}
REX_EXTERN(__imp__sub_8244FFF8) {}
REX_EXTERN(__imp__sub_82487EF8) {}
REX_EXTERN(__imp__sub_8248A690) {}
REX_EXTERN(__imp__sub_824476B8) {}
REX_EXTERN(__imp__sub_82451AA8) {}
REX_EXTERN(__imp__sub_8245D9A0) {}
REX_EXTERN(__imp__sub_8244BF10) {}
REX_EXTERN(__imp__sub_82452658) {}
using namespace harmony::shield_rod;
#include "verify_csr_sampler.inc"
REX_EXTERN(__savegprlr_29) {}
REX_EXTERN(__restgprlr_29) {}
#include "verify_collision_filter.inc"
REX_EXTERN(__savegprlr_26) {}
REX_EXTERN(__restgprlr_26) {}
#include "verify_collision_vector.inc"
int checks=0,submits=0,draws=0,native_guards=0,queries=0,heals=0,hearts=0,hit_allocations=0;
#define CHECK(x) do {++checks;if(!(x)){std::printf("FAILED line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
REX_EXTERN(__imp__sub_82450658) {++native_guards;}
REX_EXTERN(__imp__sub_824519C8) {ctx.f1.f64=100;}
REX_EXTERN(__imp__sub_824526D0) {ctx.f1.f64=50;}
REX_EXTERN(__imp__sub_825CEFA0) {ctx.r3.u64=0;}
REX_EXTERN(__imp__sub_825CED10) {ctx.r3.u64=0;}
struct DrawSample {uint32_t hash,frame;int x,y,px,py,dir;float sx,sy;};
std::vector<DrawSample> samples;uint32_t sprite_hash=0;
struct SoundSample {std::string cue;int x,y;};std::vector<SoundSample> sound_samples;
unsigned sound_bank_loads=0;
REX_EXTERN(VerifyQueueSoundBank);REX_EXTERN(VerifyKickSoundQueue);REX_EXTERN(VerifyNativeRegion);
void LoadSoundBank(PPCContext& ctx,uint8_t* base){CHECK(ctx.r4.u32==1||ctx.r4.u32==2);CHECK(ctx.r5.u32==0);VerifyQueueSoundBank(ctx,base);if(ctx.r3.u32)++sound_bank_loads;}
void KickSoundQueue(PPCContext& ctx,uint8_t* base){VerifyKickSoundQueue(ctx,base);}
void PlaySound(PPCContext& ctx,uint8_t* base){sound_samples.push_back({reinterpret_cast<char*>(base+ctx.r3.u32),ctx.r4.s32,ctx.r5.s32});}
REX_EXTERN(__imp__sub_823D2648) {
 ++draws;const auto sprite=ctx.r3.u32;CHECK(base[sprite+140]!=3);
 CHECK(ctx.r8.u32==0xffffffffu&&ctx.r9.u32==0);
 samples.push_back({sprite_hash,ctx.r4.u32,ctx.r5.s32,ctx.r6.s32,
  int16_t(rex::memory::load_and_swap<uint16_t>(base+sprite+116)),
  int16_t(rex::memory::load_and_swap<uint16_t>(base+sprite+118)),base[sprite+0x1C]?-1:1,
  Float(base,sprite+0x28),Float(base,sprite+0x2C)});
 constexpr uint32_t packet=0x85000,vertices=0x86000;Write(base,packet+424,vertices);
 for(unsigned i=0;i<4;++i){Float(base,vertices+i*40+32,(i>=2)?.8f:.2f);Float(base,vertices+i*40+36,(i==1||i==2)?.9f:.1f);}
 ctx.r3.u64=packet;
}
REX_EXTERN(__imp__sub_824823A0) {}
std::atomic<int> collision_inside{0},collision_peak{0};bool stress_vector=false;
constexpr uint32_t stressVector=0x9a000;
void CollisionEnter(){int active=collision_inside.fetch_add(1)+1,peak=collision_peak.load();while(peak<active&&!collision_peak.compare_exchange_weak(peak,active)){}for(int i=0;i<100;++i)std::this_thread::yield();}
REX_EXTERN(__imp__sub_823C4C40) {
 CollisionEnter();if(stress_vector){const auto item=ctx.r8.u32;ctx.r3.u64=stressVector;ctx.r4.u64=Read(base,stressVector+8);ctx.r5.u64=item;sub_823916C0(ctx,base);}
 --collision_inside;ctx.r3.u64=0;
}
REX_EXTERN(__imp__sub_823C5098) {
 CollisionEnter();if(stress_vector){const auto first=Read(base,stressVector+4),end=Read(base,stressVector+8),cap=Read(base,stressVector+12);CHECK(first<=end&&end<=cap&&(end-first)%4==0);}
 --collision_inside;ctx.r3.u64=0;
}
REX_EXTERN(sub_822269F0) {CHECK(false);}
REX_EXTERN(sub_82226B70) {CHECK(false);}
REX_EXTERN(sub_82227048) {CHECK(false);}
REX_EXTERN(sub_82227110) {CHECK(false);}
REX_EXTERN(sub_82371AF8) {CHECK(false);}
REX_EXTERN(sub_825FC588) {}
REX_EXTERN(sub_82755080) {
 CHECK(ctx.r6.u32<=ctx.r4.u32);std::memmove(base+ctx.r3.u32,base+ctx.r5.u32,ctx.r6.u32);ctx.r3.u64=0;
}
REX_EXTERN(__imp__sub_82484180) {++submits;Write(base,ctx.r3.u32+0xAC,0xFFFFFFFF);}
bool accepted_contact=false;
void Probe(PPCContext& ctx,uint8_t* base) {
 ++queries;
 if(accepted_contact && ctx.r3.u32==0x60000+0x1C0) {
   const auto out=ctx.r3.u32;Write(base,out,0x69000);Write(base,out+4,0x69400);ctx.r3.u64=1;
 } else ctx.r3.u64=0;
}
void SpriteLookup(PPCContext& ctx,uint8_t* base) {sprite_hash=Read(base,ctx.r3.u32+8);Write(base,ctx.r3.u32+12,0x81000);}
void LocalPlayer(PPCContext& ctx,uint8_t*) {ctx.r3.u64=0x10001;}
void Heal(PPCContext& ctx,uint8_t* base){CHECK(false);}
void GreenNumber(PPCContext& ctx,uint8_t* base){++heals;CHECK(ctx.r3.u32==0x30000&&ctx.r4.u32==0&&ctx.r5.s32==-8);}
void Heart(PPCContext& ctx,uint8_t* base){++hearts;CHECK(ctx.f1.f64==1&&ctx.r5.u32==0&&ctx.r6.u32==1);}
void AllocateHit(PPCContext& ctx,uint8_t*){ctx.r3.u64=0xa0000+832*hit_allocations++;}
void NativeCenter(PPCContext& ctx,uint8_t* base){const auto out=ctx.r3.u32,shape=ctx.r4.u32;Float(base,out,(Float(base,shape+8)+Float(base,shape+16))*.5f);Float(base,out+4,(Float(base,shape+12)+Float(base,shape+20))*.5f);}
REX_EXTERN(sub_825FC4B0) {AllocateHit(ctx,base);}
void ConstructHit(PPCContext& ctx,uint8_t* base){Write(base,ctx.r3.u32+0xA4,ctx.r5.u32);}
void NativeNoop(PPCContext& ctx,uint8_t*) {ctx.r3.u64=0;}
namespace rex::runtime { PPCFunc* ResolveIndirectFunction(uint32_t fn) { if(fn==0x82590680)return &LoadSoundBank;if(fn==0x82590878)return &KickSoundQueue;if(fn==0x82239218)return &PlaySound;if(fn==0x82200004)return &NativeNoop;if(fn==0x82200000)return &NativeCenter;if(fn==0x825FC4B0)return &AllocateHit;if(fn==0x82481D60)return &ConstructHit;if(fn==0x82454000)return &GreenNumber;if(fn==0x8244E268)return &Heal;if(fn==0x8244E3C8)return &Heart;if(fn==0x823D2520)return &SpriteLookup;if(fn==0x8245CCE8)return &LocalPlayer;return &Probe; } }
#include "verify_enemy_damage.inc"
#include "verify_native_guard.inc"
#include "verify_sprite_blend.inc"
bool SamplerFaults(PPCContext& ctx,uint8_t* base) {
 __try {sub_823CBF98(ctx,base);return false;}
 __except(GetExceptionCode()==EXCEPTION_ACCESS_VIOLATION?EXCEPTION_EXECUTE_HANDLER:EXCEPTION_CONTINUE_SEARCH) {return true;}
}
bool FilterFaults(PPCContext& ctx,uint8_t* base) {
 __try {__imp__sub_823C4EC8(ctx,base);return false;}
 __except(GetExceptionCode()==EXCEPTION_ACCESS_VIOLATION?EXCEPTION_EXECUTE_HANDLER:EXCEPTION_CONTINUE_SEARCH) {return true;}
}
std::array<float,4> registered_rect{};
unsigned registered_region=0;
void VerifyRectCell(PPCContext& ctx,uint8_t* base){VerifyNativeRegion(ctx,base);}
void VerifyRectSubmit(PPCContext& ctx,uint8_t* base){registered_region=ctx.r5.u32;for(unsigned i=0;i<4;++i)registered_rect[i]=Float(base,ctx.r3.u32+8+i*4);ctx.r3.u64=1;}
#include "verify_native_rectangle.inc"
void VerifyAudioMutex(PPCContext&,uint8_t*){}
#include "verify_native_audio_queue.inc"
#include "verify_native_region.inc"
int main(){
 setvbuf(stdout,nullptr,_IONBF,0);
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 auto* base=static_cast<uint8_t*>(VirtualAlloc(nullptr,0x100000000ull,MEM_RESERVE,PAGE_READWRITE));CHECK(base);
 auto commit=[&](uint32_t at,uint32_t size){CHECK(VirtualAlloc(base+at,size,MEM_COMMIT,PAGE_READWRITE));};
 commit(0x10000,0x80000);commit(0x828F5000,0x1000);commit(0xa0000,0x40000);commit(0x90000,0x10000);commit(0x200000,0x20000);commit(0x821ea000,0x1000);commit(0x82910000,0x10000);
 constexpr uint32_t M=0x10000,T=0x20000,O=0x30000,P=0x40000,S=0x50000,H=0x60000;
 constexpr uint32_t handle=0x10001;
 Write(base,0x8291D9F0,M);Write(base,M+0xAC,T);Write(base,M+0xB0,T+32);
 auto setup=[&](){
   states={};targets={};active_art=0;Float(base,0x80028,1);Float(base,0x8002c,1);
   Write(base,T+16,handle);Write(base,T+20,O);
   Write(base,O+4,handle);Write(base,O+8,2);Write(base,O+0x924,P);Write(base,O+0x9C8,0x82000);
   Write(base,P,kAlucardVtable);Write(base,P+0x2F0,0);Write(base,P+88,S);Write(base,P+0x250,0);Float(base,S+4,100);
   auto* state=Find(base,O,true);CHECK(state);return state;
 };
 PPCContext ctx{};ctx.fpscr.InitHost();
 commit(0x82930000,0x1000);commit(0x82900000,0x10000);ctx.r1.u64=0x8d000;
 const auto resetSoundQueue=[&](){std::memset(base+0x82902838,0,16);std::memset(base+0x8291a2a0,0,32*268);for(unsigned i=0;i<64;++i)Write(base,0x8291c420+i*28,0xffffffff);};
 resetSoundQueue();EnsureSounds(ctx,base);CHECK(sound_bank_loads==0);
 Write(base,0x82930b10,0x61000);
 EnsureSounds(ctx,base);EnsureSounds(ctx,base);CHECK(sound_bank_loads==2);
 CHECK(Read(base,0x82902838+8)==2&&Read(base,0x82902838+4)==2);
 for(unsigned i=0;i<2;++i){const auto job=0x8291a2a0+i*268,entry=Read(base,job+8);
  CHECK(Read(base,entry+4)==i+1&&Read(base,entry+8)==0);
  CHECK(std::string(reinterpret_cast<char*>(base+job+12))==(i?"D:\\data\\sound\\SE_SHIELDROD.xwb":"D:\\data\\sound\\SE_SHIELDROD.xsb"));
  std::string guestPath(reinterpret_cast<char*>(base+job+12));CHECK(guestPath.starts_with("D:\\"));
  std::replace(guestPath.begin(),guestPath.end(),'\\','/');std::ifstream bank("assets"+guestPath.substr(2),std::ios::binary);CHECK(bank.good());
  char magic[4]{};bank.read(magic,4);CHECK(std::string(magic,4)==(i?"DNBW":"KBDS"));}
 Write(base,0x82930b10,0);EnsureSounds(ctx,base);
 resetSoundQueue();Write(base,0x82902838+8,32);Write(base,0x82930b10,0x62000);
 EnsureSounds(ctx,base);CHECK(sound_bank_loads==2);resetSoundQueue();EnsureSounds(ctx,base);CHECK(sound_bank_loads==4);
 Write(base,0x82930b10,0);EnsureSounds(ctx,base);

 // Probe the native rectangle ABI with the old large-area arguments.
 Write(base,0x8291d918,0x64000);Float(base,0xa002c,1000);Float(base,0xa0030,1000);
 Write(base,0xa01a0,uint32_t(-427));Write(base,0xa01a4,uint32_t(-240));Write(base,0xa01a8,427);Write(base,0xa01ac,240);
 ctx.r1.u64=0x8d000;ctx.r3.u64=0xa0000;ctx.r4.u64=0xa01a0;VerifyNativeRectangle(ctx,base);
 CHECK((registered_rect==std::array<float,4>{573,760,1427,1240}));
 Write(base,0x8291d918,0);
 // Regression: the crashed native sampler indexes tiles by x/128,y/128.
 // Every generated page must fit its single allocated tile, including all pixels.
 const char* pages[]={
 #include "verify_csr_pages.inc"
 };
 for(const auto* name:pages) {
   std::ifstream file(name,std::ios::binary);CHECK(file.good());
   std::vector<unsigned char> data((std::istreambuf_iterator<char>(file)),{});
   CHECK(data.size()==0x230+8192);
   CHECK(data[0x20]==0&&data[0x21]==128&&data[0x22]==0&&data[0x23]==128);
   constexpr uint32_t info=0x87000,table=0x88000,pixels=0x89000;
   base[info+4]=0;Write(base,info+8,table);std::memset(base+table,0,16);Write(base,table,pixels);
   std::memcpy(base+pixels,data.data()+0x230,8192);
   // Reproduce the former 256-page/header mismatch: tile 3 was never allocated.
   ctx.r3.u64=info;ctx.r4.u64=128;ctx.r5.u64=128;CHECK(SamplerFaults(ctx,base));
   for(unsigned y=0;y<128;++y)for(unsigned x=0;x<128;++x) {
     ctx.r3.u64=info;ctx.r4.u64=x;ctx.r5.u64=y;sub_823CBF98(ctx,base);
     const unsigned packed=data[0x230+y*64+x/2];CHECK(ctx.r3.u32==((x&1)?packed&15:packed>>4));
   }
 }
 // Exact second crash: candidate 0x21 with an owner-bearing source faults
 // in native candidate+0x10. The wrapper rejects it, preserving valid pairs.
 constexpr uint32_t requestA=0x87c00,requestB=0x87d00;
 std::memset(base+requestA,0,32);std::memset(base+requestB,0,32);
 Write(base,requestA+16,handle);ctx.r3.u64=requestA;ctx.r4.u64=0x21;
 CHECK(FilterFaults(ctx,base));ctx.r3.u64=requestA;ctx.r4.u64=0x21;sub_823C4EC8(ctx,base);CHECK(ctx.r3.u32==0);
 for(auto invalid:{0u,0x21u,0x31u,0xffffu,0xe0000000u,0xffffffffu}){
   ctx.r3.u64=requestA;ctx.r4.u64=invalid;sub_823C4EC8(ctx,base);CHECK(ctx.r3.u32==0);
 }
 Write(base,requestB+16,0x20002);Write(base,requestB+4,0x80000002);ctx.r3.u64=requestA;ctx.r4.u64=requestB;ctx.r5.u64=1;
 sub_823C4EC8(ctx,base);CHECK(ctx.r3.u32==1);
 // Off-stage rectangles must never reach native request registration.
 constexpr uint32_t stage=0x56000,map=0x57000;
 Write(base,0x8291D918,stage);Write(base,stage+16,map);
 rex::memory::store_and_swap<uint16_t>(base+map+4,20);rex::memory::store_and_swap<uint16_t>(base+map+6,10);
 CHECK(InStage(base,0,0)&&InStage(base,319,159));CHECK(!InStage(base,-1,10)&&!InStage(base,320,10)&&!InStage(base,10,160));
 Write(base,0x8291D918,0);
 // Valid owners preserve stats and native callbacks.
 auto* s=setup();s->buff[kAtk]=s->buff[kDef]=s->buff[kInt]=10;
 CHECK(DefenseBonus(base,O)==20);
 ctx.r3.u64=O;ctx.r4.u64=0;sub_824519C8(ctx,base);CHECK(ctx.f1.f64==120);
 ctx.r3.u64=O;sub_824526D0(ctx,base);CHECK(ctx.f1.f64==70);
 CHECK(EntityOf(base,handle)==O);CHECK(EntityOf(base,0x10002)==0);CHECK(EntityOf(base,handle+0x10000)==0);
 // Summary uses the current live owner; other characters remain untouched.
 Float(base,H+0x10,10);Float(base,H+0x14,11);Float(base,H+0x18,12);Float(base,H+0x20,14);Float(base,H+0x24,17);
 Summary(ctx,base,2,H);CHECK(Float(base,H+0x10)==30&&Float(base,H+0x18)==32);CHECK(Float(base,H+0x20)==34&&Float(base,H+0x24)==17);
 Summary(ctx,base,12,H);CHECK(Float(base,H+0x10)==30);
 // Display combines the same fifty-percent reduction with existing gear
 // resistance, and INT remains visible without a live equipment pointer.
 s->buff[kFireRes]=s->buff[kThunderRes]=s->buff[kDarkRes]=10;
 Float(base,H+0x3c,20);Float(base,H+0x44,40);Float(base,H+0x4c,0);Float(base,H+0x48,7);
 Summary(ctx,base,0,H);CHECK(Float(base,H+0x3c)==60&&Float(base,H+0x44)==70&&Float(base,H+0x4c)==50);
 CHECK(Float(base,H+0x48)==7);Write(base,O+0x9c8,0);Float(base,H+0x20,50);
 Summary(ctx,base,0,H);CHECK(Float(base,H+0x20)==70&&Float(base,H+0x24)==17);
 ctx.r7.u64=0x1000;ctx.f1.f64=40;CHECK(!Incoming(ctx,base,O)&&ctx.f1.f64==20);
 ctx.r7.u64=0x800;ctx.f1.f64=40;CHECK(!Incoming(ctx,base,O)&&ctx.f1.f64==40);
 // Valid art still draws; extreme offsets cannot overflow integer coordinates.
 s->knight.phase=kWalk;s->knight.scale=1;s->knight.sprite=4;Write(base,O+0x2C,0x80000);
 Float(base,0x80028,1);CountArt();Draw(ctx,base,0x80000);CHECK(draws==1);
 s->knight.x=1e30f;Draw(ctx,base,0x80000);CHECK(draws==1);
 draws=0;
 // Zero/NaN native body transforms must not enter software raster/cache allocation.
 s->knight.x=0;const auto safeDraws=draws;Float(base,0x8002c,0);Draw(ctx,base,0x80000);CHECK(draws==safeDraws);
 Float(base,0x8002c,NAN);Draw(ctx,base,0x80000);CHECK(draws==safeDraws);Float(base,0x8002c,1);
 draws=0;
 // A component replacement must be rejected before dereferencing the new slot.
 Write(base,O+0x924,0x43);CHECK(DefenseBonus(base,O)==0);setup();
 // Non-player objects must never dereference the fake player component.
 for(uint32_t value:{0x43u,0x3E396E52u}){
   Write(base,O+8,8);Write(base,O+0x924,value);
   CHECK(AlucardPlayer(base,O)==0);
   ctx.r3.u64=O;sub_82450658(ctx,base);CHECK(native_guards>0);
   ctx.r3.u64=O;ctx.r4.u64=0;sub_824519C8(ctx,base);CHECK(ctx.f1.f64==100);
   ctx.r3.u64=O;sub_824526D0(ctx,base);CHECK(ctx.f1.f64==50);
 }
 // Host state retains a now-unmapped raw address after owner teardown.
 // Handle resolution must reject it before any owner-field read.
 for(int route=0;route<3;++route){
   s=setup();s->buff[kDef]=10;s->knight.phase=kWalk;s->knight.generation=7;
   CountArt();Write(base,T+16,handle+0x10000);
   DWORD old;CHECK(VirtualProtect(base+O,0x10000,PAGE_NOACCESS,&old));
   if(route==0){Draw(ctx,base,0x70000);CHECK(draws==0);}
   if(route==1)CHECK(DefenseBonus(base,O)==0);
   if(route==2){
     Write(base,H+0xA4,handle);Write(base,H+0x194,O);Write(base,H+0x184,7);base[H+0x17]=0;
     ResolveHit(ctx,base,H);CHECK(base[H+0x17]==1);CHECK(submits==0);
   }
   CHECK(VirtualProtect(base+O,0x10000,PAGE_READWRITE,&old));
 }
 // Same address, different handle generation: do not inherit buffs or knight.
 s=setup();s->buff[kDef]=10;s->knight.phase=kWalk;
 Write(base,T+16,handle+0x10000);Write(base,O+4,handle+0x10000);
 CHECK(DefenseBonus(base,O)==0);s=Find(base,O,true);CHECK(s&&s->buff[kDef]==0&&s->knight.phase==kIdle);
 // Missing manager and an out-of-range handle cannot read table memory.
 Write(base,0x8291D9F0,0);CHECK(EntityOf(base,handle)==0);
 Write(base,0x8291D9F0,M);Write(base,M+0xB0,T);CHECK(EntityOf(base,handle)==0);
 Write(base,M+0xB0,T+32);
 // Valid short-lived rectangles submit once; old spell generations retire.
 s=setup();s->knight.phase=kWalk;s->knight.generation=9;
 std::memset(base+H,0,832);Write(base,H+0xA4,handle);Write(base,H+0x194,O);Write(base,H+0x184,9);
 Write(base,0x8291D918,stage);Write(base,stage+16,map);
 ctx.f1.f64=1.0/60;ResolveHit(ctx,base,H);CHECK(submits==0); // resolve never registers
 PrepareHit(ctx,base,H);CHECK(submits==1);ResolveHit(ctx,base,H);CHECK(submits==1);
 ResolveHit(ctx,base,H);CHECK(submits==1);PrepareHit(ctx,base,H);CHECK(base[H+0x17]==1);
 base[H+0x17]=0;Write(base,H+0x184,8);ResolveHit(ctx,base,H);CHECK(base[H+0x17]==1&&submits==1);
 // Do not convert NaN/overflowing world positions into collision indices.
 Write(base,0x8291D918,1);const auto before=queries;
 CHECK(Call4(ctx,base,0,float(NAN),0)==0);CHECK(Call4(ctx,base,0,1e30f,0)==0);CHECK(queries==before);
 // Missing stats must not turn a cast into a low-memory read/write.
 s=setup();Write(base,P+88,0);Cast(ctx,base,O,P,*s,kShields[0]);CHECK(s->buff[kDef]==0);
 Draw(ctx,base,0);ResolveHit(ctx,base,0);
 // The knight's visible feet and attack box must share one world surface,
 // with either facing, zoomed camera layers, and an unrelated body pivot.
 for(int dir:{-1,1}) for(int zoom:{1,2}) {
   s=setup();Write(base,O+0x2C,0x80000);
   Float(base,O+64,100);Float(base,O+68,1000);
   Float(base,O+0x8EC,110);Float(base,O+0x8F0,970);Float(base,O+72,1);
   Float(base,0x80028,float(zoom));Float(base,0x8002C,float(zoom));Write(base,0x80078,zoom==2?7:0);
   Write(base,0x80074,0x004D0058); // inherited pivot 77,88 must not leak
   s->knight.phase=kWalk;s->knight.sprite=4;s->knight.x=200;s->knight.y=900;s->knight.dir=dir;
   CountArt();ctx.r5.u64=uint32_t(100*zoom-20);ctx.r6.u64=uint32_t(1000*zoom-30);
   samples.clear();Draw(ctx,base,0x80000);CHECK(samples.size()==1);
   const auto d=samples.back();CHECK(d.x==200&&d.y==900);
   CHECK(d.px==0&&d.py==0&&d.dir==dir);
   CHECK(d.y==900&&d.x==200); // native camera transform is downstream
   Float(base,O+64,450);Float(base,O+68,1300);ctx.r5.s64=-200;ctx.r6.s64=-300;
   samples.clear();Draw(ctx,base,0x80000);CHECK(samples.size()==1&&samples[0].x==200&&samples[0].y==900);
   CHECK(Read(base,0x80074)==0x004D0058);
 }
 // Every shield casts, charges once, ends its parent clip and releases bounded children.
 for(unsigned index=0;index<13;++index) for(int dir:{1,-1}) {
   s=setup();Write(base,O+0x2C,0x80000);base[0x8001c]=dir<0;Write(base,P+0x250,dir<0);
   Float(base,0x80028,1);Float(base,0x8002C,1);Write(base,0x80078,0);
   Float(base,S+8,200);Cast(ctx,base,O,P,*s,kShields[index]);
   CHECK(s->visual.active&&Float(base,S+8)==200-kShields[index].mp);
   Cast(ctx,base,O,P,*s,kShields[index]);CHECK(Float(base,S+8)==200-kShields[index].mp);
   const auto& clip=Clip(kShields[index].spell,dir);unsigned children=0;
   for(unsigned tick=0;tick<=clip.count;++tick) {
     sound_samples.clear();
     UpdateEffects(ctx,base,*s);
     std::vector<std::string> expectedSounds;
     const auto appendSounds=[&](unsigned track,unsigned age){const auto& range=kSotnSoundTracks[track];
       for(unsigned i=0;i<range.count;++i){const auto& e=kSotnSounds[range.first+i];if(e.tick==age){
         const auto cue=SpellCue(kShields[index].spell,e.id);CHECK(cue);expectedSounds.emplace_back(cue);}}};
     if(tick<clip.count)appendSounds(index*2+(dir<0),tick);
     for(const auto& a:s->actors)if(a.active)appendSounds(std::size(kSotnClips)+a.clip,a.age);
     CHECK(sound_samples.size()==expectedSounds.size());
     for(unsigned i=0;i<expectedSounds.size();++i)CHECK(sound_samples[i].cue==expectedSounds[i]);
     if(tick==10){const auto& shieldTick=kSotnTicks[clip.first+10];
      CHECK(s->visual.dir==dir&&shieldTick.x*dir<0&&shieldTick.y<0);
      CountArt();samples.clear();Draw(ctx,base,0x80000);CHECK(!samples.empty());const auto& shield=samples.back();
      CHECK(shield.x==std::lround(s->visual.x+shieldTick.x/65536.0f));CHECK(shield.y==std::lround(s->visual.y+shieldTick.y/65536.0f));CHECK(shield.dir==dir);
     }
     if(tick==161 && index<2)CHECK(s->buff[index==0?kDef:kAtk]==0);
     if(tick==162 && index<2)CHECK(s->buff[index==0?kDef:kAtk]==kBuffFrames);
     if(tick==215 && index==7)CHECK(s->buff[kInt]==kBuffFrames);
     if(tick==162 && index<2)CHECK(s->notices[index==0?kDef:kAtk].life==120);
     if(tick==215 && index==7)CHECK(s->notices[kInt].life==120);
     if(tick==143 && index==4)CHECK(s->notices[kFireRes].life==120&&!s->buff[kThunderRes]);
     if(tick==206 && index==4)CHECK(s->notices[kThunderRes].life==120&&s->notices[kFireRes].life==57);
     if(tick==186 && index==6)CHECK(s->notices[kDarkRes].life==120&&!s->buff[kFireRes]&&!s->buff[kThunderRes]);
     if(tick==79 && index==5)CHECK(std::count_if(s->actors.begin(),s->actors.end(),[](auto& a){return a.active;})==32);
     if(tick==46 && index==7)CHECK(std::count_if(s->actors.begin(),s->actors.end(),[](auto& a){return a.active;})==8);
     if(tick==78 && index==10)CHECK(std::count_if(s->actors.begin(),s->actors.end(),[](auto& a){return a.active;})==1);
     if(tick==90 && index==10)CHECK(std::count_if(s->actors.begin(),s->actors.end(),[](auto& a){return a.active;})==3);
     if(tick%31==0){CountArt();samples.clear();Draw(ctx,base,0x80000);for(auto& d:samples)CHECK(d.hash==NameHash(kShields[index].sprite));}
     if(tick==80){
      CountArt();samples.clear();Draw(ctx,base,0x80000);const auto fixed=samples;
      const float ox=Float(base,O+64),oy=Float(base,O+68),cx=PlayerX(base,O),cy=PlayerY(base,O);
      Float(base,O+64,ox+240);Float(base,O+68,oy-120);Float(base,O+0x8EC,cx+240);Float(base,O+0x8F0,cy-120);
      ctx.r5.s64=-1234;ctx.r6.s64=5678;samples.clear();Draw(ctx,base,0x80000);
      CHECK(fixed.size()==samples.size());
      for(unsigned j=0;j<fixed.size();++j){CHECK(fixed[j].x==samples[j].x&&fixed[j].y==samples[j].y);CHECK(fixed[j].frame==samples[j].frame);}
      Float(base,O+64,ox);Float(base,O+68,oy);Float(base,O+0x8EC,cx);Float(base,O+0x8F0,cy);
     }
   }
   CHECK(!s->visual.active);
   for(unsigned i=0;i<700;++i)UpdateEffects(ctx,base,*s);
   CHECK(std::none_of(s->actors.begin(),s->actors.end(),[](auto& a){return a.active;}));
   if(index==12)CHECK(s->buff[kAtk]==0&&s->buff[kDef]==0&&s->buff[kInt]==0);
 }
 // Incoming recovery must remain healing; resisted damage changes only the matching element.
 s=setup();s->buff[kFireRes]=100;ctx.r7.u64=0x100;ctx.f1.f64=40;CHECK(!Incoming(ctx,base,O)&&ctx.f1.f64==20);
 ctx.r7.u64=0x200;ctx.f1.f64=40;CHECK(!Incoming(ctx,base,O)&&ctx.f1.f64==40);
 s->invulnerable=96;CHECK(Incoming(ctx,base,O));ctx.f1.f64=-8;CHECK(!Incoming(ctx,base,O)&&ctx.f1.f64==-8);
 // Original quad corner order, UV rotation, colors and down-positive Y survive native packet conversion.
 s=setup();Write(base,O+0x2C,0x80000);Float(base,0x80028,1);Float(base,0x8002C,1);
 SotnQuad quad{};quad.frame=kSotnQuads[0].frame;quad.xy[0]=3;quad.xy[1]=4;quad.xy[2]=9;quad.xy[3]=5;
 quad.xy[4]=2;quad.xy[5]=12;quad.xy[6]=10;quad.xy[7]=13;quad.color[2]=0xff123456;
 quad.uv[4]=65535;quad.uv[5]=65535;DrawQuad(ctx,base,O,0x80000,1,quad,100,200);
 CHECK(Float(base,0x86000)==3&&Float(base,0x86004)==-4);
 CHECK(Float(base,0x86028)==2&&Float(base,0x8602c)==-12&&Read(base,0x86044)==0xff123456);
 CHECK(std::abs(Float(base,0x86048)-.8f)<.001f&&std::abs(Float(base,0x8604c)-.9f)<.001f);
 // Alucard drains MP only while its empowered shield is held.
 // Goddess's original protection event must display the notice, and the
 // notice must remain drawable after the summon and wisps have ended.
 s=setup();s->visual.spell=Spell::Goddess;s->visual.sprite=kShields[6].sprite;s->visual.x=300;s->visual.y=400;
 SotnTick noticeTick{};Dispatch(ctx,base,*s,noticeTick,983095);
 CHECK(s->buff[kDarkRes]==kBuffFrames&&s->notices[kDarkRes].life==120);
 CountArt();CHECK(active_art==1);samples.clear();Draw(ctx,base,0x80000);
 CHECK(samples.size()==1&&samples[0].frame==kGoddessMessageFrame&&samples[0].hash==NameHash(kShields[6].sprite));
 CHECK(samples[0].x==300&&samples[0].y==328);
 Float(base,O+0x8EC,900);Float(base,O+0x8F0,950);s->visual.x=800;s->visual.y=850;
 ctx.r5.s64=-999;ctx.r6.s64=-888;samples.clear();Draw(ctx,base,0x80000);
 CHECK(samples.size()==1&&samples[0].x==300&&samples[0].y==328);
 for(int i=0;i<120;++i)UpdateEffects(ctx,base,*s);CountArt();CHECK(!s->notices[kDarkRes].life&&active_art==0);
 // Original Knight footsteps repeat at ten ticks; contact plays Candle Hit.
 s=setup();auto& audibleKnight=s->knight;audibleKnight.phase=kWalk;audibleKnight.x=audibleKnight.y=600;audibleKnight.dir=1;
 sound_samples.clear();for(unsigned tick=0;tick<21;++tick){audibleKnight.grounded=true;UpdateKnight(ctx,base,O,audibleKnight);}
 CHECK(sound_samples.size()==3);for(const auto& sample:sound_samples)CHECK(sample.cue=="SE_SR_064B"&&sample.x>=600);
 audibleKnight.touched=true;UpdateKnight(ctx,base,O,audibleKnight);CHECK(audibleKnight.phase==kSwing&&sound_samples.back().cue=="SE_SR_0634");
 // A later Herald notice keeps its own line even when the earlier one ends.
 s=setup();s->visual.spell=Spell::Herald;s->visual.sprite=kShields[4].sprite;s->visual.x=300;s->visual.y=400;
 Dispatch(ctx,base,*s,noticeTick,589879);Dispatch(ctx,base,*s,noticeTick,655415);
 CHECK(s->notices[kThunderRes].y==388);s->notices[kFireRes].life=0;CountArt();samples.clear();Draw(ctx,base,0x80000);
 CHECK(samples.size()==1&&samples[0].x==300&&samples[0].y==316);
 // Dark hits the entire fixed close-view rectangle, then clips it at map edges.
 s=setup();s->visual.spell=Spell::Dark;s->visual.generation=99;s->visual.x=s->visual.y=1000;
 Write(base,0x8291D918,stage);Write(base,stage+16,map);Write(base,0x828F57A4,1);
 rex::memory::store_and_swap<uint16_t>(base+map+4,128);rex::memory::store_and_swap<uint16_t>(base+map+6,128);
 hit_allocations=0;Dispatch(ctx,base,*s,noticeTick,16480);CHECK(hit_allocations==1);
 CHECK(Float(base,0xa002c)==1000&&Float(base,0xa0030)==1000);
 CHECK(Read(base,0xa01a8)==427&&Read(base,0xa01ac)==240);
 s->visual.x=s->visual.y=5;hit_allocations=0;Dispatch(ctx,base,*s,noticeTick,16480);CHECK(hit_allocations==1);
 CHECK(Float(base,0xa002c)+int32_t(Read(base,0xa01a0))>=0&&Float(base,0xa0030)+int32_t(Read(base,0xa01a4))>=0);
 // A close-view burst crosses four native map regions. Each attack has
 // the identical full world bounds but must register in a distinct bucket.
 s=setup();s->visual.active=true;s->visual.spell=Spell::Dark;s->visual.generation=99;s->visual.x=s->visual.y=1000;
 Write(base,0x8291D918,stage);Write(base,stage+16,map);Write(base,stage+20,0x200000);Write(base,0x828F57A4,1);
 for(unsigned y=0;y<128;++y)for(unsigned x=0;x<128;++x)rex::memory::store_and_swap<uint16_t>(base+0x200000+2*(y*128+x),uint16_t((1+(x>=64)+2*(y>=64))<<8));
 hit_allocations=0;Dispatch(ctx,base,*s,noticeTick,16480);CHECK(hit_allocations==4);std::array<bool,5> seenRegions{};
 for(unsigned i=0;i<4;++i){const auto hit=0xa0000+832*i;CHECK(base[hit+0x9f]==0xfc);
  ctx.r1.u64=0x8d000;ctx.r3.u64=hit;ctx.r4.u64=hit+0x1a0;VerifyNativeRectangle(ctx,base);
  CHECK((registered_rect==std::array<float,4>{573,760,1427,1240}));CHECK(registered_region>=1&&registered_region<=4);seenRegions[registered_region]=true;
 }
 for(unsigned i=1;i<=4;++i)CHECK(seenRegions[i]);Write(base,stage+20,0);
 // Dark's 32 original projectiles span the same area as its burst.
 // They move as whole actors, preserving the source quad sizes and paths.
 for(int dir:{1,-1}){
  s=setup();s->visual={true,Spell::Dark,kShields[5].sprite,79,dir,1000,1000,99};SpawnChildren(*s);
  unsigned count=0;float minX=INFINITY,maxX=-INFINITY,minY=INFINITY,maxY=-INFINITY;
  for(const auto& a:s->actors)if(a.active){++count;const auto& c=kSotnChildren[a.clip];const auto& t=kSotnTicks[c.first];
   const float x=a.x+t.x/65536.0f,y=a.y+t.y/65536.0f;
   minX=std::min(minX,x);maxX=std::max(maxX,x);minY=std::min(minY,y);maxY=std::max(maxY,y);
   CHECK(x>=585.0f&&x<=1415.0f&&y>=784.0f&&y<=1216.0f);
   for(unsigned age:{0u,12u,24u})if(age<c.count){const auto& next=kSotnTicks[c.first+age];
    CHECK(std::abs((a.x+next.x/65536.0f-x)-(next.x-t.x)/65536.0f)<.001f);
    CHECK(std::abs((a.y+next.y/65536.0f-y)-(next.y-t.y)/65536.0f)<.001f);
    for(unsigned qi=0;qi<next.count;++qi){const auto& original=kSotnQuads[next.first+qi];const auto translated=ActorQuad(a,next,original,qi);
     for(unsigned v=0;v<8;++v)CHECK(translated.xy[v]==original.xy[v]);}
   }
  }
  CHECK(count==32);CHECK(std::abs((maxX-minX)-830)<.01f&&std::abs((maxY-minY)-432)<.01f);
 }
 // Skull's extended drawn quad and native damage area agree, in both facings;
 // its laser cue is emitted exactly once at the recorded source event.
 for(unsigned c=0;c<std::size(kSotnChildren);++c)if(kSotnChildren[c].spell==unsigned(Spell::Skull)){
  s=setup();auto& skull=s->actors[0];skull.active=true;skull.spell=Spell::Skull;skull.clip=c;
  skull.dir=kSotnChildren[c].facing?-1:1;skull.x=skull.y=1000;skull.age=-1;skull.life=kSotnChildren[c].count;skull.power=100;skull.generation=99;
  sound_samples.clear();
  for(unsigned age=0;age<skull.life;++age){hit_allocations=0;UpdateEffects(ctx,base,*s);
   if(age==18){CHECK(hit_allocations==1);CHECK(Read(base,0xa01a8)==427);
    const auto& t=kSotnTicks[kSotnChildren[c].first+age];unsigned beams=0;
    for(unsigned q=0;q<t.count;++q)if(kSotnQuads[t.first+q].role==1){const auto beam=ActorQuad(skull,t,kSotnQuads[t.first+q],q);CHECK(std::abs(beam.xy[2]-beam.xy[0])==854);++beams;}
    CHECK(beams==1);}
  }
  CHECK(sound_samples.size()==1&&sound_samples[0].cue==kSkullBeamSound);
 }
 Write(base,0x828F57A4,0);Write(base,0x8291D918,0);
 // Capture facing comes from the controller even when body draw is stale.
 // Reverse both inputs and live render scale before the swords appear.
 for(int dir:{1,-1}){
  s=setup();Write(base,O+0x2c,0x80000);Write(base,P+0x250,dir<0);base[0x8001c]=dir>0;
  Float(base,O+0x8ec,600);Float(base,O+0x8f0,600);CHECK(Apply(ctx,base,O,P,*s,kShields[2]));CHECK(s->visual.dir==dir);
  Write(base,P+0x250,dir>0);base[0x8001c]=dir<0;Float(base,0x80028,-1);
  for(int frame=0;frame<110;++frame)UpdateEffects(ctx,base,*s);
  unsigned swords=0;for(const auto& a:s->actors)if(a.active){CHECK(a.dir==dir&&kSotnChildren[a.clip].facing==(dir<0));++swords;}
  CHECK(swords==2);CountArt();samples.clear();Draw(ctx,base,0x80000);
  CHECK(!samples.empty());for(const auto& d:samples)CHECK(d.sx>0);
 }
 // Iron: sample both ends, both edges and the middle along each rotated
 // sword. Every point must lie in an emitted native attack rectangle.
 for(unsigned c=0;c<std::size(kSotnChildren);++c)if(kSotnChildren[c].spell==unsigned(Spell::Iron)) {
  for(int age:{0,40,80,110}) {
   s=setup();Write(base,0x8291D918,stage);Write(base,stage+16,map);Write(base,0x828F57A4,1);
   rex::memory::store_and_swap<uint16_t>(base+map+4,128);rex::memory::store_and_swap<uint16_t>(base+map+6,128);
   auto& sword=s->actors[0];sword.active=true;sword.spell=Spell::Iron;sword.clip=c;sword.age=age-1;
   sword.life=kSotnChildren[c].count;sword.x=sword.y=600;sword.power=40;sword.generation=55;
   hit_allocations=0;UpdateEffects(ctx,base,*s);
   // Collisions pulse every six frames; choose the nearest pulse to the sample.
   while(sword.age%6) {hit_allocations=0;UpdateEffects(ctx,base,*s);}
   CHECK(hit_allocations==8);const auto& tick=kSotnTicks[kSotnChildren[c].first+sword.age];const auto& q=kSotnQuads[tick.first];
   for(int along=0;along<=16;++along)for(float across:{0.0f,.5f,1.0f}) {
    const float u=along/16.0f;
    const float px=600+(1-across)*(q.xy[0]+u*(q.xy[2]-q.xy[0]))+across*(q.xy[4]+u*(q.xy[6]-q.xy[4]));
    const float py=600+(1-across)*(q.xy[1]+u*(q.xy[3]-q.xy[1]))+across*(q.xy[5]+u*(q.xy[7]-q.xy[5]));
    bool covered=false;
    for(unsigned i=0;i<8;++i){const uint32_t h=0xa0000+i*832;const float dx=px-Float(base,h+0x2c),dy=py-Float(base,h+0x30);
     covered|=dx>=int32_t(Read(base,h+0x1a0))-.01f&&dx<=int32_t(Read(base,h+0x1a8))+.01f&&dy>=int32_t(Read(base,h+0x1a4))-.01f&&dy<=int32_t(Read(base,h+0x1ac))+.01f;}
    CHECK(covered);
   }
  }
 }
 // Fire fans and Dark rocks: sample the actual rendered surfaces, in both
 // facings, at every sixth tick. Damage must cover their visible interiors
 // and never retain the old fixed 40x40 / 128x128 entity boxes.
 unsigned fireCovered=0,rockCovered=0;
 for(unsigned c=0;c<std::size(kSotnChildren);++c){const auto& child=kSotnChildren[c];
  const auto spell=Spell(child.spell);if(spell!=Spell::Fire&&spell!=Spell::Dark)continue;
  for(unsigned age=0;age<child.count;age+=6){
   s=setup();Write(base,0x8291D918,stage);Write(base,stage+16,map);Write(base,0x828F57A4,1);
   rex::memory::store_and_swap<uint16_t>(base+map+4,128);rex::memory::store_and_swap<uint16_t>(base+map+6,128);
   auto& actor=s->actors[0];actor.active=true;actor.spell=spell;actor.clip=c;actor.age=age-1;
   actor.life=child.count;actor.x=actor.y=1000;actor.power=30;actor.generation=88;actor.dir=child.facing?-1:1;
   hit_allocations=0;UpdateEffects(ctx,base,*s);CHECK(hit_allocations<=128);
   const auto& tick=kSotnTicks[child.first+age];
   for(unsigned i=0;i<unsigned(hit_allocations);++i){const auto h=0xa0000+i*832;
    CHECK(Read(base,h+0x184)==88);CHECK((Read(base,h+0xb0)&0x100)==(spell==Spell::Fire?0x100:0));
    bool bounded=false;
    for(unsigned qi=0;qi<tick.count;++qi){const auto& q=kSotnQuads[tick.first+qi];
     float l=INFINITY,t=INFINITY,r=-INFINITY,b=-INFINITY;
     for(unsigned v=0;v<4;++v){l=std::min(l,1000.0f+q.xy[v*2]);r=std::max(r,1000.0f+q.xy[v*2]);t=std::min(t,1000.0f+q.xy[v*2+1]);b=std::max(b,1000.0f+q.xy[v*2+1]);}
     bounded|=Float(base,h+0x2c)-Read(base,h+0x1a8)>=l-.1f&&Float(base,h+0x2c)+Read(base,h+0x1a8)<=r+.1f&&Float(base,h+0x30)-Read(base,h+0x1ac)>=t-.1f&&Float(base,h+0x30)+Read(base,h+0x1ac)<=b+.1f;
    }CHECK(bounded);
   }
   for(unsigned qi=0;qi<tick.count;++qi){const auto& q=kSotnQuads[tick.first+qi];
    if((q.mode&1)&&std::all_of(std::begin(q.color),std::end(q.color),[](uint32_t x){return !(x&0xffffff);}))continue;
    for(float u:{.2f,.5f,.8f})for(float v:{.2f,.5f,.8f}){
     const float x=1000+(1-v)*(q.xy[0]+u*(q.xy[2]-q.xy[0]))+v*(q.xy[4]+u*(q.xy[6]-q.xy[4]));
     const float y=1000+(1-v)*(q.xy[1]+u*(q.xy[3]-q.xy[1]))+v*(q.xy[5]+u*(q.xy[7]-q.xy[5]));
     if(x<2||y<2||x>2045||y>2045)continue;
     // Degenerate fragments do not have a registerable 2x2 area.
     const float width=std::max({q.xy[0],q.xy[2],q.xy[4],q.xy[6]})-std::min({q.xy[0],q.xy[2],q.xy[4],q.xy[6]});
     const float height=std::max({q.xy[1],q.xy[3],q.xy[5],q.xy[7]})-std::min({q.xy[1],q.xy[3],q.xy[5],q.xy[7]});
     if(width<8||height<8)continue;
     bool covered=false;for(unsigned i=0;i<unsigned(hit_allocations);++i){const auto h=0xa0000+i*832;
      covered|=std::abs(x-Float(base,h+0x2c))<=Read(base,h+0x1a8)+1.01f&&std::abs(y-Float(base,h+0x30))<=Read(base,h+0x1ac)+1.01f;}
     CHECK(covered);if(spell==Spell::Fire)++fireCovered;else ++rockCovered;
    }
   }
  }
 }
 CHECK(fireCovered>1000&&rockCovered>1000);
 Write(base,0x828F57A4,0);Write(base,0x8291D918,0);
 s=setup();s->leech=4096;s->leech_generation=200;Write(base,O+0x9C8,0x82000);Write(base,0x82000,kShields[11].item);
 Write(base,P+0x2C0,0x83000);Write(base,0x83000,0);Float(base,S+8,100);
 for(int i=0;i<32;++i)UpdateEffects(ctx,base,*s);CHECK(s->leech==4096&&Float(base,S+8)==100);
 Write(base,0x83000,0x20);for(int i=0;i<16;++i)UpdateEffects(ctx,base,*s);CHECK(s->leech==4080&&Float(base,S+8)==99);
 // Recovery cannot be awarded by an overlap-only probe anymore; the actual
 // native enemy HP transaction is exercised at the end of this harness.
 // Held empowerment emits thirty short-lived attacks per second, with no
 // idle-button pulses; release does not erase the last contact's protection.
 s=setup();s->leech=4096;s->leech_generation=200;Write(base,O+0x9C8,0x82000);
 Write(base,0x82000,kShields[11].item);Write(base,P+0x2C0,0x83000);Write(base,0x83000,0x20);
 Write(base,0x828F57A4,0x88000);Float(base,S+8,100);Float(base,O+0x8EC,100);Float(base,O+0x8F0,100);
 Write(base,0x8291D918,stage);Write(base,stage+16,map);
 // Execute the actual native guard registration helper, then the production
 // collision callback. Its rectangle must win over body origin/render facing.
 commit(0x82102000,0x1000);
 constexpr uint32_t shieldShape=0x8a000;
 const auto registerShield=[&](float left,float top,float right,float bottom){
  Write(base,shieldShape,0x821E10C0);Write(base,shieldShape+4,1);
  Float(base,shieldShape+8,left);Float(base,shieldShape+12,top);
  Float(base,shieldShape+16,right);Float(base,shieldShape+20,bottom);
  ctx.r3.u64=O;ctx.r4.u64=shieldShape;VerifyNativeGuard(ctx,base);
 };
 const int rapid_start=hit_allocations;
 for(int i=0;i<60;++i){
  const bool left=i>=30;Write(base,P+0x250,left);base[0x8001c]=!left;
  const float x=100+i*3,y=i%4==0?120:100;
  Float(base,O+0x8EC,x);Float(base,O+0x8F0,y);
  const float l=left?x-42:x+18,r=left?x-18:x+42;
  const int before=hit_allocations;registerShield(l,y-30,r,y+6);
  CHECK(hit_allocations==before); // registration only observes; never allocates
  UpdateEffects(ctx,base,*s);
  if(s->leech_tick%2==0){
   CHECK(hit_allocations==before+1);const auto h=0xa0000+(hit_allocations-1)*832;
   CHECK(Float(base,h+0x2c)==(l+r)*.5f&&Float(base,h+0x30)==y-12);
   CHECK(int32_t(Read(base,h+0x1a0))==-12&&int32_t(Read(base,h+0x1a4))==-18);
   CHECK(left?Float(base,h+0x2c)-12==x-42:Float(base,h+0x2c)+12==x+42);
   // Movement between emission and preparation must not leave damage behind.
   Float(base,O+0x8EC,x+2);Float(base,O+0x8F0,y+1);
   ctx.f1.f64=1.0/60;PrepareHit(ctx,base,h);
   CHECK(Float(base,h+0x2c)==(l+r)*.5f+2&&Float(base,h+0x30)==y-11);
  }else CHECK(hit_allocations==before);
 }
 CHECK(hit_allocations-rapid_start==30);
 // A turn before the next native registration mirrors the last known pose.
 Write(base,P+0x250,0);std::array<float,4> turnBounds{};CHECK(HeldShieldBounds(base,*s,turnBounds));
 CHECK(turnBounds[0]==PlayerX(base,O)+18&&turnBounds[2]==PlayerX(base,O)+42);
 // Wrong active hand, release and malformed rectangles cannot give body hits.
 Write(base,P+0x2F0,1);Write(base,0x82004,kShields[0].item);registerShield(100,80,124,116);
 CHECK(!HeldShieldBounds(base,*s,turnBounds));
 Write(base,P+0x2F0,0);Write(base,0x83000,0);registerShield(100,80,124,116);CHECK(!HeldShieldBounds(base,*s,turnBounds));
 Write(base,0x83000,0x20);registerShield(NAN,80,124,116);registerShield(100,80,99,116);CHECK(!s->shield_bounds_valid);
 // Y-hand shield uses the native rectangle too.
 Write(base,P+0x2F0,1);Write(base,0x82004,kShields[11].item);Write(base,0x83000,0x40);
 registerShield(140,90,164,126);CHECK(HeldShieldBounds(base,*s,turnBounds));CHECK(turnBounds[0]==140&&turnBounds[2]==164);
 Write(base,P+0x2F0,0);Write(base,0x83000,0x20);
 s->invulnerable=96;Write(base,0x83000,0);
 const int released_start=hit_allocations;for(int i=0;i<10;++i)UpdateEffects(ctx,base,*s);
 CHECK(hit_allocations==released_start&&s->invulnerable==86);
 ctx.f1.f64=30;CHECK(Incoming(ctx,base,O));
 for(int i=0;i<86;++i)UpdateEffects(ctx,base,*s);ctx.f1.f64=30;CHECK(!Incoming(ctx,base,O));
 Write(base,0x828F57A4,0);Write(base,0x8291D918,0);
 // Only actual enemy actors (flag 4) are homing targets. Attack entities
 // (flags 8/16) and unrelated data must never lure the lasers.
 s=setup();Write(base,M+0xB0,T+48);constexpr uint32_t enemy=0x54000;
 Write(base,T+32,0x20002);Write(base,T+36,enemy);Write(base,enemy+8,8);Float(base,enemy+64,100);Float(base,enemy+68,100);
 float tx=0,ty=0;ObserveTarget(base,0x20002,100,100);CHECK(!ClosestEnemy(base,100,100,tx,ty));
 Write(base,enemy+8,16);ObserveTarget(base,0x20002,100,100);CHECK(!ClosestEnemy(base,100,100,tx,ty));
 Write(base,enemy+8,4);Float(base,enemy+64,NAN);Float(base,enemy+68,NAN);
 constexpr uint32_t targetShape=0x7b000,targetVtable=0x7c000;
 Write(base,targetShape,targetVtable);Write(base,targetVtable+12,0x82200000);
 Float(base,targetShape+8,120);Float(base,targetShape+12,140);Float(base,targetShape+16,160);Float(base,targetShape+20,180);
 CaptureTarget(ctx,base,0x20002,targetShape);CHECK(ClosestEnemy(base,100,100,tx,ty)&&tx==140&&ty==160);
 // Native registration identifies the hurt object in r6 and the monster owner
 // in r7, or uses the monster itself in r6 with r7=0 for ordinary bodies.
 targets={};Write(base,M+0xB0,T+64);Write(base,T+48,0x40003);Write(base,T+52,0x55000);Write(base,0x55008,32);
 ctx.r3.u64=targetShape;ctx.r4.u64=0x40000042;ctx.r6.u64=0x40003;ctx.r7.u64=0x20002;
 sub_823C4C40(ctx,base);CHECK(!ClosestEnemy(base,100,100,tx,ty));
 ctx.r3.u64=targetShape;ctx.r4.u64=0x10;ctx.r6.u64=0x40003;ctx.r7.u64=0x20002;
 sub_823C4C40(ctx,base);CHECK(ClosestEnemy(base,100,100,tx,ty)&&tx==140&&ty==160);
 // The common enemy body's 0x40000009 registration is the live failure:
 // r6 is the monster itself and r7 is zero. It must be a homing candidate.
 targets={};ctx.r3.u64=targetShape;ctx.r4.u64=0x40000009;ctx.r6.u64=0x20002;ctx.r7.u64=0;
 sub_823C4C40(ctx,base);CHECK(ClosestEnemy(base,100,100,tx,ty)&&tx==140&&ty==160);
 Write(base,T+32,0x30002);CHECK(!ClosestEnemy(base,100,100,tx,ty));Write(base,M+0xB0,T+32);
 // All adjacent beam quads share EXACT edge coordinates through curved turns.
 EffectActor beam{};beam.spell=Spell::Medusa;beam.edge_count=19;
 for(unsigned i=0;i<19;++i)beam.edges[i]={float(i*3),float(i*i)-6,float(i*3),float(i*i)+6};
 SotnTick beamTick{};beamTick.count=18;SotnQuad source{};
 for(unsigned i=0;i<17;++i){const auto left=ActorQuad(beam,beamTick,source,i),right=ActorQuad(beam,beamTick,source,i+1);
  CHECK(left.xy[2]==right.xy[0]&&left.xy[3]==right.xy[1]);CHECK(left.xy[6]==right.xy[4]&&left.xy[7]==right.xy[5]);}
 // Texel centers exclude neighbouring atlas pixels at each strip boundary.
 quad.width=6;quad.height=16;DrawQuad(ctx,base,O,0x80000,1,quad,100,200);
 CHECK(std::abs(Float(base,0x86048)-.75f)<.001f&&std::abs(Float(base,0x8604c)-.875f)<.001f);
 // Production emission: one damage child at the moving head per 6 ticks,
 // no independently allocated collision areas along the beam's visual strip.
 s=setup();Write(base,0x8291D918,stage);Write(base,stage+16,map);
 rex::memory::store_and_swap<uint16_t>(base+map+4,128);rex::memory::store_and_swap<uint16_t>(base+map+6,128);
 Write(base,0x828F57A4,1);unsigned medusaClip=0;
 while(kSotnChildren[medusaClip].spell!=unsigned(Spell::Medusa)||kSotnChildren[medusaClip].facing)++medusaClip;
 auto& laser=s->actors[0];laser.active=true;laser.spell=Spell::Medusa;laser.clip=medusaClip;
 laser.age=-1;laser.life=kSotnChildren[medusaClip].count;laser.dir=1;laser.x=laser.y=600;laser.power=25;
 hit_allocations=0;for(int i=0;i<20;++i)UpdateEffects(ctx,base,*s);CHECK(hit_allocations==3);
 const auto beforeRejected=hit_allocations;Hit(ctx,base,O,-20,20,6,6,25,0,99);CHECK(hit_allocations==beforeRejected);
 Write(base,0x828F57A4,0);Write(base,0x8291D918,0);
 // Audit every spell through the actual local vtable layout and BOTH phases.
 // Dark's 32-rock burst is included; resolution must never append a request.
 for(unsigned spell=0;spell<13;++spell) {
   s=setup();Write(base,0x8291D918,stage);Write(base,stage+16,map);
   rex::memory::store_and_swap<uint16_t>(base+map+4,128);rex::memory::store_and_swap<uint16_t>(base+map+6,128);
   Float(base,O+0x8EC,600);Float(base,O+0x8F0,600);Float(base,S+8,500);Write(base,0x828F57A4,1);
   Write(base,P+0x2C0,0x83000);Write(base,0x83000,0);base[0x8001c]=0;
   CHECK(Apply(ctx,base,O,P,*s,kShields[spell]));unsigned emitted=0,peakBurst=0;
   for(unsigned tick=0;tick<700;++tick) {
     hit_allocations=0;UpdateEffects(ctx,base,*s);UpdateKnight(ctx,base,O,s->knight);
     peakBurst=std::max(peakBurst,unsigned(hit_allocations));emitted+=hit_allocations;
     for(unsigned i=0;i<unsigned(hit_allocations);++i){const auto hit=0xa0000+832*i;
       CHECK(Read(base,Read(base,hit)+0x1c)==0x824823A0);CHECK(Read(base,Read(base,hit)+0x24)==0x824827F0);
       ctx.r3.u64=hit;ctx.f1.f64=1.0/60;sub_824823A0(ctx,base);
     }
     const auto registered=submits;
     for(unsigned i=0;i<unsigned(hit_allocations);++i)ResolveHit(ctx,base,0xa0000+832*i);
     CHECK(submits==registered);
     if(tick%30==0){CountArt();samples.clear();Draw(ctx,base,0x80000);}
   }
   if(spell==5)CHECK(peakBurst>=32&&emitted>100);
   if(spell==2||spell==3||spell==8||spell==9||spell==10)CHECK(emitted>0);
   CHECK(!s->visual.active);
   Write(base,0x828F57A4,0);Write(base,0x8291D918,0);
 }
 // All four Medusa variants must acquire a real registered hurt-shape center
 // and approach it, despite invalid data at the previously guessed offsets.
 for(unsigned clipIndex=0;clipIndex<std::size(kSotnChildren);++clipIndex) {
   const auto& child=kSotnChildren[clipIndex];if(child.spell!=unsigned(Spell::Medusa))continue;
   s=setup();Write(base,M+0xB0,T+48);Write(base,T+32,0x20002);Write(base,T+36,enemy);
   Write(base,enemy+8,4);Float(base,enemy+64,NAN);Float(base,enemy+68,NAN);
   auto& beam=s->actors[0];beam.active=true;beam.spell=Spell::Medusa;beam.clip=clipIndex;beam.age=-1;
   beam.life=child.count;beam.dir=child.facing?-1:1;beam.variant=child.variant;beam.x=beam.y=600;
   float nearest=1e9;
   for(unsigned tick=0;tick<240&&beam.active;++tick){
     Float(base,targetShape+8,880);Float(base,targetShape+12,580);Float(base,targetShape+16,920);Float(base,targetShape+20,620);
     ctx.r3.u64=targetShape;ctx.r4.u64=0x40000009;ctx.r6.u64=0x20002;ctx.r7.u64=0;
     sub_823C4C40(ctx,base);UpdateEffects(ctx,base,*s);
     if(beam.age>0){CHECK(beam.target==0x20002);nearest=std::min(nearest,std::hypot(beam.x+beam.head_x-900,beam.y+beam.head_y-600));}}
   CHECK(nearest<60);Write(base,M+0xB0,T+32);
 }
 // Stress the same native vector-insertion helper from the Dark crash with
 // 32 concurrent register/query jobs. All paths must share one critical section.
 std::memset(base+stressVector,0,16);Write(base,0x828F57A4,1);hit_allocations=0;
 stress_vector=true;collision_peak=0;std::vector<std::thread> workers;
 for(unsigned i=0;i<32;++i)workers.emplace_back([&,i]{PPCContext local{};local.fpscr.InitHost();local.r1.u64=0x200000+(i+1)*0x1000-256;
   const auto item=0x94000+i*16;Write(base,item,i+1);local.r8.u64=item;local.r6.u64=0;
   sub_823C4C40(local,base);sub_823C5098(local,base);});
 for(auto& worker:workers)worker.join();stress_vector=false;CHECK(collision_peak==1);
 const auto vectorBegin=Read(base,stressVector+4),vectorEnd=Read(base,stressVector+8);CHECK(vectorEnd-vectorBegin==32*4);
 std::vector<unsigned> inserted;for(auto at=vectorBegin;at<vectorEnd;at+=4)inserted.push_back(Read(base,at));
 std::sort(inserted.begin(),inserted.end());for(unsigned i=0;i<32;++i)CHECK(inserted[i]==i+1);
 Write(base,0x828F57A4,0);
 // Death retires all active visuals/attacks and the empowered shield.
 s->visual.active=true;s->knight.phase=kWalk;s->actors[0].active=true;Float(base,S+4,0);
 FrameLocked(ctx,base,O,P);CHECK(!s->visual.active&&s->knight.phase==kIdle&&!s->leech&&!s->actors[0].active);
 // Real native transaction: reproduce the old one-second repeat immunity,
 // then verify HP decreases every two frames with the production hit interval.
 commit(0x82000000,0x200000);
 {std::ifstream image("modding/data/hod_image.bin",std::ios::binary);
  CHECK(image.good());image.read(reinterpret_cast<char*>(base+0x82000000),0x200000);CHECK(image.good());}
 for(unsigned test_case=0;test_case<3;++test_case) {
  const bool old_interval=test_case==0,iron_interval=test_case==2;
  auto* state=setup();state->leech=4096;state->leech_generation=901;
  if(iron_interval){state->leech=0;auto& sword=state->actors[0];sword.active=true;sword.spell=Spell::Iron;
   sword.generation=901;sword.life=142;sword.age=-1;sword.power=0;
   for(unsigned i=0;i<std::size(kSotnChildren);++i)if(kSotnChildren[i].spell==unsigned(Spell::Iron)){sword.clip=i;break;}}
  Write(base,M+0xB0,T+64);Write(base,T+32,0x20002);Write(base,T+36,0x54000);
  Write(base,0x54004,0x20002);Write(base,0x54008,4);Write(base,0x54000,0x9c300);
  for(unsigned off:{16u,148u,152u})Write(base,0x9c300+off,0x82200004);
  Write(base,0x9c100,0x9c200);Write(base,0x9c200,0x9c300);
  Float(base,0x54000+152,10000);Float(base,0x54000+156,10000);Float(base,0x54000+176,0);
  Write(base,0x54000+472,0x9d000);Write(base,0x9d004,0x9e000);
  Write(base,0x9d008,0x9e00c);Write(base,0x9d00c,0x9e100);
  // An ordinary shield's still-active one-second cooldown cannot block FE.
  Write(base,0x9e000,0x40000000);base[0x9e004]=1;Float(base,0x9e008,1);
  std::memset(base+0x54000+500,0,20);
  Float(base,S+4,10);Float(base,S+16,1000);Float(base,S+28,0);
  const int popups_before=heals;int hp_events=0;uint32_t current=0;
  Write(base,0x828F57A4,0x88000);Write(base,0x8291D918,stage);Write(base,stage+16,map);
  Write(base,0x83000,0);hit_allocations=0;
  for(unsigned frame=0;frame<60;++frame) {
   ctx.r1.u64=0x210000;ctx.r3.u64=0x9d000;ctx.f1.f64=1.0f/60;
   VerifyNative_sub_8224AE48(ctx,base);UpdateEffects(ctx,base,*state);
   if(frame%(iron_interval?kIronPulseFrames:2)==0) {
    Hit(ctx,base,O,100,100,12,24,30,0,901);current=0xa0000+(hit_allocations-1)*832;
    CHECK(std::abs(Float(base,current+0x114)-(iron_interval?.2f:2.0f/60))<2e-6f&&base[current+0x9F]==(iron_interval?0xFD:0xFE));
    Write(base,current+4,0x30003);Write(base,current+8,8);
    Write(base,T+48,0x30003);Write(base,T+52,current);
   }
   constexpr uint32_t attack=0x69000,hurt=0x69400,pair=0x68000;
   std::memset(base+attack,0,44);std::memset(base+hurt,0,44);std::memset(base+pair,0,16);
   Write(base,attack+4,0x80000042);Write(base,attack+16,0x30003);Write(base,attack+20,handle);
   Write(base,attack+24,30);Float(base,attack+28,old_interval?1.0f:Float(base,current+0x114));
   Write(base,attack+40,base[current+0x9F]);Write(base,hurt+4,0x40000009);Write(base,hurt+16,0x20002);
   Write(base,pair,attack);Write(base,pair+4,hurt);
   const float before=Float(base,0x54000+152);
   ctx.r1.u64=0x210000;ctx.r3.u64=0x54000;ctx.r4.u64=1;ctx.r5.u64=pair;
   ctx.r6.u64=0x54000+472;ctx.r7.u64=0x54000+500;ctx.r8.u64=0;ctx.r9.u64=0;ctx.r10.u64=0;
   sub_82246DF0(ctx,base);
   if(frame==0)CHECK(base[0x9e004]==1&&Float(base,0x9e008)>.9f);
   if(Float(base,0x54000+152)<before){++hp_events;if(!old_interval)CHECK(frame%(iron_interval?12:2)==0);}
  }
  CHECK(hp_events==(iron_interval?5:old_interval?1:30));CHECK(heals-popups_before==(iron_interval?0:hp_events));
  if(!iron_interval)CHECK(Float(base,S+4)==10+8*hp_events&&state->invulnerable>=(old_interval?37:95));
  // Clamp recovery and keep the green number visible even when already full.
  if(!iron_interval)for(float hp:{997.0f,1000.0f}) {
   Float(base,S+4,hp);state->leech_contact=0;Write(base,current+0x198,0);
   const auto popup_count=heals;Recover(ctx,base,current,0x20002);
   CHECK(Float(base,S+4)==1000&&heals==popup_count+1&&state->invulnerable==96);
   Recover(ctx,base,current,0x20002);CHECK(heals==popup_count+1);
  }
  std::printf("Native enemy HP: %s interval, %d damage events in 60 frames.\n",iron_interval?"Iron 12-frame":old_interval?"old":"two-frame",hp_events);
 }
 // Exact material selection: the old preset disables alpha; native 0 enables it.
 commit(0x82930000,0x10000);ctx.r30.u64=0x85000;ctx.r31.u64=0x80000;
 base[0x80000+140]=3;Write(base,0x85000+408,4);VerifyNativeBlend(ctx,base);
 CHECK(!(Read(base,0x85000+408)&4));base[0x80000+140]=0;VerifyNativeBlend(ctx,base);
 CHECK(Read(base,0x85000+408)&4);
 VirtualFree(base,0,MEM_RELEASE);
 std::printf("Passed %d Shield Rod callback checks.\n",checks);
}
