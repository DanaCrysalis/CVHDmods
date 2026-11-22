"""Trace shield spell MIPS from the user's USA disc; no decompiler code included."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys,struct,json,hashlib
from pathlib import Path
ROOT=hodpaths.GAME
sys.path.insert(0,str(hodpaths.legacy('modding/build/sotn_trace_deps')))
import unicorn as u
from unicorn.mips_const import *
import shield_rod as source
class Trace:
 def __init__(self,slot):
  _,disc=source.open_disc();self.slot=slot;self.code=source.WeaponSlot(disc.get('BIN/WEAPON0.BIN'),slot).code
  self.uc=u.Uc(u.UC_ARCH_MIPS,u.UC_MODE_MIPS32|u.UC_MODE_LITTLE_ENDIAN)
  self.uc.mem_map(0,0x200000)
  exe=disc.get('SLUS_000.67');at,size=struct.unpack_from('<II',exe,0x18)
  self.put(at,exe[0x800:0x800+size]);self.put(0x800A0000,disc.get('DRA.BIN'));self.put(source.V,self.code)
  self.entity=0x801E0000;self.player=0x800733D8;self.events=[];self.destroyed=False
  self.w32(self.entity,160<<16);self.w32(self.entity+4,160<<16)
  self.w32(self.player,160<<16);self.w32(self.player+4,160<<16)
  self.w16(self.player+0x24,0x100)
  self.w16(self.entity+0x26,1)
  self.w32(0x8006C3B8,self.entity)
  self.w32(0x8003C788,0x801D1000)
  for address in range(0x8003C7B0,0x8003C8A0,4):self.w32(address,0x801D0000+(address&0xFFF))
  self.prim_count=0;self.frame=0;self.prim_used=0
  self.calls={};self.uc.hook_add(u.UC_HOOK_CODE,self.hook)
 def put(self,a,b):self.uc.mem_write(a&0x1FFFFFFF,b)
 def get(self,a,n):return bytes(self.uc.mem_read(a&0x1FFFFFFF,n))
 def r32(self,a):return struct.unpack('<I',self.get(a,4))[0]
 def w32(self,a,v):self.put(a,struct.pack('<I',v&0xffffffff))
 def w16(self,a,v):self.put(a,struct.pack('<H',v&0xffff))
 def hook(self,uc,pc,n,data):
  if pc==0x801F0000:uc.emu_stop();return
  if source.V<=pc<source.V+len(self.code):return
  args=[uc.reg_read(x) for x in [UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2]]
  if 0x80016C9C<=pc<0x80017000:return  # original fixed-point sine lookup
  self.calls[pc]=args
  value=0
  if pc==0x801D07B8:
   self.prim_count=args[1]
   value=self.prim_used;self.prim_used+=self.prim_count
   for i in range(self.prim_count):
    at=0x80086FEC+(value+i)*52;self.put(at,bytes(52));self.w32(at,at+52 if i+1<self.prim_count else 0)
    # Native primitive storage starts zeroed. RGB bytes are also used as
    # counters/phase flags; inventing neutral RGB corrupts their state.
    self.put(at+7,bytes([args[0]]))
   # The native allocator clears the continuation bit on the last primitive.
   self.put(at+7,bytes([args[0]&0xef]))
  elif pc==0x801D07B4:pass
  elif pc==0x801D07D0:self.put(args[1],bytes(32))
  elif pc==0x801D07C0:self.events.append({"frame":self.frame,"shake":args[0]})
  elif pc==0x800160E4:
   self.rand=(getattr(self,"rand",1)*1103515245+12345)&0xffffffff;value=(self.rand>>16)&0x7fff
  elif pc==0x80012B24:pass # diagnostic string formatting; not used by spell geometry
  elif pc==0x801D07F4:self.events.append({'frame':self.frame,'factory':args[1]});value=0x801E1000
  elif pc==0x801D07DC:self.events.append({'frame':self.frame,'sound':args[0]})
  elif 0x801D07B0<=pc<0x801D08A0:
   self.events.append({'frame':self.frame,'api':hex(pc),'args':args})
  else:raise RuntimeError(f'unhandled external {pc:08X} ra={uc.reg_read(UC_MIPS_REG_RA):08X} {args}')
  uc.reg_write(UC_MIPS_REG_V0,value);uc.reg_write(UC_MIPS_REG_PC,uc.reg_read(UC_MIPS_REG_RA))
 def animate(self,entity):
  pointer=self.r32(entity+0x4c)
  if not pointer:return
  pose=struct.unpack('<H',self.get(entity+0x50,2))[0];timer=struct.unpack('<h',self.get(entity+0x52,2))[0]
  if timer<0:return
  if timer:
   timer-=1
   if not timer:pose+=1
  if not timer:
   for _ in range(4):
    duration,frame=struct.unpack('<HH',self.get(pointer+pose*4,4))
    if duration==0xffff:timer=-1;break
    if duration==0:pose=frame;continue
    timer=duration;self.w16(entity+0x56,frame&0x1ff);break
  self.w16(entity+0x50,pose);self.w16(entity+0x52,timer)
 def tick(self):
  self.uc.reg_write(UC_MIPS_REG_A0,self.entity);self.uc.reg_write(UC_MIPS_REG_SP,0x801FF000);self.uc.reg_write(UC_MIPS_REG_RA,0x801F0000)
  self.w32(0x8003C998,self.frame)
  self.uc.emu_start(self.r32(source.V+0x20),0x801F0000,count=100000)
  self.animate(self.entity)
  self.frame+=1
def capture(slot,facing=0):
 t=Trace(slot);t.w16(t.player+0x14,facing);t.w16(t.entity+0x14,facing)
 frames=[]
 for i in range(1200):
  t.tick();ent=t.get(t.entity,0xBC)
  phase=struct.unpack_from('<H',ent,0x2C)[0]
  if i and phase==0:break
  prims=[t.get(0x80086FEC+j*52,52).hex() for j in range(t.prim_count)]
  frames.append({'entity':ent.hex(),'prims':prims})
 else:raise RuntimeError(f'slot {slot} did not terminate')
 return {'slot':slot,'facing':facing,'code_sha256':hashlib.sha256(t.code).hexdigest(),
         'entry':hex(t.r32(source.V+0x20)),'primitive_init':'zero-v2','events':t.events,'frames':frames}
def main():
 out=hodpaths.legacy('modding/build/sotn_spell_traces');out.mkdir(parents=True,exist_ok=True)
 slots=[8,9,10,11,23,24,25,26,27,28,29,52,58] if '--all' in sys.argv else [int(sys.argv[1])]
 for slot in slots:
  for facing in [0,1]:
   
   if (out/f'{slot:02}_{facing}.json').exists() and '--refresh' not in sys.argv:continue
   r=capture(slot,facing);(out/f'{slot:02}_{facing}.json').write_text(json.dumps(r,separators=(',',':')))
   print(slot,facing,len(r['frames']),r['events'],flush=True)
if __name__=='__main__':main()
