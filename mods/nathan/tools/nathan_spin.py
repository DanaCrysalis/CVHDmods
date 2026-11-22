"""Hold-to-spin for Nathan's code module (dllTest12.dll, Simon's code rebased).

Circle of the Moon: holding attack after a whip swing makes Nathan spin the
whip until the button is let go. This adds that to his module without
touching the game's own code:

  * a 0x200-byte executable section `.nathan` (0x836EC000) in the zero gap between
    .text and .data, holding two new functions (the recompiler finds them
    through the vtable pointers below; a rebuild with codegen is needed);
  * player vtable entry 86 (setState, 0x836C2A40) -> spin_set_state:
    standing whip (state 23, motion 187) returns to state 1; crouching whip
    (state 24, motion 188) returns to state 8. With attack held, switch to
    the corresponding rotation and suppress only that normal idle return;
  * both attack-state updates maintain the hit-object phase while held,
    then request the matching standing/crouching idle when attack is released;
  * motion 191 -> slot 28 (standing spin), 192 -> slot 29 (crouching spin),
    both looping. Other state requests pass through unchanged.

Input: the standing state's object (player + 0x60) + 0xC points to the input
block; +0 = held buttons (attack 0x20, jump 0x10, Y 0x40, B 0x80).

usage: nathan_spin.py <dllTest12.dll> [<dllTest12.dll> ...]
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct, sys
from pathlib import Path

SECTION_VA = 0x836EC000
SECTION_SIZE = 0x200
SPIN_MOTION = 191
SPIN_ANIM = 28
CROUCH_SPIN_MOTION = 192
CROUCH_SPIN_ANIM = 29
MOTION_TABLE = 0x836C1DD0
ATTACK = 0x20
PHASE_ACTIVE, PHASE_DONE = 2, 3    # player + 612, read by the whip hit object
VT_SET_STATE = 0x836C2A40          # player vtable entry 86
VT_STATE23_UPDATE = 0x836C2D6C     # state 23 vtable entry 1
VT_STATE24_UPDATE = 0x836C2D84     # crouching attack update
ORIG_SET_STATE = 0x836D4690
ORIG_STATE23_UPDATE = 0x836D1468
ORIG_STATE24_UPDATE = 0x836D15D0
SET_MOTION = 0x836DBEF8            # state vtable entry 5: (state, motion, param)

# ---------------------------------------------------------------- assembler --
def D(op, rt, ra, imm): return (op << 26) | (rt << 21) | (ra << 16) | (imm & 0xFFFF)
def lwz(rt, d, ra): return D(32, rt, ra, d)
def stw(rs, d, ra): return D(36, rs, ra, d)
def li(rt, v): return D(14, rt, 0, v)
def cmpwi(cr, ra, v): return (11 << 26) | (cr << 23) | (ra << 16) | (v & 0xFFFF)
def cmplwi(cr, ra, v): return (10 << 26) | (cr << 23) | (ra << 16) | (v & 0xFFFF)
def andi_(ra, rs, v): return D(28, rs, ra, v)
BLR = 0x4E800020
def beqlr(cr): return (19 << 26) | (12 << 21) | ((4 * cr + 2) << 16) | (16 << 1)

class Asm:
    def __init__(self, origin):
        self.origin, self.code, self.fix, self.labels = origin, [], [], {}
    @property
    def pc(self): return self.origin + 4 * len(self.code)
    def label(self, name): self.labels[name] = self.pc
    def emit(self, *words): self.code.extend(words)
    def bc(self, bo, cr, eq, target):        # eq: the cr bit (2 = eq)
        self.fix.append((len(self.code), 'bc', bo, 4 * cr + eq, target)); self.code.append(0)
    def beq(self, cr, t): self.bc(12, cr, 2, t)
    def bne(self, cr, t): self.bc(4, cr, 2, t)
    def b(self, target):
        self.fix.append((len(self.code), 'b', 0, 0, target)); self.code.append(0)
    def words(self):
        for i, kind, bo, bi, t in self.fix:
            dest = self.labels[t] if isinstance(t, str) else t
            disp = dest - (self.origin + 4 * i)
            if kind == 'b':
                assert -(1 << 25) <= disp < (1 << 25)
                self.code[i] = (18 << 26) | (disp & 0x03FFFFFC)
            else:
                assert -(1 << 15) <= disp < (1 << 15)
                self.code[i] = (16 << 26) | (bo << 21) | (bi << 16) | (disp & 0xFFFC)
        return self.code

def build():
    a = Asm(SECTION_VA)
    variants=(('stand',23,1,187,SPIN_MOTION,ORIG_STATE23_UPDATE),
              ('crouch',24,8,188,CROUCH_SPIN_MOTION,ORIG_STATE24_UPDATE))
    # Preserve the caller's state-object pointer (r3) through each update.
    for name,state,rest,swing,motion,original in variants:
        a.label('spin_update' if name=='stand' else 'crouch_spin_update')
        a.emit(lwz(11,4,3),cmplwi(6,11,0)); a.beq(6,name+'_u_tail')
        a.emit(lwz(10,584,11),cmpwi(6,10,motion)); a.bne(6,name+'_u_tail')
        a.emit(lwz(10,0x60,11),lwz(10,12,10),lwz(10,0,10),andi_(10,10,ATTACK),li(10,PHASE_ACTIVE))
        a.bne(0,name+'_u_phase')
        a.emit(li(10,rest),stw(10,580,11),li(10,0),stw(10,588,11),li(10,PHASE_DONE))
        a.label(name+'_u_phase'); a.emit(stw(10,612,11))
        a.label(name+'_u_tail'); a.b(original)
    # Intercept only the matching attack's ordinary return-to-idle request.
    # Damage, jump and other interruptions continue through the original setter.
    a.label('spin_set_state')
    a.emit(lwz(11,572,3),cmpwi(6,11,23)); a.beq(6,'stand_set')
    a.emit(cmpwi(6,11,24)); a.beq(6,'crouch_set'); a.b('s_orig')
    for name,state,rest,swing,motion,original in variants:
        a.label(name+'_set')
        a.emit(cmpwi(6,4,rest)); a.bne(6,'s_orig')
        a.emit(lwz(11,0x60,3),lwz(11,12,11),lwz(11,0,11),andi_(11,11,ATTACK)); a.beq(0,'s_orig')
        a.emit(lwz(11,584,3),cmpwi(6,11,motion)); a.beq(6,'s_keep')
        a.emit(cmpwi(6,11,swing)); a.bne(6,'s_orig')
        a.emit(li(11,PHASE_ACTIVE),stw(11,612,3),lwz(3,(state+23)*4,3),li(4,motion),li(5,0))
        a.b(SET_MOTION)
    a.label('s_keep'); a.emit(li(11,PHASE_ACTIVE),stw(11,612,3),BLR)
    a.label('s_orig'); a.b(ORIG_SET_STATE)
    words = a.words()
    assert 4 * len(words) <= SECTION_SIZE
    return words, a.labels

# ------------------------------------------------------------------ XEX file --
class Xex:
    def __init__(self, path):
        self.path = Path(path)
        self.x = bytearray(self.path.read_bytes())
        assert self.x[:4] == b'XEX2'
        ff = None
        for i in range(struct.unpack_from('>I', self.x, 0x14)[0]):
            k, v = struct.unpack_from('>II', self.x, 0x18 + i * 8)
            if k == 0x000003FF: ff = v
            if k == 0x00010201: self.base = v
        assert struct.unpack_from('>HH', self.x, ff + 4) == (0, 0), 'module is encrypted or compressed'
        self.pe = struct.unpack_from('>I', self.x, 0x08)[0]
    def off(self, addr): return self.pe + addr - self.base
    def word(self, addr): return struct.unpack_from('>I', self.x, self.off(addr))[0]
    def set_word(self, addr, old, new):
        cur = self.word(addr)
        assert cur in (old, new), f'{addr:#x} is {cur:#010x}, expected {old:#010x}'
        struct.pack_into('>I', self.x, self.off(addr), new)
    def save(self): self.path.write_bytes(bytes(self.x))

def add_section(x):
    img = x.pe                                 # image (and its PE headers) start here
    pe = img + struct.unpack_from('<I', x.x, img + 0x3C)[0]
    n = struct.unpack_from('<H', x.x, pe + 6)[0]
    sec = pe + 24 + struct.unpack_from('<H', x.x, pe + 20)[0]
    names = [x.x[sec + 40 * i:sec + 40 * i + 8].rstrip(b'\0') for i in range(n)]
    if b'.nathan' in names:
        i=names.index(b'.nathan'); entry=sec+40*i
        # The existing 0x100-byte section has free space before .data.
        va=SECTION_VA-x.base
        for j in range(n):
            if j==i: continue
            size,start=struct.unpack_from('<II',x.x,sec+40*j+8)
            assert start+size<=va or start>=va+SECTION_SIZE,'expanded .nathan overlaps another section'
        struct.pack_into('<I',x.x,entry+8,SECTION_SIZE)
        struct.pack_into('<I',x.x,entry+16,SECTION_SIZE)
        return False
    assert sec + 40 * (n + 1) <= img + 0x400 and not any(x.x[sec + 40 * n:sec + 40 * (n + 1)])
    va = SECTION_VA - x.base
    struct.pack_into('<8sIIIIIIHHI', x.x, sec + 40 * n, b'.nathan', SECTION_SIZE, va,
                     SECTION_SIZE, va, 0, 0, 0, 0, 0x60000020)       # code | execute | read
    struct.pack_into('<H', x.x, pe + 6, n + 1)
    return True

def main(paths):
    words, labels = build()
    for p in paths:
        x = Xex(p)
        area = slice(x.off(SECTION_VA), x.off(SECTION_VA + SECTION_SIZE))
        assert not any(x.x[area]) or x.word(SECTION_VA) == words[0], 'section area is not empty'
        x.x[area] = bytes(SECTION_SIZE)                      # rewrite from scratch
        added = add_section(x)
        for i, w in enumerate(words):
            struct.pack_into('>I', x.x, x.off(SECTION_VA + 4 * i), w)
        for vt, orig, new in ((VT_SET_STATE, ORIG_SET_STATE, labels['spin_set_state']),
                              (VT_STATE23_UPDATE, ORIG_STATE23_UPDATE, labels['spin_update']),
                              (VT_STATE24_UPDATE, ORIG_STATE24_UPDATE, labels['crouch_spin_update'])):
            cur = x.word(vt)
            # the original function, or an earlier version of this hook
            x.set_word(vt, cur if SECTION_VA <= cur < SECTION_VA + SECTION_SIZE else orig, new)
        for motion,slot in ((SPIN_MOTION,SPIN_ANIM),(CROUCH_SPIN_MOTION,CROUCH_SPIN_ANIM)):
            m=MOTION_TABLE+8*motion
            x.set_word(m,0xFF,slot); x.set_word(m+4,0,2)
        # Separate the once-only lowering transition from crouch idle. Both
        # originally used slot 2, which replayed lowering in the looping idle.
        x.set_word(MOTION_TABLE+20*8,2,30)
        x.set_word(MOTION_TABLE+20*8+4,0,0)
        x.save()
        print(f'{p}: section {"added" if added else "kept"}, {len(words)} instructions at '
              f'{SECTION_VA:#x}, hooks set, motions 191/192 -> slots 28/29 (loop)')

if __name__ == '__main__':
    main(sys.argv[1:])
