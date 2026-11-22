"""Read-only Nathan DSS diagnostics from a running level.

Usage: python modding/tools/nathan_dss_live.py [seconds] [wait-for-level seconds]
Never writes to game memory or savedata.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json
import struct
import sys
import time
from pathlib import Path
from guestwatch import attach,find

ROOT=hodpaths.GAME

def main():
    seconds=float(sys.argv[1]) if len(sys.argv)>1 else 0
    wait=float(sys.argv[2]) if len(sys.argv)>2 else 0
    deadline=time.monotonic()+wait
    if wait: print('Waiting for Nathan in a level (read-only)...',flush=True)
    while True:
        players=[]
        try:
            read,regions,base=attach();players=find(0x836C28E8,read,regions,base)
        except SystemExit:
            pass
        if len(players)==1: break
        if time.monotonic()>=deadline: raise RuntimeError(f'Expected one live Nathan; found {players}')
        time.sleep(1)
    player=players[0]
    def u(address):
        b=read(base+address,4);return int.from_bytes(b,'big') if b else 0
    def f(address): return struct.unpack('>f',u(address).to_bytes(4,'big'))[0]
    def entity(handle):
        manager=u(0x8291D9F0);table=u(manager+0xAC) if manager else 0
        entry=table+(handle&0xFFFF)*16
        return u(entry+4) if handle and table and u(entry)==handle else 0
    def snapshot():
        if u(player)!=0x836C28E8: return {'object_destroyed':True}
        table=u(player+852);owner=table-0x74 if table else 0
        model=u(owner+0x9C8) if owner and u(owner+0x924)==player else 0
        stats=u(player+88);inp=u(player+704);motion=u(player+584)
        weapon=entity(u(model+0x50)) if model else 0
        children=u(weapon+0x3C) if weapon else 0;child=u(children) if children else 0
        return {'palette_row':u(player+1072),'body_effect_draws':u(player+1076),'summon_waves':u(player+1288),'summon_hits_created':u(player+1292),'summon_recoveries':u(player+1296),'summon_center':[f(player+1280),f(player+1284)],'action':u(player+1056),'DEF_calls':u(player+1060),'DEF_before':f(player+1064),'DEF_after':f(player+1068),'card_swap_held':u(player+1032),'card_swaps':u(player+1040),'card_last':hex(u(player+1044)),'card_draws':u(player+1052),'attribute':u(player+1016),'hold_time':round(f(player+1020),3),'whip_damage':u(child+364) if child else None,'sound_id':u(player+904),'sound_count':u(player+908),'sound_handle':hex(u(player+912)),'enabled':u(player+844),'rb_held':bool(u(inp)&0x100) if inp else False,
                'paid_swing':u(player+856),'cast_remaining':round(f(player+864),3),'fade_remaining':round(f(player+868),3),'pulse_time':round(f(player+860),3),'mp':round(f(stats+8),3) if stats else None,
                'hp':round(f(stats+4),3) if stats else None,'state':u(player+572),'motion':motion,
                'body_frame':u(player+28),'drawn_frame':u(player+872),'canonical_frame':u(player+876),'draw_count':u(player+880),'body_slot':u(table+motion*8) if table and motion<268 else None,
                'whip_hit_flags':hex(u(child+0xB0)) if child else None,
                'equipped':[hex(u(model+i*4)) for i in (0,1,12,13)] if model else [],
                'owner':hex(owner),'player_context_index':u(player+60)}
    rows=[];start=time.monotonic();last=None
    while True:
        row=snapshot();signature={k:v for k,v in row.items() if k not in ('body_frame','mp','cast_remaining','fade_remaining','pulse_time','drawn_frame','draw_count')}
        row['seconds']=round(time.monotonic()-start,3);rows.append(row)
        if signature!=last: print(json.dumps(row),flush=True);last=signature
        if time.monotonic()-start>=seconds: break
        time.sleep(.05)
    out=hodpaths.legacy('modding/build/nathan_firewhip/live_diagnostics.json')
    enabled=[r for r in rows if r.get('enabled') and not r.get('cast_remaining')]
    draw_frames=sorted(set(r.get('drawn_frame',0) for r in enabled))
    counts=[r.get('draw_count',0) for r in enabled]
    summary={'enabled_samples':len(enabled),'distinct_drawn_frames':len(draw_frames),
             'distinct_palette_rows':len(set(r.get('palette_row',0) for r in enabled)),
             'draw_count_advanced':bool(counts and max(counts)>min(counts)),
             'canonical_idle_frames':sorted(set(r.get('canonical_frame',0) for r in enabled))}
    out.write_text(json.dumps({'player':hex(player),'read_only':True,'summary':summary,'samples':rows},indent=2)+'\n')
    print('Draw-path summary:',json.dumps(summary))
    print('Read-only diagnostics:',out)

if __name__=='__main__': main()
