# hod-mods build integration for HarmonyRecomp v0.6.0.
#
# The recomp's CMakeLists.txt (patched by core/recomp/harmonyrecomp-v0.6.0.patch)
# includes this file right after generated/rexglue.cmake, appends
# ${HODMODS_EXE_SOURCES} to its executable sources, and calls
# hodmods_configure_targets() at its end.
#
# One option per repo section. A section that is off is simply not compiled;
# a section that is on can still be switched off at run time (see
# core/runtime/hod_mods.cpp: hod_native_mods.txt / dlc_packages.txt).

if(NOT HODMODS_ROOT)
    get_filename_component(HODMODS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
endif()

option(HODMOD_SHIELD_ROD "hod-mods: Shield Rod and shield spells (mods/shield-rod)" ON)
option(HODMOD_FAMILIARS "hod-mods: Alucard's familiar cards (mods/familiars)" ON)
option(HODMOD_GLYPHS "hod-mods: Shanoa's Refectio and Arma Custos glyphs (mods/glyphs)" ON)
# The two older option names stay, so existing scripts keep working.
option(HARMONYRECOMP_NATHAN "hod-mods: Nathan Graves (mods/nathan)" ON)
option(HARMONYRECOMP_POISONWORM
       "hod-mods: Chapter 14 Catacombs enemies, souls and spell (mods/catacombs); test install only" OFF)
set(HODMOD_NATHAN ${HARMONYRECOMP_NATHAN})
set(HODMOD_CATACOMBS ${HARMONYRECOMP_POISONWORM})

set(_hod "${HODMODS_ROOT}")
set(HODMODS_EXE_SOURCES
    "${_hod}/core/runtime/hod_hub.cpp"
    "${_hod}/core/runtime/hod_mods.cpp"
    "${_hod}/core/runtime/hod_overrides.cpp")
set(HODMODS_EXE_INCLUDES "${_hod}/core/runtime")
if(HODMOD_FAMILIARS OR HODMOD_NATHAN)
    # Enchanted-row card icon, shared by the familiars and Nathan.
    list(APPEND HODMODS_EXE_SOURCES "${_hod}/core/runtime/equip_card_icon.cpp")
endif()
if(HODMOD_SHIELD_ROD)
    list(APPEND HODMODS_EXE_SOURCES "${_hod}/mods/shield-rod/src/shield_rod.cpp")
    list(APPEND HODMODS_EXE_INCLUDES "${_hod}/mods/shield-rod/src")
endif()
if(HODMOD_FAMILIARS)
    list(APPEND HODMODS_EXE_SOURCES "${_hod}/mods/familiars/src/alucard_familiar.cpp")
    list(APPEND HODMODS_EXE_INCLUDES "${_hod}/mods/familiars/src")
endif()
if(HODMOD_GLYPHS)
    list(APPEND HODMODS_EXE_SOURCES "${_hod}/mods/glyphs/src/refectio.cpp" "${_hod}/mods/glyphs/src/arma_custos.cpp")
    list(APPEND HODMODS_EXE_INCLUDES "${_hod}/mods/glyphs/src")
endif()
if(HODMOD_NATHAN)
    list(APPEND HODMODS_EXE_SOURCES "${_hod}/mods/nathan/src/nathan_dss_damage.cpp")
    list(APPEND HODMODS_EXE_INCLUDES "${_hod}/mods/nathan/src")
endif()

# Same-shard calls bypass overrides: the generator emits direct calls inside a
# shard and LLVM may fold them to the local __imp__ body. Rewrite those call
# sites to the guest dispatch table (core/hooks.json lists why each is here).
# "shard:function,function,..." for functions overridden by the hub or a mod
# and called inside that shard.
set(_hodmods_rewrites
    "1:82246DF0"
    "16:823D7170,823C4C40,823C5098,823C4EC8"
    "17:823E4AB0,823E0410,823E6958,823EA810,823ED418,823F46A8,823F47C8,8245D9A0"
    "18:82412880,8245D9A0"
    "20:82451AA8,82452658,824526D0,8244BF10,82450658,824519C8,8244CA98,8244FFF8"
    "21:8246D8E8,8244CA98,8245D9A0"
    "22:824823A0,82487EF8,8248A690"
    "33:825CEFA0,825CED10")
foreach(_hodmods_entry ${_hodmods_rewrites})
    string(REPLACE ":" ";" _hodmods_pair "${_hodmods_entry}")
    string(REPLACE "," ";" _hodmods_pair "${_hodmods_pair}")
    list(GET _hodmods_pair 0 _hodmods_shard_index)
    list(SUBLIST _hodmods_pair 1 -1 _hodmods_functions)
    set(_hodmods_shard "${CMAKE_CURRENT_SOURCE_DIR}/generated/default/harmonyrecomp_recomp.${_hodmods_shard_index}.cpp")
    if(NOT EXISTS "${_hodmods_shard}")
        message(FATAL_ERROR "hod-mods: ${_hodmods_shard} missing; run the recomp's code generation first")
    endif()
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${_hodmods_shard}")
    file(READ "${_hodmods_shard}" _hodmods_before)
    set(_hodmods_after "${_hodmods_before}")
    foreach(_hodmods_function ${_hodmods_functions})
        string(REPLACE "sub_${_hodmods_function}(ctx, base);" "REX_CALL_INDIRECT_FUNC(0x${_hodmods_function});"
               _hodmods_after "${_hodmods_after}")
    endforeach()
    if(NOT _hodmods_before STREQUAL _hodmods_after)
        file(WRITE "${_hodmods_shard}" "${_hodmods_after}")
    endif()
endforeach()
unset(_hodmods_before)
unset(_hodmods_after)

# Module code: overrides inside DLC code modules (each exists only after its
# tool ran code generation for it, see the section's README).
set(_hodmods_module_sources
    "HODMOD_NATHAN|harmonyrecomp_dllTest12|mods/nathan/src|nathan_dss.cpp"
    "HODMOD_CATACOMBS|harmonyrecomp_DLL_Cm050|mods/catacombs/src|poison_worm_module.cpp"
    "HODMOD_CATACOMBS|harmonyrecomp_dllshotCm050w|mods/catacombs/src|poison_worm_shot_module.cpp"
    "HODMOD_CATACOMBS|harmonyrecomp_dllshotSoulCm050|mods/catacombs/src|poison_worm_soul_module.cpp"
    "HODMOD_CATACOMBS|harmonyrecomp_DLL_Cm068|mods/catacombs/src|cerberus_module.cpp"
    "HODMOD_CATACOMBS|harmonyrecomp_dllshotCm068|mods/catacombs/src|cerberus_shot_module.cpp"
    "HODMOD_CATACOMBS|harmonyrecomp_dllshotSoulCm068|mods/catacombs/src|cerberus_soul_module.cpp"
    "HODMOD_CATACOMBS|harmonyrecomp_dllshotLearnCm068|mods/catacombs/src|cerberus_spell_module.cpp"
    "HODMOD_CATACOMBS|harmonyrecomp_DLL_Cm007|mods/catacombs/src|skeleton_bomber_module.cpp"
    "HODMOD_CATACOMBS|harmonyrecomp_dllshotCm007|mods/catacombs/src|skeleton_bomber_shot_module.cpp"
    "HODMOD_CATACOMBS|harmonyrecomp_dllshotSoulCm007|mods/catacombs/src|skeleton_bomber_soul_module.cpp")

macro(hodmods_configure_targets)
    # Repo headers first; the recomp's src/ folder keeps the generated headers
    # the tools write (balance tables, frame lists) and generated/<module>/.
    target_include_directories(harmonyrecomp BEFORE PRIVATE ${HODMODS_EXE_INCLUDES})
    target_include_directories(harmonyrecomp PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")
    foreach(_hodmods_flag HODMOD_SHIELD_ROD HODMOD_FAMILIARS HODMOD_GLYPHS HODMOD_NATHAN HODMOD_CATACOMBS)
        if(${_hodmods_flag})
            target_compile_definitions(harmonyrecomp PRIVATE ${_hodmods_flag}=1)
        else()
            target_compile_definitions(harmonyrecomp PRIVATE ${_hodmods_flag}=0)
        endif()
    endforeach()
    if(HODMOD_CATACOMBS)
        # harmonyrecomp_app.h: the test exe always uses the userdata folder next to it.
        target_compile_definitions(harmonyrecomp PRIVATE HARMONYRECOMP_POISONWORM=1)
    endif()
    foreach(_hodmods_entry ${_hodmods_module_sources})
        string(REPLACE "|" ";" _hodmods_fields "${_hodmods_entry}")
        list(GET _hodmods_fields 0 _hodmods_flag)
        list(GET _hodmods_fields 1 _hodmods_target)
        list(GET _hodmods_fields 2 _hodmods_dir)
        list(GET _hodmods_fields 3 _hodmods_file)
        if(${_hodmods_flag} AND TARGET ${_hodmods_target})
            target_sources(${_hodmods_target} PRIVATE "${_hod}/${_hodmods_dir}/${_hodmods_file}")
            target_include_directories(${_hodmods_target} BEFORE PRIVATE "${_hod}/${_hodmods_dir}" "${_hod}/core/runtime")
            target_include_directories(${_hodmods_target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")
        endif()
    endforeach()
    if(HODMOD_NATHAN AND TARGET harmonyrecomp_dllTest12 AND WIN32)
        target_link_options(harmonyrecomp_dllTest12 PRIVATE "LINKER:/MAP:harmonyrecomp_dllTest12.map")
    endif()
    message(STATUS "hod-mods ${HODMODS_ROOT}: shield-rod=${HODMOD_SHIELD_ROD} familiars=${HODMOD_FAMILIARS} "
                   "glyphs=${HODMOD_GLYPHS} nathan=${HODMOD_NATHAN} catacombs=${HODMOD_CATACOMBS}")
endmacro()
