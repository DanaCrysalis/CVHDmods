#pragma once
#include <cstdint>
#include <cmath>
#include "nathan_dss_assets.h"
#include "nathan_salamander_assets.h"
#include "nathan_all_dss_assets.h"
#include "nathan_dss_balance.h"

namespace harmony::nathan {
constexpr uint32_t kVtable = 0x836C28E8;
constexpr uint32_t kMercury = 0x6CD, kVenus = 0x6D9, kSalamander = 0x6CE, kWhip = 0xC4;
constexpr uint32_t kActionMercury=0,kActionVenus=1,kActionUranus=2,kActionJupiter=3,kActionPluto=4,kActionUnavailable=5,kActionDiana=6,kActionApollo=7,kActionSaturn=8,kActionMars=9,kActionNeptune=10;
// Internal action bit 8 (Personal Skill), not the raw XInput RB bit 0x200.
// 824496AC maps bit 8 -> control binding 2; default binding 5 -> physical RB.
constexpr uint32_t kRb = 0x100;
constexpr uint32_t kOriginalSize = 844, kSize = 8192;
constexpr uint32_t kFireDamage = 0x100; // WEPN fire bit 8 -> collision bit 0x100
constexpr float kCotmHz=59.72750057f, kPulseSeconds=128.0f/kCotmHz, kFadeSeconds=32.0f/kCotmHz;
constexpr float kMpCost=kMercuryMp[0], kStrengthMultiplier = 1.05f; // Salamander compatibility
// CotM Mercury row 0x080E47E8: ten 12-byte records, MP at +6, STR% at +8.
constexpr float kMercuryStrength[10]={1.05f,.71f,1.10f,1.0f,1.10f,.89f,.87f,1.0f,1.22f,1.41f};
// Native HoD collision attributes: fire, ice, lightning, holy, dark, poison,
// curse and stone. Plant/earth/wind retain the physical whip damage types.
constexpr uint32_t kMercuryElements[10]={0x100,0x200,0,0,0x8000,0x2000,0,0x400,0x800,0x1000};
// CotM Venus row 080E4860: 16.16 MP/frame at +0, STR percent at +8.
// Raw ROM drain rows are scaled by the shared HoD balance policy at use.
constexpr uint32_t kVenusDrain[10]={4368,4368,4368,17472,2184,2184,4368,17472,8736,8736};
constexpr unsigned kVenusStrength[10]={112,100,100,100,100,100,100,100,71,141};
constexpr float kSummonSeconds=448.0f/kCotmHz;
// CotM per-use MP, rows 0x080E49C8 (Diana), 0x080E4A40 (Apollo), 0x080E4B30 (Saturn).
// CotM Jupiter row 0x080E48D8: 16.16 MP/frame.
constexpr uint32_t kJupiterDrain[10]={4368,4368,17472,4368,8736,4368,4368,4368,8736,8736};
constexpr uint32_t kPlutoDrain[10]={4368,4368,4368,8736,8736,0,4368,4368,21840,5460};
constexpr float kMarsPower[10]={1.10f,.71f,1.12f,1,1.22f,.89f,1.41f,1,1.73f,2};
inline bool TimedAction(uint32_t action) { return action==kActionVenus || action==kActionJupiter || action==kActionPluto || action==kActionNeptune; }
inline bool VenusAvailable(uint32_t attribute) { return attribute<10 && kVenusDrain[attribute]!=0; }

// Appended to Nathan's own allocation; no save fields or shared globals.
struct DssState {
  uint32_t enabled = 0;
  uint32_t previous_rb = 0;
  uint32_t motion_table = 0;
  uint32_t paid_swing = 0;
  float pulse_time = 0;
  float cast_remaining = 0;
  float fade_remaining = 0;
  uint32_t drawn_frame=0, canonical_frame=0, draw_count=0;

  uint32_t attribute=0;
  float hold_time=0;
  uint32_t action=kActionMercury;
  bool Direct() const {return action==kActionApollo || (action==kActionPluto && attribute==0);}
  float Cost() const { return action==kActionMars ? kMarsMp[attribute<10?attribute:0] : action==kActionUranus ? kUranusCost[attribute<10?attribute:0] : action==kActionMercury ? kMercuryMp[attribute<10?attribute:0] : action==kActionDiana ? kDianaMp[attribute<10?attribute:0] : action==kActionApollo ? kApolloMp[attribute<10?attribute:0] : action==kActionSaturn ? kSaturnMp[attribute<10?attribute:0] : 1.0f; }
  float Strength() const { return action!=kActionMercury && action!=kActionVenus ? 1.0f : action==kActionVenus ? kVenusStrength[attribute<10?attribute:0]/100.0f : kMercuryStrength[attribute<10?attribute:0]; }
  float Defense() const { return attribute==1 ? 1.25f : attribute==8 ? 2.0f : attribute==9 ? .5f : 1.0f; }
  float Drain() const { const auto rate=attribute>=10 ? 0 : action==kActionVenus ? kVenusDrain[attribute] : action==kActionJupiter ? kJupiterDrain[attribute] : action==kActionPluto ? kPlutoDrain[attribute] : action==kActionNeptune ? 3276u : 0; return rate/65536.0f*kCotmHz*kDssUpkeepScale; }
  uint32_t Element() const { return kMercuryElements[attribute<10?attribute:0]; }
  void Select(uint32_t next,uint32_t next_action=kActionMercury) {
    if (next!=attribute || next_action!=action) Disable();
    attribute=next<10?next:10;
    action=next_action;
  }
  void Disable(bool flash=true) {
    if (enabled && flash) fade_remaining=kFadeSeconds;
    enabled=paid_swing=0;cast_remaining=0;hold_time=0;
  }
  unsigned Level() const {
    if (action==kActionUranus) return 0;
    if (fade_remaining>0) return unsigned(std::ceil(fade_remaining/kFadeSeconds*kWhiteLevels));
    if (!enabled || cast_remaining>0) return 0;
    const float phase=std::fmod(pulse_time,kPulseSeconds)/kPulseSeconds;
    return unsigned(std::round((phase<0.5f ? phase*2 : (1-phase)*2)*kGoldLevels));
  }
  uint32_t BodyFrame(uint32_t frame) const { return frame; }
  unsigned PaletteOffset(uint32_t frame) const {
    const auto level=Level();
    return ((frame<kBaseFrames && kBodyTintable[frame]) || SalamanderBody(frame) || AllDssBody(frame)) && level
      ? (fade_remaining>0 ? kWhitePalette : kGoldPalette)+level-1 : 0;
  }

  void Frame(bool rb, bool paired, bool alive, float mp, bool attacking, float dt=1.0f/60) {
    if (!(dt>0 && dt<=0.1f)) dt=1.0f/60;
    cast_remaining=std::fmax(0.0f,cast_remaining-dt);
    fade_remaining=std::fmax(0.0f,fade_remaining-dt);
    if (enabled && cast_remaining<=0) pulse_time+=dt;
    const bool edge = rb && !previous_rb;
    previous_rb = rb;
    if (!paired || !alive) { Disable(alive); if (!alive) fade_remaining=0; return; }
    if(Direct()) {if(enabled && cast_remaining<=0)Disable(false);return;}
    if (action==kActionUranus) {
      if (enabled) {
        pulse_time+=dt;
        if (cast_remaining<=0) Disable(false);
      } else if (edge && !attacking && mp>=Cost()) {
        enabled=1;pulse_time=0;cast_remaining=kSummonSeconds;fade_remaining=0;
      }
      return;
    }
    if (edge) {
      if (enabled) Disable();
      else if (mp>=Cost()) {
        enabled=1;pulse_time=0;cast_remaining=kCastSeconds;fade_remaining=0;
      }
    }
    if (!attacking) {
      paid_swing = 0;
      if (mp < (TimedAction(action) ? 0.000001f : Cost())) Disable();
    }
  }
  void DrainMana(float& mp,float dt) {
    if (!enabled || !TimedAction(action) || Direct()) return;
    if (!(dt>0 && dt<=.1f)) dt=1.0f/60;
    mp=std::fmax(0.0f,mp-Drain()*dt);
    if (mp<=0) Disable();
  }
  bool Swing(bool paired, bool alive, float& mp) {
    paid_swing = 0;
    if (action!=kActionMercury && action!=kActionDiana && action!=kActionMars) return false; // Timed actions never charge per swing.
    if (!enabled) return false;
    if (!paired || !alive || mp < Cost()) { Disable(); return false; }
    // Thunderbird is paid by the spinning discharge, not the entry whip.
    if (!(action==kActionDiana && attribute==7)) mp -= Cost();
    paid_swing = 1;hold_time=0;
    return true;
  }
  bool Fire() const { return action==kActionMercury && enabled && paid_swing; }
};
static_assert(sizeof(DssState) == 52);
}
