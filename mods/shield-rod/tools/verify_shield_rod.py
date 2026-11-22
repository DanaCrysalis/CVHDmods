"""Run Shield Rod's production code against sparse guest-memory fixtures."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json
import subprocess
from pathlib import Path
ROOT=hodpaths.GAME
def main():
    # Execute HoD's real texture sampler, including the tile lookup that faulted.
    native=(ROOT/'.setup/package/src/generated/default/harmonyrecomp_recomp.16.cpp').read_text()
    first=native.index('DEFINE_REX_FUNC(sub_823CBF98)')
    end=native.index('DEFINE_REX_FUNC(',first+30)
    (hodpaths.legacy('modding/build/verify_csr_sampler.inc')).write_text(native[first:end])
    first=native.index('DEFINE_REX_FUNC(sub_823C4EC8)')
    end=native.index('DEFINE_REX_FUNC(',first+30)
    filter_code=native[first:end].replace('DEFINE_REX_FUNC(sub_823C4EC8)','REX_EXTERN(__imp__sub_823C4EC8)')
    (hodpaths.legacy('modding/build/verify_collision_filter.inc')).write_text(filter_code)
    vector_native=(ROOT/'.setup/package/src/generated/default/harmonyrecomp_recomp.14.cpp').read_text()
    first=vector_native.index('DEFINE_REX_FUNC(sub_823916C0)')
    end=vector_native.index('DEFINE_REX_FUNC(',first+30)
    (hodpaths.legacy('modding/build/verify_collision_vector.inc')).write_text(vector_native[first:end])
    # Execute the native rectangle conversion, rather than treating its
    # four integer inputs as guessed endpoint coordinates.
    geometry=(ROOT/'.setup/package/src/generated/default/harmonyrecomp_recomp.22.cpp').read_text()
    a=geometry.index('DEFINE_REX_FUNC(sub_82484180)');b=geometry.index('DEFINE_REX_FUNC(',a+30)
    rectangle=geometry[a:b].replace('DEFINE_REX_FUNC(sub_82484180)','REX_EXTERN(VerifyNativeRectangle)').replace('sub_823C3150(ctx, base)','VerifyRectCell(ctx, base)').replace('sub_823C4C40(ctx, base)','VerifyRectSubmit(ctx, base)')
    (hodpaths.legacy('modding/build/verify_native_rectangle.inc')).write_text(rectangle)
    guard_native=(ROOT/'.setup/package/src/generated/default/harmonyrecomp_recomp.20.cpp').read_text()
    a=guard_native.index('DEFINE_REX_FUNC(sub_8244B558)');b=guard_native.index('DEFINE_REX_FUNC(',a+30)
    (hodpaths.legacy('modding/build/verify_native_guard.inc')).write_text(guard_native[a:b].replace('DEFINE_REX_FUNC(sub_8244B558)','REX_EXTERN(VerifyNativeGuard)'))
    queue_native=(ROOT/'.setup/package/src/generated/default/harmonyrecomp_recomp.33.cpp').read_text()
    queue_parts=[]
    for fn in ['825908D0','82590680','82590878']:
        a=queue_native.index('DEFINE_REX_FUNC(sub_'+fn+')');b=queue_native.index('DEFINE_REX_FUNC(',a+30);part=queue_native[a:b]
        for old,new in [('825908D0','VerifyAllocateSoundJob'),('82590680','VerifyQueueSoundBank'),('82590878','VerifyKickSoundQueue')]:
            part=part.replace('DEFINE_REX_FUNC(sub_'+old+')','REX_EXTERN('+new+')').replace('sub_'+old+'(ctx, base)',new+'(ctx, base)')
        part=part.replace('sub_82657AA8(ctx, base)','VerifyAudioMutex(ctx, base)').replace('sub_82657AB0(ctx, base)','VerifyAudioMutex(ctx, base)')
        queue_parts.append(part)
    (hodpaths.legacy('modding/build/verify_native_audio_queue.inc')).write_text('\n'.join(queue_parts))
    geometry=(ROOT/'.setup/package/src/generated/default/harmonyrecomp_recomp.16.cpp').read_text()
    a=geometry.index('DEFINE_REX_FUNC(sub_823C3150)');b=geometry.index('DEFINE_REX_FUNC(',a+30)
    (hodpaths.legacy('modding/build/verify_native_region.inc')).write_text(geometry[a:b].replace('DEFINE_REX_FUNC(sub_823C3150)','REX_EXTERN(VerifyNativeRegion)'))
    # Real enemy damage transaction, repeat-hit gate/timer and damage math.
    import re
    sources={}
    native1=(ROOT/'.setup/package/src/generated/default/harmonyrecomp_recomp.1.cpp').read_text()
    native0=(ROOT/'.setup/package/src/generated/default/harmonyrecomp_recomp.0.cpp').read_text()
    for fn,text in [('82246DF0',native1),('8224E4E8',native1),('8224AE48',native1),('8224AEA0',native1),('82227B70',native0)]:
        first=text.index('DEFINE_REX_FUNC(sub_'+fn+')');end=text.index('DEFINE_REX_FUNC(',first+30)
        sources['sub_'+fn]=text[first:end]
    deps=set(re.findall(r'\b(sub_[A-Fa-f0-9]+|__savegprlr_\d+|__restgprlr_\d+)\(ctx, base\)', ''.join(sources.values())))
    names={name:('VerifyNative_'+name) for name in deps|set(sources)}
    names['sub_82246DF0']='__imp__sub_82246DF0'
    out=['void VerifyTrap(PPCContext&,uint8_t*,uint16_t){std::abort();}']+['REX_EXTERN('+name+');' for name in names.values()]
    for fn,code in sources.items():
        for old,new in names.items():code=re.sub(r'\b'+old+r'\b',new,code)
        code=code.replace('DEFINE_REX_FUNC(', 'REX_EXTERN(').replace('ppc_trap(', 'VerifyTrap(')
        out.append(code)
    for dep in sorted(deps-set(sources)):
        name=names[dep]
        if dep.startswith('__savegprlr_') or dep.startswith('__restgprlr_'):
            first=int(dep.rsplit('_',1)[1]);save=dep.startswith('__save')
            body=''
            for reg in range(first,32):
                at=-(32-reg)*8-8
                body+=(f'rex::memory::store_and_swap<uint64_t>(base+ctx.r1.u32+({at}),ctx.r{reg}.u64);' if save else f'ctx.r{reg}.u64=rex::memory::load_and_swap<uint64_t>(base+ctx.r1.u32+({at}));')
            if save:body+='rex::memory::store_and_swap<uint32_t>(base+ctx.r1.u32-8,ctx.r12.u32);'
            else:body+='ctx.lr=rex::memory::load_and_swap<uint32_t>(base+ctx.r1.u32-8);'
        elif dep=='sub_825C09A8':body='ctx.r3.u64=0x9c100;'
        elif dep=='sub_8245F3C8':body='ctx.f1.f64=0;'
        elif dep=='sub_8245F478':body=''
        elif dep in ('sub_823C70A8','sub_823C7010','sub_82454930'):body='Float(base,ctx.r3.u32,0);Float(base,ctx.r3.u32+4,0);'
        else:body='ctx.r3.u64=0;'
        out.append('REX_EXTERN('+name+') {'+body+'}')
    (hodpaths.legacy('modding/build/verify_enemy_damage.inc')).write_text('\n'.join(out))
    # Execute the renderer's actual blend-selection tail, including opaque 3.
    first=native.index('DEFINE_REX_FUNC(sub_823D1938)');last=native.index('DEFINE_REX_FUNC(',first+30)
    material=native[first:last];first=material.index('loc_823D1E8C:');last=material.index('loc_823D1F04:')
    (hodpaths.legacy('modding/build/verify_sprite_blend.inc')).write_text('REX_EXTERN(VerifyNativeBlend) {\n'+material[first:last]+'loc_823D1F04: return;\n}\n')
    assets=json.loads((hodpaths.legacy('modding/build/shield_sotn_assets/verified_assets.json')).read_text())['assets']
    pages=[name for name in assets if name.startswith('T_SF')]
    (hodpaths.legacy('modding/build/verify_csr_pages.inc')).write_text('\n'.join(json.dumps((hodpaths.legacy('modding/build/shield_sotn_assets')/name).as_posix())+',' for name in pages))
    exe=hodpaths.legacy('modding/build/verify_shield_rod.exe')
    subprocess.run([str(ROOT/'.setup/toolchain/llvm/bin/clang++.exe'),'-std=c++23','-msse4.1',
        '-DSPDLOG_FMT_EXTERNAL','-DSPDLOG_COMPILED_LIB','-DHOD_VERIFY_HARNESS','-I',str(ROOT/'.setup/package/sdk/include'),
        # repo sources, the generated .inc files above, then the recomp's src/ (generated headers)
        '-I',str(hodpaths.REPO/'mods/shield-rod/src'),'-I',str(hodpaths.REPO/'core/runtime'),
        '-I',str(hodpaths.legacy('modding/build')),'-I',str(ROOT/'.setup/package/src/src'),
        str(hodpaths.legacy('modding/tools/verify_shield_rod.cpp')),'-o',str(exe)],check=True,cwd=ROOT)
    result=subprocess.run([str(exe)],capture_output=True,text=True,cwd=ROOT)
    print(result.stdout,result.stderr,end='');result.check_returncode()
    (hodpaths.legacy('modding/build/shield_rod_verification.json')).write_text(json.dumps({
        'native_callback_checks':result.stdout.strip(),'live_gameplay_verified':False,'all_shields_audited':13,
        'native_collision_vector_threads':32,'medusa_homing_variants_checked':4,
        'collision_phases_separated':True,'alucard_hit_interval_frames':2,
        'alucard_native_held_shield_geometry_checked':True,'alucard_hp_and_green_popup_checked':True,'alucard_protection_ticks':96,'native_enemy_hp_events_old_interval':1,
        'native_enemy_hp_events_two_frame_interval':30,'native_repeat_gate_executed':True,
        'native_blend_selection_executed':True,'ordinary_monster_homing_checked':True,
        'world_anchor_all_shields_checked':True,'iron_hit_interval_frames':12,
        'iron_contact_interval_frames':3,'native_iron_hp_events_in_60_frames':5,
        'source_sound_tracks_checked':184,'sound_dispatch_all_parent_facings_checked':True,
        'fire_and_dark_quad_coverage_checked':True,'sound_cues_use_guest_names':True,
        'qualified_sound_bank_paths_checked':True,'dark_visual_projectiles':32,
        'dark_projectile_spawn_span':[830,432],'dark_projectile_sizes_and_motion_preserved':True},indent=2)+'\n')
if __name__=='__main__':main()
