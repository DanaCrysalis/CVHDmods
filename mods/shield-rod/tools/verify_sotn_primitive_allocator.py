"""Check the capture allocator against original instructions on the user's disc."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
from trace_sotn_shields import Trace,u
from unicorn.mips_const import UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_RA,UC_MIPS_REG_SP,UC_MIPS_REG_V0

class NativeTrace(Trace):
 def hook(self,uc,pc,n,data):
  if 0x800eda70<=pc<0x800eda94 or 0x800edb58<=pc<0x800edc80:return
  super().hook(uc,pc,n,data)

def main():
 checks=0
 for kind in (1,3,4,0x14):
  for count in (1,12,32):
   native=NativeTrace(8);fixture=Trace(8)
   # Dirty free storage proves the native routine clears bytes, rather than
   # accidentally depending on newly allocated emulator memory being zero.
   dirty=bytearray([0xa5]*(52*1024))
   dirty[7::52]=bytes(1024)
   native.put(0x80086fec,bytes(dirty));fixture.put(0x80086fec,bytes(dirty))
   for t in (native,fixture):
    t.uc.reg_write(UC_MIPS_REG_A0,kind);t.uc.reg_write(UC_MIPS_REG_A1,count)
    t.uc.reg_write(UC_MIPS_REG_RA,0x801f0000);t.uc.reg_write(UC_MIPS_REG_SP,0x801ff000)
   native.uc.emu_start(0x800edb58,0x801f0000,count=100000)
   fixture.hook(fixture.uc,0x801d07b8,4,None)
   assert native.uc.reg_read(UC_MIPS_REG_V0)==fixture.uc.reg_read(UC_MIPS_REG_V0)==0
   assert native.get(0x80086fec,52*count)==fixture.get(0x80086fec,52*count),(kind,count)
   checks+=1
 print(f'Passed {checks} native-disc allocator comparisons (dirty free storage, RGB, links, types).')

if __name__=='__main__':main()
