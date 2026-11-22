// hod-mods hook hub registry (see hod_hooks.h). No guest symbols here: the
// overrides and the game's own functions are wired in hod_overrides.cpp, so
// a test harness can link this file with stand-ins.
#include "hod_hooks.h"
#include <rex/ppc/context.h>
#include <algorithm>
#include <array>
#include <mutex>
#include <string>
#include <vector>
#ifndef HOD_VERIFY_HARNESS
#include <rex/logging.h>
#endif

namespace hod {
namespace {

struct Entry {
  Mod mod;
  int order;
  unsigned sequence;  // registration order breaks ties, so equal orders stay stable
  Handler handler;
  const char* name;
};
struct Observer {
  Mod mod;
  int order;
  unsigned sequence;
  ShapeObserver observer;
  const char* name;
};

constexpr unsigned kHooks = unsigned(Hook::kCount);

struct HookInfo {
  uint32_t address;
  const char* name;
};
constexpr std::array<HookInfo, kHooks> kInfo{{
    {0x8244CA98, "player spawn event"},
    {0x824823A0, "collider prepare"},
    {0x824827F0, "collider attack"},
    {0x823C4C40, "collision shape registration"},
    {0x82246DF0, "enemy HP transaction"},
    {0x8244FFF8, "player update"},
    {0x82487EF8, "skill factory"},
    {0x8248A690, "skill preload"},
    {0x824476B8, "owner draw"},
    {0x82451AA8, "physical DEF"},
    {0x8245D9A0, "status summary"},
    {0x8244BF10, "incoming damage"},
    {0x82452658, "attack value"},
}};

std::array<std::vector<Entry>, kHooks>& Chains() {
  static std::array<std::vector<Entry>, kHooks> chains;
  return chains;
}
std::array<Original, kHooks>& Originals() {
  static std::array<Original, kHooks> originals{};
  return originals;
}
std::vector<Observer>& Observers() {
  static std::vector<Observer> observers;
  return observers;
}
unsigned NextSequence() {
  static unsigned sequence = 0;
  return sequence++;
}

template <class T>
bool Earlier(const T& a, const T& b) {
  return a.order != b.order ? a.order < b.order : a.sequence < b.sequence;
}

void LogChainsOnce() {
#ifndef HOD_VERIFY_HARNESS
  static std::once_flag once;
  std::call_once(once, [] {
    for (unsigned h = 0; h < kHooks; ++h) {
      const auto& chain = Chains()[h];
      if (chain.empty()) continue;
      std::string line;
      for (const auto& e : chain) {
        if (!line.empty()) line += " > ";
        line += std::string(ModId(e.mod)) + ":" + e.name + "(" + std::to_string(e.order) + ")" +
                (Enabled(e.mod) ? "" : "[off]");
      }
      REXLOG_INFO("[hod] {:08X} {}: {} > game", kInfo[h].address, kInfo[h].name, line);
    }
    std::string observers;
    for (const auto& o : Observers()) {
      if (!observers.empty()) observers += ", ";
      observers += std::string(ModId(o.mod)) + ":" + o.name + (Enabled(o.mod) ? "" : "[off]");
    }
    if (!observers.empty()) REXLOG_INFO("[hod] collision shape observers: {}", observers);
  });
#endif
}

}  // namespace

const char* HookName(Hook hook) { return hook < Hook::kCount ? kInfo[unsigned(hook)].name : "?"; }
uint32_t HookAddress(Hook hook) { return hook < Hook::kCount ? kInfo[unsigned(hook)].address : 0; }

void Next::operator()(PPCContext& ctx, uint8_t* base) const {
  const auto& chain = Chains()[unsigned(hook_)];
  for (unsigned i = index_; i < chain.size(); ++i) {
    if (!Enabled(chain[i].mod)) continue;
    chain[i].handler(ctx, base, Next(hook_, uint16_t(i + 1)));
    return;
  }
  if (const auto original = Originals()[unsigned(hook_)]) original(ctx, base);
}

void Dispatch(Hook hook, PPCContext& ctx, uint8_t* base) {
  LogChainsOnce();
  Next(hook, 0)(ctx, base);
}

bool SetOriginal(Hook hook, Original original) {
  Originals()[unsigned(hook)] = original;
  return true;
}

bool Register(Hook hook, Mod mod, int order, Handler handler, const char* name) {
  auto& chain = Chains()[unsigned(hook)];
  const Entry entry{mod, order, NextSequence(), handler, name};
  chain.insert(std::upper_bound(chain.begin(), chain.end(), entry, Earlier<Entry>), entry);
  return true;
}

bool RegisterShapeObserver(Mod mod, int order, ShapeObserver observer, const char* name) {
  auto& list = Observers();
  const Observer entry{mod, order, NextSequence(), observer, name};
  list.insert(std::upper_bound(list.begin(), list.end(), entry, Earlier<Observer>), entry);
  return true;
}

void RunShapeObservers(const PPCContext& original, uint8_t* base, uint32_t handle, uint32_t result) {
  for (const auto& o : Observers())
    if (Enabled(o.mod)) o.observer(original, base, handle, result);
}

std::recursive_mutex& CollisionLock() {
  static std::recursive_mutex lock;
  return lock;
}

}  // namespace hod
