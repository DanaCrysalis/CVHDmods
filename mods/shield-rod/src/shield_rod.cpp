// Shield Rod for Alucard (package 19): Symphony of the Night's shield spells.
//
// HoD's Alucard holds a weapon on X (equipment slot 0) and one on Y (slot 1).
// A shield in either slot guards while its button is held: the owner update
// calls 82450658 every frame, which asks 82450708 for the held slot holding a
// category-14 item and passes it to the player (vtable +0x220, Alucard keeps
// it at player+0x2F0). This file overrides 82450658: after the native guard,
// a new press of the other button, while that slot holds the Shield Rod,
// casts the shield's spell (SotN: Shield Rod + shield, both attack buttons).
//
// Spell numbers come from shield_rod_balance.h, generated from the player's
// own HoD tables and SotN disc (modding/tools/shield_rod.py header). Behaviour
// follows SotN as documented in modding/docs/SHIELD_ROD_PLAN.md; the code is
// written for HoD, nothing is copied from SotN or its decompilation.
//
// Spell art is drawn from the shield's own HoD weapon sprite: HoD converted
// each shield's whole SotN weapon file, the cut spell frames included. Extra
// frames are drawn once after Alucard's owner draw (824476B8) through a copy
// of his body's sprite instance whose resource is
// the shield sprite, found by name (FNV-1 of "P_ARSH%02X", 823D2520). Hits
// are HoD's normal short-lived attack rectangles (as Nathan's summons), tagged
// so the collider attack chain (core/runtime/hod_hooks.cpp) hands them to
// ResolveHit.
//
// Shared guest functions are owned by the hook hub; this file registers its
// handlers at the end (HOD_HOOK). Its own overrides (82450658 guard start,
// 824519C8 attack, 824526D0 INT, two sound-bank logs) pass straight to the
// game when the mod is switched off.
//
// All thirteen shield spells use disc-traced parent/child geometry and factory
// timing. Combat, camera projection and elemental recovery use HoD services.
#include "../generated/default/harmonyrecomp_init.h"
#include "shield_rod.h"
#include "shield_rod_balance.h"
#include "shield_rod_sotn_trace.h"
#include "shield_rod_audio.h"
#include "hod_guest.h"
#include "hod_hooks.h"
#include <rex/logging.h>
#include <rex/memory/utils.h>
#include <rex/system/xmemory.h>
#include <array>
#include <algorithm>
#include <atomic>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <utility>

REX_EXTERN(__imp__sub_825CEFA0);
REX_EXTERN(__imp__sub_825CED10);
REX_EXTERN(__imp__sub_82450658);
REX_EXTERN(__imp__sub_824519C8);
REX_EXTERN(__imp__sub_824526D0);

namespace harmony::shield_rod {
namespace {
constexpr uint32_t kAlucardVtable = 0x83002DA0;  // dllAlucard player vtable (entry 144 answers 2)
constexpr uint32_t kSlotButton[2] = {0x20, 0x40};  // X, Y in the held-button mask
constexpr uint32_t kWeaponItems = 0x33, kWeaponItemsEnd = 0x227;  // 821D4878 item ranges
constexpr uint32_t kShieldCategory = 14;
constexpr auto kCastSound = "SE_SR_0641";
constexpr auto kRefusedSound = "SE_SYS_GET_MAGICITEM";
constexpr unsigned kSpriteBytes = 192, kColliderBytes = 832, kColliderTable = 512;
// Empowered-shield contact pulses: Valmanway's rate when attacking nonstop
// (measured November 19: a hit every 100 ms, repeat window 0.083 s).
constexpr unsigned kLeechHitFrames = 6;
constexpr unsigned kIronHitFrames = 12, kIronPulseFrames = 3;
// Fixed close-view footprint (1280x720 at the normal 1.5 sprite scale).
constexpr float kSpellViewWidth=854, kSpellViewHeight=480;
constexpr auto kSkullBeamSound="SE_SR_0660";
constexpr float kFrameOriginX = 64, kFrameOriginY = 47;  // Canonical pivot of the native knight frames

uint32_t Read(uint8_t* base, uint32_t a) { return rex::memory::load_and_swap<uint32_t>(base + a); }
void Write(uint8_t* base, uint32_t a, uint32_t v) { rex::memory::store_and_swap<uint32_t>(base + a, v); }
float Float(uint8_t* base, uint32_t a) { return std::bit_cast<float>(Read(base, a)); }
void Float(uint8_t* base, uint32_t a, float v) { Write(base, a, std::bit_cast<uint32_t>(v)); }

uint32_t Call(PPCContext& ctx, uint8_t* base, uint32_t fn, uint32_t a, uint32_t b = 0) {
  PPCContext call = ctx;  // never disturb the caller's registers
  call.r3.u64 = a;
  call.r4.u64 = b;
  rex::runtime::ResolveIndirectFunction(fn)(call, base);
  return call.r3.u32;
}
uint32_t EntityOf(uint8_t* base, uint32_t handle) {  // handle -> object (entity manager table)
  const auto manager = Read(base, 0x8291D9F0);
  if (!manager || !handle) return 0;
  const auto table = Read(base, manager + 0xAC);
  if (!table) return 0;
  const auto end = Read(base, manager + 0xB0);
  const uint32_t offset = (handle & 0xFFFF) << 4;
  if (end < table || end - table > 65536 * 16 || end - table < 16 || offset > end - table - 16) return 0;
  const auto entry = table + offset;
  return Read(base, entry) == handle ? Read(base, entry + 4) : 0;
}

enum Buff { kAtk, kDef, kInt, kFireRes, kThunderRes, kDarkRes, kBuffs };
struct BuffNotice {unsigned life=0;float x=0,y=0;uint32_t sprite=0,frame=0;};
enum Phase : uint8_t { kIdle, kWalk, kSwing };
struct KnightTrail {float x=0,y=0;uint32_t frame=62;int age=24,dir=1;};
struct Knight {
  Phase phase = kIdle;
  int t = 0, walked = 0, falling = 0;
  float x = 0, y = 0, vy = 0, scale = 0;  // SotN entity position (native pivot 64,47), world
  int dir = 1;
  bool grounded = false, touched = false;
  uint32_t sprite = 0, generation = 0;
  float power = 0;
  std::array<KnightTrail,6> trails{};
};
struct BuffVisual {
  bool active = false;
  Spell spell = Spell::Leather;
  uint32_t sprite = 0;
  int t = 0, dir = 1;
  float x = 0, y = 0;
  uint32_t generation = 0;

};
struct BeamEdge {float x0=0,y0=0,x1=0,y1=0;};
struct EffectActor {
  bool active = false;
  Spell spell = Spell::Iron;
  uint32_t generation = 0, sprite = 0, frame = 62, clip = 0;
  int age = 0, life = 0, variant = 0, dir = 1;
  float x = 0, y = 0, vx = 0, vy = 0, power = 0;
  float head_x=0,head_y=0,heading=0,rotation=0;
  uint32_t target=0;
  std::array<BeamEdge,19> edges{};unsigned edge_count=0;
};
struct State {
  uint32_t owner = 0, handle = 0, player = 0;
  uint32_t held = 0;
  std::array<uint32_t, kBuffs> buff{};
  Knight knight;
  BuffVisual visual;
  std::array<EffectActor, 96> actors{};
  uint32_t leech = 0, leech_tick = 0, leech_generation = 0, leech_contact = 0, invulnerable = 0;
  bool shield_bounds_valid=false;int shield_dir=1;
  std::array<float,4> shield_bounds{};
  uint32_t player_vtable = 0;
  std::array<BuffNotice,kBuffs> notices{};

};
std::array<State, 8> states;  // one per owner (six players, with room)
std::recursive_mutex& collision_lock = hod::CollisionLock();  // core/runtime: shared with every mod
std::mutex target_lock;
struct Target {uint32_t handle=0;float x=0,y=0;std::chrono::steady_clock::time_point seen{};};
std::array<Target,512> targets{};
uint32_t target_scratch=0;
std::recursive_mutex lock;     // owners update on several game threads
std::atomic<int> active_art{0};   // active spell art: lets every other sprite draw skip the lock
uint32_t scratch = 0;          // guest memory: lookup sprite, draw sprite
uint32_t sound_scratch = 0;    // synchronous cue-name lookup, protected by lock
uint32_t generation = 0;
uint32_t AlignedScratch(uint32_t bytes) {
  const auto raw=REX_KERNEL_MEMORY()->SystemHeapAlloc(bytes+15);
  return raw?(raw+15)&~15u:0;
}
void CountArt() {
  int n = 0;
  for (const auto& s : states) n += s.owner && (std::any_of(s.notices.begin(),s.notices.end(),[](const auto& n){return n.life;}) || s.knight.phase != kIdle || std::any_of(s.knight.trails.begin(),s.knight.trails.end(),[](const auto& t){return t.age<24;}) || s.visual.active || s.leech || std::any_of(s.actors.begin(), s.actors.end(), [](const auto& a){return a.active;}));
  active_art.store(n, std::memory_order_relaxed);
}

uint32_t AlucardPlayer(uint8_t* base, uint32_t owner) {
  const auto player = owner && (Read(base, owner + 8) & 2) ? Read(base, owner + 0x924) : 0;
  return player && Read(base, player) == kAlucardVtable ? player : 0;
}
bool Current(uint8_t* base, const State& s) {
  // Resolve the saved generation handle BEFORE touching a saved owner address.
  // Host-side spell state can outlive the guest allocation on room/owner teardown.
  return s.owner && s.handle && s.player && EntityOf(base, s.handle) == s.owner &&
         (Read(base, s.owner + 8) & 2) && Read(base, s.owner + 0x924) == s.player &&
         Read(base, s.player) == s.player_vtable;
}
State* Find(uint8_t* base, uint32_t owner, bool create) {
  if (!owner) return nullptr;
  for (auto& s : states) {
    if (s.owner && !Current(base, s)) s = State{};
    if (s.owner == owner) return &s;
  }
  if (!create) return nullptr;
  const auto player = (Read(base, owner + 8) & 2) ? Read(base, owner + 0x924) : 0;
  const auto handle = player ? Read(base, owner + 4) : 0;
  if (!handle || EntityOf(base, handle) != owner) return nullptr;
  for (auto& s : states) if (!s.owner) { s = State{}; s.owner = owner; s.handle = handle; s.player = player; s.player_vtable = Read(base, player); return &s; }
  // Do not discard a live owner's state just because all slots are occupied.
  return nullptr;
}
bool Alive(uint8_t* base, uint32_t player) {
  const auto stats = Read(base, player + 88);
  return stats && Float(base, stats + 4) > 0;
}
// Same test as 82450708: a weapon item whose row is in the shield category.
bool IsShield(PPCContext& ctx, uint8_t* base, uint32_t item) {
  if (item < kWeaponItems || item >= kWeaponItemsEnd) return false;
  const auto row = Call(ctx, base, 0x823C8BE8, item);
  return row && Call(ctx, base, 0x8246C700, row) == kShieldCategory;
}
const ShieldSpell* SpellFor(uint32_t item) {
  for (const auto& s : kShields) if (s.item == item) return &s;
  return nullptr;
}
void SoundAt(PPCContext& ctx,uint8_t* base,float x,float y,const char* cue) {
  if(!std::isfinite(x)||!std::isfinite(y))return;
  if(!sound_scratch)sound_scratch=AlignedScratch(64);if(!sound_scratch)return;
  const auto length=std::strlen(cue);if(length>=64)return;
  // 825993B0 resolves the cue name synchronously. Avoid hardcoded addresses
  // of strings in an executable whose rdata changes with title updates.
  std::memcpy(base+sound_scratch,cue,length+1);
  PPCContext call = ctx;
  call.r3.u64 = sound_scratch;
  call.r4.s64 = int32_t(x);
  call.r5.s64 = int32_t(y);
  call.r6.u64 = 1;
  rex::runtime::ResolveIndirectFunction(0x82239218)(call, base);
  static unsigned missing=0;
  if(call.r3.s32==-1 && missing++<8)REXLOG_WARN("[shield rod] sound cue unavailable: {}",cue);
}
void Sound(PPCContext& ctx,uint8_t* base,uint32_t owner,const char* cue) {
  SoundAt(ctx,base,Float(base,owner+0x8EC),Float(base,owner+0x8F0),cue);
}
static bool OriginalSoundBankPath(uint8_t* base,uint32_t path) {
  if(path<0x10000||path>=0xE0000000u)return false;
  const auto name=reinterpret_cast<const char*>(base+path);
  const auto end=static_cast<const char*>(std::memchr(name,0,256));
  if(!end)return false;
  const std::string filename(name,end);return filename.find("SE_SHIELDROD.")!=std::string::npos;
}
static const char* SpellCue(Spell,unsigned id) {
  for(const auto& sound:kShieldSounds)if(sound.id==id)return sound.cue;
  return nullptr;
}
// 825912B8 accepts BGM/VX/VXJ prefixes only. SE banks must be submitted directly
// to its lower-level queue (82590680), then kicked with 82590878.
static void EnsureSounds(PPCContext& ctx,uint8_t* base) {
  static uint32_t queue=0;static unsigned queued=0;
  const auto current=Read(base,0x82930B10); // native audio queue mutex, used by 82590680
  if(!current){queue=0;queued=0;return;}
  if(queue!=current){queue=current;queued=0;}
  if(queued==3)return;
  if(!sound_scratch)sound_scratch=AlignedScratch(64);if(!sound_scratch)return;
  // Native worker: kind 1 -> 825CEFA0 / CreateSoundBank (engine vtable +32),
  // kind 2 -> 825CED10 / CreateInMemoryWaveBank (engine vtable +36).
  // This low-level queue does NOT add the game's drive prefix. Root-relative
  // paths reach NtCreateFile literally and fail; D: is the guest asset mount.
  const char* paths[]={"D:\\data\\sound\\SE_SHIELDROD.xsb","D:\\data\\sound\\SE_SHIELDROD.xwb"};
  bool changed=false;
  for(unsigned i=0;i<2;++i)if(!(queued&(1u<<i))){
    std::memcpy(base+sound_scratch,paths[i],std::strlen(paths[i])+1);
    PPCContext load=ctx;load.r3.u64=sound_scratch;load.r4.u64=i+1;load.r5.u64=0; // common group
    rex::runtime::ResolveIndirectFunction(0x82590680)(load,base);
    if(load.r3.u32){queued|=1u<<i;changed=true;}
  }
  if(changed){Call(ctx,base,0x82590878,0);REXLOG_INFO("[shield rod] original sound-bank queue mask {} (3 = both files)",queued);}
}
static void SpellSounds(PPCContext& ctx,uint8_t* base,Spell spell,unsigned track,unsigned age,float x,float y) {
  const auto& range=kSotnSoundTracks[track];
  for(unsigned i=0;i<range.count;++i){const auto& e=kSotnSounds[range.first+i];
    if(e.tick==age)if(const auto cue=SpellCue(spell,e.id))SoundAt(ctx,base,x,y,cue);}
}
const char* Name(Spell s) {
  static constexpr const char* names[] = {"Leather", "Knight", "Iron", "Axe Knight", "Herald", "Dark", "Goddess",
                                          "Shaman", "Medusa", "Skull", "Fire", "Alucard", "Alucart"};
  return names[unsigned(s)];
}
// The player's SotN-style entity position in HoD world coordinates (Y runs
// down): the body center owner+0x8EC/0x8F0, recomputed by the shared owner
// update every frame.
float PlayerX(uint8_t* base, uint32_t owner) { return Float(base, owner + 0x8EC); }
float PlayerY(uint8_t* base, uint32_t owner) { return Float(base, owner + 0x8F0); }

// Stage collision, the push-out queries HoD's own movers use. Tiles come from
// the stage map at 8291D918 (823C31D8: 16 px tiles, an attribute byte each;
// bit 0x01 floor, 0x02 solid wall, top bits the slope shape, 3 = solid block).
//  823C2D80(x, y, out, flag): pixels (negative) a point must move up to leave
//    the floor, climbing stacked tiles; 0 when the point is not in floor.
//    flag 0 includes one-way platforms.
//  823C2468 / 823C2720(x, y, out, flag): the same sideways against walls.
// (823C2340, used first, answers attribute bit 0x08 only: never a floor.)
uint32_t Call4(PPCContext& ctx, uint8_t* base, uint32_t fn, float x, float y) {
  if (!std::isfinite(x) || !std::isfinite(y) ||
      double(x) < INT32_MIN || double(x) > INT32_MAX || double(y) < INT32_MIN || double(y) > INT32_MAX) return 0;
  if (!Read(base, 0x8291D918)) return 0;  // no stage loaded
  PPCContext call = ctx;
  call.r3.u64 = uint32_t(int32_t(std::floor(x)));
  call.r4.u64 = uint32_t(int32_t(std::floor(y)));
  call.r5.u64 = 0;
  call.r6.u64 = 0;
  rex::runtime::ResolveIndirectFunction(fn)(call, base);
  return call.r3.u32;
}
int FloorPush(PPCContext& ctx, uint8_t* base, float x, float y) { return int32_t(Call4(ctx, base, 0x823C2D80, x, y)); }
bool Wall(PPCContext& ctx, uint8_t* base, float x, float y) {
  return Call4(ctx, base, 0x823C2468, x, y) != 0 || Call4(ctx, base, 0x823C2720, x, y) != 0;
}
float Intellect(PPCContext& ctx, uint8_t* base, uint32_t owner) {
  PPCContext call = ctx;
  call.r3.u64 = owner;
  rex::runtime::ResolveIndirectFunction(0x824526D0)(call, base);
  return std::isfinite(call.f1.f64) ? float(call.f1.f64) : 0.0f;
}
// HoD's magic rule (82533878): P + (P/64 + 0.25) * INT.
float MagicPower(PPCContext& ctx, uint8_t* base, uint32_t owner, float p) {
  const float power = p + (p / 64 + .25f) * std::fmax(0.0f, Intellect(ctx, base, owner));
  return std::isfinite(power) ? std::fmax(1.0f, std::floor(power)) : 1.0f;
}

// The collision manager partitions the currently loaded stage. Never register
// an off-stage custom attack; visual trails can finish without a collision area.
static bool InStage(uint8_t* base,float x,float y) {
  const auto manager=Read(base,0x8291D918);if(manager<0x10000)return false;
  const auto map=Read(base,manager+16);if(map<0x10000)return false;
  const auto width=rex::memory::load_and_swap<uint16_t>(base+map+4);
  const auto height=rex::memory::load_and_swap<uint16_t>(base+map+6);
  return x>=0 && y>=0 && x<float(width)*16 && y<float(height)*16;
}
static bool RequestAddress(uint32_t p) {return p>=0x10000 && p<0xE0000000u && !(p&3);}

// One short-lived native attack rectangle, as Nathan's summons spawn them.
static void SubmitArea(PPCContext& ctx,uint8_t* base,uint32_t hit){
  PPCContext area=ctx;area.r3.u64=hit;area.r4.u64=hit+0x1A0;
  __imp__sub_82484180(area,base);
  if(Read(base,hit+0xAC)!=0xFFFFFFFFu)Write(base,hit+0x18C,1);
}
void Hit(PPCContext& ctx, uint8_t* base, uint32_t owner, float x, float y, int half_w, int half_h, float damage,
         uint32_t element, uint32_t gen,uint32_t* created=nullptr,bool submit=true) {
  if(created)*created=0;
  if(!std::isfinite(x)||!std::isfinite(y)||!std::isfinite(damage)||std::abs(x)>1e7f||std::abs(y)>1e7f||damage<=0||half_w<=0||half_h<=0)return;
  if(!InStage(base,x,y))return;
  const auto heap = Read(base, 0x828F57A4);
  if (!heap) return;
  PPCContext call = ctx;
  call.r3.u64 = heap; call.r4.u64 = kColliderBytes; call.r5.u64 = 0;
  rex::runtime::ResolveIndirectFunction(0x825FC4B0)(call, base);
  const auto hit = call.r3.u32;
  if (!hit) return;
  std::memset(base + hit, 0, kColliderBytes);
  call = ctx;
  call.r3.u64 = hit; call.r4.u64 = 0; call.r5.u64 = Read(base, owner + 4); call.r6.u64 = 12;
  rex::runtime::ResolveIndirectFunction(0x82481D60)(call, base);
  std::memcpy(base + hit + kColliderTable, base + 0x821EA0F0, 0x90);
  Write(base, hit, hit + kColliderTable);
  Write(base, hit + kColliderTable + 0x24, 0x824827F0);
  Write(base, hit + kColliderTable + 0x80, 0x825F4170);
  Write(base, hit + kColliderTable + 0x1C, 0x824823A0);  // prepare, then +0x24 resolves
  Write(base, hit + kColliderTable + 0x78, 0x825F4170);
  Float(base, hit + 0x2C, x); Float(base, hit + 0x30, y);
  Float(base, hit + 0x44, 0); Float(base, hit + 0x48, 0);
  Float(base, hit + 0x110, damage);
  bool leech=false,iron=false,dark=false;
  {std::lock_guard guard(lock);const auto* state=Find(base,owner,false);
    leech=state && state->leech && state->leech_generation==gen;
    dark=state && state->visual.active && state->visual.spell==Spell::Dark && state->visual.generation==gen;
    if(state)for(const auto& actor:state->actors)
      if(actor.active && actor.generation==gen && actor.spell==Spell::Iron){iron=true;break;}}
  // Native 8224E4E8 keys repeat-hit immunity by owner/type/byte +9F, and
  // takes its duration from +114. A fresh collider handle does not bypass it.
  Float(base, hit + 0x114, leech ? float(kLeechHitFrames)/60.0f : iron ? float(kIronHitFrames)/60.0f-1e-6f : 1.0f);
  if(leech)base[hit+0x9F]=0xFE; // independent of the ordinary shield's cooldown
  else if(iron)base[hit+0x9F]=0xFD; // all blade slices share one target cooldown
  else if(dark)base[hit+0x9F]=0xFC; // screen burst must not inherit held-shield repeat immunity
  Write(base, hit + 0xB0, (Read(base, hit + 0xB0) & 0xC0000000u) | 2 | 0x40 | element);
  Write(base, hit + 0x180, 0xFF); Write(base, hit + 0x184, gen);
  Write(base, hit + 0x190, kHitTag); Write(base, hit + 0x194, owner);
  Float(base, hit + 0x188, 0); Write(base, hit + 0x18C, 0);
  Write(base, hit + 0x1A0, uint32_t(-half_w)); Write(base, hit + 0x1A4, uint32_t(-half_h));
  Write(base, hit + 0x1A8, half_w); Write(base, hit + 0x1AC, half_h);
  // Submit the area now. Enemies query the collision lists in their own
  // update, which in most frames runs before a collider's prepare phase, so
  // areas submitted there were seen only when the timing lined up: familiar
  // hits made the same way landed one time in three or fewer, and every time
  // once submitted from the player update (November 18). The prepare phase
  // (PrepareHit) only retries an area that could not be submitted here.
  if(submit)SubmitArea(ctx,base,hit);
  if(created)*created=hit;
}
// 82469D18 obtains the held shield's current native OPD guard rectangle and
// 8244B558 registers it in world coordinates. Reuse that geometry, including
// walking/crouching/air poses and facing; the body render flag is not facing.
// Called after releasing collision_lock so state -> collision lock order holds.
// Owner +0x930 is HoD's control type: 1 = this machine's player. Remote
// copies (online) are driven by the PAMA snapshot and have no input.
static bool Local(uint8_t* base,uint32_t owner){return Read(base,owner+0x930)==1;}
// Guarding with the Alucard Shield. Local players: the held button of the
// guard hand. Remote copies: their guard slot arrives in the snapshot
// (PAMA +0x47 -> owner +0xA64 -> player +0x2F0, -1 while not guarding).
static bool GuardingAlucardShield(uint8_t* base,uint32_t owner,uint32_t player) {
  const auto hand=Read(base,player+0x2F0),equipment=Read(base,owner+0x9C8);
  if(hand>=2||!equipment||Read(base,equipment+hand*4)!=kShields[11].item)return false;
  if(!Local(base,owner))return true;
  const auto input=Read(base,player+0x2C0);
  return input && (Read(base,input)&kSlotButton[hand]);
}
static void ObserveGuard(uint8_t* base,uint32_t handle,float left,float top,float right,float bottom) {
  if(!std::isfinite(left)||!std::isfinite(top)||!std::isfinite(right)||!std::isfinite(bottom))return;
  const float width=right-left,height=bottom-top;
  if(width<=0||height<=0||width>256||height>256)return;
  std::lock_guard guard(lock);
  const auto owner=EntityOf(base,handle);auto* s=Find(base,owner,false);
  if(!s||!s->leech||!AlucardPlayer(base,owner)||!Alive(base,s->player))return;
  if(!GuardingAlucardShield(base,owner,s->player)){s->shield_bounds_valid=false;return;}
  const float x=PlayerX(base,owner),y=PlayerY(base,owner);
  s->shield_bounds={left-x,top-y,right-x,bottom-y};
  s->shield_dir=Read(base,s->player+0x250)?-1:1;s->shield_bounds_valid=true;
}
static bool HeldShieldBounds(uint8_t* base,const State& s,std::array<float,4>& bounds) {
  if(!s.shield_bounds_valid)return false;
  if(!GuardingAlucardShield(base,s.owner,s.player))return false;
  bounds=s.shield_bounds;
  // If the turn precedes this frame's guard preparation, mirror the previous
  // pose around the current owner origin. Translation never lags movement.
  if((Read(base,s.player+0x250)?-1:1)!=s.shield_dir){const float l=bounds[0];bounds[0]=-bounds[2];bounds[2]=-l;}
  const float x=PlayerX(base,s.owner),y=PlayerY(base,s.owner);
  bounds[0]+=x;bounds[2]+=x;bounds[1]+=y;bounds[3]+=y;return true;
}
// The empowered Alucard Shield's damaging area: the held shield's guard
// rectangle reached only enemies right at the shield (user, November 19:
// Dracula's first form's head, Legion's corpse body and Wargs were missed),
// so it extends past the shield in front and above and below it.
// Set to 0 (user, November 19: too far once hits registered on time; the
// guard rectangle alone is being retested).
constexpr float kLeechReachFront = 0, kLeechReachUp = 0, kLeechReachDown = 0;
static std::array<float,4> LeechArea(uint8_t* base,const State& s,std::array<float,4> b) {
  if(Read(base,s.player+0x250))b[0]-=kLeechReachFront;else b[2]+=kLeechReachFront;
  b[1]-=kLeechReachUp;b[3]+=kLeechReachDown;
  return b;
}
static void SetShieldHitBounds(uint8_t* base,uint32_t hit,const std::array<float,4>& bounds) {
  Float(base,hit+0x2C,(bounds[0]+bounds[2])*.5f);Float(base,hit+0x30,(bounds[1]+bounds[3])*.5f);
  const int hw=int(std::ceil((bounds[2]-bounds[0])*.5f)),hh=int(std::ceil((bounds[3]-bounds[1])*.5f));
  Write(base,hit+0x1A0,uint32_t(-hw));Write(base,hit+0x1A4,uint32_t(-hh));
  Write(base,hit+0x1A8,hw);Write(base,hit+0x1AC,hh);
}
// Large screen/beam areas must be clipped before registration, rather than
// handing the stage partitioner negative or off-map cell coordinates.
static unsigned AreaHit(PPCContext& ctx,uint8_t* base,uint32_t owner,float left,float top,float right,float bottom,float power,uint32_t gen,uint32_t element=0) {
  const auto manager=Read(base,0x8291D918);if(manager<0x10000)return 0;
  const auto map=Read(base,manager+16);if(map<0x10000)return 0;
  const float width=rex::memory::load_and_swap<uint16_t>(base+map+4)*16.0f;
  const float height=rex::memory::load_and_swap<uint16_t>(base+map+6)*16.0f;
  left=std::max(0.0f,left);top=std::max(0.0f,top);right=std::min(width-1,right);bottom=std::min(height-1,bottom);
  if(right-left<2||bottom-top<2)return 0;
  // Native 82484180 registers into ONE room/region, selected from the
  // attack entity's origin by 823C3150. A large shape alone cannot reach
  // enemies registered in other regions. Register an identical world-space
  // shape in each region touched by the area, without enlarging its bounds.
  unsigned count=0;const auto regions=Read(base,manager+20);
  const auto emit=[&](float x,float y){uint32_t hit=0;
    Hit(ctx,base,owner,x,y,std::max(1,int((right-left)*.5f)),std::max(1,int((bottom-top)*.5f)),power,element,gen,&hit,false);
    if(!hit)return;
    Write(base,hit+0x1A0,uint32_t(int32_t(std::ceil(left-x))));Write(base,hit+0x1A4,uint32_t(int32_t(std::ceil(top-y))));
    Write(base,hit+0x1A8,uint32_t(int32_t(std::floor(right-x))));Write(base,hit+0x1AC,uint32_t(int32_t(std::floor(bottom-y))));SubmitArea(ctx,base,hit);++count;
  };
  if(regions<0x10000){emit((left+right)*.5f,(top+bottom)*.5f);return count;}
  std::array<bool,256> seen{};const unsigned columns=unsigned(width/16);
  for(unsigned y=unsigned(top)/16;y<=unsigned(bottom)/16;++y)for(unsigned x=unsigned(left)/16;x<=unsigned(right)/16;++x){
    const unsigned region=rex::memory::load_and_swap<uint16_t>(base+regions+2*(y*columns+x))>>8;
    if(seen[region])continue;seen[region]=true;
    emit(std::clamp(float(x*16+8),left,right),std::clamp(float(y*16+8),top,bottom));
  }
  return count;
}
constexpr float kFeet = kAxeWalkBox[1] + kAxeWalkBox[3] - kFrameOriginY;  // frame-space feet below the entity

// A frame-space hitbox (x, y, w, h) of the knight, placed in the world.
void KnightHit(PPCContext& ctx, uint8_t* base, uint32_t owner, const Knight& k, const int box[4], float scale) {
  const float cx = k.x + (box[0] + box[2] * .5f - kFrameOriginX) * k.dir;
  const float cy = k.y + (box[1] + box[3] * .5f - kFrameOriginY);
  Hit(ctx, base, owner, cx, cy, box[2] / 2, box[3] / 2, k.power * scale, 0, k.generation);
}

// ------------------------------------------------------------- spells -----
bool StartAxeKnight(PPCContext& ctx, uint8_t* base, uint32_t owner, uint32_t player, State& s, const ShieldSpell& spell) {
  if (s.knight.phase != kIdle) return false;  // one knight at a time
  auto& k = s.knight;
  const auto body = Read(base, owner + 0x2C);
  k = Knight{};
  k.phase = kWalk;
  k.dir = body && base[body + 0x1C] ? -1 : 1;  // the body sprite's facing
  k.x = PlayerX(base, owner);
  k.y = PlayerY(base, owner) - 8;
  k.sprite = spell.sprite;
  k.power = MagicPower(ctx, base, owner, float(spell.power));
  k.generation = ++generation;
  return true;
}

static const SotnClip& Clip(Spell spell, int dir) { return kSotnClips[unsigned(spell)*2+(dir<0)]; }
static bool ActiveGeneration(const State& s, uint32_t gen) {
  if (s.knight.phase != kIdle && s.knight.generation == gen) return true;
  if (s.leech && s.leech_generation == gen) return true;
  if (s.visual.active && s.visual.generation == gen)return true;
  for (const auto& a:s.actors) if(a.active && a.generation==gen)return true;
  return false;
}
// All thirteen spells enter their recorded parent routine. MP is paid once;
// buffs and child attacks occur on the original factory-event frames.
bool Apply(PPCContext&, uint8_t* base, uint32_t owner, uint32_t player, State& s, const ShieldSpell& spell) {
  if(s.visual.active || !std::isfinite(PlayerX(base,owner)) || !std::isfinite(PlayerY(base,owner)))return false;
  if(spell.spell==Spell::AxeKnight && s.knight.phase!=kIdle)return false;
  // Alucard vtable +648 returns player+0x250. The rendered body's facing
  // includes animation mirroring and can lag input until its next draw.
  const int dir=Read(base,player+0x250)?-1:1; // controller: 0 = right, 1 = left
  s.visual={true,spell.spell,spell.sprite,0,dir,PlayerX(base,owner),PlayerY(base,owner),++generation};
  return true;
}

// Online play. HoD replicates player spawn events: 8244CA98 (owner, id, kind,
// sub, slot, r8, r9, r10, f1, three stack bytes) spawns a player attack
// object and, for this machine's player in a network game, queues the call
// in the owner's PASH list (+0x9F4); every other machine replays the same
// call on its copy of that player (824626F0 -> 8244CA98). Kind 11 / sub 1 is
// HoD's own "queue only" event: it spawns nothing on either side. A cast is
// announced with it: id = the shield item, r9/r10 = "SR" "OD". Unpatched
// peers replay it as the native no-op. In single player nothing is queued.
constexpr uint32_t kSyncKind = 11, kSyncSub = 1, kSyncTagA = 0x5352, kSyncTagB = 0x4F44;
void Announce(PPCContext& ctx, uint8_t* base, uint32_t owner, const ShieldSpell& spell) {
  PPCContext call = ctx;
  // A fresh guest frame below the live stack: the callee reads its three
  // stack arguments at sp+0x5C/+0x64/+0x6C and copies them into the record.
  const uint32_t sp = (ctx.r1.u32 - 0x400) & ~15u;
  std::memset(base + sp, 0, 0x100);
  call.r1.u64 = sp;
  call.r3.u64 = owner; call.r4.u64 = spell.item; call.r5.u64 = kSyncKind; call.r6.u64 = kSyncSub;
  call.r7.u64 = 0; call.r8.u64 = 0; call.r9.u64 = kSyncTagA; call.r10.u64 = kSyncTagB; call.f1.f64 = 0;
  rex::runtime::ResolveIndirectFunction(0x8244CA98)(call, base);
}
// A remote player's announced cast: run the same spell on this machine's
// copy of them, without MP. Its attack areas belong to the remote owner, so
// HoD shows hits and damage numbers here but applies the damage only on the
// caster's machine (8224E700: attacks of non-local owners); recovery,
// MP drain and buffs on the caster's own stats stay on the caster's machine.
void Replay(PPCContext& ctx, uint8_t* base, uint32_t owner, uint32_t item) {
  const auto* spell = SpellFor(item);
  const auto player = AlucardPlayer(base, owner);
  if (!spell || !player || !Alive(base, player)) return;
  std::lock_guard guard(lock);
  auto* s = Find(base, owner, true);
  if (!s) return;
  if (Apply(ctx, base, owner, player, *s, *spell))
    REXLOG_INFO("[shield rod] online player {} cast {} Shield spell", Read(base, owner + 0x938), Name(spell->spell));
  else
    REXLOG_INFO("[shield rod] online player {} {} Shield spell not replayed (a spell is still active)",
                Read(base, owner + 0x938), Name(spell->spell));
  CountArt();
}

void Cast(PPCContext& ctx, uint8_t* base, uint32_t owner, uint32_t player, State& s, const ShieldSpell& spell) {
  const auto stats = Read(base, player + 88);
  if (!stats) return;
  const float mp = Float(base, stats + 8);
  if (!std::isfinite(mp)) return;
  if (mp < spell.mp) {
    REXLOG_INFO("[shield rod] {} Shield spell: {:.0f} MP needed, {:.0f} left", Name(spell.spell), spell.mp, mp);
    Sound(ctx, base, owner, kRefusedSound);
    return;
  }
  if (!Apply(ctx, base, owner, player, s, spell)) {
    REXLOG_INFO("[shield rod] {} Shield spell not cast (another spell is still active); no MP spent",
                Name(spell.spell));
    return;
  }
  Float(base, stats + 8, mp - spell.mp);
  Announce(ctx, base, owner, spell);
  static bool identified=false;if(!identified){identified=true;
    REXLOG_INFO("[shield rod] build SR-20261116-alucard-native-shield-contact: empowered contact uses native held-shield world rectangle");}
  REXLOG_INFO("[shield rod] cast {} Shield spell for {:.0f} MP ({:.0f} left)", Name(spell.spell), spell.mp,
              mp - spell.mp);
}

// SotN's Axe Knight Shield: the shield grows above Alucard and fades, a knight
// appears, falls to the floor and marches forward (2.5 px a frame, following
// slopes). On its first contact with an enemy, or at a wall, it swings its axe
// in a wide arc and vanishes. Timings are SotN's (60 frames a second).
uint32_t KnightFrame(const Knight& k) {
  constexpr unsigned cycle[14]={0,0,0,1,1,2,2,3,3,3,2,2,1,1};
  return k.phase==kSwing?(k.t<=1?kAxeSwingFrame:kAxeAfterFrame):kAxeWalkFrames[cycle[unsigned(k.walked)%14]];
}
void UpdateKnight(PPCContext& ctx, uint8_t* base, uint32_t owner, Knight& k) {
  for(auto& trail:k.trails)if(trail.age<24)++trail.age;
  if (k.phase == kIdle) return;
  ++k.t;
  switch (k.phase) {
    case kWalk: {
      const float feet = k.y + kFeet;
      const float ahead = k.x + (kAxeWalkBox[0] + kAxeWalkBox[2] - kFrameOriginX) * k.dir + k.dir;
      if (!k.grounded) {  // SotN: 1 px a frame forward, gravity 1/8, at most 6
        k.x += k.dir;
        k.y += k.vy;
        k.vy = std::fmin(6.0f,k.vy+.125f);
        const int push = FloorPush(ctx, base, k.x, k.y + kFeet);
        if (push < 0) { k.y += push; k.grounded = true; k.vy = 0; SoundAt(ctx,base,k.x,k.y,SpellCue(Spell::AxeKnight,0x64B)); }  // landed: stand on the surface
      } else {
        if((k.t-1)%10==0)SoundAt(ctx,base,k.x,k.y,SpellCue(Spell::AxeKnight,0x64B));
        // Wall at chest height ahead: swing.
        if (Wall(ctx, base, ahead, feet - 24) || Wall(ctx, base, ahead, feet - 40)) { k.touched = true; break; }
        k.x += 2.5f * k.dir;
        // Stay on the floor: the surface within 8 px below the feet (or the
        // feet are in it, up a slope). None: walked off a ledge, fall.
        const float probe = k.y + kFeet + 8;
        const int push = FloorPush(ctx, base, k.x, probe);
        if (push < 0 && push >= -24) k.y += probe + push - (k.y + kFeet);
        else if (push < -24) k.touched = true;  // a step too high to climb: treat as a wall
        else { k.grounded = false; k.vy = 0; }
      }
      if(k.walked%4==0) {
        auto& trail=k.trails[(unsigned(k.walked)/4)%k.trails.size()];
        trail={k.x,k.y,KnightFrame(k),0,k.dir};
      }
      if (++k.walked % 6 == 1) KnightHit(ctx, base, owner, k, kAxeWalkBox, 1);
      if (k.walked > 360) k.touched = true;  // six seconds at most
      if (!k.grounded && ++k.falling > 90) {  // fell 1.5 s without finding a floor: give up
        REXLOG_INFO("[shield rod] Axe Knight found no floor; spell ends");
        k.phase = kIdle;
      }
      if (k.grounded) k.falling = 0;
      break;
    }
    case kSwing:
      if (k.t == 1) { KnightHit(ctx, base, owner, k, kAxeSwingBox, 1.0f); }
      if (k.t >= 13) { k.phase = kIdle; REXLOG_INFO("[shield rod] Axe Knight done"); }
      break;
    default: break;
  }
  if (k.phase == kWalk && k.touched) { k.phase = kSwing; k.t = 0; SoundAt(ctx,base,k.x,k.y,SpellCue(Spell::AxeKnight,0x634)); }
}

// Every machine runs this for every cast (its own, or a replayed online one),
// so each machine buffs its own local players and the buff counts where that
// player's damage and stats are computed. Player handles: [8291D968]+0x14
// points to an array of six (native 8245BE80, 8245CCE8, 8238D1xx read
// *(manager+0x14) + i*4); the array is NOT inline in the manager.
static void ShareBuff(uint8_t* base,uint32_t owner,Buff kind) {
  static constexpr const char* names[]={"ATK","DEF","INT","fire resistance","thunder resistance","dark resistance"};
  if(auto* own=Find(base,owner,true))own->buff[kind]=kBuffFrames;
  const auto list=Read(base,0x8291D968);
  const auto handles=list?Read(base,list+0x14):0;
  if(!handles){REXLOG_WARN("[shield rod] {} buff: no player list",names[kind]);return;}
  unsigned players=0,shared=0,distant=0;
  for(unsigned i=0;i<6;++i) {
    const auto ally=EntityOf(base,Read(base,handles+i*4));
    if(!ally || !(Read(base,ally+8)&2))continue;
    ++players;
    if(ally==owner)continue;
    const float dx=PlayerX(base,ally)-PlayerX(base,owner),dy=PlayerY(base,ally)-PlayerY(base,owner);
    if(!(std::abs(dx)<=320 && std::abs(dy)<=240)){++distant;
      REXLOG_INFO("[shield rod] {} buff: player {} too far ({:.0f}, {:.0f})",names[kind],Read(base,ally+0x938),dx,dy);continue;}
    if(auto* a=Find(base,ally,true)){
      ++shared;a->buff[kind]=kBuffFrames;
      REXLOG_INFO("[shield rod] {} buff shared with {} player {}",names[kind],
                  Read(base,ally+0x930)==1?"local":"online",Read(base,ally+0x938));
    }
  }
  REXLOG_INFO("[shield rod] {} buff from player {}: {} players, {} shared, {} too far",names[kind],
              Read(base,owner+0x938),players,shared,distant);
}
static void SpawnChildren(State& s) {
  const auto& v=s.visual;
  float min_x=INFINITY,min_y=INFINITY,max_x=-INFINITY,max_y=-INFINITY;
  if(v.spell==Spell::Dark)for(const auto& c:kSotnChildren){
    if(c.spell!=unsigned(v.spell)||c.facing!=(v.dir<0)||c.start!=v.t)continue;
    const auto& first=kSotnTicks[c.first];
    const float x=first.x/65536.0f,y=first.y/65536.0f;
    min_x=std::min(min_x,x);max_x=std::max(max_x,x);min_y=std::min(min_y,y);max_y=std::max(max_y,y);
  }
  for(unsigned i=0;i<std::size(kSotnChildren);++i) {
    const auto& c=kSotnChildren[i];
    if(c.spell!=unsigned(v.spell) || c.facing!=(v.dir<0) || c.start!=v.t)continue;
    for(auto& a:s.actors)if(!a.active) {
      a=EffectActor{};a.active=true;a.spell=v.spell;a.generation=++generation;
      a.sprite=v.sprite;a.clip=i;a.life=c.count;a.age=-1;a.variant=c.variant;a.dir=v.dir;
      a.x=v.x;a.y=v.y;a.power=float(kShields[c.spell].power);
      if(v.spell==Spell::Dark){
        // Redistribute the original 32 spawn points over HoD's close view.
        // Translate each whole actor; keep sprite sizes, original motion,
        // animation, sound positions and fragment colliders together.
        const auto& first=kSotnTicks[c.first];const float x=first.x/65536.0f,y=first.y/65536.0f;
        const float u=max_x>min_x?(x-min_x)/(max_x-min_x):.5f;
        const float w=max_y>min_y?(y-min_y)/(max_y-min_y):.5f;
        a.x+=(u-.5f)*(kSpellViewWidth-24)-x;
        a.y+=(w-.5f)*(kSpellViewHeight-48)-y;
      }
      break;
    }
  }
}
static void Dispatch(PPCContext& ctx,uint8_t* base,State& s,const SotnTick& tick,uint32_t factory) {
  auto& v=s.visual;const auto& spell=kShields[unsigned(v.spell)];
  const unsigned type=factory&0xFFF,variant=(factory>>16)&0x7F;
  const float x=v.x+tick.x/65536.0f,y=v.y+tick.y/65536.0f;
  if(type==55) {
    Buff kind=kBuffs;
    switch(variant){case 6:kind=kInt;break;case 7:kind=kAtk;break;case 8:kind=kDef;break;
    case 9:kind=kFireRes;break;case 10:kind=kThunderRes;break;case 15:kind=kDarkRes;break;}
    if(kind!=kBuffs){ShareBuff(base,s.owner,kind);
      const auto line=std::count_if(s.notices.begin(),s.notices.end(),[](const auto& n){return n.life;});
      s.notices[kind]={120,v.x,v.y-12*line,v.sprite,kSotnNoticeFrames[unsigned(v.spell)][kind]};}
    return;
  }
  switch(v.spell) {
    case Spell::AxeKnight:
      if(type==88){StartAxeKnight(ctx,base,s.owner,s.player,s,spell);s.knight.phase=kWalk;s.knight.t=0;
        s.knight.x=x;s.knight.y=y;s.knight.vy=0;s.knight.scale=1;s.knight.dir=v.dir;}
      break;
    case Spell::Alucard:if(type==44){s.leech=kBuffFrames;s.leech_tick=0;s.shield_bounds_valid=false;s.leech_generation=++generation;}break;
    case Spell::Dark:if(type==96){const auto regions=AreaHit(ctx,base,s.owner,v.x-kSpellViewWidth*.5f,v.y-kSpellViewHeight*.5f,
      v.x+kSpellViewWidth*.5f,v.y+kSpellViewHeight*.5f,MagicPower(ctx,base,s.owner,float(spell.power)),v.generation);
      REXLOG_INFO("[shield rod] Dark area center ({:.0f},{:.0f}), 854x480, {} region attacks",v.x,v.y,regions);}break;
    default:break;
  }
}
static void ObserveTarget(uint8_t* base,uint32_t handle,float x,float y) {
  const auto owner=EntityOf(base,handle);if(!owner || !(Read(base,owner+8)&4) || (Read(base,owner+8)&0x1A) ||
    !std::isfinite(x)||!std::isfinite(y))return;
  std::lock_guard guard(target_lock);Target* oldest=&targets[0];
  for(auto& t:targets){if(t.handle==handle || !t.handle){
    if(!t.handle){static unsigned announced=0;if(announced++<16)REXLOG_INFO("[shield rod] observed native enemy {:08X} center ({:.0f},{:.0f})",handle,x,y);}
    t={handle,x,y,std::chrono::steady_clock::now()};return;}if(t.seen<oldest->seen)oldest=&t;}
  *oldest={handle,x,y,std::chrono::steady_clock::now()};
}
static bool ClosestEnemy(uint8_t* base,float x,float y,float& tx,float& ty,uint32_t* handle=nullptr) {
  std::lock_guard guard(target_lock);const auto now=std::chrono::steady_clock::now();
  float best=600*600;bool found=false;
  for(auto& t:targets) {
    if(!t.handle || now-t.seen>std::chrono::milliseconds(250))continue;
    const auto owner=EntityOf(base,t.handle);if(!owner || !(Read(base,owner+8)&4) || base[owner+0x17]){t={};continue;}
    const float d=(t.x-x)*(t.x-x)+(t.y-y)*(t.y-y);
    if(std::isfinite(d)&&d<best){best=d;tx=t.x;ty=t.y;if(handle)*handle=t.handle;found=true;}
  }
  return found;
}
// Observe native registration using its shape's own center getter, not an
// assumed enemy actor layout. The shape is valid for the duration of this call.
static void CaptureTarget(PPCContext& original,uint8_t* base,uint32_t handle,uint32_t shape) {
  const auto owner=EntityOf(base,handle);if(!owner || !(Read(base,owner+8)&4) || (Read(base,owner+8)&0x1A) || !RequestAddress(shape))return;
  const auto vtable=Read(base,shape);if(!RequestAddress(vtable))return;
  const auto getter=Read(base,vtable+12);if(getter<0x82000000 || getter>=0x90000000)return;
  if(!target_scratch)target_scratch=AlignedScratch(16);if(!target_scratch)return;
  Float(base,target_scratch,NAN);Float(base,target_scratch+4,NAN);
  PPCContext call=original;call.r3.u64=target_scratch;call.r4.u64=shape;
  rex::runtime::ResolveIndirectFunction(getter)(call,base);
  ObserveTarget(base,handle,Float(base,target_scratch),Float(base,target_scratch+4));
}
// HoD targeting bridge: preserve the recorded speed pulse/quad strip, steer
// its head with SotN's 0x50 initial turn limit, +8 per tick, capped at 0x100.
static SotnQuad ActorQuad(const EffectActor& a,const SotnTick& tick,const SotnQuad& source,unsigned segment) {
  auto q=source;
  if(a.spell==Spell::Skull && q.role==1) {
    if(a.dir>0){q.xy[2]=q.xy[6]=int16_t(q.xy[0]+kSpellViewWidth);}
    else {q.xy[0]=q.xy[4]=int16_t(q.xy[2]-kSpellViewWidth);}
    return q;
  }
  if(a.spell!=Spell::Medusa || a.edge_count<2)return q;
  const unsigned count=std::min(unsigned(tick.count),a.edge_count-1);
  if(segment>=count)return q;
  const auto& older=a.edges[count-segment];const auto& newer=a.edges[count-segment-1];
  const float xy[8]={older.x0,older.y0,newer.x0,newer.y0,older.x1,older.y1,newer.x1,newer.y1};
  for(unsigned i=0;i<8;++i)q.xy[i]=int16_t(std::clamp(std::lround(xy[i]),-32768l,32767l));
  return q;
}
static void QuadHit(PPCContext& ctx,uint8_t* base,uint32_t owner,const EffectActor& a,
                    const SotnQuad& q,float damage,uint32_t element) {
  if((q.mode&1) && std::all_of(std::begin(q.color),std::end(q.color),[](uint32_t c){return !(c&0xFFFFFF);}))return;
  // Tile the same quad drawn by DrawTick. Fire's rotating flame fans need
  // narrow strips; Dark rocks only need their own small visible rectangle.
  const unsigned pieces=a.spell==Spell::Fire?4:1;
  const auto distance=[&](unsigned i,unsigned j){return std::hypot(float(q.xy[i]-q.xy[j]),float(q.xy[i+1]-q.xy[j+1]));};
  const bool across=distance(0,4)+distance(2,6)>distance(0,2)+distance(4,6);
  for(unsigned part=0;part<pieces;++part){
    float min_x=INFINITY,min_y=INFINITY,max_x=-INFINITY,max_y=-INFINITY;
    for(unsigned edge=0;edge<2;++edge)for(unsigned end=0;end<2;++end){
      const unsigned left=across?edge*2:edge*4,right=left+(across?4:2);
      const float u=float(part+end)/pieces;
      const float x=q.xy[left]+u*(q.xy[right]-q.xy[left]),y=q.xy[left+1]+u*(q.xy[right+1]-q.xy[left+1]);
      min_x=std::min(min_x,x);max_x=std::max(max_x,x);min_y=std::min(min_y,y);max_y=std::max(max_y,y);
    }
    AreaHit(ctx,base,owner,a.x+min_x,a.y+min_y,a.x+max_x,a.y+max_y,damage,a.generation,element);
  }
}
static void UpdateEffects(PPCContext& ctx,uint8_t* base,State& s) {
  for(auto& n:s.notices)if(n.life)--n.life;
  if(s.invulnerable)--s.invulnerable;
  if(s.leech_contact)--s.leech_contact;
  if(s.visual.active){auto& v=s.visual;const auto& clip=Clip(v.spell,v.dir);
    if(v.t>=clip.count)v.active=false;
    else {SpawnChildren(s);const auto& tick=kSotnTicks[clip.first+v.t];
      for(unsigned i=0;i<clip.event_count;++i){const auto& ev=kSotnEvents[clip.event_first+i];if(ev.tick==v.t)Dispatch(ctx,base,s,tick,ev.factory);}
      SpellSounds(ctx,base,v.spell,unsigned(v.spell)*2+(v.dir<0),v.t,v.x+tick.x/65536.0f,v.y+tick.y/65536.0f);
      if(v.spell!=Spell::Dark && tick.hw && tick.hh && v.t%6==0 && kShields[unsigned(v.spell)].power>0)
        Hit(ctx,base,s.owner,v.x+tick.x/65536.0f+tick.hx*v.dir,v.y+tick.y/65536.0f+tick.hy,
          tick.hw,tick.hh,MagicPower(ctx,base,s.owner,float(kShields[unsigned(v.spell)].power)),0,v.generation);
      ++v.t;}}
  for(auto& a:s.actors)if(a.active) {
    if(++a.age>=a.life){a.active=false;continue;}
    const auto& child=kSotnChildren[a.clip];const auto& tick=kSotnTicks[child.first+a.age];
    if(a.spell==Spell::Medusa) {
      constexpr float tau=6.283185307f;
      const float initial=(a.dir>0?0x700-(a.variant<<9):(a.variant<<9)+0x100)*tau/4096;
      if(a.age==0){a.head_x=tick.x/65536.0f;a.head_y=tick.y/65536.0f;a.heading=-initial;}
      else {
        float tx=0,ty=0;uint32_t target=0;
        if(ClosestEnemy(base,a.x+a.head_x,a.y+a.head_y,tx,ty,&target)) {
          if(a.target!=target){a.target=target;REXLOG_INFO("[shield rod] Medusa acquired enemy {:08X} at ({:.0f},{:.0f})",target,tx,ty);}
          const float desired=std::atan2(ty-a.y-a.head_y,tx-a.x-a.head_x);
          const float turn=std::min(256.0f,80.0f+(a.age-1)*8)*tau/4096;
          a.heading+=std::clamp(std::remainder(desired-a.heading,tau),-turn,turn);
        }
        const float step=tick.move/65536.0f;
        a.head_x+=std::cos(a.heading)*step;a.head_y+=std::sin(a.heading)*step;
      }
      a.rotation=a.heading+tick.angle*tau/4096;
      if(!std::isfinite(a.head_x)||!std::isfinite(a.head_y)||std::abs(a.head_x)>2048||std::abs(a.head_y)>2048){a.active=false;continue;}
      // A strip of shared cross-sections stays connected as the head turns.
      // Retain the original pulse width and vertical displacement at the head.
      BeamEdge edge{a.head_x,a.head_y-8,a.head_x,a.head_y+8};
      if(tick.count){const auto& q=kSotnQuads[tick.first+tick.count-1];
        const float c=std::cos(a.rotation),sn=std::sin(a.rotation),x=tick.x/65536.0f,y=tick.y/65536.0f;
        const float dx0=q.xy[2]-x,dy0=q.xy[3]-y,dx1=q.xy[6]-x,dy1=q.xy[7]-y;
        edge={a.head_x+c*dx0-sn*dy0,a.head_y+sn*dx0+c*dy0,a.head_x+c*dx1-sn*dy1,a.head_y+sn*dx1+c*dy1};}
      for(unsigned i=18;i>0;--i)a.edges[i]=a.edges[i-1];a.edges[0]=edge;a.edge_count=std::min(19u,a.edge_count+1);
    }
    SpellSounds(ctx,base,a.spell,std::size(kSotnClips)+a.clip,a.age,
      a.x+(a.spell==Spell::Medusa?a.head_x:tick.x/65536.0f),a.y+(a.spell==Spell::Medusa?a.head_y:tick.y/65536.0f));
    if(a.power<=0 || a.age%(a.spell==Spell::Iron?kIronPulseFrames:6))continue;
    const float damage=MagicPower(ctx,base,s.owner,a.power);
    const float x=a.x+tick.x/65536.0f,y=a.y+tick.y/65536.0f;
    const uint32_t element=a.spell==Spell::Fire?0x100:a.spell==Spell::Medusa?0x8000:0;
    if(a.spell==Spell::Iron && tick.count) {
      // The entity's 16x16 box is only the center of a 128-pixel sword.
      // Tile the actual rotated blade quad so its tip and hilt both hit,
      // without turning its diagonal bounding box into a large square.
      const auto& q=kSotnQuads[tick.first];
      for(unsigned part=0;part<8;++part) {
        float min_x=INFINITY,min_y=INFINITY,max_x=-INFINITY,max_y=-INFINITY;
        for(unsigned edge=0;edge<2;++edge)for(unsigned end=0;end<2;++end) {
          const float u=float(part+end)/8;const unsigned left=edge*4,right=left+2;
          const float px=q.xy[left]+u*(q.xy[right]-q.xy[left]);
          const float py=q.xy[left+1]+u*(q.xy[right+1]-q.xy[left+1]);
          min_x=std::min(min_x,px);max_x=std::max(max_x,px);min_y=std::min(min_y,py);max_y=std::max(max_y,py);
        }
        Hit(ctx,base,s.owner,a.x+(min_x+max_x)*.5f,a.y+(min_y+max_y)*.5f,
          std::max(1,int(std::ceil((max_x-min_x)*.5f))),std::max(1,int(std::ceil((max_y-min_y)*.5f))),damage,element,a.generation);
      }
    }
    else if(a.spell==Spell::Skull) {
      for(unsigned i=0;i<tick.count;++i){const auto& source=kSotnQuads[tick.first+i];if(source.role!=1)continue;
        const auto q=ActorQuad(a,tick,source,i);
        AreaHit(ctx,base,s.owner,a.x+std::min(q.xy[0],q.xy[2]),a.y+std::min(q.xy[1],q.xy[5]),
          a.x+std::max(q.xy[0],q.xy[2]),a.y+std::max(q.xy[1],q.xy[5]),damage,a.generation);}
    }
    else if(a.spell==Spell::Fire || a.spell==Spell::Dark) {
      for(unsigned i=0;i<tick.count;++i)QuadHit(ctx,base,s.owner,a,ActorQuad(a,tick,kSotnQuads[tick.first+i],i),damage,element);
    }
    else if(tick.hw && tick.hh)
      Hit(ctx,base,s.owner,x+tick.hx*a.dir,y+tick.hy,tick.hw,tick.hh,damage,element,a.generation);
    else if(a.spell==Spell::Medusa && tick.count) {
      // SotN's short-lived six-pixel damage child follows the laser HEAD.
      // Do not leave many independent colliders along the visual trail.
      Hit(ctx,base,s.owner,a.x+a.head_x,a.y+a.head_y,6,6,damage,element,a.generation);
    }
  }
  if(s.leech){const bool local=Local(base,s.owner);bool guarding=false;
    if(local){const auto equipment=Read(base,s.owner+0x9C8),input=Read(base,s.player+0x2C0);const auto held=input?Read(base,input):0;
      for(unsigned i=0;equipment&&i<2;++i)guarding|=Read(base,equipment+i*4)==kShields[11].item && (held&kSlotButton[i]);}
    else guarding=GuardingAlucardShield(base,s.owner,s.player);
    if(guarding){const auto stats=Read(base,s.player+88);if(!stats){s.leech=0;return;}
      ++s.leech_tick;
      if(local){  // MP is the caster's own; a remote copy only replays the contact attack
        if(!std::isfinite(Float(base,stats+8))){s.leech=0;return;}
        if(s.leech_tick%8==0)Float(base,stats+8,std::max(0.0f,Float(base,stats+8)-1));
        if(--s.leech==0||Float(base,stats+8)<=0){s.leech=0;return;}
      }else if(--s.leech==0)return;
      std::array<float,4> bounds{};
      if(s.leech_tick%kLeechHitFrames==0 && HeldShieldBounds(base,s,bounds) && (bounds=LeechArea(base,s,bounds),true))
        Hit(ctx,base,s.owner,(bounds[0]+bounds[2])*.5f,(bounds[1]+bounds[3])*.5f,
            int(std::ceil((bounds[2]-bounds[0])*.5f)),int(std::ceil((bounds[3]-bounds[1])*.5f)),
            MagicPower(ctx,base,s.owner,30),0,s.leech_generation);
    }else s.shield_bounds_valid=false;}
}

void FrameLocked(PPCContext& ctx, uint8_t* base, uint32_t owner, uint32_t player) {
  auto* s = Find(base, owner, player != 0);
  if (!s) return;
  for (auto& t : s->buff) if (t) --t;
  if (!player || !Alive(base, player)) { s->held = 0; s->knight=Knight{}; s->visual.active = false; s->actors={};s->leech=0;s->notices={};return; }
  if(Read(base,player)==kAlucardVtable)EnsureSounds(ctx,base);
  UpdateEffects(ctx,base,*s);
  UpdateKnight(ctx, base, owner, s->knight);
  if (Read(base,player)!=kAlucardVtable || Read(base, owner + 0x930) != 1) { s->held = 0; return; }  // local input only
  const auto input = Read(base, player + 0x2C0);  // vtable +0x43C: input block, +0 held buttons
  const auto held = input ? Read(base, input) : 0;
  const auto pressed = held & ~s->held;
  s->held = held;
  const auto equipment = Read(base, owner + 0x9C8);
  if (!equipment) return;
  const uint32_t items[2] = {Read(base, equipment), Read(base, equipment + 4)};
  for (unsigned shield = 0; shield < 2; ++shield) {
    const unsigned rod = 1 - shield;
    if (items[rod] != kRodItem || !(held & kSlotButton[shield]) || !(pressed & kSlotButton[rod])) continue;
    const auto* spell = SpellFor(items[shield]);
    if (!spell || !IsShield(ctx, base, items[shield])) continue;
    REXLOG_INFO("[shield rod] combo: shield on {}, rod pressed on {} (guard slot {})", shield ? "Y" : "X",
                rod ? "Y" : "X", int32_t(Read(base, player + 0x2F0)));
    Cast(ctx, base, owner, player, *s, *spell);
  }
}
void Frame(PPCContext& ctx, uint8_t* base, uint32_t owner) {
  const auto player = owner && (Read(base,owner+8)&2) ? Read(base,owner+0x924) : 0;
  std::lock_guard guard(lock);
  FrameLocked(ctx, base, owner, player);
  CountArt();
}

// The other hand holds a shield while `weapon` (global WEPN index) is the rod.
bool RodWithShield(PPCContext& ctx, uint8_t* base, const uint32_t items[2], uint32_t weapon) {
  if (weapon != kRodWeapon) return false;
  for (unsigned rod = 0; rod < 2; ++rod)
    if (items[rod] == kRodItem && IsShield(ctx, base, items[1 - rod])) return true;
  return false;
}
bool Equipment(uint8_t* base, uint32_t owner, uint32_t items[2]) {
  const auto equipment = owner ? Read(base, owner + 0x9C8) : 0;
  if (!equipment) return false;
  items[0] = Read(base, equipment); items[1] = Read(base, equipment + 4);
  return true;
}
float BuffBonus(uint8_t* base, uint32_t owner, Buff b) {
  std::lock_guard guard(lock);
  const auto* s = Find(base, owner, false);
  return s && s->buff[b] ? kBuffAmount : 0.0f;
}
uint32_t NameHash(uint32_t sprite) {  // 825BFF28: FNV-1 of the resource basename
  char name[16];
  std::snprintf(name, sizeof name, "P_ARSH%02X", sprite);
  uint32_t h = 0x811C9DC5u;
  for (const char* c = name; *c; ++c) { h *= 0x01000193u; h ^= uint8_t(*c); }
  return h;
}
}  // namespace

float DefenseBonus(uint8_t* base, uint32_t owner) { return BuffBonus(base, owner, kDef); }

// Invulnerability and resistance are checked before HoD commits incoming damage.
bool Incoming(PPCContext& ctx,uint8_t* base,uint32_t owner) {
  if(!(ctx.f1.f64>=0))return false;
  std::lock_guard guard(lock);const auto* s=Find(base,owner,false);if(!s)return false;
  if(s->invulnerable)return true;
  const auto element=ctx.r7.u32;
  if((s->buff[kFireRes] && (element&0x100)) || (s->buff[kThunderRes] && (element&0x400)) ||
     (s->buff[kDarkRes] && (element&0x1000)))ctx.f1.f64*=.5;
  return false;
}
// Recovery is called only after 82246DF0 has actually reduced enemy HP.
// Native hurt requests often identify their monster directly at +10, with
// +14 zero; 0x10 geometry is not the ordinary monster body (0x40000009).
static void Recover(PPCContext& ctx,uint8_t* base,uint32_t hit,uint32_t target) {
  if(!hit || Read(base,hit)!=hit+kColliderTable || Read(base,hit+0x190)!=kHitTag)return;
  const auto owner=EntityOf(base,Read(base,hit+0xA4));if(!owner)return;
  std::lock_guard guard(lock);auto* s=Find(base,owner,false);
  if(!s || !s->leech || s->leech_generation!=Read(base,hit+0x184) || s->leech_contact || !Alive(base,s->player))return;
  if(!target || Read(base,hit+0x198)==target)return;
  Write(base,hit+0x198,target);s->leech_contact=kLeechHitFrames;s->invulnerable=96;
  // Use the same explicit, clamped recovery and native green-number path as
  // DSS recovery. Show the source's 8 even at full HP, so contact is visible.
  const auto stats=Read(base,s->player+88);
  const float hp=Float(base,stats+4),maximum=Float(base,stats+16)+Float(base,stats+28);
  if(std::isfinite(hp)&&std::isfinite(maximum)&&maximum>0) {
    Float(base,stats+4,std::min(maximum,hp+8));
    PPCContext popup=ctx;popup.r3.u64=owner;popup.r4.u64=0;popup.r5.s64=-8;
    rex::runtime::ResolveIndirectFunction(0x82454000)(popup,base);
  }
  // HoD hearts replenish MP; preserve that game's native resource convention.
  PPCContext heal=ctx;heal.r3.u64=owner;heal.f1.f64=1;heal.r5.u64=0;heal.r6.u64=1;
  rex::runtime::ResolveIndirectFunction(0x8244E3C8)(heal,base);
  static unsigned announced=0;if(announced++<8)
    REXLOG_INFO("[shield rod] Alucard enemy contact {:08X}: 8 HP, 1 MP, 96 protection ticks",target);
}

// Draw a world-positioned native shield frame using its own OPD pivot, not
// Alucard's inherited body pivot. All sprite state is changed on a scratch copy.
static uint32_t DrawFrame(const PPCContext& original, uint8_t* base, uint32_t owner, uint32_t body,
                      uint32_t sprite_id, uint32_t frame, float world_x, float world_y, float scale, int dir, uint8_t blend=0, float opacity=1, float scale_y=-1, float rotation=0) {
  if (!owner || !body || !(scale > 0) || !std::isfinite(scale) || !std::isfinite(scale_y) || scale_y==0) return 0;
  const float body_x=Float(base,body+0x28),body_y=Float(base,body+0x2C);
  if(!std::isfinite(body_x)||!std::isfinite(body_y)||std::abs(body_x)<1e-6f||std::abs(body_y)<1e-6f)return 0;
  const ShieldArt* art = nullptr;
  for (const auto& a : kSotnArt) if (a.sprite == sprite_id && a.frame == frame) { art = &a; break; }
  if (!art) return 0;  // only frames verified against the user's assets
  if (!scratch) scratch = AlignedScratch(2 * kSpriteBytes + 64);
  if (!scratch) return 0;
  const auto lookup = scratch, sprite = scratch + kSpriteBytes;
  std::memcpy(base + lookup, base + body, kSpriteBytes);
  base[lookup] = 1;
  Write(base, lookup + 8, NameHash(sprite_id)); Write(base, lookup + 12, 0); Write(base, lookup + 0xA0, 0);
  PPCContext query = original; query.r3.u64 = lookup;
  rex::runtime::ResolveIndirectFunction(0x823D2520)(query, base);
  const auto resource = Read(base, lookup + 12);
  if (!resource) return 0;  // equipping/loading the resource can lag the first frame
  std::memcpy(base + sprite, base + body, kSpriteBytes);
  Write(base, sprite + 12, resource);
  base[sprite + 0x54] = base[sprite + 0x55] = 0;
  Write(base, sprite + 0xA0, 0); base[sprite + 0xA4] = 1;
  base[sprite + 0x1C] = dir < 0;
  // Renderer subtracts frame.head[33/35] and adds sprite+116/118. Compensate
  // for the OPD pivot so visible parts and the spell's hit geometry agree.
  rex::memory::store_and_swap<uint16_t>(base + sprite + 116, uint16_t(art->pivot_x - art->origin_x));
  rex::memory::store_and_swap<uint16_t>(base + sprite + 118, uint16_t(art->pivot_y - art->origin_y));
  Float(base, sprite + 0x28, std::abs(Float(base, body + 0x28)) * scale);
  Float(base, sprite + 0x2C, std::abs(Float(base, body + 0x2C)) * (scale_y<0?scale:scale_y));
  Float(base,sprite+80,opacity);base[sprite+140]=blend;
  Float(base,sprite+48,0);Float(base,sprite+52,0);Float(base,sprite+56,rotation);
  PPCContext draw = original;
  draw.r3.u64 = sprite; draw.r4.u64 = frame; draw.r7.u64 = 0;
  draw.r8.u64=0xffffffffu;draw.r9.u64=0; // independent tint and no caller's output-pointer side effect
  // 824476B8 -> 823D31C8 passes owner world X/Y, then the clip step adds
  // pose offsets before 823D2648. Afterimages supply historical positions.
  // Neither belongs to a detached spell: native 823D69E0/material setup
  // applies the camera to these independent world coordinates itself.
  if(!std::isfinite(world_x)||!std::isfinite(world_y))return 0;
  const double x = std::round(double(world_x));
  const double y = std::round(double(world_y));
  if (x < INT32_MIN || x > INT32_MAX || y < INT32_MIN || y > INT32_MAX) return 0;
  draw.r5.u64 = uint32_t(int32_t(x)); draw.r6.u64 = uint32_t(int32_t(y));
  __imp__sub_823D2648(draw, base);
  return draw.r3.u32;
}
// Reuse native material/texture/camera setup, then replace the single patch's
// vertices with the original PSX quad. The queued packet is unique per draw.
static void DrawQuad(const PPCContext& ctx,uint8_t* base,uint32_t owner,uint32_t body,
                     uint32_t sprite,const SotnQuad& q,float x,float y) {
  const uint8_t blend=(q.mode&1)?1:0; // 3 DISABLES blending; 0 is native alpha, 1 additive
  const auto packet=DrawFrame(ctx,base,owner,body,sprite,q.frame,x,y,1,1,blend);
  if(!packet)return;
  const auto vertices=Read(base,packet+424);if(!vertices)return;
  float u0=Float(base,vertices+32),u1=u0,v0=Float(base,vertices+36),v1=v0;
  for(unsigned i=1;i<4;++i){const auto at=vertices+i*40;u0=std::min(u0,Float(base,at+32));u1=std::max(u1,Float(base,at+32));v0=std::min(v0,Float(base,at+36));v1=std::max(v1,Float(base,at+36));}
  if(q.width){const float inset=(u1-u0)/(2*q.width);u0+=inset;u1-=inset;}
  if(q.height){const float inset=(v1-v0)/(2*q.height);v0+=inset;v1-=inset;}
  constexpr unsigned corners[4]={0,2,3,1};
  for(unsigned i=0;i<4;++i){const auto at=vertices+i*40,k=corners[i];
    Float(base,at,float(q.xy[k*2]));Float(base,at+4,float(-q.xy[k*2+1]));
    Write(base,at+28,q.color[k]);Float(base,at+32,u0+(u1-u0)*q.uv[k*2]/65535.0f);
    Float(base,at+36,v0+(v1-v0)*q.uv[k*2+1]/65535.0f);
  }
}
static void DrawTick(const PPCContext& ctx,uint8_t* base,uint32_t owner,uint32_t body,
                     uint32_t sprite,const SotnTick& tick,float x,float y,int dir,const EffectActor* actor=nullptr) {
  // Preserve the original primitive priority ordering, including silhouette layers.
  std::array<uint16_t,128> order{};const unsigned count=std::min(unsigned(tick.count),unsigned(order.size()));
  for(unsigned i=0;i<count;++i)order[i]=uint16_t(i);
  std::stable_sort(order.begin(),order.begin()+count,[&](unsigned a,unsigned b){return kSotnQuads[tick.first+a].priority<kSotnQuads[tick.first+b].priority;});
  for(unsigned i=0;i<count;++i){const auto& q=kSotnQuads[tick.first+order[i]];DrawQuad(ctx,base,owner,body,sprite,actor?ActorQuad(*actor,tick,q,order[i]):q,x,y);}
  if(tick.visible)DrawFrame(ctx,base,owner,body,sprite,tick.frame,x+tick.x/65536.0f,
    y+tick.y/65536.0f,tick.scale/256.0f,dir,0,1,tick.scale_y/256.0f,tick.rotation*360.0f/4096);
}
void Draw(const PPCContext& original, uint8_t* base, uint32_t body) {
  if(!body || !active_art.load(std::memory_order_relaxed))return;
  std::lock_guard guard(lock);
  for(auto& s:states) {
    if(s.owner && !Current(base,s)){s=State{};continue;}
    if(!s.owner || Read(base,s.owner+0x2C)!=body)continue;
    const auto& k=s.knight;
    for(const auto& trail:k.trails)if(trail.age<24)
      DrawFrame(original,base,s.owner,body,k.sprite,trail.frame,trail.x,trail.y,1,trail.dir,0,(128-trail.age*2)/256.0f);
    if(k.phase!=kIdle) {
      const uint32_t frame=KnightFrame(k);
      DrawFrame(original,base,s.owner,body,k.sprite,frame,k.x,k.y,1,k.dir);
    }
    const auto& v=s.visual;
    if(v.active){const auto& clip=Clip(v.spell,v.dir);const auto tick=std::min(unsigned(std::max(0,v.t-1)),unsigned(clip.count-1));
      DrawTick(original,base,s.owner,body,v.sprite,kSotnTicks[clip.first+tick],v.x,v.y,v.dir);}
    for(const auto& a:s.actors)if(a.active && a.age>=0 && a.age<a.life)
      DrawTick(original,base,s.owner,body,a.sprite,kSotnTicks[kSotnChildren[a.clip].first+a.age],a.x,a.y,a.dir,&a);
    for(const auto& n:s.notices)if(n.life){
      DrawFrame(original,base,s.owner,body,n.sprite,n.frame,n.x,n.y-72,1,1,0,std::min(1.0f,n.life/20.0f));}
  }
  CountArt();
}

// Attack phase of a tagged rectangle (from Nathan's 824827F0 override):
// Register in preparation and query only in the later +0x24 collision phase.
void PrepareHit(PPCContext& ctx, uint8_t* base, uint32_t hit) {
  if (!hit) return;
  // The collider stores a native generation handle at +0xA4. Its raw owner
  // pointer at +0x194 alone cannot establish that the owner is still alive.
  const auto owner = EntityOf(base, Read(base, hit + 0xA4));
  {
    std::lock_guard guard(lock);
    const auto* s = owner ? Find(base, owner, false) : nullptr;
    if (!s || owner != Read(base, hit + 0x194) || !Alive(base, s->player) ||
        !ActiveGeneration(*s,Read(base,hit+0x184))) {
      base[hit + 0x17] = 1;
      return;
    }
  }
  // Refresh moving shield attacks at preparation, after the native guard has
  // supplied its current pose. Do not allocate entities during registration.
  if(base[hit+0x9F]==0xFE){
    std::lock_guard guard(lock);const auto* s=Find(base,owner,false);std::array<float,4> bounds{};
    if(!s||!HeldShieldBounds(base,*s,bounds)){base[hit+0x17]=1;return;}
    if(!(Read(base,hit+0x18C)&1))SetShieldHitBounds(base,hit,LeechArea(base,*s,bounds));
  }
  const auto status=Read(base,hit+0x18C);
  if(status&2){base[hit+0x17]=1;return;}
  float dt=float(ctx.f1.f64);if(!(dt>0&&dt<=.1f))dt=1.0f/60;
  const float age=Float(base,hit+0x188)+dt;Float(base,hit+0x188,age);
  if(age>.12f || !InStage(base,Float(base,hit+0x2C),Float(base,hit+0x30))){base[hit+0x17]=1;return;}
  if(status&1)return;  // submitted when created (Hit)
  PPCContext area=ctx;area.r3.u64=hit;area.r4.u64=hit+0x1A0;
  __imp__sub_82484180(area,base);
  Write(base,hit+0x18C,1);
}

void ResolveHit(PPCContext& ctx, uint8_t* base, uint32_t hit) {
  if (!hit) return;
  // The collider stores a native generation handle at +0xA4. Its raw owner
  // pointer at +0x194 alone cannot establish that the owner is still alive.
  const auto owner = EntityOf(base, Read(base, hit + 0xA4));
  {
    std::lock_guard guard(lock);
    const auto* s = owner ? Find(base, owner, false) : nullptr;
    if (!s || owner != Read(base, hit + 0x194) || !Alive(base, s->player) ||
        !ActiveGeneration(*s,Read(base,hit+0x184))) {
      base[hit + 0x17] = 1;
      return;
    }
  }
  const auto status=Read(base,hit+0x18C);
  if(!(status&1)||(status&2))return;
  Write(base,hit+0x18C,status|2);
  const auto request = Read(base, hit + 0xAC);
  if (request == 0xFFFFFFFFu) return;
  uint32_t mask = 0x40000000u;
  const auto flags = Read(base, hit + 0xB0);
  if (flags & 0x80000000u) {
    const auto game = Call(ctx, base, 0x82223348, 0);
    mask = game && Read(base, game + 0xFB8) == 2 ? 15 : 12;
  } else if (flags & 0x40000000u) mask = 3;
  std::memset(base + hit + 0x1C0, 0, 16);
  PPCContext resolve = ctx;
  resolve.r3.u64 = hit + 0x1C0; resolve.r4.u64 = request; resolve.r5.u64 = mask;
  rex::runtime::ResolveIndirectFunction(0x823C4E00)(resolve, base);
  // Did it touch an enemy? (0x40000000: report only, 0x20 neutral hurt volumes.)
  std::memset(base + hit + 0x1D0, 0, 16);
  PPCContext probe = ctx;
  probe.r3.u64 = hit + 0x1D0; probe.r4.u64 = request; probe.r5.u64 = 0x40000000u | 0x20u | 2u;
  rex::runtime::ResolveIndirectFunction(0x823C4E00)(probe, base);
  const auto struck = Read(base, hit + 0x1D0);
  if (probe.r3.u32 && struck && hod::IsHurtRecord(Read(base, struck + 4))) {
    std::lock_guard guard(lock);
    if (auto* s = Find(base, owner, false); s && s->knight.generation == Read(base, hit + 0x184) && s->knight.phase == kWalk) {
      s->knight.touched = true;
      REXLOG_INFO("[shield rod] Axe Knight reached an enemy");
    }
  }
}

// Status/equipment screens (Nathan's 8245D9A0 override calls this for every
// character): per-hand ATK at out+0x10 (X) and +0x14 (Y), DEF at +0x18.
// Character 0 = the live player in a stage (8245D9A0 then reads the owner);
// any other value is a character's saved build. Spell buffs can be on any
// character (allies receive them), so they apply to every live summary; the
// Shield Rod's own +ATK applies to Alucard only.
void Summary(PPCContext& ctx, uint8_t* base, uint32_t character, uint32_t out) {
  if (!out || (character != 0 && character != 2)) return;
  const auto owner = EntityOf(base, Call(ctx, base, 0x8245CCE8, 0));
  const bool player = owner && (Read(base, owner + 8) & 2);
  uint32_t items[2]{};
  const bool live = player && AlucardPlayer(base, owner);
  const bool equipped = live && Equipment(base, owner, items);
  if (!live && character == 2) {
    const auto game = Call(ctx, base, 0x82223348, 0);  // save model: game+0x1018, 15 slots a character
    if (!game) return;
    const auto save = game + 0x1018;
    for (unsigned slot = 0; slot < 2; ++slot) items[slot] = Read(base, save + (2 * 15 + slot) * 4 - 20);
  }
  if (live || character == 2)
    for (unsigned rod = 0; rod < 2; ++rod)
      if(!live || equipped)
      if (RodWithShield(ctx, base, items, items[rod] - kWeaponItems))
        Float(base, out + 0x10 + 4 * rod, Float(base, out + 0x10 + 4 * rod) + kRodAttackWithShield);
  if (!live && !(player && character == 0)) return;
  if (const float atk = BuffBonus(base, owner, kAtk))
    for (unsigned hand = 0; hand < 2; ++hand) Float(base, out + 0x10 + 4 * hand, Float(base, out + 0x10 + 4 * hand) + atk);
  if (const float intelligence=BuffBonus(base,owner,kInt))Float(base,out+0x20,Float(base,out+0x20)+intelligence);
  if (const float def = BuffBonus(base, owner, kDef)) Float(base, out + 0x18, Float(base, out + 0x18) + def);
  // Summary resistance entries start at +30: slash/strike/pierce, fire,
  // ice, thunder, holy, dark ... They store percent resistance, not damage.
  std::lock_guard guard(lock);const auto* state=Find(base,owner,false);if(!state)return;
  for(const auto pair:{std::pair{ kFireRes,0x3Cu },std::pair{ kThunderRes,0x44u },std::pair{ kDarkRes,0x4Cu }})
    if(state->buff[pair.first]){const float old=Float(base,out+pair.second);
      if(std::isfinite(old))Float(base,out+pair.second,100-(100-old)*.5f);}
}
}  // namespace harmony::shield_rod

using namespace harmony::shield_rod;

// Report the actual native bank creation result, not just the queued request.
REX_EXTERN(sub_825CEFA0) {
  HOD_PASS_IF_OFF(kShieldRod, __imp__sub_825CEFA0);
  const bool ours=ctx.r4.u32&&ctx.r5.u32&&OriginalSoundBankPath(base,ctx.r3.u32);
  __imp__sub_825CEFA0(ctx,base);
  if(ours)REXLOG_INFO("[shield rod] original XSB bank creation result {} (-1 = failed)",ctx.r3.s32);
}
REX_EXTERN(sub_825CED10) {
  HOD_PASS_IF_OFF(kShieldRod, __imp__sub_825CED10);
  const bool ours=ctx.r4.u32&&ctx.r5.u32&&OriginalSoundBankPath(base,ctx.r3.u32);
  __imp__sub_825CED10(ctx,base);
  if(ours)REXLOG_INFO("[shield rod] original XWB bank creation result {} (-1 = failed)",ctx.r3.s32);
}

// Guard start (owner update, every frame): native guard, then the combo.
REX_EXTERN(sub_82450658) {
  HOD_PASS_IF_OFF(kShieldRod, __imp__sub_82450658);
  const auto owner = ctx.r3.u32;
  __imp__sub_82450658(ctx, base);
  Frame(ctx, base, owner);
}

// Physical attack of one weapon (owner, global weapon index) -> f1:
// ATK + (ATK/64 + 0.25) * STR + bonuses. SotN adds +5 to the Shield Rod with a
// shield in the other hand, and +20 while an ATK buff runs, after STR.
REX_EXTERN(sub_824519C8) {
  HOD_PASS_IF_OFF(kShieldRod, __imp__sub_824519C8);
  const auto owner = ctx.r3.u32, weapon = ctx.r4.u32;
  uint32_t items[2]{};
  PPCContext probe = ctx;
  const bool with_shield = AlucardPlayer(base, owner) && Equipment(base, owner, items) &&
                           RodWithShield(probe, base, items, weapon);
  __imp__sub_824519C8(ctx, base);
  double bonus = BuffBonus(base, owner, kAtk);
  if (with_shield) bonus += kRodAttackWithShield;
  if (bonus) ctx.f1.f64 += bonus;
}

// INT total (owner) -> f1. Shaman Shield: +20 INT while its buff runs.
REX_EXTERN(sub_824526D0) {
  HOD_PASS_IF_OFF(kShieldRod, __imp__sub_824526D0);
  const auto owner = ctx.r3.u32;
  __imp__sub_824526D0(ctx, base);
  if (const float bonus = BuffBonus(base, owner, kInt)) ctx.f1.f64 += bonus;
}

// ---- Handlers in the shared chains (core/runtime/hod_hooks.h) -------------
namespace {

// 8244CA98 player spawn event (see Announce): a remote copy replays a Shield
// Rod cast; every event, the marker itself included, continues natively.
void SpawnEvent(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  if (owner && ctx.r5.u32 == kSyncKind && ctx.r6.s32 == int32_t(kSyncSub) &&
      (ctx.r9.u32 & 0xFFFF) == kSyncTagA && (ctx.r10.u32 & 0xFFFF) == kSyncTagB &&
      (Read(base, owner + 8) & 2) && !Local(base, owner))
    Replay(ctx, base, owner, ctx.r4.u32 & 0xFFFF);
  next(ctx, base);
}

// 824823A0 collider prepare: register a spell's area in this phase; the attack
// phase (+0x24) later resolves the completed lists.
void ColliderPrepare(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto hit = ctx.r3.u32;
  if (hod::AttackCollider(base, hit) && hod::ColliderTag(base, hit) == kHitTag) { PrepareHit(ctx, base, hit); return; }
  next(ctx, base);
}

// 824827F0 collider attack phase of a spell's area.
void ColliderAttack(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto hit = ctx.r3.u32;
  if (hod::AttackCollider(base, hit) && hod::ColliderTag(base, hit) == kHitTag) { ResolveHit(ctx, base, hit); return; }
  next(ctx, base);
}

// 823C4C40, outside the collision lock: the native guard rectangle, observed
// after the game registered it. Only the native guard helper supplies this
// rectangle; never read an arbitrary shape or an enemy collider as a shield.
void GuardShape(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto source=ctx.r6.u32,owner=ctx.r7.u32,shape=ctx.r3.u32,flags=ctx.r4.u32;
  const bool shield=ctx.lr==0x8244B5B4 && flags==0x80000010u && source==owner &&
                    RequestAddress(shape) && Read(base,shape)==0x821E10C0;
  std::array<float,4> bounds{};
  if(shield)for(unsigned i=0;i<4;++i)bounds[i]=Float(base,shape+8+i*4);
  next(ctx, base);
  if(shield && ctx.r3.u32!=0xFFFFFFFFu)ObserveGuard(base,owner,bounds[0],bounds[1],bounds[2],bounds[3]);
}

// Every registered shape, under the collision lock: enemy bodies 1/4/10 as
// before, plus 8, a sleeping enemy's only hurt box (run 219).
void TargetShape(const PPCContext& original, uint8_t* base, uint32_t handle, uint32_t result) {
  const auto shape = original.r3.u32, flags = original.r4.u32;
  if (result == 0xFFFFFFFFu || !(flags & 0x1D) || (flags & 2)) return;
  PPCContext copy = original;
  CaptureTarget(copy, base, handle, shape);
}

// 82246DF0 enemy HP transaction: observe a real HP loss from a spell's hit,
// beyond overlap and native repeat-hit rejection (native defenses, per-owner
// hit history, boss rules and death all stay native).
void EnemyHp(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto enemy=ctx.r3.u32,pair=ctx.r5.u32;
  uint32_t hit=0,target=0;float before=0;
  if(enemy && pair && (ctx.r4.u32&1) && (Read(base,enemy+8)&4) &&
     EntityOf(base,Read(base,enemy+4))==enemy) {
    const auto attack=Read(base,pair);
    if(RequestAddress(attack)) {
      const auto candidate=EntityOf(base,Read(base,attack+0x10));
      if(hod::AttackCollider(base,candidate) && hod::ColliderTag(base,candidate)==kHitTag)
        {hit=candidate;target=Read(base,enemy+4);before=Float(base,enemy+152);}
    }
  }
  next(ctx, base);
  if(hit && EntityOf(base,target)==enemy && std::isfinite(before) && Float(base,enemy+152)<before)
    Recover(ctx,base,hit,target);
}

// 824476B8 owner draw: detached spell art once per owner, after every native
// body/afterimage draw (rendering from 823D2648 repeated it for afterimages).
void OwnerDraw(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  next(ctx, base);
  if (owner) Draw(ctx, base, Read(base, owner + 0x2C));
}

// 82451AA8 physical DEF: Leather Shield spell, +20 DEF.
void PhysicalDefense(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto owner = ctx.r3.u32;
  next(ctx, base);
  ctx.f1.f64 += DefenseBonus(base, owner);
}

// 8245D9A0 status summary: rod ATK and buff values on the menus.
void StatusSummary(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  const auto character = ctx.r3.u32, out = ctx.r4.u32;
  next(ctx, base);
  Summary(ctx, base, character, out);
}

// 8244BF10 incoming damage: Alucard Shield's invulnerability window cancels
// the hit; Herald/Goddess resistances halve it.
void IncomingDamage(PPCContext& ctx, uint8_t* base, const hod::Next& next) {
  if (Incoming(ctx, base, ctx.r3.u32)) { ctx.r3.s64 = -1; return; }
  next(ctx, base);
}

}  // namespace

// Orders: see the tables in docs/HOOKS.md (lower runs first / outermost).
HOD_HOOK(kSpawnEvent, kShieldRod, 30, SpawnEvent);
HOD_HOOK(kColliderPrepare, kShieldRod, 20, ColliderPrepare);
HOD_HOOK(kColliderAttack, kShieldRod, 10, ColliderAttack);
HOD_HOOK(kShapeRegister, kShieldRod, 10, GuardShape);
HOD_SHAPE_OBSERVER(kShieldRod, 10, TargetShape);
HOD_HOOK(kEnemyHp, kShieldRod, 10, EnemyHp);
HOD_HOOK(kOwnerDraw, kShieldRod, 50, OwnerDraw);
HOD_HOOK(kPhysicalDefense, kShieldRod, 20, PhysicalDefense);
HOD_HOOK(kStatusSummary, kShieldRod, 30, StatusSummary);
HOD_HOOK(kIncomingDamage, kShieldRod, 10, IncomingDamage);
