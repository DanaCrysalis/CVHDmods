"""Where things are, for every hod-mods tool.

  REPO  this checkout (the folder holding hodmods.json)
  GAME  the HarmonyRecomp game folder: harmonyrecomp.exe, .setup/, assets/, dlc/
  WORK  the working folder for build output, backups, pristine copies of game
        files and other game-derived caches. Never committed. The tools'
        original home was <GAME>/modding, so that is the default.
  TEST  the separate test install used for the Catacombs chapter.

GAME is found from, in order: the HOD_GAME_DIR environment variable,
"game_dir" in hodmods.local.json at the repo root (not committed), or the
repo's parent folder when it holds harmonyrecomp.exe. WORK: HOD_WORK_DIR,
"work_dir" in hodmods.local.json, else <GAME>/modding.

The tools were written for a flat <GAME>/modding/tools folder. legacy() maps
the old "modding/..." paths onto this layout, so a tool's own path logic
stays readable:

  tools/<file>       -> the tool, wherever it lives in the repo (tool())
  <name>.json        -> a section's settings, mods/*/config (setting())
  data/<mod's file>  -> mods/<section>/data (the mod's own records)
  art/...            -> the hand-made art that ships (mods/nathan/art, core/art)
  docs/<file>        -> the repo's docs, when the file is there
  anything else      -> WORK/<path> (build/, backups/, originals/, data/, ...)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "hodmods.json").is_file())


def _local() -> dict:
    f = REPO / "hodmods.local.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except (OSError, ValueError) as e:
        raise SystemExit(f"{f}: {e}")


def _game() -> Path:
    for candidate in (os.environ.get("HOD_GAME_DIR"), _local().get("game_dir")):
        if candidate:
            return Path(candidate).expanduser().resolve()
    if (REPO.parent / "harmonyrecomp.exe").is_file():
        return REPO.parent
    raise SystemExit("hod-mods: set HOD_GAME_DIR (or game_dir in hodmods.local.json) to the HarmonyRecomp game folder")


GAME = _game()
WORK = Path(os.environ.get("HOD_WORK_DIR") or _local().get("work_dir") or GAME / "modding").expanduser().resolve()
# The separate test install the Catacombs chapter is developed in (its own
# userdata; see mods/catacombs/README.md): HOD_TEST_DIR / "test_dir".
TEST = Path(os.environ.get("HOD_TEST_DIR") or _local().get("test_dir") or GAME.parent / "HoD Test - Poison Worm").expanduser()

TOOL_DIRS = [REPO / "core" / "tools", *sorted((REPO / "mods").glob("*/tools")), *sorted((REPO / "mods").glob("*/tools/legacy"))]
SETTING_DIRS = [REPO / "core" / "config", *sorted((REPO / "mods").glob("*/config"))]


def tool(name: str) -> Path:
    """A tool file (script, harness source, helper) anywhere in the repo."""
    for d in TOOL_DIRS:
        if (d / name).exists():
            return d / name
    raise FileNotFoundError(f"hod-mods: no tool named {name}")


def setting(name: str) -> Path:
    """A section's settings file (mods/<section>/config/<name>)."""
    for d in SETTING_DIRS:
        if (d / name).exists():
            return d / name
    raise FileNotFoundError(f"hod-mods: no settings file named {name}")


_MOD_DATA = {
    "nathan_module_patches.json": "mods/nathan/data",
    "nathan_game_reads.json": "mods/nathan/data",
    "nathan_card_drop_originals.json": "mods/nathan/data",
    "alucard_familiar_drop_originals.json": "mods/familiars/data",
}
_ART = {"dive_kick": "mods/nathan/art", "menu": "mods/nathan/art", "equip_slot": "core/art"}


def legacy(path: str) -> Path:
    """Map an old "modding/<rest>" path (see the module docstring)."""
    rest = path.replace("\\", "/")
    if rest == "modding" or rest == "modding/":
        return WORK
    assert rest.startswith("modding/"), path
    rest = rest[len("modding/"):]
    parts = rest.split("/")
    if parts[0] == "tools" and len(parts) >= 2 and parts[1]:
        return tool(parts[-1])
    if len(parts) == 1 and rest.endswith(".json"):
        try:
            return setting(rest)
        except FileNotFoundError:
            return WORK / rest
    if parts[0] == "data" and len(parts) == 2 and parts[1] in _MOD_DATA:
        return REPO / _MOD_DATA[parts[1]] / parts[1]
    if parts[0] == "art" and len(parts) >= 2 and parts[1] in _ART:
        return REPO / _ART[parts[1]] / "/".join(parts[1:])
    if parts[0] == "docs" and len(parts) == 2 and parts[1]:
        found = sorted(REPO.glob(f"**/docs/{parts[1]}"))
        if found:
            return found[0]
    if parts[0] == "patches":
        return REPO / "core" / "recomp" / "legacy-patches" / "/".join(parts[1:])
    return WORK / rest


def add_tool_dirs() -> None:
    """Put every tool folder on sys.path (the tools import each other by name)."""
    for d in reversed(TOOL_DIRS):
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))


add_tool_dirs()
