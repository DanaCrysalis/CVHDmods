"""Extend hunter item permissions to Nathan without changing other characters.

Base tables remain base tables; DLC tables remain in their original packages.
No shared-path overrides are introduced in Nathan's package. No save edits.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse
import datetime
import hashlib
import json
import shutil
import struct
from pathlib import Path

ROOT = hodpaths.GAME
STAGE = hodpaths.legacy('modding/build/nathan_equipment_access')
NATHAN = 0x800
HUNTERS = 0x21C  # Jonathan, Julius, Richter, Simon (character IDs 3,4,5,10)
CLASSIC = 0x18   # Julius/Richter sub-weapons, including Bible and Ricochet Rock


def candidates():
    yield ROOT/'assets/data/player/guardset.dat', Path('base/data/player/guardset.dat'), 78, 0x14, HUNTERS
    yield ROOT/'assets/data/player/subweaponset.dat', Path('base/data/player/subweaponset.dat'), 70, 0x22, CLASSIC
    dlc = ROOT/'.setup/package/src/assets/dlc'
    for pattern, size, offset, inherit in [('guardset_dlc*.dat',78,0x14,HUNTERS),
                                          ('subweaponset_dlc*.dat',70,0x22,CLASSIC)]:
        for p in sorted(dlc.rglob(pattern)):
            yield p, Path('dlc')/p.relative_to(dlc), size, offset, inherit


def build():
    report=[]
    for source,rel,size,offset,inherit in candidates():
        old=source.read_bytes(); data=bytearray(old)
        count,first=struct.unpack_from('>II',old,8)
        assert len(old)==20+count*size
        eligible=[]; allowed=set()
        for i in range(count):
            p=16+i*size+offset; mask=struct.unpack_from('>I',old,p)[0]
            if mask&inherit:
                struct.pack_into('>I',data,p,mask|NATHAN)
                eligible.append(first+i); allowed.update(range(p,p+4))
            else:
                assert not mask&NATHAN, 'Unexpected prior Nathan grant outside hunter set'
            assert (int.from_bytes(data[p:p+4],'big')&~NATHAN)==(mask&~NATHAN)
        assert all(a==b for i,(a,b) in enumerate(zip(old,data)) if i not in allowed)
        # Exclude Fuma-only tables, etc., which have no eligible equipment.
        if not eligible: continue
        target=STAGE/rel; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
        report.append({'path':rel.as_posix(),'record_size':size,'permission_offset':offset,
                       'inherit_mask':hex(inherit),'eligible_indices':eligible,
                       'sha256':hashlib.sha256(data).hexdigest()})
    (STAGE/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Built hunter permissions:',sum(len(r['eligible_indices']) for r in report),'items in',len(report),'tables')


def install(active=False):
    report=json.loads((STAGE/'report.json').read_text())
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=hodpaths.legacy('modding/backups')/f'nathan_equipment_access_{stamp}'
    changes=[]
    for row in report:
        rel=Path(row['path']); source=STAGE/rel; data=source.read_bytes()
        assert hashlib.sha256(data).hexdigest()==row['sha256']
        if rel.parts[0]=='base':
            if active: continue
            targets=[ROOT/'assets'/Path(*rel.parts[1:]), ROOT/'.setup/package/src/assets'/Path(*rel.parts[1:])]
        elif active:
            targets=[Path.home()/'Documents/harmonyrecomp/0000000000000000/58410A7A/00000002'/Path(*rel.parts[1:])]
        else:
            targets=[ROOT/'.setup/package/src/assets'/rel]
        for target in targets:
            assert target.is_file(),f'Missing installed table: {target}'
            old=target.read_bytes(); assert len(old)==len(data)
            size,off=row['record_size'],row['permission_offset']
            # An install must change only the Nathan permission bit.
            first=int.from_bytes(old[12:16],'big')
            allowed={16+(index-first)*size+off+2 for index in row['eligible_indices']}
            assert all(a==b for i,(a,b) in enumerate(zip(old,data)) if i not in allowed), str(target)
            assert all((old[i]^data[i]) in (0,8) for i in allowed)
            dest=backup/str(len(changes))/target.name; dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,dest)
            target.write_bytes(data); assert target.read_bytes()==data
            changes.append({'target':str(target),'backup':str(dest),'sha256':row['sha256']})
    backup.mkdir(parents=True,exist_ok=True)
    (backup/'install_manifest.json').write_text(json.dumps(changes,indent=2)+'\n')
    print('Installed',len(changes),'tables; backups:',backup)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--install',action='store_true'); ap.add_argument('--active',action='store_true')
    args=ap.parse_args()
    if args.install or args.active: install(active=args.active)
    else: build()
