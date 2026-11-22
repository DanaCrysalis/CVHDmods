"""Execute the emitted PPC hook instructions against synthetic player memory.

Verifies the actual branch/CR behavior without requiring the game to be open.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
from nathan_spin import *

def signed(v,bits): return v-(1<<bits) if v&(1<<(bits-1)) else v

def execute(entry,registers,memory):
    words,labels=build(); code={SECTION_VA+i*4:w for i,w in enumerate(words)}
    r=[0]*32
    for i,v in registers.items(): r[i]=v
    cr={}; pc=labels[entry]; mem=dict(memory)
    for _ in range(200):
        if pc not in code: return pc,r,mem
        word=code[pc]; pc+=4; op=word>>26; rt=(word>>21)&31; ra=(word>>16)&31; imm=signed(word&0xffff,16)
        if word==BLR: return 0,r,mem
        if op==14: r[rt]=((r[ra] if ra else 0)+imm)&0xffffffff
        elif op==32: r[rt]=mem.get((r[ra]+imm)&0xffffffff,0)
        elif op==36: mem[(r[ra]+imm)&0xffffffff]=r[rt]
        elif op in (10,11): cr[((word>>23)&7)*4+2]=r[ra]==(imm&0xffffffff if op==11 else word&0xffff)
        elif op==28:
            r[ra]=r[rt]&(word&0xffff); cr[2]=r[ra]==0
        elif op==18: pc=pc-4+signed(word&0x3fffffc,26)
        elif op==16:
            bo=(word>>21)&31; bi=(word>>16)&31; assert bo in (4,12)
            if cr.get(bi,False)==(bo==12): pc=pc-4+signed(word&0xfffc,16)
        else: raise AssertionError(hex(word))
    raise AssertionError('Hook did not terminate')

def main():
    player,state_obj,input_state,input_ptr=0x10000,0x20000,0x30000,0x40000
    count=0
    for state,rest,swing,spin,entry,tail in ((23,1,187,191,'spin_update',ORIG_STATE23_UPDATE),
                                          (24,8,188,192,'crouch_spin_update',ORIG_STATE24_UPDATE)):
        mem={player+572:state,player+584:swing,player+0x60:input_state,input_state+12:input_ptr,
             input_ptr:ATTACK,player+(state+23)*4:state_obj,state_obj+4:player}
        target,r,m=execute('spin_set_state',{3:player,4:rest,5:0},mem)
        assert target==SET_MOTION and r[3:6]==[state_obj,spin,0] and m[player+612]==2; count+=1
        # Already rotating: do not reset the motion or frame on every idle request.
        mem[player+584]=spin
        target,r,m=execute('spin_set_state',{3:player,4:rest,5:0},mem)
        assert target==0 and r[3]==player and m[player+612]==2; count+=1
        target,r,m=execute(entry,{3:state_obj},mem)
        assert target==tail and r[3]==state_obj and m[player+612]==2 and player+580 not in m; count+=1
        mem[input_ptr]=0
        target,r,m=execute(entry,{3:state_obj},mem)
        assert target==tail and r[3]==state_obj and m[player+580]==rest and m[player+588]==0 and m[player+612]==3; count+=1
        target,r,m=execute('spin_set_state',{3:player,4:rest,5:17},mem)
        assert target==ORIG_SET_STATE and r[3:6]==[player,rest,17]; count+=1
        mem[input_ptr]=ATTACK
        for request in (7,16,31):
            target,r,m=execute('spin_set_state',{3:player,4:request,5:123},mem)
            assert target==ORIG_SET_STATE and r[3:6]==[player,request,123]; count+=1
        mem[player+584]=239  # special/non-whip attack
        target,r,m=execute('spin_set_state',{3:player,4:rest,5:0},mem)
        assert target==ORIG_SET_STATE; count+=1
        target,r,m=execute(entry,{3:state_obj},{state_obj+4:0})
        assert target==tail and r[3]==state_obj; count+=1
    print(f'Passed {count} emitted-PPC checks: standing/crouching entry, hold, release, null player, special attacks and interruptions.')

if __name__=='__main__': main()
