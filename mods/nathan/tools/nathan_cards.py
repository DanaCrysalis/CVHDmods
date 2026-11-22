"""Build/install Nathan's DSS card equipment using existing soul equipment rows.

Mercury: Guardian/Personal Skill (RB), Salamander: Enchantment (passive).
Combat behavior is implemented in src/nathan_dss.cpp and nathan_dss_damage.cpp.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse
import datetime
import hashlib
import json
import math
import re
import shutil
import struct
import subprocess
from pathlib import Path
from txrc import decode,encode
from nathan_dss_balance import description as balance_description,write_header,cost as balance_cost,CONFIG as BALANCE_CONFIG

ROOT=hodpaths.GAME
IDENT='000000000000000000000000000000000C00001758'
SOURCE=ROOT/'.setup/package/src/mods'/IDENT
STAGE=hodpaths.legacy('modding/build/nathan_cards_package')
SOUL_BASE=0x673
FIRST=90
MERCURY=SOUL_BASE+FIRST
SALAMANDER=MERCURY+1
CARD_SWAP=0xC5  # utility weapon, global WEPN index 0x92
LEGACY_CARD_SWAP=0x6D8  # obsolete sub-weapon; reserved for migration only
VENUS=0x6D9  # index 102; never reuse obsolete Card Swap index 101
ACTIONS=('Mercury','Venus','Jupiter','Mars','Diana','Apollo','Neptune','Saturn','Uranus','Pluto')
NEW_ACTION_ITEMS=tuple(range(VENUS,VENUS+9))
MASK=1<<11
# Native collection list at definition +0x8C (8245D320): mode 1 sums owned
# copies, each capped at 9. That total drives the Hunter Whip's ATK
# (8245D178, weapon row min..max) and its three hit levels (8244D4E8).
COLLECTION=0x8C
CARD_CHESTS=BALANCE_CONFIG['card_chests']
CARD_ITEMS=(MERCURY,*range(SALAMANDER,SALAMANDER+10),*NEW_ACTION_ITEMS)
LANGS=('en','de','fr','es','it','ja')
# Nathan's Martial Art. Name at skill-name index 20 (after the 20 cards),
# description at skill-description index 120 (after the 100 pair texts).
TACKLE_TEXT={
 'en':('Tackle','Dash forward with a shoulder\ncharge that strikes foes in your\npath.'),
 'de':('Rempler','Schulterangriff nach vorn, der\nGegner auf dem Weg trifft.'),
 'fr':('Charge',"Foncez en avant d'un coup\nd'épaule qui frappe les ennemis."),
 'es':('Placaje','Embiste hacia delante con el\nhombro y golpea a los enemigos.'),
 'it':('Carica','Scatta in avanti con una spallata\nche colpisce i nemici sul cammino.'),
 'ja':('タックル','肩から前方へ突進し、\n進路上の敵を攻撃する。'),
}
TACKLE_NAME_INDEX,TACKLE_DESCRIPTION_INDEX=20,120
# The Martial Art row itself is appended to the base martialartsset.dat by
# nathan_card_drops.py: the game only looks Martial Arts up in the base table.

TEXT={
 'en':(('Mercury','Action Card. With Salamander:\nRB toggles Fire Whip (+5% STR).\nEach whip swing costs 6 MP.'),
       ('Salamander','Fire Attribute Card. Pair with\nMercury to use Fire Whip.\nRB toggles; 6 MP per swing.')),
 'de':(('Merkur','Mit Salamander: RB aktiviert\ndie Feuerpeitsche (+5% STR).\nJeder Peitschenhieb kostet 6 MP.'),
       ('Salamander','Feuer-Attributkarte. Mit Merkur\ndie Feuerpeitsche nutzen.\nRB schaltet um; 6 MP pro Hieb.')),
 'fr':(('Mercure',"Avec Salamandre : RB active\nle fouet de feu (+5% FOR).\nChaque coup coûte 6 PM."),
       ('Salamandre',"Carte de feu. Avec Mercure,\nutilisez le fouet de feu.\nRB : activer/arrêter. 6 PM/coup.")),
 'es':(('Mercurio','Con Salamandra: RB activa\nel látigo de fuego (+5% FUE).\nCada latigazo cuesta 6 PM.'),
       ('Salamandra','Carta de fuego. Con Mercurio,\npermite usar el látigo de fuego.\nRB activa/desactiva. 6 PM/golpe.')),
 'it':(('Mercurio',"Con Salamandra: RB attiva la\nfrusta di fuoco (+5% FOR).\nOgni frustata costa 6 PM."),
       ('Salamandra',"Carta del fuoco. Con Mercurio,\npermette la frusta di fuoco.\nRB attiva/disattiva. 6 PM/colpo.")),
 'ja':(('マーキュリー','サラマンダーと組み合わせると\nRBで炎のムチを切替（STR+5%）。\nムチ攻撃ごとにMPを6消費。'),
       ('サラマンダー','炎の属性カード。マーキュリーと\n組み合わせると炎のムチになる。\nRBで切替。攻撃ごとにMPを6消費。')),
}

# Attribute IDs follow the existing Salamander; passive slot for all ten.
ATTRIBUTES=('Salamander','Serpent','Mandragora','Golem','Cockatrice','Manticore','Griffin','Thunderbird','Unicorn','Black Dog')
COSTS=(6,2,6,8,6,6,10,10,20,40)
STR=(105,71,110,100,110,89,87,100,122,141)
ELEMENTS=('Fire','Ice','Plant','Earth','Stone','Poison','Wind','Lightning','Holy','Dark')
# Card rule texts per language: Mercury's, the shared attribute text, then
# the nine other action cards (same order as ACTIONS[1:]). Each line fits
# the menu box (at most 3 lines of 40 characters).
CARD_RULES={
 'en':('Action Card. Pair with an\nAttribute Card. RB toggles DSS.\nMP is consumed per whip swing.',
       'Attribute Card. Pair with an\nAction Card to use DSS.\nMore copies make the pair stronger.',
       ('Enhancement Action Card.\nRB toggles stat boosts.\nConsumes MP while active.',
        'Shield Action Card.\nRB toggles the equipped shield.\nConsumes MP while active.',
        'Weapon Action Card.\nRB toggles the equipped weapon.\nConsumes MP per attack.',
        'Projectile Action Card.\nRB toggles whip projectiles.\nConsumes MP per whip swing.',
        'Explosive Action Card.\nRB casts the equipped spell directly.\nMP is consumed once per cast.',
        'Resistance Action Card.\nRB toggles a damage resistance.\nConsumes MP while active.',
        'Familiar Action Card.\nRB toggles the equipped familiar.\nConsumes MP per familiar attack.',
        'Summoning Action Card.\nRB casts the equipped summon.\nConsumes MP once per cast.',
        'Special Action Card.\nSalamander: RB casts Item Crash.\nOther pairs: RB toggles the effect.')),
 'de':('Aktionskarte. Mit einer Attribut-\nkarte kombinieren; RB schaltet DSS.\nMP-Verbrauch pro Peitschenhieb.',
       'Attributkarte. Mit einer Aktions-\nkarte für DSS kombinieren. Mehr\nKopien stärken die Kombination.',
       ('Verstärkungs-Aktionskarte.\nRB schaltet Statusboni um.\nVerbraucht MP, solange aktiv.',
        'Schild-Aktionskarte.\nRB schaltet den Schild um.\nVerbraucht MP, solange aktiv.',
        'Waffen-Aktionskarte.\nRB schaltet die Waffe um.\nVerbraucht MP pro Angriff.',
        'Geschoss-Aktionskarte.\nRB schaltet Peitschengeschosse um.\nVerbraucht MP pro Peitschenhieb.',
        'Explosions-Aktionskarte.\nRB wirkt den Zauber direkt.\nMP-Verbrauch pro Zauber.',
        'Resistenz-Aktionskarte.\nRB schaltet eine Resistenz um.\nVerbraucht MP, solange aktiv.',
        'Vertrauten-Aktionskarte.\nRB schaltet den Vertrauten um.\nMP-Verbrauch pro Angriff.',
        'Beschwörungs-Aktionskarte.\nRB wirkt die Beschwörung.\nMP-Verbrauch pro Beschwörung.',
        'Spezial-Aktionskarte.\nSalamander: RB wirkt Item Crash.\nSonst: RB schaltet den Effekt.')),
 'fr':("Carte d'action. À combiner avec\nune carte d'attribut. RB : DSS.\nCoûte des PM à chaque coup.",
       "Carte d'attribut. À combiner avec\nune carte d'action pour le DSS.\nPlus d'exemplaires = plus fort.",
       ("Carte d'action d'amélioration.\nRB active les bonus de stats.\nConsomme des PM tant qu'active.",
        "Carte d'action de bouclier.\nRB active le bouclier équipé.\nConsomme des PM tant qu'active.",
        "Carte d'action d'arme.\nRB active l'arme équipée.\nCoûte des PM à chaque attaque.",
        "Carte d'action de projectile.\nRB active les tirs du fouet.\nCoûte des PM à chaque coup.",
        "Carte d'action explosive.\nRB lance le sort directement.\nCoûte des PM à chaque sort.",
        "Carte d'action de résistance.\nRB active une résistance.\nConsomme des PM tant qu'active.",
        "Carte d'action de familier.\nRB active le familier équipé.\nCoûte des PM à chaque attaque.",
        "Carte d'action d'invocation.\nRB lance l'invocation équipée.\nCoûte des PM par invocation.",
        "Carte d'action spéciale.\nSalamandre : RB lance Item Crash.\nSinon : RB active l'effet.")),
 'es':('Carta de acción. Combínala con\nuna carta de atributo. RB: DSS.\nGasta PM con cada latigazo.',
       'Carta de atributo. Combínala con\nuna carta de acción para el DSS.\nMás copias, combinación más fuerte.',
       ('Carta de acción de mejora.\nRB activa mejoras de atributos.\nGasta PM mientras está activa.',
        'Carta de acción de escudo.\nRB activa el escudo equipado.\nGasta PM mientras está activa.',
        'Carta de acción de arma.\nRB activa el arma equipada.\nGasta PM con cada ataque.',
        'Carta de acción de proyectil.\nRB activa los disparos del látigo.\nGasta PM con cada latigazo.',
        'Carta de acción explosiva.\nRB lanza el hechizo directamente.\nGasta PM con cada hechizo.',
        'Carta de acción de resistencia.\nRB activa una resistencia.\nGasta PM mientras está activa.',
        'Carta de acción de familiar.\nRB activa el familiar equipado.\nGasta PM con cada ataque.',
        'Carta de acción de invocación.\nRB lanza la invocación equipada.\nGasta PM con cada invocación.',
        'Carta de acción especial.\nSalamandra: RB lanza Item Crash.\nOtras: RB activa el efecto.')),
 'it':("Carta azione. Da abbinare a una\ncarta attributo. RB: DSS.\nConsuma PM a ogni frustata.",
       "Carta attributo. Da abbinare a una\ncarta azione per il DSS. Più\ncopie rendono la coppia più forte.",
       ("Carta azione di potenziamento.\nRB attiva i bonus alle statistiche.\nConsuma PM finché è attiva.",
        "Carta azione scudo.\nRB attiva lo scudo equipaggiato.\nConsuma PM finché è attiva.",
        "Carta azione arma.\nRB attiva l'arma equipaggiata.\nConsuma PM a ogni attacco.",
        "Carta azione proiettile.\nRB attiva i colpi della frusta.\nConsuma PM a ogni frustata.",
        "Carta azione esplosiva.\nRB lancia l'incantesimo subito.\nConsuma PM a ogni lancio.",
        "Carta azione resistenza.\nRB attiva una resistenza.\nConsuma PM finché è attiva.",
        "Carta azione famiglio.\nRB attiva il famiglio equipaggiato.\nConsuma PM a ogni attacco.",
        "Carta azione evocazione.\nRB lancia l'evocazione.\nConsuma PM a ogni evocazione.",
        "Carta azione speciale.\nSalamandra: RB lancia Item Crash.\nAltre: RB attiva l'effetto.")),
 'ja':('アクションカード。属性カードと\n組み合わせ、RBでDSSを切替。\nムチ攻撃ごとにMPを消費。',
       '属性カード。アクションカードと\n組み合わせてDSSを使う。\n枚数が多いほど効果が強まる。',
       ('強化のアクションカード。\nRBで能力強化を切替。\n発動中はMPを消費し続ける。',
        '盾のアクションカード。\nRBで装備中の盾を切替。\n発動中はMPを消費し続ける。',
        '武器のアクションカード。\nRBで装備中の武器を切替。\n攻撃ごとにMPを消費。',
        '飛び道具のアクションカード。\nRBでムチの飛び道具を切替。\nムチ攻撃ごとにMPを消費。',
        '爆発のアクションカード。\nRBで魔法を直接発動。\n発動ごとにMPを消費。',
        '耐性のアクションカード。\nRBでダメージ耐性を切替。\n発動中はMPを消費し続ける。',
        '使い魔のアクションカード。\nRBで使い魔を切替。\n使い魔の攻撃ごとにMPを消費。',
        '召喚のアクションカード。\nRBで召喚を発動。\n発動ごとにMPを消費。',
        '特殊のアクションカード。\nサラマンダー：RBでアイテムクラッシュ。\n他の組み合わせ：RBで効果を切替。')),
}
# The Japanese menu uses katakana card names; the others keep CotM's names.
JA_NAMES=dict(zip(('Venus','Jupiter','Mars','Diana','Apollo','Neptune','Saturn','Uranus','Pluto',
                   'Serpent','Mandragora','Golem','Cockatrice','Manticore','Griffin','Thunderbird','Unicorn','Black Dog'),
                  ('ヴィーナス','ジュピター','マーズ','ダイアナ','アポロ','ネプチューン','サターン','ウラヌス','プルート',
                   'サーペント','マンドラゴラ','ゴーレム','コカトリス','マンティコア','グリフォン','サンダーバード','ユニコーン','ブラックドッグ')))
assert set(CARD_RULES)==set(LANGS)
for lang in LANGS:
    mercury,attribute,actions=CARD_RULES[lang]
    assert len(actions)==9 and all(len(t.splitlines())<=3 and max(map(len,t.splitlines()))<=40 for t in (mercury,attribute,*actions)),lang
    name=(lambda n: JA_NAMES.get(n,n)) if lang=='ja' else (lambda n: n)
    rows=list(TEXT[lang])
    rows[0]=(rows[0][0],mercury)
    for i in range(1,10): rows.append((name(ATTRIBUTES[i]),attribute))
    rows[1]=(rows[1][0],attribute)
    for n,text in zip(('Venus','Jupiter','Mars','Diana','Apollo','Neptune','Saturn','Uranus','Pluto'),actions):
        rows.append((name(n),text))
    TEXT[lang]=tuple(rows)
venus=('STR 112%; 4 MP/sec.','DEF +25%; 4 MP/sec.','LCK +25%; 4 MP/sec.','DEF +2% per owned card (max 40%).\n16 MP/sec.','Walking: +1 XP/min per equipped skill.\n2 MP/sec.','Heart MP x2; 2 MP/sec.','INT +25%; 4 MP/sec.','ATK +2% per owned card (max 40%).\n16 MP/sec.','DEF x2, STR 71%; 8 MP/sec.','STR 141%, DEF half; 8 MP/sec.')
# One localized resource per action/attribute pair. The runtime selects the
# text ID using Nathan's current equipped Action Card; no global text mutation.
PAIR_DESCRIPTIONS=[]
for action in ACTIONS:
    for i,attribute in enumerate(ATTRIBUTES):
        if action=='Mercury':
            effect=f'{ELEMENTS[i]} Whip; STR {STR[i]}%.'
            if i==8: effect+=' Heals 1% HP.'
            effect+=f'\n{COSTS[i]} MP/swing.'
        elif action=='Venus':
            effect=venus[i]
        elif i==0 and action in ('Jupiter','Mars','Diana','Apollo','Neptune','Saturn','Pluto'):
            effect={
                'Jupiter':'Two orbiting flame shields.\n4 MP/sec.',
                'Mars':'Fire sword; 110% attack power.\n8 MP/swing.',
                'Diana':'Whip launches a fireball.\n32 MP/swing.',
                'Apollo':'Throw a fire bomb.\n20 MP/bomb.',
                'Neptune':'Fire damage reduced by 50%.\n3 MP/sec.',
                'Saturn':'Bat familiar shoots when you attack.\n4 MP/shot.',
                'Pluto':'Item Crash from your B subweapon.'}[action]
        elif action=='Jupiter' and i==6:
            effect='Shields Nathan while moving.\n4 MP/sec.'
        elif action=='Pluto' and i in (2,4,7):
            effect={2:'Subweapon mastery XP +20%.\n4 MP/sec.',4:'DEF +1%/6 min as Nathan (max 20%).\n8 MP/sec.',7:'ATK +1%/6 min as Nathan (max 20%).\n4 MP/sec.'}[i]
        elif action=='Uranus':
            effect=('Summon fire across nearby enemies.','Summon ice; freezes nearby enemies.','Summon a burst of plant energy.','Summon falling rocks.','Summon petrifying stone attacks.','Summon a cloud of poison.','Summon a sweeping wind attack.','Summon nearby lightning strikes.','Heals you and nearby allies for 16% HP.','Summon darkness; hits heal 1% HP.')[i]
            effect+=f'\n{(160,120,100,100,200,80,100,200,100,100)[i]} MP/cast.'
        else:
            descriptions={
              'Jupiter':('Two flame shields.','Four fast orbiting ice shields.','Recover HP while standing still.','Extended post-hit invulnerability.','Stone immunity; movement slowed.','Damaging poison mist.','Shield while moving.','Incoming damage is halved.','Holy barrier blocks enemy shots.','Dark cloud; poisons Nathan.'),
              'Mars':('Fire sword.','Fast ice sword.','Large plant sword.','Hammer plus a ground quake.','Stone blades.','Poison claws strike twice.','Hold X to charge a long slash.','Tap X repeatedly for a combo.','Long holy sword.','Slow, powerful dark gun.'),
              'Diana':('Fireball on whip extension.','Short-range ice shards pierce enemies.','Three drifting petal plumes.','Piercing earth wave follows the ground.','Three arcing petrifying stones.','Sticky poison blob hits repeatedly.','Fast piercing wind shot.','Lightning while spinning the whip.','Homing holy orb; repeated hits.','Eight piercing dark shots burst outward.'),
              'Apollo':('Fire bomb.','Ice orb bursts into eight shards.','Flower leaves a damaging leaf trail.','Five spears rise from the ground.','Six falling stone meteors.','Lingering poison cloud.','Tornado fires wind projectiles.','Lightning orb sticks to its target.','Rain of holy lances.','Large homing dark orb.'),
              'Neptune':('Fire damage reduced by 50%.','Ice damage reduced by 50%.','Slash damage reduced by 50%.','Strike damage reduced by 50%.','Stone damage reduced by 50%.','Poison damage reduced by 50%.','Pierce damage reduced by 50%.','Lightning damage reduced by 50%.','Holy damage reduced by 50%.','Dark damage reduced by 50%.'),
              'Saturn':('Bat shoots fireballs.','Ghost attacks nearby enemies.','Owl shoots when Nathan attacks.','Hawk dives into enemies.','Medusa fires petrifying shots.','Mist attacks enemies behind Nathan.','Fairy shoots while the whip spins.','Electric hawk dives into enemies.','Angel throws knives during spins.','Devil: spin longer for stronger shots.'),
              'Pluto':('Item Crash.','Extra subweapon; excludes Cross.','Subweapon mastery XP +20%.','A shadow mirrors attacks.','Defense grows with Nathan playtime.','Subweapon MP costs reduced by 50%.','Double movement speed.','Attack grows with Nathan playtime.','Invincible; attacks deal no damage.','Skeleton: any hit kills; rare big bone.')}
            effect=descriptions[action][i]
            if action=='Mars':effect+=f'\n{(8,4,10,4,12,8,16,16,32,32)[i]} MP/attack.'
            elif action=='Diana':effect+=f'\n{(32,64,96,16,16,16,128,12,48,32)[i]} MP/use.'
            elif action=='Apollo':effect+=f'\n{(20,20,40,30,60,10,60,80,80,120)[i]} MP/cast.'
            elif action=='Saturn':effect+=f'\n{(4,4,4,4,6,8,8,16,32,4)[i]} MP/attack.'
            elif action=='Neptune':effect+='\n3 MP/sec.'
            elif action=='Jupiter':effect+=f'\n{(4,4,16,4,8,4,4,4,8,8)[i]} MP/sec.'
            elif action=='Pluto' and i!=5:effect+=f'\n{(0,4,4,8,8,0,4,4,20,5)[i]} MP/sec.'

        PAIR_DESCRIPTIONS.append(f'{action} + {attribute}\n{effect}')
# Keep displayed costs and runtime generated tables on the same policy.
TEXT={lang:tuple((name,balance_description(text)) for name,text in rows) for lang,rows in TEXT.items()}
PAIR_DESCRIPTIONS=[balance_description(text) for text in PAIR_DESCRIPTIONS]
# The menu shows a pair's cost natively ("MP n" on the description's bottom
# line, like souls and subweapons; 823E4AB0 kind 1), so the text carries no MP
# line. The unit (per second, swing, cast...) is in each Action Card's text.
# Native MP is a whole number: fractional upkeep rounds to nearest, at least 1.
# 0 = no MP shown (Pluto + Manticore). Item Crash's 0 is replaced at runtime
# by the equipped B subweapon's crash cost (nathan_dss_damage.cpp, 823E4AB0).
_MP=re.compile(r'(?:; |\n)(\d+(?:\.\d+)?) MP/\w+\.')
PAIR_MENU_MP=[]
for _i,_text in enumerate(PAIR_DESCRIPTIONS):
    _found=_MP.findall(_text); assert len(_found)<=1,_text
    PAIR_MENU_MP.append(max(1,math.floor(float(_found[0])+.5)) if _found else 0)
    PAIR_DESCRIPTIONS[_i]=_MP.sub(lambda m:'.' if m[0].startswith(';') else '',_text)
    assert 'MP/' not in PAIR_DESCRIPTIONS[_i],PAIR_DESCRIPTIONS[_i]
def write_menu_header():
    p=ROOT/'.setup/package/src/src/nathan_dss_menu.h'
    rows=['#pragma once','// Generated by modding/tools/nathan_cards.py; do not hand-edit.',
          '// MP shown on each pair\'s menu description (action*10+attribute); 0 = none.',
          'namespace harmony::nathan {',
          'constexpr unsigned kPairMenuMp[100]={'+','.join(map(str,PAIR_MENU_MP))+'};','}']
    p.write_text('\n'.join(rows)+'\n');return p
# (text index, icon, soul type, permission). Reserve obsolete item 0x6D8
# as inaccessible so old-save cleanup can never delete the new Venus card.
# Icons: the game's two soul icons (23 action, 22 attribute) unless
# nathan_card_icons.py has built card icons into Nathan's own icon sheets.
_ICON_CELLS=hodpaths.legacy('modding/build/nathan_card_icons/cells.json')
_cells=json.loads(_ICON_CELLS.read_text()) if _ICON_CELLS.exists() else {}
def _icon(name,default):
    cell=_cells.get(name,default);assert 0<=cell<128;return cell
CARD_RECORDS=tuple((i,_icon('Mercury',23) if i==0 else _icon(ATTRIBUTES[i-1],22),14 if i==0 else 3,MASK) for i in range(11))+((0,0,0,0),)+tuple((11+i,_icon(ACTIONS[1+i],23),14,MASK) for i in range(9))

# Soul row order: Mercury, ten attributes, the retired Card Swap row, then
# the other nine action cards.
CARD_NAMES=('Mercury',*ATTRIBUTES,None,*ACTIONS[1:])
assert len(CARD_NAMES)==len(CARD_RECORDS) and set(CARD_CHESTS['ranks'])=={n for n in CARD_NAMES if n}
assert all(0<=r<=10 or 101<=r<=407 for r in CARD_CHESTS['ranks'].values()) and 1<=CARD_CHESTS['weight']<=0x7fff
BOSS_CARDS={n for c in BALANCE_CONFIG['boss_chests']['chests'] for n in c['cards']}
# Every card must be obtainable exactly one way: an ordinary-chest rank or a boss chest.
ENEMY_CARDS={d['card'] for d in BALANCE_CONFIG['enemy_cards']['drops']}
assert all((CARD_CHESTS['ranks'][n]>0)+(n in BOSS_CARDS)+(n in ENEMY_CARDS)==1 for n in CARD_NAMES if n)
# The two-drops-per-enemy rule is enforced by nathan_card_drops.py, which owns the enemy tables.

def write(rel,data):
    p=STAGE/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data)

def build():
    write_header(); write_menu_header()
    # Existing DLC soul ranges are 0..89, within the reserved 200-soul space.
    ranges=[]
    for p in [ROOT/'assets/data/player/soulset.dat',*list((ROOT/'.setup/package/src/assets/dlc').rglob('soulset_dlc*.dat'))]:
        if p.name=='soulset_dlc17.dat': continue
        b=p.read_bytes(); assert b[:4]==b'SOUL'
        n,first=struct.unpack_from('>II',b,8); ranges.extend(range(first,first+n))
    assert max(ranges)==FIRST-1 and FIRST+len(CARD_RECORDS)<=200
    # Text IDs use the mod's existing package-17 namespace and skill groups.
    lengths=[]
    for lang in LANGS:
        rel=Path(f'data/text/textres17_{lang}.txrc'); doc=decode((SOURCE/rel).read_bytes())
        groups=doc['sections'][0]
        if groups[13] and groups[13][0] in tuple(TEXT[l][0][0] for l in LANGS):
            assert (len(groups[13]),len(groups[14])) in ((2,2),(11,11),(12,12),(20,20),(20,120),(21,121))
            groups[13]=[]; groups[14]=[]
        assert len(groups[13])==len(groups[14])==0,'Unexpected existing skill text: allocate new indices explicitly'
        assert len(groups[0])==len(groups[1]) and len(groups[0]) in (1,2)
        groups[0]=groups[0][:1]+['Card Swap']
        groups[1]=groups[1][:1]+['Hold Y to show equipped cards.\nLeft/Right: Action Card.\nUp/Down: Attribute Card.']
        for name,description in TEXT[lang]: groups[13].append(name); groups[14].append(description)
        groups[14].extend(PAIR_DESCRIPTIONS)
        assert (len(groups[13]),len(groups[14]))==(TACKLE_NAME_INDEX,TACKLE_DESCRIPTION_INDEX)
        groups[13].append(TACKLE_TEXT[lang][0]); groups[14].append(TACKLE_TEXT[lang][1])
        encoded=encode(doc); assert decode(encoded)==doc
        write(rel,encoded)
    entries=[]
    for index,icon,soul_type,permission in CARD_RECORDS:
        e=bytearray(60)
        struct.pack_into('>I',e,0,1)  # uncommon presentation tier
        struct.pack_into('>I',e,4,0x440d0000|index)
        struct.pack_into('>I',e,8,0x440e0000|index)
        struct.pack_into('>I',e,12,permission)
        # +0x10 is the soul TYPE, read by 8246EA48 and classified by
        # 8246EC70/823C96C8. Type 14 -> RB; type 3 -> passive.
        # +0x12 is the effect selector. +0x34 is only the inventory icon.
        struct.pack_into('>H',e,0x10,soul_type)
        struct.pack_into('>H',e,0x30,1)
        struct.pack_into('>H',e,0x34,icon)
        struct.pack_into('>H',e,0x38,1)
        entries.append(e)
    table=bytearray(b'SOUL'+struct.pack('>III',1,len(CARD_RECORDS),FIRST)+b''.join(entries)+bytes(4))
    # Chest loot (823A9CD0) reads the true 60-byte row, which starts 4 bytes
    # after each entry built above: rank at row +0x36, weight at row +0x38.
    for i,name in enumerate(CARD_NAMES):
        if name is None: continue
        rank=CARD_CHESTS['ranks'][name]
        struct.pack_into('>HH',table,20+60*i+0x36,rank,CARD_CHESTS['weight'] if rank else 0)
    table=bytes(table)
    write(Path('data/item/soulset_dlc17.dat'),table)
    # Y is secondary weapon slot 1. Its item must be WEPN, not SOUL (B skills).
    rel=Path('data/item/weaponset_dlc17.dat'); weapons=(SOURCE/rel).read_bytes()
    assert weapons[:4]==b'WEPN' and struct.unpack_from('>I',weapons,12)[0]==0x91
    primary=weapons[16:166];assert len(primary)==150
    utility=bytearray(primary)
    # No attack stats, elemental flags, skill effect, or weapon sprite.
    utility[0x0c:0x10]=bytes(4);utility[0x12:0x2a]=bytes(0x18)
    utility[0x44:0x54]=bytes(0x10);utility[0x54:0x94]=bytes([255])*64
    struct.pack_into('>I',utility,0x38,MASK)
    # Name/description indices: 823C8E24 / 823C91A8 read file +3C/+40.
    struct.pack_into('>II',utility,0x3c,1,1)
    write(rel,b'WEPN'+struct.pack('>III',3,2,0x91)+primary+utility+bytes(4))
    rel=Path('data/player/player_test12.def'); data=bytearray((SOURCE/rel).read_bytes())
    assert int.from_bytes(data[4:8],'big')==12
    flags=struct.unpack_from('>H',data,0x2c)[0]; assert flags in (0x4ffc,0x7ffc,0x7dfc,0x7efc)
    struct.pack_into('>H',data,0x2c,(flags|0x3300)&~3)  # card slots enabled; Y slot locked
    struct.pack_into('>II',data,0x60,MERCURY,SALAMANDER)
    for slot,default in zip(range(8,12),(0x614,0x610,0x612,0x611)):
        if struct.unpack_from('>I',data,0x30+slot*4)[0]==LEGACY_CARD_SWAP:
            struct.pack_into('>I',data,0x30+slot*4,default)
    struct.pack_into('>I',data,0x30+1*4,CARD_SWAP)
    # The 16-byte resource path ends at +0x8C ("nathan/p_nathan" fills it).
    assert data[COLLECTION] in (1,2) and data[COLLECTION-1]==0
    data=data[:COLLECTION]+struct.pack('>BBH',1,len(CARD_ITEMS),0)+b''.join(struct.pack('>I',item) for item in CARD_ITEMS)
    write(rel,data)
    report={'character_id':12,'equipment_permission_mask':hex(MASK),'first_soul_index':FIRST,
            'cards':[{'name':'Mercury','item_id':MERCURY,'slot':12,'menu_row':'Personal Skill / RB','soul_type':14,'icon':23},
                     {'name':'Salamander','item_id':SALAMANDER,'slot':13,'menu_row':'Enchantment Soul / passive','soul_type':3,'icon':22}],
            'definition_slot_mask':hex((flags|0x3300)&~3),'combat_effects_implemented':True,
            'native_runtime_required':['src/nathan_dss.cpp','src/nathan_dss_damage.cpp'],
            'source_evidence':{'definition_slot_flags':'8245D68C: flags -> 15 slot-enabled bytes',
                               'starting_equipment':'8245D6B0: copy 15 u32 defaults from record +0x2C',
                               'soul_category':'8246EA94: type at runtime +0x0C (file entry +0x10); 8246EC70/823C96C8 classify equipment row',
                               'soul_icon':'823C96C0: icon at runtime +0x30 (file entry +0x34)',
                               'permission':'823C9A60: soul character mask at runtime +8 (file entry +0x0C)',
                               'save_io':'8259CECC/8259D34C: raw 0x3B00 save block; no checksum/encryption'}}
    report['card_swap']={'item_id':CARD_SWAP,'slot':1,'category':'WEPN','locked':True}
    report['cards']=[{'name':'Mercury','item_id':MERCURY,'slot':12}]+[{'name':name,'item_id':SALAMANDER+i,'slot':13,'mp':balance_cost(COSTS[i]),'cotm_mp':COSTS[i],'str_percent':STR[i]} for i,name in enumerate(ATTRIBUTES)]
    report['cards'].extend({'name':name,'item_id':item,'slot':12,'combat_effects_implemented':True} for name,item in zip(ACTIONS[1:],NEW_ACTION_ITEMS))
    report['venus']={'disabled_attributes':[],'Manticore':'Double MP gained from heart pickups','drain':'CotM 16.16 MP/frame scaled by native GBA refresh rate and shared HoD MP scale','STR_percent':[112,100,100,100,100,100,100,100,71,141]}
    report['mp_balance']=BALANCE_CONFIG
    report['reserved_legacy_item_id']=LEGACY_CARD_SWAP
    (STAGE/'card_report.json').write_text(json.dumps(report,indent=2)+'\n')
    verify()
    print('Built all ten Nathan-only Action Cards and ten Attribute Cards.')

def verify():
    b=(STAGE/'data/item/soulset_dlc17.dat').read_bytes()
    assert len(b)==16+60*len(CARD_RECORDS)+4 and struct.unpack_from('>III',b,4)==(1,len(CARD_RECORDS),FIRST)
    for i,(text_index,icon,soul_type,permission) in enumerate(CARD_RECORDS):
        e=b[16+60*i:76+60*i]
        assert struct.unpack_from('>I',e,12)[0]==permission
        assert [c for c in range(1,17) if int.from_bytes(e[12:16],'big')&(1<<(c-1))]==([12] if permission else [])
        assert int.from_bytes(e[52:54],'big')==icon
        assert int.from_bytes(e[16:18],'big')==soul_type
        rank,weight=struct.unpack_from('>HH',b,20+60*i+0x36)
        name=CARD_NAMES[i]
        assert (rank,weight)==((CARD_CHESTS['ranks'][name],CARD_CHESTS['weight'] if CARD_CHESTS['ranks'][name] else 0) if name else (0,0)),(i,rank,weight)
        for lang in LANGS:
            groups=decode((STAGE/f'data/text/textres17_{lang}.txrc').read_bytes())['sections'][0]
            assert groups[13][text_index]==TEXT[lang][text_index][0] and groups[14][text_index]==TEXT[lang][text_index][1]
    for lang in LANGS:
        groups=decode((STAGE/f'data/text/textres17_{lang}.txrc').read_bytes())['sections'][0]
        assert len(groups[13])==21 and groups[14][20:120]==PAIR_DESCRIPTIONS and len(groups[14])==121
        assert groups[13][TACKLE_NAME_INDEX]==TACKLE_TEXT[lang][0] and groups[14][TACKLE_DESCRIPTION_INDEX]==TACKLE_TEXT[lang][1]
    assert all(len(t[1].splitlines())<=3 and max(map(len,t[1].splitlines()))<=40 for t in TACKLE_TEXT.values())
    assert len(PAIR_DESCRIPTIONS)==100
    assert all(len(t.splitlines())<=3 and max(map(len,t.splitlines()))<=40 for t in PAIR_DESCRIPTIONS)
    original=(SOURCE/'data/player/player_test12.def').read_bytes()
    new=(STAGE/'data/player/player_test12.def').read_bytes()
    assert len(new)==COLLECTION+4+4*len(CARD_ITEMS) and len(CARD_ITEMS)==20 and len(set(CARD_ITEMS))==20
    assert all(a==b for i,(a,b) in enumerate(zip(original[:COLLECTION],new[:COLLECTION])) if i not in {*range(0x2c,0x2e),*range(0x60,0x68),*range(0x34,0x38),*range(0x50,0x60)})
    assert struct.unpack_from('>BBH',new,COLLECTION)==(1,20,0)
    assert struct.unpack_from('>20I',new,COLLECTION+4)==CARD_ITEMS and LEGACY_CARD_SWAP not in CARD_ITEMS
    assert tuple(struct.unpack_from('>II',new,0x60))==(MERCURY,SALAMANDER)
    assert struct.unpack_from('>H',new,0x2c)[0]==0x7ffc
    assert struct.unpack_from('>I',new,0x34)[0]==CARD_SWAP
    assert struct.unpack_from('>I',new,0x50)[0]!=LEGACY_CARD_SWAP

def install(target,backup):
    changes=[]
    for src in STAGE.rglob('*'):
        if src.suffix not in ('.txrc','.def','.dat'): continue
        rel=src.relative_to(STAGE); dest=target/rel
        assert dest.resolve().is_relative_to(target.resolve())
        if dest.exists():
            out=backup/rel; out.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(dest,out)
        changes.append({'path':rel.as_posix(),'new_file':not dest.exists(),'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
    for entry in changes:
        src=STAGE/entry['path']; dest=target/entry['path']; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dest)
        assert dest.read_bytes()==src.read_bytes()
    (backup/'install_manifest.json').write_text(json.dumps(changes,indent=2)+'\n')
    print(f'Installed {len(changes)} verified card files: {target}')

def migrate_save(path,backup):
    if 'harmonyrecomp.exe' in subprocess.check_output(['tasklist','/fo','csv','/nh']).decode().lower():
        raise RuntimeError('Close HarmonyRecomp before save migration')
    old=path.read_bytes(); assert len(old)==0x3b00
    data=bytearray(old); equipment=0x28+11*15*4
    assert struct.unpack_from('>I',data,equipment)[0]==0xc4,'Unexpected Nathan equipment record'
    # Grant inventory without replacing the player's card selections.
    for item in (*range(MERCURY,SALAMANDER+10),*NEW_ACTION_ITEMS):
        p=0x3e8+item
        data[p]=(max(1,data[p]>>4)<<4)|(data[p]&15)|3
    for slot,default in zip(range(8,12),(0x614,0x610,0x612,0x611)):
        if struct.unpack_from('>I',data,equipment+slot*4)[0]==LEGACY_CARD_SWAP:
            struct.pack_into('>I',data,equipment+slot*4,default)
    struct.pack_into('>I',data,equipment+1*4,CARD_SWAP)
    data[0x3e8+CARD_SWAP]=(max(1,data[0x3e8+CARD_SWAP]>>4)<<4)|(data[0x3e8+CARD_SWAP]&15)|3
    data[0x3e8+LEGACY_CARD_SWAP]=0
    allowed={0x3e8+item for item in range(MERCURY,SALAMANDER+10)}|{0x3e8+CARD_SWAP,0x3e8+LEGACY_CARD_SWAP}|{0x3e8+item for item in NEW_ACTION_ITEMS}|set(range(equipment+4,equipment+8))|set(range(equipment+32,equipment+48))
    assert all(a==b for i,(a,b) in enumerate(zip(old,data)) if i not in allowed)
    backup.mkdir(parents=True,exist_ok=True); (backup/'savedata.dat').write_bytes(old)
    (backup/'save_change_manifest.json').write_text(json.dumps({'before_sha256':hashlib.sha256(old).hexdigest(),
            'after_sha256':hashlib.sha256(data).hexdigest(),'changes':[{'offset':i,'before':a,'after':b} for i,(a,b) in enumerate(zip(old,data)) if a!=b]},indent=2)+'\n')
    path.write_bytes(data); assert path.read_bytes()==data
    print('Granted DSS cards and equipped locked Card Swap on Y; other equipment/save bytes unchanged.')

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--install-source',action='store_true'); ap.add_argument('--install-active',action='store_true'); ap.add_argument('--migrate-save',action='store_true'); args=ap.parse_args()
    if not any(vars(args).values()): build(); return
    verify(); stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=hodpaths.legacy('modding/backups')/f'nathan_cards_{stamp}'; backup.mkdir(parents=True,exist_ok=True)
    if args.install_source:
        install(SOURCE,backup/'source')
        install(ROOT/'.setup/package/src/assets/dlc'/IDENT,backup/'build_assets')
    if args.install_active:
        install(Path.home()/'Documents/harmonyrecomp/0000000000000000/58410A7A/00000002'/IDENT,backup/'active')
    if args.migrate_save:
        migrate_save(Path.home()/'Documents/harmonyrecomp/B13EBABEBABEBABE/58410A7A/00000001/dchd_savedata/savedata.dat',backup/'save')
    print('Backup:',backup)

if __name__=='__main__': main()
