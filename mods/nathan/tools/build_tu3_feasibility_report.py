"""Read-only source audit and HTML assessment; does not build/install a TU."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
from pathlib import Path
import hashlib,html,json,re,sys
R=hodpaths.GAME;S=R/'.setup/package/src';E=html.escape
def c(x):return '<code>'+E(str(x))+'</code>'
def table(head,rows):return '<div class="table"><table><thead><tr>'+''.join('<th>'+E(x)+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def link(p,label):return '<a href="'+Path(p).as_uri()+'">'+E(label)+'</a>'
parts=[]
def sec(id,title,body):parts.append((id,title,body))
sec('verdict','Verdict and meaning of “Title Update 3”',"""
<p><strong>A two-part user rollout is feasible, but an ordinary Xbox Title Update cannot replace our current native HarmonyRecomp changes on its own.</strong> The practical route is an unofficial PC “TU3” update bundle containing the matching native runtime changes, plus the Nathan DLC. A literal 000B0000 Xbox update requires a separate guest-code port and still needs matching ahead-of-time native compilation for HarmonyRecomp.</p>
<p>This assessment targets the current local ReXGlue 0.8-based build. It is a source/package audit, not a working TU3 prototype. No game binaries, saves, DLC data or update packages were changed for this assessment.</p>
"""+table(['Proposed rollout','Assessment'],[
('Drop a normal Xbox TU3 and Nathan DLC into an unchanged HarmonyRecomp build','No. The installed native code/registry does not gain new functions from PPC patch bytes.'),
('Unofficial PC TU3 bundle + Nathan DLC','Yes, with an installer that deploys the matching EXE/native DLLs, update data and DLC metadata. This meets the two-deliverable user experience.'),
('One compatible base build, then a shared extension framework and versioned Nathan DLC','Feasible architecture work. Provides a path to making future Nathan changes DLC-owned, but is not implemented today.'),
('True cumulative Xbox TU3 with PPC game changes + guest Nathan DLC','Possible in principle for guest gameplay/data; substantial porting, patch authoring and testing. HarmonyRecomp must still generate/build matching native code.'),
('Package every existing PC feature as guest Xbox TU code','No. Windows timing, host graphics/UI, native networking, loader/build and SDK behavior are host-side concerns.')]))
sec('evidence','What the existing loader actually does',"""
<p>The installed official TU2 is a 000B0000 STFS package. Read-only enumeration found <code>default.xexp</code> (720,896 bytes), six base-character <code>.dllp</code> patches, shared item tables, text and art. The format can carry guest patches and replacement data; the existing pipeline already supports that part.</p>
<p><code>build.py:step_title_update()</code> extracts the update over assets, requires default.xexp, and regenerates native code with <code>REX_XEX_APPLY_PATCHES</code>. <code>OnLoadXexImage()</code> enables the same patching at runtime so guest data/layout matches the compiled image. This is not runtime recompilation of arbitrary new PPC instructions.</p>
<p><a href="https://github.com/rexglue/rexglue-sdk/wiki/Kernel-State-%26-Objects">ReXGlue’s own code/data loading documentation</a> states that XEX images supply runtime layout/data while execution goes through prebuilt native function pointers. The local generated <code>sub_836E4018</code> literally assigns <code>ctx.r3 = 12</code>; it does not fetch/interpret the original PPC li instruction from guest memory.</p>
<p><code>dlc.cpp</code> installs only packages in the built DLC list; unknown/uncompiled packages are skipped or removed from the installed content set. The generated registry maps 117 guest modules to native libraries, including Nathan. A new guest DLC DLL does not automatically supply its corresponding compiled PC DLL or register itself.</p>
<p><strong>Packaging location and executable format are different questions.</strong> Our Nathan logic compiled into harmonyrecomp_dllTest12.dll is PC machine code even though it belongs to the DLC target. Its source is not currently compiled into the Xbox dllTest12.dll in the package. Moving a C++ file or adding it to an STFS archive will not make either runtime execute it.</p>
<p>Likewise, moving the main executable’s strong overrides into Nathan’s native DLL is not a complete solution: existing generated calls and weak-alias optimizations must be prepared to dispatch to a registered callback. The current same-shard fixes demonstrate why a compatible host bridge is necessary.</p>""")
sec('split','Current changes: what can move where',table(['Change group','Normal TU / DLC data?','What would be required'],[
('Sprites, palettes, cards, sound banks, descriptions and Nathan defaults','Nathan DLC','Keep in the DLC; already suitable content formats. Package the guest module and matching native library through a compatible installer.'),
('PPC identity/path/motion/spin patches','Guest Nathan DLL','Already guest edits. Keep character-specific changes with Nathan and recompile that module.'),
('170 gear / 11 subweapon permission changes','Base tables can be update data; other DLC tables need routing verification','Do not assume update: shadows package-qualified files inside every other DLC. Prefer a shared Nathan-aware permission policy at verified native query points to avoid distributing changed copies of others’ packages.'),
('21 shared native game wrappers','Not as current C++ in default.xexp','TU3 PC bundle can ship the rebuilt EXE. A true guest TU needs equivalent PPC implementations/trampolines and matching recompilation.'),
('10 Nathan native callbacks','Not supplied by current guest DLC DLL','Ship the native Nathan DLL in the DLC/update installer, or port these callbacks into the guest DLL and regenerate.'),
('Frame constants / object size / extension offsets','Cross-component contract','Version these together; current 8,192-byte player allocation and frame layout are understood by both compilation targets.'),
('Module registry / CMake dispatch / function tables / mods discovery','Host build/loader changes','Require compatible setup/host support; cannot be solved by a guest table replacement.'),
('Graphics, framerate, Windows timer, networking and host fixes','Host behavior','If “all patches” includes these, retain/distribute them in the PC update bundle; a normal Xbox TU cannot replace host OS/SDK code.'),
('Test-save grants and old equipment repair','Not an external save-file rollout step','Use native defaults plus a tested in-game old-save migration policy. Decide actual card acquisition separately; testing grants are not a release loot system.')])+"""
<p>The current runtime has 31 Nathan-related overrides: 21 in the main executable and 10 in Nathan’s native DLL. Header helpers implement additional logic behind those entry points. Some shared hooks can become generic extension points; the classification above describes their current implementation, not an unproven one-step conversion.</p>""")
remaining=[
('Mercury',10,0,'Existing whips/stat/MP path; richer status/projectile parity may need more callbacks.'),
('Venus',10,0,'Existing derived stats, hearts, mastery and progression; requested adaptations already included.'),
('Jupiter',2,8,'Additional shield actors, interception, damage/element policies and lifecycle.'),
('Mars',1,9,'Alternative melee art, motion/hold behavior, geometry, attack ownership and damage.'),
('Diana',1,9,'Projectile/child-actor spawning, collision, lifetime, costs and effects.'),
('Apollo',1,9,'Additional spell/projectile behaviors and activation/cost/state rules; pair details still need source verification.'),
('Neptune',1,9,'Incoming-hit element/absorption and recovery policies, feedback and resource accounting.'),
('Saturn',1,9,'Persistent familiar actors, AI/targeting, attacks, cleanup, ownership and synchronization.'),
('Uranus',10,0,'Existing summon framework; latest enemy/status behavior still needs gameplay verification.'),
('Pluto',4,6,'Special movement/state/stat/drop/transform policies; exact remaining pair adaptations need specification.')]
remaining=[(a,10,0,e) for a,b,d,e in remaining]
sec('dss','All 100 DSS paths and remaining fidelity work',table(['Action','Implemented','Remaining','Framework pressure'],[(a,b,d,E(e)) for a,b,d,e in remaining])+"""
<p>All 100 pairs now have initial implementation paths. The table shows current code-path coverage; the framework-pressure column preserves the earlier subsystem planning notes. The broad update still needs live validation and CotM fidelity work. These are subsystem planning categories, not a claim that all unimplemented source behaviors have been individually verified. Extracted dss_coverage.json is an initial asset checklist and explicitly leaves many resource/behavior assignments unverified.</p>
<p><strong>The unfinished combinations do not make the two-package distribution goal impossible. They do prevent us from promising that today’s shared hooks will be the final frozen TU3.</strong> Persistent actors, damage absorption, transformed movement/hitboxes, attack replacement, targeting, drops and cleanup reach more systems than the current stat/whip implementation.</p>
<p>Recommended shared capabilities: character-identified input/state callbacks; outgoing/incoming damage and element policies; MP/HP/mastery/drop queries; actor spawn/update/contact/destruction; render/palette routing; native equipment/text policy; and versioned save/network state. Keep individual card definitions, artwork and effect controllers with Nathan. Future executable behavior still requires matching native DLC code unless a specifically implemented scripting/behavior runtime supports it—tables alone cannot express arbitrary new AI or transformations.</p>
<h3>Concrete resource constraint</h3>
<p><strong>Resolved after the initial assessment:</strong> the body now has 3,217 frames instead of 45,975. Native shader palette-row offsets replace all 80 shade/fade geometry copies, while 377 clipped effect-layer frames retain exact visible pixel priority. The build reclaims 42,758 entries and leaves 62,318 under the 65,535-frame count limit. Future canonical body frames add at most one effect frame; shade count no longer multiplies geometry. Larger independent actors can still use separate sprite resources.</p>
<p>A 16-slot per-player object pool, native terrain queries, fire absorption, sword routing and subweapon Item Crash adapters now exist; the current allocation is 8,192 bytes. New state fields still need a versioned allocation contract rather than ad hoc extension offsets. New guest projectile/familiar DLLs need native module registration/codegen; reusing existing actor primitives reduces that burden but does not remove behavior work. All clients must agree on card selection, costs, actor state and update versions for multiplayer.</p>""")
sec('options','Recommended architecture and rollout',"""
<h3>Practical near-term release</h3>
<p>Use an explicitly named <strong>Unofficial TU3 for HarmonyRecomp</strong> PC update bundle. It installs the matching EXE, native modules, shared update data and compatibility manifest. Distribute Nathan’s package as the separate DLC deliverable, with its native module installed automatically if placed there. Users should never manually edit tables, copy individual DLLs or patch saves. This is a PC update bundle, not a promise that a normal Xbox 000B0000 file alone updates an arbitrary existing recomp build.</p>
<h3>Maintainable long-term split</h3>
<p>Prepare a compatible host with shared extension points, and keep Nathan-specific implementations in a versioned DLC/native module. The host must resolve registration and dispatch correctly, including calls currently folded directly to local generated implementations. Gate extension use by loaded character/package and preserve native fallback behavior with Nathan absent.</p>
<p>Define the missing DSS behaviors before freezing the extension API. Implement representative difficult cases—a projectile pair, an elemental absorption pair, a persistent familiar and a transformation/state-changing pair—then assess whether the common callbacks suffice. It is not necessary to finish all 100 effects before a first release, but unsupported pairs must remain explicitly unavailable and new API requirements may require another update.</p>
<h3>If a genuine guest Title Update is a requirement</h3>
<p>Port shared wrappers to PPC guest code, including ABI-correct calls, trampolines/new code placement, actor callbacks and original fallbacks. Port character-only C++ to the guest Nathan DLL as well. Author a valid cumulative XEXP/DLLP update against the intended original image/version and retain TU2’s required behavior and data. Rebuild HarmonyRecomp from that patched guest image. This is a separate substantial engineering project, not repackaging the current source.</p>""")
sec('gates','Loader changes and proof gates before a rollout commitment',"""
<ol><li><strong>Update identity:</strong> replace “largest file wins” with explicit version/compatibility selection. Current build.py chooses max(package size), hardcodes the TU2 codegen config, and runtime labels any default.xexp build “2.04”. File size is not a reliable unofficial version ordering.</li>
<li><strong>Cumulative base:</strong> the current setup selects one update, not a TU2→TU3 stack. A real TU3 must preserve TU2 compatibility and match the expected base image/version. Do not assume a new delta targeting an already patched image will be layered automatically.</li>
<li><strong>Native/guest agreement:</strong> check base and patched image hashes, native API/build ID, target architecture, generated module paths and frame/state versions. Reject mismatches clearly. Loading different patch data with old compiled functions can silently execute the wrong logic.</li>
<li><strong>DLC installation:</strong> extend package/native module discovery and registration. Ensure the built list does not remove Nathan or new actor modules as uncompiled content.</li>
<li><strong>Clean content test:</strong> fresh TU2 base + proposed update + Nathan only; no development loose files or pre-edited unrelated DLC. Verify shared permission routing, not just the existing edited install.</li>
<li><strong>Saves:</strong> test fresh profiles, existing profiles with no Nathan data, current test saves and rollback. Use game-side migration; decide release card acquisition rather than granting every test card by accident.</li>
<li><strong>Future-DSS prototype:</strong> exercise projectile, shield/interception, absorption, familiar, transformation and stat/drop callbacks before committing to a frozen API.</li>
<li><strong>Multiplayer:</strong> replace the coarse 2.04 label with a TU3 build fingerprint plus DLC/API/content versions. Current lobby distinguishes game versions and treats some DLC differences as playable; incompatible DSS builds must not be accepted as identical.</li>
<li><strong>Packaging validation:</strong> no local STFS/XEXP authoring workflow has yet produced a TU3. The installed tools prove extraction/patch loading and direct XEX editing, not completed update-container construction. A PC bundle needs its own manifest/install/rollback proof.</li></ol>
<p>Readiness: a PC two-deliverable rollout has a clear implementation route. A literal drop-in guest TU3 on an unchanged recomp is a no-go. A genuine guest-code TU3 is technically plausible for gameplay after a port and matching rebuild, but is not validated by this audit.</p>""")
refs=[
(S/'scripts/build.py','step_title_update','Update extraction, one-update selection and build-time patch application'),
(S/'src/harmonyrecomp_app.h','OnLoadXexImage','Runtime update data mapping and hardcoded version reporting'),
(S/'src/dlc.cpp','void InstallDlcPackages','Built DLC allowlist and runtime installation rules'),
(S/'generated/default/module_registry.cpp','harmonyrecomp_dllTest12','Native module registration'),
(S/'CMakeLists.txt','nathan_dss_damage.cpp','Native targets, dispatch bridges and function-table placement'),
(S/'src/nathan_dss_damage.cpp','REX_EXTERN(sub_823D7170)','Shared native hooks, including verified menu palette fix'),
(S/'src/nathan_dss.cpp','REX_EXTERN(sub_836D0000)','Nathan native callbacks and extension allocation'),
(S/'src/netplay/lobby.cpp','Same version but different DLC','Game-version versus DLC mismatch handling'),
(hodpaths.legacy('modding/tools/nathan_equipment_access.py'),'def candidates','Permission patches span base and other DLC tables')]
rows=[];audit=[]
for p,needle,role in refs:
    data=p.read_bytes();lines=data.decode('utf-8-sig',errors='replace').splitlines();line=next((i+1 for i,s in enumerate(lines) if needle in s),None)
    rows.append((link(p,str(p.relative_to(R))),line or '—',E(role)))
    audit.append({'path':str(p),'line':line,'sha256':hashlib.sha256(data).hexdigest()})
sec('sources','Audit references and limits',table(['Local source','Line','Evidence'],rows)+"""
<p>Primary external references: <a href="https://github.com/rexglue/rexglue-sdk/wiki/Kernel-State-%26-Objects">ReXGlue code versus data loading</a>; <a href="https://github.com/rexglue/rexglue-sdk">ReXGlue static recompilation overview</a>; <a href="https://github.com/xenia-project/xenia/blob/master/src/xenia/cpu/xex_module.cc">Xenia’s underlying XEX patch implementation</a>. The local loader/build is the authority for this installation; newer SDK capabilities are not assumed present.</p>
<p>Judgments about port effort, the future extension API, palette scaling and remaining DSS subsystem requirements are engineering inferences from the inspected code. No custom TU3, signature compatibility, clean-install deployment or multiplayer prototype was produced/tested in this assessment.</p>""")
old=(hodpaths.legacy('modding/docs/Nathan_DLC_Technical_Report.html')).read_text(encoding='utf-8')
css=re.search(r'<style>(.*?)</style>',old,re.S).group(1)
nav=''.join('<a href="#'+id+'">'+E(title)+'</a>' for id,title,_ in parts)
body=''.join('<section id="'+id+'"><h2>'+E(title)+'</h2>'+text+'</section>' for id,title,text in parts)
page='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Unofficial TU3 — Nathan Rollout Feasibility</title><style>'+css+'</style></head><body><aside class="nav"><div class="brand">HarmonyRecomp · Architecture review</div><strong>Unofficial TU3<br>Feasibility check</strong><nav>'+nav+'</nav></aside><main><header class="hero"><small>Assessment · November 9, 2026</small><h1>Can TU3 + DLC<br>be the whole rollout?</h1><p>Current native hooks, the title-update pipeline and all 100 DSS implementation paths assessed together.</p><div class="meta">Verdict: feasible as a coordinated PC update and DLC release; not as a normal guest update on an unchanged recomp.</div></header>'+body+'<footer>Read-only feasibility audit; no runtime, save or content changes were made.</footer></main></body></html>'
out=hodpaths.legacy('modding/docs/Nathan_TU3_Feasibility.html');out.write_text(page,encoding='utf-8')
(out.with_suffix('.audit.json')).write_text(json.dumps({'date':'2026-11-09','target':'local ReXGlue 0.8-based HarmonyRecomp','implemented_pairs':100,'remaining_pairs':0,'exact_cotm_parity_complete':False,'guest_tu3_built':False,'files':audit},indent=2)+'\n')
print(out)
