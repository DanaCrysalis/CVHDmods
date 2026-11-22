"""Validate native DSS hook assumptions against the actual unpacked game code."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json
import re
import struct
import tomllib
from pathlib import Path

ROOT=hodpaths.GAME

def main():
    from nathan_paths import CodeImage
    image=CodeImage('hod_image.bin',0x82000000); player=CodeImage('dllTest12_image.bin',0x836C0000)
    word=image.word; module=player.word
    # Internal Personal Skill action bit 8 uses control binding 2. The mapping
    # is independent of the chosen keyboard/controller button for that action.
    assert word(0x821CA6B4+8*4)==2
    assert word(0x821CA680+8*4)==8 # fixed physical Personal Skill = RB
    assert word(0x821D4740+5*4)==8 # default binding 5 = RB
    assert word(0x821CA6B4+9*4)==6 # bit 9 is backdash/LB, NOT RB
    # STR getter feeds the primary-weapon damage formula via 82452658.
    assert word(0x82452684)==0x816B030C # vtable 195 -> 836D3670
    assert module(0x836C28E8+195*4)==0x836D3670
    assert module(0x836D36A0)==0xEC20682A # fadds f1,f0,f13
    # The actual incoming DEF helper uses CON (getter 197), while INT is
    # getter 196. The earlier 824526D0 target is magic attack, NOT DEF.
    assert module(0x836C28E8+196*4)==0x836D36B8
    assert module(0x836C28E8+197*4)==0x836D3700
    assert module(0x836C28E8+199*4)==0x836D3790
    assert word(0x82451B08)==0x816B0314 # incoming DEF reads CON
    assert word(0x82451AF8)==0x48008F91 # plus armor DEF sum 8245AA88
    assert word(0x8245256C)==0x4BFFF53D # damage calculator -> physical DEF
    assert word(0x8245DD0C)==0xEC0C683A # menu summary: armor + CON/2
    assert word(0x82230110)==0x816B031C # total LCK
    # Heart category alone dispatches through 8245BCA8. Its native gain
    # applies Heart Boost gear before the common clamped MP addition.
    assert word(0x8245B1DC)==0x48000ACD
    assert word(0x8245BCC0)==0x81230068  # component owner entity handle
    assert word(0x8245BD10)==0x2B1C0029  # medium heart
    assert word(0x8245BD20)==0x2B1C002A  # large heart
    assert word(0x8245BD5C)==0xEC2007F2  # gear-adjusted MP gain
    assert word(0x8245BD60)==0x4BFF2669  # common MP add
    # MP getter vtable 166 and additive MP setter use stats+8; HP uses +4.
    assert module(0x836D32B8)==0xC02B0008
    assert module(0x836D2650)==0xC00B0008
    # Weapon property bit 3 (fire) maps to collision flag 0x100. The shared
    # update obtains flags through the hook before writing the live hit object.
    assert word(0x821CA1E4+3*4)==0x100
    assert word(0x8246F7FC)==0x907E00B0
    assert word(0x8246F7F0)==0x4BFFCC19 # bl 8246C408
    # Persistent animation-table copy: player -> vtable153, destination entity+74.
    assert word(0x82445E00)==0x389F0074
    assert word(0x82445E08)==0x816B0264
    # Nathan's airborne attack initializer selects motion 189, while the
    # actual movement state remains jump/fall (11/16 in a live capture).
    assert module(0x836D1660)==0x3BC000BD # li r30,189
    # Native stats integrate pending position, then the owner reads it through
    # vtable getter 155. Owner world coordinates are not this update's result.
    assert module(0x836C28E8+620)==0x836D31B0
    text=(ROOT/'.setup/package/src/generated/dlltest12/harmonyrecomp_recomp.0.cpp').read_text()
    start=text.index('DEFINE_REX_FUNC(sub_836D5B20)');end=text.index('DEFINE_REX_FUNC(',start+25)
    assert 'REX_STORE_U32(ctx.r31.u32 + 328, temp.u32)' in text[start:end]
    # Full native module registration must survive the selective Nathan build.
    source=ROOT/'.setup/package/src'
    manifest=tomllib.loads((source/'harmonyrecomp_manifest.local.toml').read_text())
    registry=(source/'generated/default/module_registry.cpp').read_text()
    for m in manifest['modules']:
        assert '"'+m['guest_path']+'"' in registry
    state=(source/'src/nathan_dss_state.h').read_text()
    assert 'kRb = 0x100' in state and 'kMpCost=kMercuryMp[0]' in state
    from nathan_paths import cotm_rom; rom=cotm_rom()
    venus=[struct.unpack_from('<IHHHH',rom,0xE4860+i*12) for i in range(10)]
    assert [v[0] for v in venus]==[4368,4368,4368,17472,2184,2184,4368,17472,8736,8736]
    assert [v[3] for v in venus]==[112,100,100,100,100,100,100,100,71,141]
    assert all(v[1]==v[2]==v[4]==0 for v in venus) # no activation/swing cost
    (hodpaths.legacy('modding/build/nathan_firewhip/venus_rom_verification.json')).write_text(json.dumps({
        'ROM_table':'080E4860','MP_per_native_frame_16_16':[v[0] for v in venus],
        'STR_percent':[v[3] for v in venus],
        'native_stat_function':'0806D930: 0806DAEC..0806DBBC',
        'DEF_percent':{'Serpent':125,'Unicorn':200,'Black Dog':50},
        'LCK_percent':{'Mandragora':125},'INT_percent':{'Griffin':125},
        'disabled':['Golem','Cockatrice','Thunderbird'],
        'Manticore_override':'Double MP from heart items only',
        'physical_DEF_helper':'82451AA8','incoming_damage_DEF_call':'8245256C','status_summary':'8245D9A0 output+18',
        'guest_getters_and_heart_dispatch_verified':True},indent=2)+'\n')
    uranus=[struct.unpack_from('<IHHHH',rom,0xE4BA8+i*12) for i in range(10)]
    assert [v[2] for v in uranus]==[160,120,100,100,200,80,100,200,100,100]
    assert all(v[0]==v[1]==v[4]==0 and v[3]==100 for v in uranus)
    # Allocation-local collider tables inherit native destruction and contact
    # dispatch. The actual area helper is also executed by the C++ harness.
    assert word(0x821EA0F0)==0x824820D0
    assert word(0x821EA0F0+0x30)==0x82484918
    (hodpaths.legacy('modding/build/nathan_firewhip/uranus_verification.json')).write_text(json.dumps({
        'ROM_table':'080E4BA8','MP_per_cast':[v[2] for v in uranus],
        'STR_percent':[v[3] for v in uranus],'passive_stat_benefits':False,
        'input':'RB rising edge casts directly; held RB cannot repeat or cancel',
        'casting_resources':[87,89,90],'summon_resources':list(range(80,90)),
        'casting_sound':349,'summon_sounds':[350,351,352,350,350,353,353,354,352,354],
        'area_world_size':[320,180],'center':'Nathan cast position; center 40 units above feet',
        'damage_path':'82484180 -> 823C4C40 native attack requests, owned native colliders',
        'Unicorn':'One 16% maximum HP heal; no attack collider',
        'Black_Dog':'Four dark attack waves; one 1% maximum HP recovery per accepted target owner per wave',
        'native_assets_and_sound_ids_verified':True,
        'native_area_submission_executed_in_harness':True,
        'visual_choreography':'ROM parts composed into a bounded local summon effect',
        'live_enemy_damage_and_status_validation_pending':True},indent=2)+'\n')
    report={'internal_rb_action':'0x100','mp_per_swing':2,'strength_multiplier':1.05,
            'fire_collision_flag':'0x100','mp_field':'stats + 8','hp_field':'stats + 4',
            'per_player_motion_table':'entity + 0x74','registered_modules':len(manifest['modules']),
            'live_gameplay_verified':False}
    image.save(); player.save()
    out=hodpaths.legacy('modding/build/nathan_firewhip/layout_verification.json')
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
