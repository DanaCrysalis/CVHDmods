// Which mods run this session.
//
// A mod runs when it is compiled in (its CMake option, see
// core/cmake/hodmods.cmake) and switched on. The switch, checked once at the
// first hooked call:
//
//   1. hod_native_mods.txt next to harmonyrecomp.exe, if it names the mod:
//        # comment
//        shield-rod = off
//        nathan = on
//      (on/off, yes/no, true/false, 1/0). A mod loader writes this file before
//      it starts the game to turn a mod's code on or off without rebuilding.
//   2. Otherwise: on when the mod's DLC package is listed in the
//      dlc_packages.txt next to the exe (the list the recomp installs from), so
//      removing a package also switches its code off.
//   3. With no dlc_packages.txt at all: on (the behaviour of older builds).
//
// The environment variable HOD_NATIVE_MODS ("shield-rod=off,nathan=on")
// overrides the file, for testing.
#include "hod_hooks.h"
#include <rex/filesystem.h>
#include <rex/logging.h>
#include <algorithm>
#include <array>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <optional>
#include <sstream>
#include <string>

#ifndef HODMOD_SHIELD_ROD
#define HODMOD_SHIELD_ROD 0
#endif
#ifndef HODMOD_FAMILIARS
#define HODMOD_FAMILIARS 0
#endif
#ifndef HODMOD_GLYPHS
#define HODMOD_GLYPHS 0
#endif
#ifndef HODMOD_NATHAN
#define HODMOD_NATHAN 0
#endif
#ifndef HODMOD_CATACOMBS
#define HODMOD_CATACOMBS 0
#endif

namespace hod {
namespace {

constexpr unsigned kMods = unsigned(Mod::kCount);

struct ModInfo {
  const char* id;
  bool compiled;
  const char* content_id;  // its DLC package (nullptr: none)
};
constexpr std::array<ModInfo, kMods> kInfo{{
    {"core", true, nullptr},
    {"shield-rod", HODMOD_SHIELD_ROD != 0, "000000000000000000000000000000535200001358"},
    {"familiars", HODMOD_FAMILIARS != 0, "000000000000000000000000000000464D00001558"},
    {"refectio", HODMOD_GLYPHS != 0, "000000000000000000000000000000524600001458"},
    {"arma-custos", HODMOD_GLYPHS != 0, "000000000000000000000000000000435400000A58"},  // its glyph row is in the Catacombs package
    {"nathan", HODMOD_NATHAN != 0, "000000000000000000000000000000000C00001758"},
    {"catacombs", HODMOD_CATACOMBS != 0, "000000000000000000000000000000435400000A58"},
}};

std::string Lower(std::string s) {
  std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return char(std::tolower(c)); });
  return s;
}
std::string Trim(const std::string& s) {
  const auto a = s.find_first_not_of(" \t\r\n");
  if (a == std::string::npos) return {};
  const auto b = s.find_last_not_of(" \t\r\n");
  return s.substr(a, b - a + 1);
}
std::optional<bool> ParseSwitch(const std::string& value) {
  const auto v = Lower(Trim(value));
  if (v == "on" || v == "yes" || v == "true" || v == "1") return true;
  if (v == "off" || v == "no" || v == "false" || v == "0") return false;
  return std::nullopt;
}
int IndexOf(const std::string& id) {
  for (unsigned i = 0; i < kMods; ++i)
    if (Lower(Trim(id)) == kInfo[i].id) return int(i);
  return -1;
}

struct Decision {
  bool on = true;
  const char* why = "default";
};

std::array<Decision, kMods> Decide() {
  std::array<Decision, kMods> out{};
  std::array<std::optional<bool>, kMods> explicit_switch{};
  const auto folder = rex::filesystem::GetExecutableFolder();

  const auto apply = [&](const std::string& key, const std::string& value, const char* source) {
    const int i = IndexOf(key);
    const auto on = ParseSwitch(value);
    if (i <= 0 || !on) {
      REXLOG_WARN("[hod] {}: ignored '{} = {}'", source, key, value);
      return;
    }
    explicit_switch[unsigned(i)] = on;
  };
  if (std::ifstream file(folder / "hod_native_mods.txt"); file) {
    for (std::string line; std::getline(file, line);) {
      line = Trim(line.substr(0, line.find('#')));
      if (line.empty()) continue;
      const auto eq = line.find('=');
      if (eq == std::string::npos) {
        REXLOG_WARN("[hod] hod_native_mods.txt: ignored '{}'", line);
        continue;
      }
      apply(line.substr(0, eq), line.substr(eq + 1), "hod_native_mods.txt");
    }
  }
  if (const char* env = std::getenv("HOD_NATIVE_MODS")) {
    std::stringstream list(env);
    for (std::string item; std::getline(list, item, ',');) {
      const auto eq = item.find('=');
      if (eq != std::string::npos) apply(item.substr(0, eq), item.substr(eq + 1), "HOD_NATIVE_MODS");
    }
  }

  std::string listed;
  bool have_list = false;
  if (std::ifstream file(folder / "dlc_packages.txt"); file) {
    have_list = true;
    std::stringstream all;
    all << file.rdbuf();
    listed = Lower(all.str());
  }

  for (unsigned i = 0; i < kMods; ++i) {
    auto& d = out[i];
    if (!kInfo[i].compiled) {
      d = {false, "not compiled in"};
    } else if (i == unsigned(Mod::kCore)) {
      d = {true, "always"};
    } else if (explicit_switch[i]) {
      d = {*explicit_switch[i], "switched in hod_native_mods.txt / HOD_NATIVE_MODS"};
    } else if (!have_list || !kInfo[i].content_id) {
      d = {true, have_list ? "no package" : "no dlc_packages.txt"};
    } else {
      const bool on = listed.find(Lower(kInfo[i].content_id)) != std::string::npos;
      d = {on, on ? "package listed" : "package not listed in dlc_packages.txt"};
    }
  }
  for (unsigned i = 1; i < kMods; ++i)
    REXLOG_INFO("[hod] native mod {}: {} ({})", kInfo[i].id, out[i].on ? "on" : "off", out[i].why);
  return out;
}

const std::array<Decision, kMods>& Decisions() {
  static const auto decisions = Decide();
  return decisions;
}

}  // namespace

const char* ModId(Mod mod) { return mod < Mod::kCount ? kInfo[unsigned(mod)].id : "?"; }
bool Compiled(Mod mod) { return mod < Mod::kCount && kInfo[unsigned(mod)].compiled; }
bool Enabled(Mod mod) { return mod < Mod::kCount && Decisions()[unsigned(mod)].on; }

}  // namespace hod
