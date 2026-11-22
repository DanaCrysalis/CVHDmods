"""Read-only facts about a DLC enemy module: base, factory export, object vtable, init slot.

  python modding/tools/modinfo.py <module.dll> [vtable slots to disassemble...]
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from moddisasm import load, disasm


def factory(image, base):
    """Export 1 from the XEX export table (magic 00 48 56 45 'HVE')."""
    at = image.find(b'\x00\x48\x56\x45')
    words = struct.unpack_from('>12I', image, at - 4)
    assert words[8] == base >> 16, 'export table base mismatch'
    return base + words[11]


def vtable(image, base, fac):
    """The first `stw rX,0(r31)` after the factory's lis/addi pair gives the vtable."""
    from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
    md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    regs = {}
    for i in md.disasm(image[fac - base:fac - base + 0x200], fac):
        ops = [o.strip() for o in i.op_str.split(',')]
        if i.mnemonic == 'lis':
            regs[ops[0]] = (int(ops[1], 0) << 16) & 0xFFFFFFFF
        elif i.mnemonic == 'addi' and ops[1] in regs:
            regs[ops[0]] = (regs[ops[1]] + int(ops[2], 0)) & 0xFFFFFFFF
        elif i.mnemonic == 'stw' and ops[1] == '0(r31)' and ops[0] in regs:
            return regs[ops[0]]
    return None


if __name__ == '__main__':
    image, base = load(sys.argv[1])
    fac = factory(image, base)
    vt = vtable(image, base, fac)
    print(f'base {base:#x} factory {fac:#x} vtable {vt:#x}')
    for s in sys.argv[2:]:
        slot = int(s, 0)
        target = struct.unpack_from('>I', image, vt - base + 4 * slot)[0]
        print(f'--- slot {slot} ({slot * 4:#x}) -> {target:#x}')
        disasm(image, base, target, 0x180)
