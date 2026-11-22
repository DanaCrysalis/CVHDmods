"""Build a self-contained report from the installed Nathan source snapshot."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap

from pathlib import Path

import base64, hashlib, html, json, re, sys

from datetime import datetime, timezone, timedelta

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

R=hodpaths.GAME

SRC=R/'.setup/package/src'; N=SRC/'src'; DOC=hodpaths.legacy('modding/docs')

IDENT='000000000000000000000000000000000C00001758'

PKG=SRC/'mods'/IDENT


from hodsprite import read_opd

E=html.escape

def c(s):return '<code>'+E(str(s))+'</code>'

def pre(s):return '<pre><code>'+E(s)+'</code></pre>'

def link(p,label=None):

    p=Path(p);return '<a href="'+E(p.as_uri(),quote=True)+'">'+E(label or str(p))+'</a>'

def table(head,rows):

    return '<div class="table"><table><thead><tr>'+''.join('<th>'+E(str(x))+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def pic(p,caption,cls=''):

    return '<figure class="'+cls+'"><img alt="'+E(caption)+'" src="data:image/png;base64,'+base64.b64encode(Path(p).read_bytes()).decode()+'"><figcaption>'+E(caption)+'</figcaption></figure>'

def note(s):return '<aside class="note">'+s+'</aside>'

sections=[]

def sec(id,title,body):sections.append((id,title,body))



sec('overview','Scope and installed snapshot',"""

<p>This report documents Nathan Graves as character 12 in the local HarmonyRecomp installation: the DLC package, ROM asset conversion, guest PPC patches, native C++ overrides, shared game hooks, equipment, persistence, audio, DSS and supporting tooling. It describes the installed state after the November 10, 2026 all-DSS first-pass update, including direct RB Apollo casts and Pluto/Salamander Item Crash.</p>

<div class="metrics"><div><b>112</b><span>body animation clips</span></div><div><b>6,592</b><span>OPD frames</span></div><div><b>96</b><span>body texture pages</span></div><div><b>20</b><span>DSS cards defined</span></div></div>

<p>Nathan began as an isolated, rebased Simon module. He now uses Circle of the Moon art, reconstructed timings, sounds, Hunter Whip, card equipment and DSS behavior. HoD supplies the underlying player states, native enemy combat, item model, renderer, audio mixer and normal save flow.</p>

"""+note("<strong>Evidence boundary.</strong> Current source and installed hashes take precedence over historical README sections and feature reports. Older counts, allocation sizes and disabled-card lists have been reconciled here. Without a pristine upstream repository, this is not an exhaustive diff of unrelated game infrastructure. Existing netplay, graphics/UI and general fixes are not attributed to Nathan development.")+table(['Action','Current support'],[

('Mercury','All 10 elemental whip pairs.'),('Venus','All 10 enhancements, including the three requested replacement effects.'),('Jupiter','All 10 shields and defensive enhancements; initial adapters.'),('Uranus','All 10 summons; RB casts directly.'),('Pluto','All 10 special effects; includes requested adaptations.'),('Mars, Diana, Apollo, Neptune, Saturn','All 10 pairs per action now have initial implementation paths; see the current limitations below.')])+"""

<p>All 100 pairs have activation and effect paths. This is an initial HoD implementation, not a claim of complete CotM behavior parity or live verification of every pair.</p>""")



sec('architecture','Architecture, package identity and deployment paths',"""

<div class="flow"><div>CotM ROM + local recomp<br><small>source pixels, scripts, palettes, sounds and mechanic evidence</small></div><span>↓</span><div>Python conversion tools<br><small>OPD / CSR / COL · SOUL / WEPN / DEF · TXRC · XACT</small></div><span>↓</span><div>Nathan guest module + native overrides<br><small>original states, PPC spin hooks, input, DSS, combat and rendering</small></div><span>↓</span><div>Game root + Documents DLC<br><small>backed-up deployment and native saving</small></div></div>

<p><code>harmonyrecomp_dllTest12.dll</code> compiles <code>src/nathan_dss.cpp</code>: allocation, lifecycle, update, motions, STR/INT/LCK and sound-bank callbacks. The main <code>harmonyrecomp.exe</code> compiles <code>src/nathan_dss_damage.cpp</code>: shared rendering/weapons, final DEF/ATK, menu stats, descriptions, mastery, shield and summon resolution.</p>

<p>Strong <code>sub_XXXXXXXX</code> symbols override generated weak guest functions. Originals remain callable as <code>__imp__sub_XXXXXXXX</code>. Nathan code lives outside <code>generated/</code> so regeneration preserves it. Most wrappers call the original and adjust a scoped result. Moving shield deliberately returns before the native incoming-hit transaction.</p>

"""+table(['Identity','Value'],[

('Package',c(IDENT)),('Character / namespace','Character 12; package namespace 17; internal name Test12.'),

('Guest / native module',c('dllTest12.dll')+' / '+c('harmonyrecomp_dllTest12.dll')),

('Image / player vtable',c('0x836C0000')+' / '+c('0x836C28E8')),

('Definition',c('data/player/player_test12.def')),('Body',c('data/opd/player/nathan/p_nathan.opd')+'; c_nath.col and Nathan CSR pages.'),

('Tables','weaponset_dlc17.dat, soulset_dlc17.dat and six textres17_*.txrc files.'),

('Banks','VX_NATHN and VXJ_NATHN, each with .xsb/.xwb files.')])+"""

<p>Both the definition and module must identify character 12. The in-level character-ID virtual method is entry 144 (+0x240); leaving the copied Simon return as 10 selects Simon's save record and weapon-sprite slot. This return was patched to 12. Definition sprite paths drive menus; the module has its own gameplay path, also redirected to Nathan. Native bank callbacks now provide unique voice paths.</p>

<p>Menu names/artwork occupy package 17. DDS menu art uses native big-endian A8R8G8B8 bytes and the reference layout produced by <code>make_menu_art.py</code>. The rebased module has a unique guest path and address; the loader rejects duplicate module paths.</p>

"""+table(['Role','Location'],[

('Source package',link(PKG)),('Build mirror',link(SRC/'assets/dlc'/IDENT)),

('Native build',link(SRC/'out/build/win-amd64-release')),('Game root',link(R)),

('Active DLC',link(Path.home()/'Documents/harmonyrecomp/0000000000000000/58410A7A/00000002'/IDENT)),

('Outputs / backups',link(hodpaths.legacy('modding/build'))+'<br>'+link(hodpaths.legacy('modding/backups')))])+"""

<p>The package is listed in <code>dlc_packages.txt</code> and uses a matching installed header under <code>Headers/00000002/</code>. Mounted package paths can collide; new art/audio names are unique. Shared equipment tables are patched in their original base/DLC locations rather than shadowed inside Nathan's package.</p>""")



sec('formats','Binary records, Hunter Whip and equipment access',table(['Format','Relevant layout'],[

('DEF','ID +0x04; text IDs +0x08…+0x10; slot mask +0x2C; 15 starting-equipment words +0x30; internal name +0x6C; sprite path +0x7C.'),

('WEPN','16-byte header, version 3, global index; 150-byte entries; 4-byte trailer. Permission +0x38; name/description +0x3C/+0x40; character weapon sprite IDs +0x54.'),

('SOUL','16-byte header, 60-byte entries. Permission +0x0C; native type +0x10; icon +0x34. Type controls equipment category, not icon.'),

('GURD / SWPN','Permission at entry +0x14 / +0x22. Character bit = 1 << (ID−1); Nathan = 0x800.'),

('TXRC','Encrypted string resources with section/group/string tables; txrc.py preserves the byte-key cipher.'),

('OPD / CSR / COL','Timeline, parts and hitboxes / indexed 4bpp textures / 256 palettes × 16 colors. COL bytes are B,G,R,pad.')])+"""

<p>Guest structures use big endian; <code>Read</code>, <code>Write</code> and float bit-casts centralize conversion. ROM records are little endian and decoded separately. Every guest address/offset here refers to the inspected local executable/module layout.</p>

<h3>Hunter Whip</h3>

<p>Nathan-only item <code>0xC4</code> is WEPN index <code>0x91</code>. His body frames already contain the visible whip. Weapon sprites <code>p_wpf0.opd</code>, <code>p_wpf1.opd</code> and <code>p_wpf2.opd</code> therefore have no drawing parts; hitboxes and timings retain native weapon combat without drawing a duplicate whip.</p>

<p>Normal swing/spin geometry is synchronized by <code>nathan_whip_hitboxes.py</code>, <code>nathan_spin_weapon.py</code> and <code>nathan_spin_hitboxes.py</code>. Mercury geometry fits the final composed elemental pixels. Long diagonals use short hitbox segments instead of filling empty space beneath the whip. Weapon clips 0/1 stay normal; clips 2–31 represent ten attributes × three poses, followed by held geometry.</p>

<h3>Normal hunter gear</h3>

<p><code>nathan_equipment_access.py</code> adds permission bit 0x800 to six base hunter subweapons (Knife, Axe, Holy Water, Cross, Ricochet Rock, Bible), five compatible DLC subweapons and 170 defensive items usable by the existing hunter group. Other characters' bits, item stats, IDs, prices and text remain intact. Access does not grant ownership.</p>""")



mapping=json.loads((hodpaths.legacy('modding/nathan_rom_mapping.json')).read_text())

ar=json.loads((hodpaths.legacy('modding/build/nathan_rom/animation_report.json')).read_text())

animrows=[]

for a in ar:

    d=mapping['slots'][str(a['slot'])]

    animrows.append((c(a['slot']),E(a['move']),str(d['source'])+(' (effect)' if d.get('family')=='effects' else ''),f"{a['frames']} / {a['ticks']}",E(d.get('adaptation','Native sequence / held pose as mapped.'))))

sec('animations','ROM reconstruction and player animation fixes',"""

<p>The source is the local USA AAME Circle of the Moon ROM, SHA-1 <code>d661b01eb94186435723ac03344792c11c20c522</code>. <code>&lt;research folder&gt;/tools/extract_cotm.py</code> verifies that hash before fixed-offset extraction. Indexed parts, origins, flips, scripts, palettes, effect metadata and audio metadata are exported under <code>&lt;research folder&gt;/extracted/cotm</code>. The ROM is read, not modified.</p>

<p>Source mechanic evidence comes from the local <code>&lt;research folder&gt;/research/cotm-recomp</code> and ARM/Thumb disassembly. Audio metadata alone is not mixed SFX: <code>render_cotm_audio.py</code> renders non-music numeric IDs with the local agbplay CLI; the DLC builder consumes PCM16 exports.</p>

<p>The authoritative map is <code>modding/nathan_rom_mapping.json</code>. The earlier sliced-sheet mapping and tools/nathan* sheet outputs are legacy material. <code>nathan_rom_animations.py</code> reconstructs 31 base clips, 138 frames and 7 original texture pages. It preserves part coordinates, priority, flips and finite script timing. Source 4095-tick values are hold sentinels, not literal 68-second actions. CotM runs at about 59.7275 Hz; the host timeline targets 60 Hz, with explicit adaptations recorded in the map.</p>

<h3>Behavior corrections</h3>

<ul><li><strong>Slide:</strong> all seven frames of native resource 22, fitted to HoD's 31-tick window, instead of dash/braking art.</li><li><strong>Crouch:</strong> motion 20 plays lowering clip 30 once; motion 21 holds a single lowered frame in clip 2.</li><li><strong>Rotation:</strong> standing resource 20 → clip 28 / motion 191; crouching resource 21 → clip 29 / motion 192; native frame delays preserved.</li><li><strong>Projectile slots 26/27:</strong> flight/impact art replaces mistaken death frames. Inherited shared shot code still controls behavior.</li><li><strong>HoD-only adaptations:</strong> death holds the final frame for cleanup; co-op, backdash, crouched throw, petrification/shake and recovery use documented native pose combinations.</li></ul>

<h3>Injected PPC spin code</h3>

<p><code>nathan_spin.py</code> adds a 0x200-byte executable <code>.nathan</code> section at <code>0x836EC000</code>. It patches setState vtable entry 86 at <code>0x836C2A40</code> and attack-state 23/24 updates at <code>0x836C2D6C</code>/<code>0x836C2D84</code>. Holding attack as the whip requests idle selects motion 191/192 and preserves phase 2. Release requests standing state 1 or crouching state 8 and phase 3; other interruptions delegate to the original setter.</p>

<p>A separate executable section is necessary for recompiler discovery; bytes appended after .text can be interpreted as import thunks. PPC changes require code generation and rebuilding the DLL. The crouch entry/hold correction is data-only.</p>

"""+'<details><summary>Complete 31-slot animation mapping</summary>'+table(['Slot','Host move','CotM resource','Frames / host ticks','Adaptation'],animrows)+'</details>')



from nathan_cards import ACTIONS, ATTRIBUTES, COSTS, STR, ELEMENTS

from nathan_dss_balance import CONFIG as BALANCE, cost as hod_cost

cardrows=[('Hunter Whip','0xC4','WEPN 0x91','X / slot 0'),('Card Swap','0xC5','WEPN 0x92','Y / slot 1'),('Mercury','0x6CD','SOUL 90','RB / slot 12')]

cardrows += [(name,hex(0x6CE+i),'SOUL '+str(91+i),'Attribute / slot 13') for i,name in enumerate(ATTRIBUTES)]

cardrows += [('Reserved obsolete Card Swap','0x6D8','SOUL 101, inaccessible','Migration only')]

cardrows += [(name,hex(0x6D9+i),'SOUL '+str(102+i),'RB / slot 12') for i,name in enumerate(ACTIONS[1:])]

sec('cards','Cards, Card Swap and contextual descriptions',table(['Item','Global item ID','Record','Equipment row'],[(E(a),c(b),E(d),E(e)) for a,b,d,e in cardrows])+"""

<p>All 20 cards are Nathan-only. SOUL contains 21 records because obsolete Card Swap ID 0x6D8 remains reserved/inaccessible. Venus starts at 0x6D9 so old-save cleanup cannot confuse it with the utility. New character defaults equip Mercury and Salamander. Additional cards were granted to the existing playtest save through explicit backed-up migrations.</p>

<h3>Fixed Y, editable B</h3>

<p>Card Swap is a utility WEPN, not a subweapon SOUL. It has no attack stats, element, attack sprite or ordinary weapon effect. Name/description use WEPN +0x3C/+0x40. Definition mask <code>0x7FFC</code> locks X/Y weapon rows, enables card rows and leaves B slots 8–11 editable. Those lower rows are B, Up+B, Right+B and Down+B—not extra Y slots.</p>

<p>Runtime input enforces Card Swap in slot 1 for old loadouts. Obsolete SOUL Card Swap in B slots is replaced only where present, using original defaults <code>0x614/0x610/0x612/0x611</code>. The final Y placement and unlocked B rows were user-confirmed.</p>

<p>The original card inventory problem came from classifying by icon. SOUL type at file +0x10 is the actual category input: native <code>823C96C8</code>/<code>8246EC70</code> routes type 14 to Personal Skill/RB slot 12 and type 3 to Enchantment slot 13. These reuse Soma's menu positions without enabling Soma's mechanics.</p>

<h3>In-game controls and persistence</h3>

<ul><li>Hold Y (logical 0x40) to display two cards above Nathan.</li><li>Left/Right (1/2) cycles Action; Up/Down (4/8) cycles Attribute. Press edges advance once, wrap and skip unowned/wrong-character/wrong-category items. Opposite directions cancel.</li><li>Candidate scanning covers the native 200-SOUL range and uses native permission/category queries; future correctly typed owned cards join automatically.</li><li>Y, RB and selection directions are consumed during the inherited update, then restored in its input block. Swapping suppresses RB activation. Changing the pair disables its previous effect.</li><li>Selections update live equipment and Nathan's normal in-memory save record; disk persistence remains with native saving.</li></ul>

<h3>Full-size card artwork</h3>

<p><code>nathan_card_swap_assets.py</code> decodes the original 64×96 illustrations from ROM LZ77 pointer table <code>0x0866CFEC</code>, palettes <code>0x0866D03C</code>. The runtime draws them at half scale (32×48 world units), replacing reliance on small menu thumbnails. Forty frames use palette rows 200–219. A separate 192-byte sprite-instance copy has its render-packet cache and reflection cleared, preserving Nathan's body packet.</p>

<h3>Action-dependent descriptions</h3>

<p><code>nathan_cards.py</code> writes 20 names and 120 descriptions per resource: 20 general descriptions plus 100 pair texts. Shared getter <code>823C90C0</code> selects the equipped Action's package-local description using <code>0x440E0000 + 20 + actionIndex×10 + attributeIndex</code>. It does not mutate global text. Attribute descriptions omit the repeated RB-toggle instruction; Action descriptions explain activation. Pair text is checked for at most three lines and 40 characters per line.</p>

"""+note('Six language resource files are structurally populated and verified. Newer DSS descriptions are largely English in those files; this is not a claim of complete translation quality.')+

pic(hodpaths.legacy('modding/build/nathan_firewhip/card_swap_preview.png'),'Builder preview of the original larger DSS illustrations used by Card Swap.'))



sec('state','DSS update flow and MP accounting',"""

<p>The controller uses remapped game actions, not physical controller bits. Personal Skill/RB is <code>0x100</code> in the character input block; physical XInput RB 0x200 is not the same mask. Early activation also failed because <code>player+60</code> (decimal, +0x3C) was treated as an entity handle; live inspection showed a numeric context/player index. Input instead comes through the standing-state pointer at <code>player+0x60</code> (hexadecimal, +96 decimal), then state+12. Owner lookup derives the entity from the persistent motion-table destination and validates its player link.</p>

<p><code>DssState</code> stores enabled state, previous RB, motion-table pointer, paid swing, pulse/cast/fade times, drawn/canonical frame and draw count, attribute, held-whip time and Action. Runtime enum order is Mercury=0, Venus=1, Uranus=2, Jupiter=3, Pluto=4, Unavailable=5; it differs from menu card order.</p>

<p>Update order: read equipment/input → process Card Swap → select/validate the pair → handle RB, life and MP → pay drain/new summon → select animations/sounds → suppress inherited input → run native update → anchor live summon → update progression/whip/audio → restore input. Native damage, status and recovery timers continue running.</p>

<ul><li><strong>Mercury:</strong> enabling is free but requires enough MP for one swing. Motion entry 187–190 pays once. Rotations 191/192 do not repeatedly charge. An unaffordable new swing disables DSS; a paid swing that spends the last MP retains its element until it ends.</li><li><strong>Venus/Jupiter/Pluto:</strong> RB toggles, activation requires at least 1 MP, and elapsed-time drain continues while enabled. Low MP disables the pair.</li><li><strong>Uranus:</strong> a new RB edge pays its entire cost once. Held RB cannot repeat/cancel/refund the summon.</li><li><strong>Invalidation:</strong> card/weapon changes, death and lifecycle resets disable active DSS. Enabled flags/timers are transient, not new saved fields.</li><li><strong>Same-frame switch fix:</strong> changing either card counts as a new activation even if the old pair was enabled, preventing a card-switch/RB update from skipping summon payment.</li></ul>

<p>A jumping whip stays recognized in jump/fall states 11–16 as well as grounded attack states 23–25 while whip motion 187–192 remains active. The earlier grounded-only check removed the fire effect on the first airborne update.</p>

<p><code>Animations()</code> rewrites only the owner's private 268-entry motion table, using immutable original <code>0x836C1DD0</code> as its base. Toggling one Nathan cannot rewrite another player's table. Stat wrappers adjust derived results/menu output rather than accumulating changes into stored base stats.</p>""")



resources=[54,57,60,66,63,78,69,72,75,81]

merrows=[]

for i,a in enumerate(ATTRIBUTES):

    extra='1% max HP per paid swing' if i==8 else 'Held extension strength 63%' if i==6 else 'Held extension strength 1%' if i==7 else ''

    merrows.append((E(a),E(ELEMENTS[i]),hod_cost(COSTS[i]),str(STR[i])+'%',str(resources[i])+'–'+str(resources[i]+2),extra))

sec('mercury','Mercury: ten elemental whips',table(['Attribute','Appearance / element','MP/swing','STR','Native body IDs','Additional behavior'],merrows)+"""

<p>MP/STR profiles come from CotM table <code>0x080E47E8</code>, ten 12-byte records (MP +6, STR percent +8). <code>nathan_mercury_assets.py</code> composes body/effect banks 0–9 at the union of native frame endpoints, retaining intermediate changes from both scripts.</p>

<p>Fire clips 31–34 and hand-cast clip 35 keep stable indices. Clip 36 is dedicated airborne fire. Slots 37–81 add the other nine elemental attack/hold sets. Generated <code>kMercurySlots[10][6]</code> routes motions 187–192 for standing, crouching, airborne and held attacks.</p>

"""+table(['HoD collision flag','Attribute'],[(c('0x100'),'Salamander/fire'),(c('0x200'),'Serpent/ice'),(c('0x400'),'Thunderbird/lightning'),(c('0x800'),'Unicorn/holy'),(c('0x1000'),'Black Dog/dark'),(c('0x2000'),'Manticore/poison'),(c('0x8000'),'Cockatrice/stone'),('Physical','Mandragora/plant, Golem/earth, Griffin/wind')])+"""

<p>The weapon flag getter ORs the element into native flags only for an active paid Nathan Hunter Whip attack. Faction flags remain intact. Live-hit refresh reapplies flags as the weapon updates. Held Griffin/Thunderbird scaling uses the cached native hit field; HoD's normal damage system determines final enemy damage.</p>

"""+note('<strong>Adaptations:</strong> HoD has no separate plant/earth/wind resistance type. Existing HoD poison/freeze/petrification rules apply, not CotM-specific status thresholds. Independent Manticore cloud projectiles are absent. Most non-fire held extensions adapt HoD controls rather than porting every original CotM child actor.')+

pic(hodpaths.legacy('modding/build/nathan_firewhip/mercury_comparison.png'),'Generated Mercury body/effect comparison from native ROM resources.'))



venus=[('Salamander','STR 112%','4'),('Serpent','Final physical DEF +25%','4'),('Mandragora','LCK +25%','4'),('Golem','DEF +2% per distinct owned DSS card, maximum +40%','16'),('Cockatrice','1 mastery XP/minute of actual walking per distinct equipped subweapon','2'),('Manticore','Double positive MP gain from heart pickups','2'),('Griffin','INT +25%','4'),('Thunderbird','Physical ATK +2% per distinct owned DSS card, maximum +40%','16'),('Unicorn','DEF ×2; STR 71%','8'),('Black Dog','STR 141%; DEF ×0.5','8')]

sec('enhancements','Venus, Jupiter and Pluto enhancements',"""

<h3>Venus combinations</h3>"""+table(['Attribute','Effect while DSS is active','CotM MP/sec (HoD runs at x0.25)'],venus)+"""

<p>Golem, Cockatrice and Thunderbird replace previously disabled pairs. Manticore uses the requested heart-MP adaptation. The other Venus stat profiles retain their source behavior. STR/INT/LCK use the correct native getters and the specified floor rounding.</p>

<h3>Jupiter and Pluto additions</h3>"""+table(['Combination','Effect','CotM MP/sec (HoD runs at x0.25)'],[

('Jupiter + Griffin','Shield while moving with horizontal input; native effect 026 wind artwork.','4'),

('Pluto + Mandragora','20% more native subweapon mastery XP.','4'),

('Pluto + Cockatrice','DEF +1% per six minutes as Nathan; maximum +20%.','8'),

('Pluto + Thunderbird','Physical ATK +1% per six minutes as Nathan; maximum +20%.','4')])+pre(

'ownedCards = number of the 20 DSS inventory entries with quantity > 0\n'

'cardBonus = 0.02 × min(20, ownedCards)\n'

'timeBonus = 0.01 × min(20, floor(NathanPlaySeconds / 360))\n'

'boostedDEF = nativeFinalPhysicalDEF × (1 + matchingBonus)\n'

'boostedATK = nativePhysicalATK × (1 + matchingBonus)')+"""

<p>Stack quantities do not multiply card bonuses. Full ownership yields +40%; the playtime cap is reached at two hours. Nathan time uses his native saved character-time record plus current allocation elapsed time. If native time flushes during a stage, the baseline absorbs only excess growth to prevent double counting. No new save schema is allocated.</p>

<h3>Walking and mastery rules</h3>

<p>Movement detection requires a live initialized Nathan, exactly one horizontal direction, state 1–16, actual horizontal displacement greater than 0.01 and below 16 world units, and vertical displacement below 16. Walking mastery additionally requires state ≤9 and an original motion mapped to walk clip 1. Standing or pushing against a wall earns nothing.</p>

<p>Only owned native subweapons in B slots 8–11 count; duplicate equipped items are deduplicated. Every completed 60 seconds grants each distinct equipped skill one XP, capped at 99,999. Partial walking time survives temporary inactivity within the same allocation.</p>

<p>Pluto/Mandragora measures the native award's actual XP delta after equipment modifiers, then adds one extra XP for every five awarded XP. Separate remainder bytes per skill retain fractions. Other award categories, inactive pairs and unrelated characters receive no bonus. Partial bonus carry is session state, not a new persisted record.</p>

<h3>Moving shield</h3>

<p>Jupiter/Griffin checks cached real movement plus current horizontal input before intercepting <code>8244BF10</code>. It returns the native ignored-hit value (-1) before HP loss, knockback, statuses and feedback. Negative-power healing still executes normally. Idle/wall input does not shield. Three native wind frames cycle in an independent overlay.</p>

<h3>Combat stats and the separate menu summary</h3>

<p>Initial Venus/Serpent code did not change the DEF used for incoming damage. The corrected hook is <code>82451AA8</code>, final armor + CON/2 after native modifiers, called by incoming damage helper <code>82452198</code>. Physical ATK bonuses wrap <code>82452658</code>. Menu/status routine <code>8245D9A0</code> builds a separate summary and receives the same DEF/ATK factors.</p>

<p>Summary offsets are HP/MP +0/+4, max HP/MP +8/+0xC, primary/secondary ATK +0x10/+0x14, DEF +0x18, STR/INT/CON/MND/LCK +0x1C…+0x2C. Heart doubling is scoped to <code>8245BCA8</code> → <code>8244E3C8</code>; passive regen, potions and other MP restoration remain native.</p>

<p class="fine">These rates are the original CotM values; Nathan drains at a quarter of them in HoD. Fixed-point rates 2184/4368/8736/17472 divided by 65,536 and multiplied by 59.72750057 Hz yield approximately 1.9904/3.9808/7.9617/15.9233 MP/sec. Drain uses elapsed time, not update count.</p>""")



ucost=[hod_cost(v) for v in BALANCE['cotm_costs']['Uranus']]

power=['1.00','1.00','1.12','1.12','1.10','0.71','0.84','1.32','—','0.22']

sounds=[350,351,352,350,350,353,353,354,352,354]

sec('uranus','Uranus summons: ROM particles, repeated hits and recovery',"""

<p>A new RB edge starts a 448-tick (about 7.50-second) cast and pays once. The timeline includes a 54-tick casting entrance and the original controllers' complete particle tail. CotM's Uranus table gives no passive stat bonus. Held RB cannot repeat or cancel the cast.</p>"""+table(['Attribute','MP/cast','Magic power multiplier','Sound','Behavior'],[

(E(a),ucost[i],power[i],sounds[i],'One 16% max-HP recovery with native green feedback; ally heal area' if i==8 else 'Visible passing body starts target-following drain phases; repeat damage and native green recovery' if i==9 else 'Original particle motion and frames; one moving native attack per visible particle') for i,a in enumerate(ATTRIBUTES)])+"""

<h3>Original controllers and sprite art</h3>

<p><code>trace_cotm_summons.py</code> executes the original USA ROM's Thumb summon controllers, child factories and animation scripts with Unicorn ARM. Allocators, sound output and the HP-popup helper are substituted. No enemies or terrain contacts are injected into the isolated trace. Recorded positions, spawn cadence, frame selection and inverse affine scale replace the earlier authored emitters and measured core paths. Resources 80–89 supply the original indexed art; Nathan still uses floating resources 87/89/90.</p>

<p>Each particle frame is clipped to a local 320×192 view. Creature scaling uses the GPU, avoiding a separate texture for every scale. Current body: 7,249 frames, 112 clips and 82 total texture pages (75 generated, compared with 89 previously). The body/card frames, palette rows and older DSS art are checked separately for preservation.</p>

<h3>Transparency and rendering limits</h3>

<p>Ordered Bayer coverage has been removed. Private scratch sprites use native HoD alpha material 0 and opacity 0.75, with independent tint and zero inherited mirror pivot for scaled creature draws. Opacity is a video-matched adaptation, not a recovered GBA blend-register trace. Unicorn's light column remains a small procedural background-effect adaptation, with smooth intensity at its edges, additive blending and a real alpha entrance/exit. Full-screen GBA palette flashes are not reproduced.</p>

<h3>Visible, repeated attack regions</h3>

<p>The four large offensive waves are removed. Each visible particle receives an 832-byte native attack actor. Tight opaque sprite bounds, including the traced scale and clipping, drive its moving AABB. These are rectangular bounds, not per-pixel collision masks. The actor's origin follows the particle center so the game's region lookup does not register every particle at Nathan's feet.</p>

<p>Registration runs in native preparation (<code>824823A0</code>); resolution runs later (<code>824827F0</code>). A narrow optional preparation hook in the shared Shield Rod dispatcher routes Nathan's tagged actors without changing Shield Rod behavior. Cast generations, native owner handles, particle disappearance, death and stage exit retire stale actors. Repeated hits use the native target cooldown with a 12-CotM-tick interval (about 0.201 seconds). Separate particle keys avoid the whip and Shield Rod keys. The actual native repeat gate and timer are executed in the harness.</p>

<h3>Black Dog and healing</h3>

<p>Black Dog uses its original aura and collapse frames at a contacted enemy, tracked by a native generation handle. Up to eight target effects fit in unused space in the existing 8,192-byte Nathan component. To honor visible damage regions, contact begins from the visible passing creature rather than CotM's invisible eight-position screen scanner. This is an explicit HoD adaptation. Contact hit actors follow the aura's animation and retire when it ends.</p>

<p>Unicorn retains its single 16% max-HP heal and native ally healing rectangle. Recovery goes through <code>SummonHeal()</code>, which clamps to missing HP and calls native popup <code>82454000</code> with a negative recovery amount. Full HP produces no popup. The offensive particle changes do not turn Unicorn into an attack.</p>

<p>See <a href="Nathan_Summon_Animation_Audit.html">the summon audit</a> for previews, source addresses, verification and remaining limits. Live gameplay and peer replay still need user verification.</p>

""")



sec('palette','Palette encoding, DSS pulse and color option 8',"""

<p>The blue Nathan/fire/gold problem came from treating COL bytes as RGB. Native order is <code>B,G,R,pad</code>. Fixing <code>hodsprite.py</code>'s read/write boundary and rebuilding restored correct normal/fire/gold colors while keeping correctly encoded assets byte-exact on round trip.</p>

<p>Ordinary DSS uses standing hand-cast resource 53 in slot 35, at 52 host ticks, including its brief blue outline. Uranus independently uses floating resources 87/89/90.</p>

<p>The pulse follows CotM palette table <code>0x080E0558</code>: normal <code>0x08456464</code>, gold <code>0x08456524</code>, phase increment 4 per GBA tick, reflect at 256 and wrap at 512. Its 128-tick cycle is approximately 2.143 seconds. There are 64 gold blend levels and 16 white fade levels; disable uses the requested white flash over 32 GBA ticks.</p>

<p>The first pulse attempt modified player+28, an animation-event field, so numbers changed without drawn colors changing. The working scope begins at <code>824476B8</code> and remaps the resolved OPD frame at <code>823D2648</code>, after native clip selection. The compact implementation keeps canonical frame identity and changes the native shader palette-row offset at draw time. Independent clipped effect layers preserve elemental colors and pixel priority. Nested draw scopes restore their prior target.</p>

"""+table(['Frame block','Current indices'],[

('Canonical body/Mercury/cast','0–560: 561 frames; gold/white use shader offsets, not geometry copies.'),

('Card illustrations','561–600: 40 frames.'),

('Summon / moving shield','601–1,094: 494 frames.'),

('Clipped body effects','1,095–1,471: 377 independent effect-layer frames.')])+"""

<p>The previous 45,975-frame layout multiplied each canonical frame across 64 gold and 16 white copies. The compact migration reduced the body to 1,472 frames. The full effect import now brings it to 3,217 frames and 80 texture pages, reclaiming 42,758 entries compared with the original expanded build. Each new canonical frame needs at most one clipped effect frame; pulse shade count no longer multiplies geometry.</p>

<p>Part order is preserved by clipping effect pixels hidden behind higher body parts before splitting the draw. Native hitboxes and all 82 animation scripts remain unchanged. Tests compare all 561 canonical compositions through every gold/white level in both default and color-8 costumes: 90,882 exact pixel comparisons. Body shade row and effect draw count are recorded at player+1072/+1076; live palette verification now tracks row cycling rather than duplicated frame IDs.</p>

<h3>Reference costume in option 8</h3>

<p>Character Select draws a preview eight times with offsets 0–7. New wrapper <code>82412880</code> scopes Nathan's preview using the selected runtime character record. A Nathan body/preview draw temporarily maps native offset 7 to reserved offset 96, then restores it. Native option/save indices remain unchanged.</p>

<p>Rows 96–191 hold the supplied magenta/navy/green costume, unchanged copies of elemental rows 1–15, 64 gold blends and 16 white fades. Reference colors are quantized to 5-bit COL channels. Fire keeps its own palette while the costume pulses from its own normal colors. Card/summon/shield instance copies clear the inherited offset; rows 200–219 remain cards and effects begin at 220.</p>

<p>The small player-list/menu portrait uses another draw path and initially retained the old color 8. Common palette lookup hook <code>823D7170</code> now identifies Nathan by sprite+8, the native FNV-1 basename hash <code>825BFF28("p_nathan") = 0x854D90C4</code>, and remaps offset 7 to 96 around the original lookup. This covers portrait draws outside the character scope, restores sprite state, and does not double-remap an already translated offset. CMake also forces the same-shard call in generated shard 16 through guest dispatch.</p>

"""+'<div class="pair">'+pic(hodpaths.legacy('modding/build/nathan_firewhip/color8_preview.png'),'Generated option-8 preview.','pixel')+pic(Path('%USERPROFILE%/AppData/Local/Temp/codex-clipboard-3fc4ee5e-daf7-4d60-ba87-ec3e638e892c.png'),'User-supplied costume palette reference.','pixel')+'</div>'+

pic(hodpaths.legacy('modding/build/nathan_firewhip/comparison.png'),'Normal, gold peak, white fade, hand cast and fire-whip builder comparison.')+

note('The user confirmed color 8 in the color selector and gameplay. The subsequent small menu-portrait fix passes native lookup/hash tests; its final portrait appearance awaits user verification.'))



sec('audio','Audio: CotM sound IDs to native XACT playback',"""

<p><code>nathan_audio_assets.py</code> builds 21 source sound events into unique <code>VX_NATHN</code> / <code>VXJ_NATHN</code> bank pairs. Both language settings use the original CotM recordings. The bank getter returns persistent paths in Nathan's extension; it neither writes read-only guest module data nor returns temporary stack strings.</p>

<p>The builder consumes 48 kHz stereo PCM16 WAV exports, trims silence with short pre/post rolls, converts samples to big endian, aligns wave payloads and constructs Xbox XWB/XSB headers. It verifies cue/wave indices, duration/PCM length, wave bounds and linked cue-name lookup chains. Format evidence includes the original game banks and FAudio's parser. Native mixer categories are player SFX (9) and player voice (23).</p>

"""+table(['Sound ID','Purpose'],[

('101 / 102 / 103','Jump / double jump / landing'),('104','Impact SFX retained in the bank; not Nathan knockback voice.'),

('105 / 120 / 106','Backdash / slide / death'),('107 / 108','Whip swing / held spin'),('300','Ordinary DSS activation'),

('322','Apollo fire-bomb explosion, verified at CotM 080781A4'),('349','Uranus levitation cast'),('350–354','Attribute-specific summon sound groups'),('418–420','Attack grunts'),('421 / 422','Alternating knockback grunts')])+"""

<p>Playback uses existing helper <code>82239218</code> with a copied PPC context, world position and cue such as <code>VX_NAT_S421</code>. Inherited Simon voice callback <code>836D1378</code> is suppressed. Actual HP transitions emit knockback/death once; movement transitions select jump/landing/slide/dash. Attack grunts rotate on one in three new swings, rather than every frame.</p>

<p>Held spin sound 108 repeats every eight CotM ticks using elapsed time. No invented DSS-off cue is added because the original off routine has no sound call. HoD's ordinary weapon/impact sound system continues running.</p>

<p>Initial volume byte 180 was too loud. Current byte 90 is approximately −12 dB, retaining mixer/category controls. Impact 104 was initially mistaken for Nathan's hit voice; source routines <code>0806C1BC</code>/<code>0806C298</code> and table <code>080E0ADA</code> identified grunts 421/422. The user confirmed improved volume and the corrected getting-hit voice.</p>""")



sec('salamander-actors','Salamander combinations: November 10 update',table(['Action','Behavior','MP'],[

('Mercury','Existing fire whip and 105% STR.','6/swing'),

('Venus','Existing 112% STR enhancement.','~4/sec'),

('Jupiter','Two native flame sprites; slow 256-tick orbit, 24–40 pixel radius and native easing.','~4/sec'),

('Mars','Three dedicated native sword clips; separate flame layer; fire hit at extension; inherited whip collider disabled.','8/swing'),

('Diana','Dedicated fireball releases at whip extension; persistent direction, impact and terrain cleanup.','32/swing'),

('Apollo','RB directly casts a native bomb flight/explosion and throw poses; ROM gravity and launch velocity; swept native terrain checks.','20/bomb'),

('Neptune','Every pairing halves damage of its type (fire, ice, slash, strike, stone, poison, pierce, lightning, holy, dark); elemental hits still flash the Neptune effect.','~3/sec'),

('Saturn','Native bat/firing/shot art; ROM follow-offset table; eight-tick attack delay and 32-tick cooldown while attacking.','4/shot'),

('Uranus','Existing direct RB summon and levitation retained.','160/cast'),

('Pluto','RB directly casts Item Crash selected by normal B subweapon; all 11 eligible equipment IDs map to seven families.','Crash cost only; no armed drain')])+"""

<p>145 appended source frames retain their indexed pixels, palette banks, origins, and source sequence ticks. Three additional sword clips preserve all original 82 clips. Body/costume tint remains independent of elemental art. Native collisions use owned attack objects, normal enemy defenses/status handling and kill credit. Pool slots carry generations so delayed contacts cannot affect a replacement object.</p>

<p>Pluto adapts shared Knife/Axe/Holy Water/Cross crashes to HoD, and adds explicit HoD variants for Ricochet Rock, Bible, and Javelin. Uses HoD subweapon artwork; the seven crash MP costs are 40/60/80/100/60/80/60 respectively. Those costs, damage/choreography, and the additional HoD-only crashes are adaptation choices, not a claim of identical CotM Item Crash parity. No stopwatch is added, because Nathan has no compatible equipped stopwatch in the current hunter inventory.</p>

<p>Native stage query <code>823C2340</code> is the same solid/slope/dynamic-shape point test called by <code>824823A0</code>. Four-unit sweep steps stop bombs at walls/floors and reflect Ricochet Rocks; no fabricated launch-height floor or fixed screen collision boundary is used. Moving platforms, multiplayer replication and full stage coverage still need live testing. Imported asset pixels and wrapper tests do not establish live gameplay parity.</p>

"""+pic(hodpaths.legacy('modding/build/nathan_firewhip/salamander_sequences.png'),'Dedicated Salamander sequences and subweapon crash artwork; labels show source tick durations.'))



memory=[

('0–843','Original player fields','Original guest layout retained.'),

('844–883','DSS / draw state','Enabled, prior RB, motion table, paid swing, pulse/cast/fade; drawn/canonical frame and count.'),

('884–951','Audio','Previous state/motion/HP, counters, cue scratch and spin cadence.'),

('952–1015','Bank paths','Two persistent 32-byte buffers.'),

('1016 / 1020','Mercury state','Attribute / held extension elapsed time.'),

('1024 / 1028','Whip cache','Original flags / native hit field for held scaling.'),

('1032–1055','Card Swap / diagnostics','Held Y, direction edges, swaps, last item, knockback variation, card draw count.'),

('1056','Action','Runtime Action enum.'),

('1060–1071','DEF diagnostics','Call count, native result, modified result.'),

('1072 / 1076','Palette/layer diagnostics','Last submitted body palette row / independent effect draw count.'),

('1088–1279','Card sprite','192-byte independent overlay instance.'),

('1280–1343','Summon data','Captured position, waves, actors, recoveries and resolution counter.'),

('1344–1535','Summon/shield sprite','192-byte independent overlay instance.'),

('1728–2751','DSS object pool','16 objects, 64 bytes each: kind, position, motion, lifetime, power, element, art, generation.'),

('2752–2815','DSS object controls','Command window, bat cooldown, sword/release timing, absorption window, generation, special casting pose.'),

('2816–3007','FX lookup sprite','Independent weapon-resource readiness query.'),

('3008–3135','FX descriptor','Private 112-byte body descriptor with an independent palette pointer.'),

('3136–3327','Additional DSS state','Palette cache, timers, charge/combo counters and scoped table-query flags.'),

('3328–4095','Shadow history','48 position, frame and facing records.'),

('4096–7595','Subweapon table copies','50 stable 70-byte records; private MP discounts without shared table mutation.'),

('7596–8191','Reserved','Allocation padding for future state.'),

('1536–1727','Progression','Owned cards, saved-time baseline/session elapsed, walking accumulator, prior position, moving flags/counters; skill carry at 1600–1649.')]

sec('memory','Memory layout, ownership and save persistence',"""

<p>The factory now allocates <strong>8,192 bytes</strong> instead of the original 844. Earlier 1,280-byte notes describe prior builds. State is per player and initialized at allocation. Lifecycle resets clear DSS/audio/summons; progression reset occurs at factory allocation.</p>

"""+table(['Player offset (decimal)','Purpose','Contents'],[(c(a),E(b),E(d)) for a,b,d in memory])+"""

<h3>Important guest relationships</h3>

"""+table(['Address / offset','Meaning'],[

(c('0x8291D9F0'),'Entity manager. Table at +0xAC has 16-byte entries indexed by handle low 16 bits; full handle/generation must match.'),

(c('player+852'),'Persistent motion-table destination = owner+0x74. Subtract 0x74, validate owner+0x924 == player.'),

(c('owner+0x9C8'),'15-word equipment model: weapon 0/1, B skills 8–11, cards 12/13.'),

(c('player+88'),'Stats pointer: HP +4; MP +8; max HP +16/+28; max MP +20/+32; death/status gate +308.'),

(c('player+564 / +572 / +584'),'Elapsed time / player state / motion ID. States are not clip numbers.'),

(c('owner+0x8D4 / +0x8D8'),'Current world position; previous +0x8DC/+0x8E0, display +0x8EC/+0x8F0.'),

(c('82223348 → game+0x1018'),'Native 0x3B00-byte save model.'),

(c('save+0x3E8+item'),'Inventory quantity in upper nibble; lower flags preserved on migration.'),

(c('save+0x28+11×60'),'Nathan equipment: 15 big-endian u32 words.'),

(c('save+0x24A4'),'Native Nathan playtime seconds.'),

(c('save+4×(0x98E+11×50+localSkill)'),'Nathan subweapon mastery; 50 entries, 99,999 cap.')])+"""

<p>Enabled flags, cast/pulse timers, sprite scratch and fractional XP carry are transient. Equipment selections and mastery update existing native save fields. No new disk schema/checksum/encryption is introduced; savedata.dat stays 0x3B00 bytes.</p>

<p><code>nathan_cards.py --migrate-save</code> is a separate closed-game operation, with a full backup and byte-change manifest. Its allowlist grants cards, installs utility Card Swap in Y, removes reserved obsolete Card Swap and repairs only its old B placements. Action/Attribute selections and unrelated bytes are preserved. Current asset/runtime installation does not run migration or edit the save file.</p>

<p class="fine">Revalidate these offsets after changing guest images or game versions. Walking/XP remainder state is not independently persisted across a fresh player allocation.</p>""")



hookdesc={

'8246D8E8':'Scoped private subweapon-table copy for Pluto/Manticore MP discount.',

'836D0000':'Extended factory allocation and initialization.','836D00F8':'Lifecycle resets; original initializer continues.',

'836D11B8':'Capture private motion table; DSS mapping.','836D1FC8':'Input, Card Swap, DSS/drain/cast, anchoring, progression, audio and restoration.',

'836DBEF8':'Pay Mercury swing; Unicorn swing recovery; attack audio/remapping.','836D3670':'Derived STR.',

'836D36B8':'Venus/Griffin INT.','836D3790':'Venus/Mandragora LCK.','836D1358':'Persistent sound-bank path.',

'836D1378':'Suppress inherited Simon voice.','82451AA8':'Final physical DEF plus diagnostics.',

'8245D9A0':'Equipment/status summary DEF/ATK/STR/INT/LCK.','8245BCA8':'Heart-pickup MP scope.',

'8244E3C8':'Venus/Manticore positive heart MP doubling.','8246C408':'Paid Hunter Whip elemental flags.',

'824476B8':'Nathan body draw scope.','82412880':'Nathan Character Select palette scope.',

'823D2648':'Resolved body/palette draw, costume and overlays.','824699B8':'Weapon animation start scope.',

'82469D18':'Weapon collision query scope.','823D31C8':'Scoped weapon clip remap.',

'823D4098':'Scoped collision clip remap.','8246F5C0':'Cache native hit field and refresh whip.',

'823C90C0':'Action-dependent attribute description.','824827F0':'Owned summon actor update, submit/resolve and lifetime.',

'82484918':'Black Dog contact deduplication and healing.','82452658':'Final physical ATK.',

'8244BF10':'Moving shield: ignore positive hit transaction, allow healing.','8245D008':'20% bonus on actual native subweapon mastery delta.',

'823D7170':'Common sprite palette lookup: identify Nathan basename hash; color-8 menu portrait remap.'}

hooks=[]

for fn in ['nathan_dss.cpp','nathan_dss_damage.cpp']:

    for h in re.findall(r'REX_EXTERN\(sub_([0-9A-F]+)\)',(N/fn).read_text()):

        hooks.append((c('0x'+h),E(fn),E(hookdesc.get(h,'See source appendix.'))))

sec('hooks','Native hook register and build integration',table(['Guest address','Implementation','Role'],hooks)+"""

<h3>Weak-alias folding and indirect dispatch</h3>

<p>A linked strong hook is insufficient if LLVM folds a generated caller to its local weak alias/original in the same translation unit. That bypassed the DEF wrapper despite successful linking. CMake idempotently rewrites same-shard calls in <code>harmonyrecomp_recomp.20.cpp</code> for <code>82451AA8</code>, <code>82452658</code> and <code>8244BF10</code> to <code>REX_CALL_INDIRECT_FUNC(...)</code>. Shard 21 also dispatches subweapon table query 8246D8E8 indirectly. It does the same for preview <code>82412880</code> in shard 18 and common palette lookup <code>823D7170</code> in shard 16. Configure dependencies reapply the substitution after regeneration. Linker maps verify strong-symbol ownership.</p>

<h3>Package discovery and function-table placement</h3>

<p><code>modding/patches/build-py-mods-folder.patch</code> adds <code>mods/&lt;package&gt;</code> discovery to build.py: require 000info, stage under assets/dlc, discover unique guest DLL paths, add them to the local manifest and install the package list. Duplicate module paths are detected.</p>

<p>The local CMake configuration places the main indirect function table at 0x8C000000 and packs DLL tables from 0x8D000000, rounded to 64 KB and bounded below 0x90000000. This prevents default table locations overlapping fixed-address player images. These are supporting local settings; unrelated existing infrastructure is not assigned Nathan authorship.</p>

<p>The full local manifest/registry has 117 recompiled modules. Selective Nathan-only codegen can overwrite it with a one-module registry and break content. Preserve/regenerate the complete manifest. PPC changes need regeneration; C++ changes need rebuilding; asset-header frame changes need rebuilding native consumers.</p>""")



nv=json.loads((hodpaths.legacy('modding/build/nathan_firewhip/native_verification.json')).read_text())

installs=[]

for name in [sorted((hodpaths.legacy('modding/backups')).glob('nathan_dss_*_'+kind))[-1].name for kind in ('source','active')]:

    p=hodpaths.legacy('modding/backups')/name/'install_manifest.json'

    entries=json.loads(p.read_text())

    mismatches=sum(hashlib.sha256(Path(e['target']).read_bytes()).hexdigest()!=e['sha256'] for e in entries)

    installs.append((name,p,entries,mismatches))

sec('speed-mp','November 10 revision: MP balance, native speed and recovery numbers',"""

<p>""" + E(BALANCE['policy']) + """ Source: <code>modding/nathan_dss_balance.json</code>, which generates <code>src/nathan_dss_balance.h</code> and scales every card description. The original CotM numbers are retained there.</p>"""+table(['Family','CotM MP per use','HoD MP per use'],[(k,' / '.join(map(str,v)),' / '.join(str(hod_cost(x)) for x in v)) for k,v in BALANCE['cotm_costs'].items()])+"""

<h3>Speed</h3>

<p>Gear effect type 1 (Mercury Boots 20, Winged Boots 50, Sonic Boots 60) is resolved by best value into <code>stats+388</code>; type 30 penalties are resolved by worst value into <code>stats+392</code>. Native target speed in <code>836DC9A0</code>, and the matching threshold in <code>836D7C50</code>, is <code>(1 + (stats+388 + stats+392) x 0.01) x stats+316</code>.</p>

<p><code>DssSpeedScope</code> wraps only those two routines. Pluto/Griffin acts as +100 boots (best value, so exactly 2x and no stacking with equipped boots). Jupiter/Cockatrice acts as a -50 penalty (0.5x, partly offset by boots, as native penalties are). Equipment values are restored when each routine returns. Backdash and other routines that do not read the boots fields are unaffected, the same as with real boots.</p>

<h3>Recovery numbers</h3>

<p>Every HP recovery path now goes through <code>SummonHeal</code>: Mercury/Unicorn, Uranus/Unicorn, Uranus/Black Dog contact and Jupiter/Mandragora. It shows the actual capped gain, shows nothing at full HP, and rounds fractional recovery up so a real heal never displays 0. Jupiter/Black Dog HP loss stays silent.</p>

"""+note('The speed and number behavior is covered by native harness checks with a stand-in for the two movement routines, plus a source guard on their field reads. It has not been confirmed in live play.'))



PAIR=BALANCE['pair_level']

sec('card-level','November 10 revision: card copies drive the whip and every pair',"""

<h3>Hunter Whip: native collection scaling</h3>

<p>Nathan's definition previously kept Simon's collection list (mode 2: mastery of five subweapons). It now lists the 20 DSS cards with mode 1, which sums owned copies capped at 9 each (<code>8245D320</code>), out of 180. That total is used natively in two places. <code>8245D178</code> sets the whip's ATK to row min + (max - min) x total/180, which for the Hunter Whip row is 10 to 60. <code>8244D4E8</code> gives the whip's hit level, passed to <code>824702F0</code>: level 1 below 20, level 2 at 20 or more, level 3 at 180. One copy of every card is therefore whip level 2. The definition loader reads the count byte and fills a resizable list, so the 20-entry list is safe.</p>

<h3>Pair level</h3>

<p>""" + E(PAIR['policy']) + """ Level = (min(action copies,9) + min(attribute copies,9)) / 2, refreshed every update by <code>ProgressFrame</code> into the progress block at +1580.</p>"""+table(['Kind','Level 1','Level 9','Where'],[

('Damage','x1',f"x{PAIR['damage_at_max']:g}",'ProjectilePower (all projectile and melee pairs, Item Crash), Uranus summons, Mercury whip STR (excluded from ProjectilePower to avoid double scaling)'),

('Healing','x1',f"x{PAIR['healing_at_max']:g}",'SummonHeal: Mercury/Unicorn, Jupiter/Mandragora, Uranus/Unicorn and Black Dog'),

('Stat bonus','bonus x1',f"bonus x{PAIR['bonus_at_max']:g}",'Venus STR/DEF/INT/LCK, Venus card bonuses, Pluto playtime bonuses; penalties such as Unicorn STR 71% stay fixed')])+"""

<p>Not scaled: MP costs and drains, damage reduction and immunity, invincibility, speed, durations, projectile counts and Pluto/Skeleton's fixed rare bone.</p>

"""+note('Covered by native harness checks for level calculation, all three growth kinds, the Mercury double-scaling guard and the Venus percent path. The whip ATK and hit level use unmodified native code driven by the new definition list; they have not been confirmed in live play.'))



sec('verification','Verification and remaining limits',table(['Evidence','Meaning'],[

('Current native harness',E(nv['native_wrapper_checks'])+' Actual Nathan C++ runs against sparse guest memory.'),

('Real native helper execution','Original final DEF 82451AA8, area 82484180, request lookup 823C4E00, recovery-number wrapper 82454000, palette lookup 823D7170 and basename hash 825BFF28 execute in the harness; other behavior is stubbed where needed.'),

('Behavior cases','RB edges/payment, drain rates, same-frame switch, allocation, input restoration, airborne attacks, pair invalidation, menu/combat stats, owned-card count, mastery fractions/caps, walking/wall checks, shield/healing gates, summons, capped recovery and palette isolation.'),

('Guest PPC','20 emitted-PPC regression cases for standing/crouching spin, release and interruption behavior.'),

('Assets','Pixel fidelity, valid references, byte-exact OPD round trips, original clips retained, body/weapon timings and hitboxes synchronized; all 64 gold shades verified against ROM.'),

('Equipment/text','Original classifier, Nathan-only permissions, 170 gear items, 11 subweapons, locked Y/editable B, all 100 pair texts.'),

('Build/deployment','EXE and DLL build; linker ownership and six same-shard substitutions checked; latest source/runtime and active manifests are rehashed when this report is generated.')])+"""

<h3>Gameplay evidence</h3>

<p>The user confirmed the corrected casting/pulse, Card Swap, final Y/B arrangement, corrected hit voice and better audio volume. Earlier live captures showed RB activation, paid fire flags, retained airborne fire selection and cycling drawn palette frames. A live Venus/Serpent native DEF call increased 31.5 → 39.375 (×1.25); description switching was user-confirmed.</p>

<p>The first Uranus user test confirmed Unicorn healing but no popup, and Golem no damage. Both code paths have now been corrected and exercised in the harness. The latest enemy damage/status behavior, healing-number appearance and seven new progression/shield pairs need final gameplay confirmation. The user confirmed color 8 in the selector/gameplay; the subsequent small menu-portrait fix was user-verified. A successful harness is not an exhaustive running-game/multiplayer test.</p>

<h3>Intentional limits</h3>

<ul><li>All pairs have code paths; the new family-specific behavior is a first pass and needs live tuning.</li><li>Skeleton mode uses source art and bone attacks. Bear Ring is absent in HoD; the conditional bear transformation remains unimplemented.</li><li>Summons use original art with adapted local choreography and a fixed nearby rectangle, not literal global viewport attacks or full original actors.</li><li>HoD resistances/status rules apply; CotM status thresholds are not reproduced. Jupiter/Black Dog uses a periodic HP loss to simulate self-poison, without a native poison icon.</li><li>Some host-only animations and held extensions are deliberate adaptations.</li><li>Card-count, walking, moving-shield and capped Nathan-playtime mechanics are requested HoD adaptations, not assertions about original CotM behavior.</li><li>Saving remains native; transient bonus/carry state is not a new independently persisted system. Multiplayer and every enemy interaction are not exhaustively validated.</li></ul>""")



history=[

('Slide used dash','Native slide 22; seven frames /31 ticks.'),

('Crouch spin failed','Patch state 24 as well as 23; motion 192/clip 29 and synchronized weapon geometry.'),

('Crouch repeatedly lowered','One-shot clip 30 plus single-pose hold clip 2.'),

('No normal hunter equipment','Permission bit 0x800 in original eligible item tables.'),

('Cards in subweapon lists','Correct SOUL type 14/3; icon alone does not route rows.'),

('RB failed','Correct logical mask and owner/input relationships.'),

('Blue Nathan/fire/gold','Correct BGR COL serialization.'),

('Pulse values changed, art did not','Remap resolved OPD draw frames, not animation-event fields.'),

('Wrong activation pose','Resource 53 hand gesture; floating 87/89/90 reserved for Uranus.'),

('Jump whip lost fire','Recognize jump/fall attack motions and retain paid swing.'),

('Early audio rollout stage crash','Current banks/path lifetimes/callbacks validated; available records do not establish a uniquely proven historical crash cause.'),

('Loud audio, no spin, wrong hit voice','Volume 90; repeated 108 every eight ticks; grunts 421/422 instead of impact 104.'),

('Card Swap locked B, Y empty','WEPN utility in actual slot 1; corrected mask and old-placement repair.'),

('Blurry cards','64×96 original illustrations at half world scale.'),

('Serpent DEF unchanged','Hook final physical DEF and menu summary; force same-shard indirect dispatch.'),

('Crowded attribute descriptions','One contextual pair description; remove repeated RB reminder.'),

('Unicorn no green heal number','Native recovery-number call with capped gain.'),

('Pluto/Griffin gave no speed','Removed the position correction; the pair now joins the native boots speed fields.'),

('Mercury/Unicorn healed silently','Paid swings now use SummonHeal and show the actual capped recovery.'),

('DSS costs too large for a 100 MP pool','Central balance file: per-use costs are a quarter of CotM, rounded up, minimum 1; drains are a quarter without rounding.'),

('Golem no damage','Explicitly resolve registered area requests in actor update.'),

('Palette copies exhausted frame headroom','Use runtime shader rows plus clipped body/effect layers; 45,975 frames reduced to 1,472.'),

('Small menu portrait retained old color 8','Common palette lookup identifies Nathan by native basename hash and remaps that separate draw path.'),

('Free same-frame switch summon risk','Detect changed pair as a new paid activation.')]

sec('history','Issue-to-fix record',table(['Reported problem','Correction'],history))



sec('workflow','Build, installation and rollback',"""

<p>The following is the documented workflow, not a claim that these commands were rerun merely to generate the report. Run from the game root. Rebuild the base ROM mapping only when changing its source/mapping; downstream elemental assets depend on it.</p>

"""+pre("""python modding/tools/nathan_rom_animations.py    # if base mapping/art changed

python modding/tools/nathan_firewhip_assets.py   # Mercury, pulse, cards, summons, color 8

python modding/tools/nathan_cards.py             # records, defaults, contextual text

python modding/tools/nathan_audio_assets.py      # if sound banks changed



python modding/tools/verify_nathan_spin.py

python modding/tools/verify_nathan_dss.py

python modding/tools/verify_nathan_dss_palette.py

python modding/tools/verify_nathan_compact_layers.py

python modding/tools/verify_nathan_equipment.py""")+"""

<p>Put the bundled CMake, LLVM and Ninja directories on PATH. Rebuild after native C++ or generated frame headers change:</p>

"""+pre(".setup/toolchain/cmake/bin/cmake.exe --build .setup/package/src/out/build/win-amd64-release --target harmonyrecomp harmonyrecomp_dllTest12 --parallel 8")+"""

<p>Regenerate from the complete local manifest first for XEX/PPC edits. Check link-map symbol ownership and generated same-shard dispatch after rebuilding.</p>

"""+pre("python modding/tools/install_nathan_dss.py --source\npython modding/tools/install_nathan_dss.py --active")+"""

<p>The installer refuses replacement while HarmonyRecomp is running. Source mode deploys staged card/firewhip/audio files to source and mirror, plus the EXE, maps and full 117-DLL bundle. Active mode deploys Documents DLC data. It backs up every destination before copying and verifies SHA-256 afterward. Copied file counts include unchanged bundle members, not just authored files.</p>

"""+table(['Latest manifest-backed backup','Files copied','Current hash mismatches'],[(link(p.parent,name),len(entries),bad) for name,p,entries,bad in installs])+"""

<p>These latest backups preserve the immediately preceding deployment; earlier backups retain earlier development states. Roll back with the game closed, restoring matching runtime/source/mirror and active-DLC files from their manifests. Mismatching sprite assets and native generated frame constants can select wrong frames.</p>

<p>Equipment permission installation is separate: <code>nathan_equipment_access.py --install</code> changes original source/base tables; <code>--active</code> updates installed DLC tables. Save migration is also separate. Ordinary runtime/asset deployment does not edit savedata.dat.</p>""")



extra_tools=['hodsprite.py','txrc.py','make_menu_art.py','xexunpack.py','xexrebase.py','xexpatchstr.py','xexpatchword.py','sheet2hod.py','overlap.py','guestwatch.py','hod_disasm.py']

toolpaths=sorted({*[p for d in hodpaths.TOOL_DIRS for p in d.glob('*nathan*.py')],*[p for d in hodpaths.TOOL_DIRS for p in d.glob('*nathan*.cpp')],*[hodpaths.legacy('modding/tools')/s for s in extra_tools],*list(Path('<research folder>/tools').glob('*.py'))})

toolrows=[]

for p in toolpaths:

    if not p.is_file():continue

    data=p.read_bytes();s=data.decode('utf-8-sig',errors='replace')

    doc=re.search(r'"""(.*?)"""',s,re.S)

    desc=doc.group(1).strip().split('\n\n')[0].replace('\n',' ') if doc else 'Source/support tool; inspect linked file.'

    toolrows.append((link(p,p.name),E(desc),f'{len(data):,}',c(hashlib.sha256(data).hexdigest()[:16])))

packagefiles=sorted(p for p in PKG.rglob('*') if p.is_file())

sec('files','Source/tool index and package inventory',"""

<p>Links below open the real local files. Hash prefixes identify the source snapshot. The HTML embeds all styles, figures and native source text; adjacent images are not required to read it. Local links naturally require the original workspace.</p>

"""+table(['Tool','Purpose / source docstring','Bytes','SHA-256 prefix'],toolrows)+

f'<details><summary>All {len(packagefiles)} source-package files: paths, sizes and full hashes</summary>'+

table(['Package-relative file','Bytes','SHA-256'],[(E(p.relative_to(PKG).as_posix()),f'{p.stat().st_size:,}',c(hashlib.sha256(p.read_bytes()).hexdigest())) for p in packagefiles])+'</details>'+

"""<p>The package inventory includes loader/historical files that the active-data installer may not recopy. Source mode additionally includes mirrored data and the complete runtime bundle; current counts are in the installation table.</p>

<h3>Authoritative local references</h3><ul>"""+

''.join('<li>'+link(p,label)+'</li>' for p,label in [

(hodpaths.legacy('modding/nathan_rom_mapping.json'),'Current ROM animation mapping'),

(hodpaths.legacy('modding/build/nathan_firewhip/native_verification.json'),'Current native verification result'),

(hodpaths.legacy('modding/build/nathan_firewhip/cotm_palette_verification.json'),'Palette evidence'),

(hodpaths.legacy('modding/build/nathan_cards_package/card_report.json'),'Current card records'),

(hodpaths.legacy('modding/build/nathan_equipment_access/report.json'),'Equipment permission changes'),

(hodpaths.legacy('modding/patches/build-py-mods-folder.patch'),'build.py mods-folder patch'),

(SRC/'CMakeLists.txt','CMake targets and dispatch integration'),

(Path('<research folder>/research/cotm-recomp'),'Local CotM recomp research')])+'</ul>')





from nathan_cards import ACTIONS,ATTRIBUTES,PAIR_DESCRIPTIONS

allcheck=json.loads((hodpaths.legacy('modding/build/nathan_firewhip/all_dss_asset_verification.json')).read_text())

sec('all-dss','All DSS families: current first-pass implementation',note('<strong>Gameplay boundary.</strong> Automated verification confirms source art, activation/cost routing and selected native wrapper behavior. The new effects have not been exhaustively tested in a running stage. They are adapted initial implementations; do not interpret the 100-pair count as exact CotM parity.')+"""

<p>Apollo casts every Attribute combination directly on an RB rising edge. Pluto/Salamander does the same for Item Crash; there is no armed drain or directional command. Holding RB through cast completion cannot repeatedly spend MP. Uranus retains its direct summon behavior. Other pairs retain toggle activation.</p>

<p>New art uses the invisible weapon's independent COL bank, with 98 source palette rows. The renderer copies the body descriptor per player and changes only its palette pointer. Shared resources remain unchanged. The existing gold/white pulse and eighth costume still use the original body COL. If the FX bank is not ready, transformed-body drawing falls back to Nathan's normal body rather than hiding him. Actual resource lookup readiness remains a live-test item.</p>

<p>The expanded body contains 6,592 frames, 112 animation clips and 96 pages. There are no geometry copies per pulse shade. Per-player allocation is 8,192 bytes, including the existing 16-object pool, lookup scratch, private resource descriptor, charge/AI state, shadow history, and 50 private subweapon rows.</p>

<p>The approved HoD adaptations are Pluto/Manticore: half subweapon MP costs; Neptune/Mandragora, Golem and Griffin: half slash, strike and pierce damage respectively. Ordinary menu MP numbers still show base costs; discounted lookup is scoped to Nathan's native update and does not mutate shared item tables.</p>

<h3>Remaining fidelity work</h3>

<ul><li>Four imported resource banks lack a usable native timeline; their frame cadence is explicitly marked unverified in the asset report.</li><li>Mars hit rectangles and several hit thresholds, Apollo choreography, familiar AI and attack cadence are adapted. Exact CotM collision/AI parity is unfinished.</li><li>New projectile impact art is currently removed on impact rather than playing every original impact sequence.</li><li>Jupiter/Golem currently uses a four-second post-hit guard rather than multiplying each original gear-dependent invulnerability duration. Thunderbird halves the incoming attack term, before all native final-damage calculations.</li><li>Jupiter/Black Dog simulates poison with a nonlethal HP tick. Pluto/Serpent spawns an extra DSS actor; it is not a cloned native subweapon instance.</li><li>Skeleton's rare powerful bone and lethal-hit mode are implemented; Bear Ring and its conditional transformation are not.</li><li>Networking, moving platforms and full enemy/status coverage remain unverified.</li></ul>

"""+table(['Action','Attribute','Current effect and cost'],[(E(a),E(b),E(PAIR_DESCRIPTIONS[i*10+j].split('\n',1)[1]).replace('\n','<br>')) for i,a in enumerate(ACTIONS) for j,b in enumerate(ATTRIBUTES)])+table(['Automated asset evidence','Result'],[(E(k),str(v)) for k,v in allcheck.items()]))



nativefiles=sorted(N.glob('nathan_*'))

appendix=''

for p in nativefiles+[hodpaths.legacy('modding/tools/nathan_spin.py'),hodpaths.legacy('modding/patches/build-py-mods-folder.patch'),SRC/'CMakeLists.txt']:

    data=p.read_bytes();text=data.decode('utf-8-sig')

    appendix+='<details class="source"><summary>'+E(p.name)+f' <small>{len(text.splitlines())} lines</small></summary><p>'+link(p)+'<br><span class="hash">SHA-256 '+hashlib.sha256(data).hexdigest()+'</span></p>'+pre(text)+'</details>'

sec('source','Appendix: exact native and integration source',f"""

<p>Embedded below are complete copies of all {len(nativefiles)} current Nathan C++ source/header files, the PPC spin patch tool, the mods-folder patch and CMake configuration. Generated frame headers are included because they define the runtime/asset contract. The CMake snapshot also contains existing supporting configuration; it is not a claim that every line was authored for Nathan.</p>

<p>These copies and hashes are a fixed snapshot. Later edits to local files do not automatically update the report. Use the source links for the working files and rebuild this report when needed.</p>

"""+appendix)



CSS="""

:root{--ink:#192a3c;--muted:#5b6c7d;--accent:#24608a;--line:#dce5ed}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:25px}body{margin:0;background:#f0f4f8;color:var(--ink);font:16px/1.72 system-ui,"Segoe UI",sans-serif}a{color:var(--accent);overflow-wrap:anywhere;text-underline-offset:3px}.nav{position:fixed;inset:0 auto 0 0;width:260px;background:#102638;padding:28px 22px;color:#d8e6f0;overflow:auto}.brand{font-size:11px;letter-spacing:.17em;text-transform:uppercase;color:#9fb9cb}.nav strong{display:block;font-size:24px;line-height:1.3;margin:10px 0 24px}.nav a{display:block;font-size:12px;line-height:1.5;text-decoration:none;color:#bed3e2;border-left:2px solid transparent;padding:8px}.nav a:hover,.nav a.active{background:#1b3c54;color:white;border-color:#dca754}.nav input{width:100%;font:12px system-ui;color:white;background:#19394f;border:1px solid #476478;border-radius:5px;padding:10px;margin-bottom:15px}.nav input::placeholder{color:#bad0df}main{margin-left:260px;max-width:1560px;padding:40px 5.5vw 70px}.hero{padding:38px 42px;color:white;background:linear-gradient(130deg,#10283c,#27566f);border-top:5px solid #daa552;border-radius:5px 5px 12px 12px}.hero small{color:#b9cfdf;font-size:11px;letter-spacing:.16em;text-transform:uppercase}.hero h1{font-size:clamp(34px,4.2vw,58px);line-height:1.08;letter-spacing:-.035em;margin:18px 0}.hero p{max-width:750px;color:#d6e5ef}.meta{padding-top:18px;margin-top:25px;border-top:1px solid #ffffff35;font-size:12px;color:#c0d7e6}.actions{display:flex;gap:12px;margin:18px 0}.actions button{background:white;border:1px solid #bdcddb;border-radius:6px;font:13px system-ui;padding:10px 15px;cursor:pointer;color:var(--ink)}section{padding:31px 36px;margin:24px 0;background:white;border:1px solid var(--line);border-radius:10px}h2{font-size:25px;line-height:1.3;letter-spacing:-.02em;margin:0 0 22px;padding-bottom:16px;border-bottom:2px solid #e9eff5}h3{font-size:18px;color:#264f6c;margin:28px 0 10px;line-height:1.4}p{margin:12px 0}li{margin:8px 0}code{font:12px/1.6 ui-monospace,Consolas,monospace;color:#1f4c6e;background:#edf3f8;border-radius:4px;padding:2px 5px;overflow-wrap:anywhere}pre{max-height:660px;overflow:auto;padding:20px;background:#102638;border-radius:7px;font-size:12px;line-height:1.6;color:#e1edf5;tab-size:2}pre code{white-space:pre;background:none;color:inherit;padding:0;overflow-wrap:normal}.table{overflow-x:auto;border:1px solid var(--line);border-radius:6px;margin:20px 0}table{width:100%;border-collapse:collapse;font-size:13px;line-height:1.6;text-align:left}th{font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:#2a4d68;background:#eaf1f7}td,th{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}tbody tr:nth-child(even){background:#f7f9fc}tbody tr:last-child td{border:0}.note{padding:17px 20px;background:#edf5fa;border-left:4px solid #4b83aa;border-radius:0 5px 5px 0;margin:23px 0;font-size:14px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:25px 0}.metrics div{padding:18px;background:#f0f5fa;border:1px solid #e0e9f1;border-radius:7px}.metrics b{font-size:29px;line-height:1.2;display:block;color:#235676}.metrics span{font-size:11px;color:var(--muted)}figure{padding:15px;background:#111c29;border-radius:8px;margin:24px 0}figure img{max-width:100%;height:auto;display:block;margin:auto}figcaption{font-size:12px;color:#bfd0df;line-height:1.6;margin-top:13px}.pair{display:flex;gap:16px}.pair figure{width:50%;display:flex;flex-direction:column;justify-content:center}.pixel img{image-rendering:pixelated;max-height:270px}details{border:1px solid var(--line);border-radius:6px;padding:0 16px;margin:15px 0}summary{padding:15px 0;cursor:pointer;color:#255d82;font-weight:650;font-size:14px}details[open]{padding-bottom:14px}summary small{font-weight:400;color:var(--muted);margin-left:12px}.source pre{font-size:11px}.fine,.hash{font-size:12px;color:var(--muted)}.hash{overflow-wrap:anywhere}footer{padding:20px 2px;font-size:12px;color:var(--muted)}.hidden{display:none!important}.flow{max-width:750px;margin:25px auto;text-align:center}.flow div{padding:15px;background:#eef5fa;border:1px solid #d5e3ee;border-radius:7px;font-weight:650}.flow small{font-weight:400;font-size:12px;color:var(--muted)}.flow span{display:block;font-size:21px;color:#819bb0}

@media(max-width:1100px){.nav{width:210px;padding:24px 14px}main{margin-left:210px;padding:25px}section{padding:26px}.metrics{grid-template-columns:repeat(2,1fr)}}@media(max-width:750px){.nav{position:relative;width:100%;padding:20px}.nav nav{display:grid;grid-template-columns:1fr 1fr}.nav strong{font-size:20px}main{margin:0;padding:15px 12px}section{padding:22px 17px}.hero{padding:25px 22px}h2{font-size:22px}.actions{flex-wrap:wrap}.pair{gap:10px}}@media print{@page{margin:16mm 14mm}body{background:white;font-size:10pt;line-height:1.5}.nav,.actions{display:none}main{margin:0;padding:0;max-width:none}.hero{padding:18px 0;color:#203e55;background:white;border-radius:0}.hero h1{font-size:30pt}.hero p,.hero small,.meta{color:#4c6579}section{border:0;box-shadow:none;padding:16px 0;margin:0}h2,h3,summary{break-after:avoid}table{font-size:8pt}tr,figure,.metrics div{break-inside:avoid}.table{overflow:visible}pre{max-height:none;white-space:pre-wrap;overflow-wrap:anywhere;background:#eef3f6;color:#20354a;font-size:7pt}pre code{white-space:pre-wrap}.source:not([open]){display:none}.source[open]{break-before:page}a{color:inherit;text-decoration:none}.metrics b{font-size:22pt}}

"""

JS="""

const navLinks=[...document.querySelectorAll('nav a')];

document.querySelector('#search').addEventListener('input',e=>{const q=e.target.value.toLowerCase();navLinks.forEach(a=>a.classList.toggle('hidden',!a.textContent.toLowerCase().includes(q)))});

document.querySelector('#print').onclick=()=>window.print();

document.querySelector('#expand').onclick=()=>{const a=[...document.querySelectorAll('details.source')];const open=a.some(d=>!d.open);a.forEach(d=>d.open=open);document.querySelector('#expand').textContent=open?'Collapse source appendix':'Expand source appendix'};

const obs=new IntersectionObserver(es=>{for(const e of es)if(e.isIntersecting)navLinks.forEach(a=>a.classList.toggle('active',a.hash==='#'+e.target.id))},{rootMargin:'-10% 0px -75% 0px'});

document.querySelectorAll('section').forEach(s=>obs.observe(s));

"""

try:

    report_zone=ZoneInfo('America/Chicago')

except ZoneInfoNotFoundError:

    # Windows Python may lack tzdata. This November 9 snapshot is in CST.

    report_zone=timezone(timedelta(hours=-6),'CST')

now=datetime.now(report_zone).strftime('%B %d, %Y · %I:%M %p %Z')

nav=''.join('<a href="#'+id+'">'+f'{i+1:02d} · '+E(title)+'</a>' for i,(id,title,body) in enumerate(sections))

body=''.join('<section id="'+id+'"><h2>'+f'{i+1:02d} / '+E(title)+'</h2>'+text+'</section>' for i,(id,title,text) in enumerate(sections))

page='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>Nathan Graves DLC — Technical Implementation Report</title><style>'+CSS+'</style></head><body><aside class="nav"><div class="brand">HarmonyRecomp · Character 12</div><strong>Nathan Graves<br>Technical report</strong><input id="search" aria-label="Filter table of contents" placeholder="Filter contents…"><nav>'+nav+'</nav></aside><main><header class="hero"><small>Circle of the Moon → Harmony of Despair</small><h1>Nathan Graves<br>DLC implementation</h1><p>A technical record of the character package, ROM assets, PPC patches, native game hooks, DSS, audio, equipment, save integration and build tooling.</p><div class="meta">Prepared '+E(now)+'<br>Installed snapshot: all 100 DSS paths in an initial HoD implementation; direct RB casts, independent FX palettes, compact pulse rendering and color option 8.</div></header><div class="actions"><button id="print">Print / save as PDF</button><button id="expand">Expand source appendix</button></div>'+body+'<footer>Source-backed snapshot. Embedded text and hashes are fixed at generation time. User observations and native/harness verification are distinguished from pending gameplay validation.</footer></main><script>'+JS+'</script></body></html>'

DOC.mkdir(parents=True,exist_ok=True)

out=DOC/'Nathan_DLC_Technical_Report.html'

out.write_text(page,encoding='utf-8')

sp=read_opd(PKG/'data/opd/player/nathan/p_nathan.opd')

meta={'generated':now,'sections':len(sections),'native_source_files':len(nativefiles),'native_hooks':len(hooks),'package_files':len(packagefiles),'body_clips':len(sp.anims),'body_frames':len(sp.frames),'body_textures':len(sp.textures),'native_verification':nv,'installed_files_hash_verified':sum(len(x[2]) for x in installs),'installed_hash_mismatches':sum(x[3] for x in installs),'html_bytes':out.stat().st_size,'html_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}

(DOC/'Nathan_DLC_Technical_Report.metadata.json').write_text(json.dumps(meta,indent=2)+'\n')

print(out)

print(json.dumps(meta,indent=2))

