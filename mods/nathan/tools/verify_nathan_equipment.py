"""Check staged permissions and equipment routing against the guest's classifier.

Uses the original soul-type jump table and return instructions, rather than
assuming inventory icon numbers are equipment categories.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json
import struct
from pathlib import Path
import nathan_cards as cards
import nathan_equipment_access as access


def main():
    cards.verify()
    from nathan_paths import CodeImage
    image=CodeImage('hod_image.bin',0x82000000); word=image.word; byte=image.byte
    # 8246EA48 reads runtime +0xC: file entry +0x10 (lookup skips 4 bytes).
    assert word(0x8246ea94)==0xA063000C
    assert word(0x823c96c0)==0xA1630030  # distinct icon getter
    # Item category 6 (SOUL) dispatches to 823C9798 -> 8246EC70.
    assert 0x823c9738+byte(0x821dedd8+6)==0x823c9798
    assert word(0x823c9798)==0x480A54D9
    assert word(0x823c97ac)==0x3860000D  # soul class 2 -> passive slot 13
    assert word(0x823c97b4)==0x3860000C  # soul class 1 -> RB slot 12
    def slot(entry):
        soul_type=int.from_bytes(entry[16:18],'big')
        if not 3<=soul_type<=14: return 8
        va=0x8246ecb4+byte(0x821ded70+soul_type-3)
        ins=word(va); assert ins>>16==0x3860  # li r3, immediate
        return {0:8,1:12,2:13}[ins&0xffff]
    table=(cards.STAGE/'data/item/soulset_dlc17.dat').read_bytes()
    for index,expected in enumerate((12,)+(13,)*10+(8,)+(12,)*9):
        e=bytearray(table[16+index*60:76+index*60])
        assert slot(e)==expected
        # Icon changes must never affect equipment placement.
        e[52:54]=bytes(2); assert slot(e)==expected
        assert int.from_bytes(e[12:16],'big')==(0 if index==11 else 0x800)
    # Card Swap must belong to the upper secondary-weapon Y row. All lower
    # directional B rows remain enabled. This checks native classification,
    # actual item metadata and the character definition together.
    weapon=(cards.STAGE/'data/item/weaponset_dlc17.dat').read_bytes()
    assert struct.unpack_from('>III',weapon,4)==(3,2,0x91)
    utility=weapon[166:316]
    assert len(utility)==150 and cards.CARD_SWAP==0x33+0x92
    assert struct.unpack_from('>II',utility,0x3c)==(1,1)
    assert int.from_bytes(utility[0x38:0x3c],'big')==0x800
    assert utility[0x54:0x94]==bytes([255])*64
    assert word(0x821D4878+3*4)<=cards.CARD_SWAP<word(0x821D4878+4*4)
    assert 0x823c9738+byte(0x821dedd8+3)==0x823c9740
    assert word(0x823c9740)==0x38600000 # WEPN -> weapon equipment class
    definition=(cards.STAGE/'data/player/player_test12.def').read_bytes()
    flags=int.from_bytes(definition[0x2c:0x2e],'big')
    assert not flags&3 and flags&0xF00==0xF00
    assert int.from_bytes(definition[0x34:0x38],'big')==cards.CARD_SWAP
    assert all(int.from_bytes(definition[0x30+i*4:0x34+i*4],'big')!=cards.LEGACY_CARD_SWAP for i in range(8,12))
    counts={'guard':0,'subweapon':0}
    for source,rel,size,off,inherit in access.candidates():
        old=source.read_bytes(); target=access.STAGE/rel
        if not target.exists(): continue
        new=target.read_bytes(); n=int.from_bytes(old[8:12],'big')
        allowed=set()
        for i in range(n):
            p=16+i*size+off; before=int.from_bytes(old[p:p+4],'big'); after=int.from_bytes(new[p:p+4],'big')
            assert after==(before|0x800 if before&inherit else before)
            assert before&0x7ff==after&0x7ff
            if before&inherit:
                allowed.update(range(p,p+4)); counts['guard' if size==78 else 'subweapon']+=1
        assert len(old)==len(new) and all(a==b for i,(a,b) in enumerate(zip(old,new)) if i not in allowed)
    base=(access.STAGE/'base/data/player/subweaponset.dat').read_bytes()
    assert [i for i in range(12) if int.from_bytes(base[16+i*70+34:16+i*70+38],'big')&0x800]==list(range(6))
    report={'card_equipment_slots':[slot(table[16+i*60:76+i*60]) for i in range(len(cards.CARD_RECORDS))],
            'hunter_items_enabled':counts,'other_character_permissions_unchanged':True,
            'Card_Swap':{'category':'WEPN','item_id':hex(cards.CARD_SWAP),'locked_Y_slot':1,'B_slots_8_to_11_unlocked':True},'guest_classifier_verified':True,'live_menu_verified':False}
    image.save()
    (access.STAGE/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
