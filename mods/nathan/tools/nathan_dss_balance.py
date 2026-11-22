"""One MP balance policy for native code generation and all card descriptions."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,math,re
from pathlib import Path
ROOT=hodpaths.GAME
CONFIG=json.loads((hodpaths.legacy('modding/nathan_dss_balance.json')).read_text())
def cost(value):return max(1,math.ceil(value*CONFIG['scale'])) if value>0 else 0
def description(text):
    def replace(m):
        value=float(m[1]);unit=m[2]
        amount=value*CONFIG['scale'] if unit=='sec' else cost(value)
        return f'{amount:g} MP/{unit}'
    text=re.sub(r'(\d+(?:\.\d+)?) MP/(sec|swing|attack|use|cast|bomb|shot)',replace,text)
    return re.sub(r'(\d+) MP per swing',lambda m:f'{cost(int(m[1]))} MP per swing',text)
def write_header():
    rows=['#pragma once','// Generated from modding/nathan_dss_balance.json; do not hand-edit.','// ROM costs retained in JSON; runtime values are adapted to HoD.','namespace harmony::nathan {',f"constexpr float kDssUpkeepScale={CONFIG['scale']}f;"]
    pair=CONFIG['pair_level']
    for key,name in (('damage_at_max','kPairDamageAtMax'),('healing_at_max','kPairHealingAtMax'),('bonus_at_max','kPairBonusAtMax')):
        assert 1<=pair[key]<=10,key
        rows.append(f'constexpr float {name}={float(pair[key])!r}f;')
    attributes=('Salamander','Serpent','Mandragora','Golem','Cockatrice','Manticore','Griffin','Thunderbird','Unicorn','Black Dog')
    for action in ('Diana','Apollo','Saturn'):
        flags=CONFIG['pass_through'][action];assert set(flags)==set(attributes),action
        rows.append(f'constexpr bool k{action}PassThrough[10]={{'+','.join('true' if flags[a] else 'false' for a in attributes)+'};')
    for name,values in CONFIG['cotm_costs'].items():
        variable='k'+name+('Cost' if name in ('Uranus','Crash') else 'Mp')
        rows.append(f'constexpr float {variable}[{len(values)}]={{'+','.join(str(cost(v)) for v in values)+'};')
    t=CONFIG['tackle']
    assert 1<=t['mp']<=200 and 0<t['power']<=5 and 1<=t['speed_walks']<=8 and 0<t['dash_seconds']<=1
    rows+=[f"constexpr uint32_t kTackleArt=11, kTackleMotion=193; // global Martial Art index (base has 0..10); unused motion",
           f"constexpr float kTackleMp={float(t['mp'])!r}f, kTacklePower={float(t['power'])!r}f, kTackleSpeedWalks={float(t['speed_walks'])!r}f, kTackleDashSeconds={float(t['dash_seconds'])!r}f;",
           f"constexpr int kTackleHalfWidth={int(t['hit_half_width'])}, kTackleHalfHeight={int(t['hit_half_height'])}, kTackleAhead={int(t['hit_ahead'])};"]
    regen=float(CONFIG['mp_regen']['per_second']);assert 0<regen<=10
    rows+=[f"constexpr float kMpRegenPerSecond={regen!r}f; // natural MP regeneration (stats +0x2C)"]
    rows+=['}']
    p=ROOT/'.setup/package/src/src/nathan_dss_balance.h';p.write_text('\n'.join(rows)+'\n');return p
if __name__=='__main__':print(write_header())
