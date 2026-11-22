"""Check generated native costs against the balance policy and serialized menus."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,re,math
from pathlib import Path
from txrc import decode
from nathan_cards import ACTIONS,ATTRIBUTES
R=hodpaths.GAME
d=json.loads((hodpaths.legacy('modding/nathan_dss_balance.json')).read_text())
h=(R/'.setup/package/src/src/nathan_dss_balance.h').read_text()
arrays={name:[float(v) for v in values.split(',')] for name,values in re.findall(r'constexpr float (k\w+)\[\d+\]=\{([^}]+)\}',h)}
for family,raw in d['cotm_costs'].items():
    name='k'+family+('Cost' if family in ('Uranus','Crash') else 'Mp')
    expected=[math.ceil(v/4) for v in raw]
    assert arrays[name]==expected,(family,arrays[name],expected)
    assert all(1<=v<=50 for v in arrays[name])
# Pair costs are shown natively in the menu (823E4AB0 kind 1), from
# nathan_dss_menu.h; the descriptions carry no MP line.
menu=[int(v) for v in re.search(r'kPairMenuMp\[100\]=\{([^}]+)\}',(R/'.setup/package/src/src/nathan_dss_menu.h').read_text())[1].split(',')]
assert len(menu)==100 and all(0<=v<=50 for v in menu)
checks=0
for language in ('en','de','es','fr','it','ja'):
    text=decode((hodpaths.WORK/f'build/nathan_cards_package/data/text/textres17_{language}.txrc').read_bytes())['sections'][0][14]
    assert len(text)==121  # 20 cards, 100 pairs, then the Tackle Martial Art (index 120)
    for a,action in enumerate(ACTIONS):
        for b,attribute in enumerate(ATTRIBUTES):
            value=text[20+a*10+b]
            assert value.startswith(f'{action} + {attribute}{chr(10)}') and 'MP/' not in value,(language,value)
            if action in d['cotm_costs']:
                name='k'+action+('Cost' if action=='Uranus' else 'Mp')
                assert menu[a*10+b]==max(1,math.floor(arrays[name][b]+.5)),(action,attribute,menu[a*10+b],arrays[name][b])
            checks+=1
assert menu[9*10+0]==0 and menu[9*10+5]==0  # Item Crash: the subweapon's own cost; Pluto + Manticore: none
assert arrays['kUranusCost']==[40,30,25,25,50,20,25,50,25,25]
assert arrays['kApolloMp']==[5,5,10,8,15,3,15,20,20,30]
print(f'Passed {checks} serialized pair descriptions across six languages (no MP in text); menu MP matches every native per-use cost (1-50).')
