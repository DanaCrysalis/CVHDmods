"""Compile and execute the actual native DSS wrappers with stubbed game calls."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json
import re
import subprocess
from pathlib import Path
from verify_nathan_dss_layout import main as verify_layout

ROOT=hodpaths.GAME

def main():
    verify_layout()
    # The speed scope is only meaningful while these routines use the boots formula.
    module=(ROOT/'.setup/package/src/generated/dlltest12/harmonyrecomp_recomp.0.cpp').read_text()
    for name in ('836DC9A0','836D7C50'):
        start=module.index(f'DEFINE_REX_FUNC(sub_{name})')
        reader=module[start:module.index('DEFINE_REX_FUNC(',start+25)]
        for field in ('388','392','316'):
            assert re.search(rf'// lfs f\d+,{field}\(r11\)',reader),(name,field)
    exe=hodpaths.legacy('modding/build/verify_nathan_dss.exe')
    # Compile the game's real physical-DEF routine, rather than a fixed-value
    # stand-in that could let a hook on the wrong derived stat pass.
    generated=(ROOT/'.setup/package/src/generated/default/harmonyrecomp_recomp.20.cpp').read_text()
    start=generated.index('DEFINE_REX_FUNC(sub_82451AA8)')
    end=generated.index('DEFINE_REX_FUNC(',start+25)
    body=generated[start:end].replace('DEFINE_REX_FUNC(sub_82451AA8)','REX_EXTERN(__imp__sub_82451AA8)')
    defense=hodpaths.legacy('modding/build/verify_nathan_original_defense.cpp')
    defense.write_text('#include "'+(ROOT/'.setup/package/src/generated/default/harmonyrecomp_init.h').as_posix()+'"\n'+body)
    generated_area=(ROOT/'.setup/package/src/generated/default/harmonyrecomp_recomp.22.cpp').read_text()
    start=generated_area.index('DEFINE_REX_FUNC(sub_82484180)')
    end=generated_area.index('DEFINE_REX_FUNC(',start+25)
    area=hodpaths.legacy('modding/build/verify_nathan_original_area.cpp')
    area.write_text('#include "'+(ROOT/'.setup/package/src/generated/default/harmonyrecomp_init.h').as_posix()+'"\n'+generated_area[start:end].replace('DEFINE_REX_FUNC(sub_82484180)','REX_EXTERN(__imp__sub_82484180)'))
    extra=hodpaths.legacy('modding/build/verify_nathan_original_summon_helpers.cpp')
    bodies=[]
    for shard,name in ((16,'823C4E00'),(20,'82454000')):
        text=(ROOT/f'.setup/package/src/generated/default/harmonyrecomp_recomp.{shard}.cpp').read_text()
        start=text.index(f'DEFINE_REX_FUNC(sub_{name})');end=text.index('DEFINE_REX_FUNC(',start+25)
        body=text[start:end].replace(f'DEFINE_REX_FUNC(sub_{name})',f'REX_EXTERN(sub_{name})')
        # The standalone harness has no guest dispatch table; retain its known query stub.
        if name=='823C4E00':body=body.replace('REX_CALL_INDIRECT_FUNC(0x823C5098);','sub_823C5098(ctx, base);')
        bodies.append(body)
    extra.write_text('#include "'+(ROOT/'.setup/package/src/generated/default/harmonyrecomp_init.h').as_posix()+'"\n'+'\n'.join(bodies))
    # Execute the real common palette lookup and native basename hasher.
    for name,output in (('823D7170','__imp__sub_823D7170'),('825BFF28','sub_825BFF28'),('823C2340','sub_823C2340')):
        paths=(ROOT/'.setup/package/src/generated/default').glob('harmonyrecomp_recomp.*.cpp')
        text=next(t for p in paths if f'DEFINE_REX_FUNC(sub_{name})' in (t:=p.read_text()))
        start=text.index(f'DEFINE_REX_FUNC(sub_{name})');end=text.index('DEFINE_REX_FUNC(',start+25)
        with extra.open('a') as f:
            f.write(text[start:end].replace(f'DEFINE_REX_FUNC(sub_{name})',f'REX_EXTERN({output})'))
    # Execute HoD's real repeat-hit gate and timer, with a preallocated vector.
    native=(ROOT/'.setup/package/src/generated/default/harmonyrecomp_recomp.1.cpp').read_text()
    names=('8224E4E8','8224AEA0','8224AE48')
    code=[]
    for fn in names:
        a=native.index('DEFINE_REX_FUNC(sub_'+fn+')');b=native.index('DEFINE_REX_FUNC(',a+25)
        body=native[a:b]
        for old in (*names,'8243F6D0','8224E700','82566C10'):
            body=body.replace('sub_'+old,'VerifySummon_'+old)
        body=body.replace('__savegprlr_26','VerifySummon_save26').replace('__restgprlr_26','VerifySummon_rest26').replace('DEFINE_REX_FUNC(','REX_EXTERN(')
        code.append(body)
    prefix='\n'.join('REX_EXTERN(VerifySummon_'+fn+');'for fn in (*names,'8243F6D0','8224E700','82566C10','save26','rest26'))+'\n'
    for first,save in ((26,True),(26,False)):
        body=''
        for reg in range(first,32):
            off=-(32-reg)*8-8
            body+=(f'rex::memory::store_and_swap<uint64_t>(base+ctx.r1.u32+({off}),ctx.r{reg}.u64);'if save else f'ctx.r{reg}.u64=rex::memory::load_and_swap<uint64_t>(base+ctx.r1.u32+({off}));')
        prefix+='REX_EXTERN(VerifySummon_'+('save26'if save else'rest26')+') {'+body+'}\n'
    prefix+='REX_EXTERN(VerifySummon_8243F6D0){ctx.r3.u64=0;}\nREX_EXTERN(VerifySummon_8224E700){ctx.r3.u64=0;}\nREX_EXTERN(VerifySummon_82566C10){std::abort();}\n'
    with extra.open('a')as f:f.write(prefix+'\n'.join(code))
    # Sources from the repo (mods/nathan/src, core/runtime); generated headers
    # (balance, menu, assets) from the recomp's src folder, where the tools write them.
    nathan_src=hodpaths.REPO/'mods/nathan/src'; core=hodpaths.REPO/'core/runtime'
    command=[str(ROOT/'.setup/toolchain/llvm/bin/clang++.exe'),'-std=c++23','-msse4.1',
             '-DSPDLOG_FMT_EXTERNAL','-DSPDLOG_COMPILED_LIB','-DNATHAN_VERIFY_HARNESS','-DHOD_VERIFY_HARNESS',
             '-I',str(ROOT/'.setup/package/sdk/include'),'-I',str(nathan_src),'-I',str(core),'-I',str(ROOT/'.setup/package/src/src'),
             str(hodpaths.tool('verify_nathan_dss.cpp')),str(defense),str(area),str(extra),str(nathan_src/'nathan_dss.cpp'),
             str(nathan_src/'nathan_dss_damage.cpp'),str(core/'hod_hub.cpp'),'-o',str(exe)]
    subprocess.run(command,check=True,cwd=ROOT)
    result=subprocess.run([str(exe)],check=False,capture_output=True,text=True,cwd=ROOT)
    if result.returncode: print(result.stdout,result.stderr);result.check_returncode()
    report={'native_wrapper_checks':result.stdout.strip(),'live_gameplay_verified':False}
    (hodpaths.legacy('modding/build/nathan_firewhip/native_verification.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(result.stdout,end='')

if __name__=='__main__': main()
