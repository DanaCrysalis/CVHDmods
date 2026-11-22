"""Execute original USA CotM summon controllers in an isolated ARM fixture.

Only engine allocation, sound and collision queries are substituted. Animation
scripts, spawns and movement run directly from the user's ROM. No enemy contacts
are injected: traces describe the unobstructed visual timeline.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys,struct,json,hashlib
from pathlib import Path
R=hodpaths.GAME
sys.path.insert(0,str(hodpaths.legacy('modding/build/sotn_trace_deps')))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import *
from nathan_paths import cotm_rom
ROM=cotm_rom();REG=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)
class Trace:
 def __init__(self,attribute):
  self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u=self.u
  for a,n in ((0x02000000,0x200000),(0x03000000,0x10000),(0x04000000,0x10000),(0x05000000,0x10000),(0x06000000,0x20000),(0x07000000,0x10000),(0x08000000,0x2000000)):
   u.mem_map(a,n)
  u.mem_write(0x08000000,ROM);u.mem_write(0x03000000,ROM[0xc39a8:0xc41d0])
  self.heap=0x02040000;self.actors=[];self.dead=set();self.tick=0;self.calls={};self.spawn=[]
  self.attribute=attribute
  self.put(0x02025368+0x304,attribute,1);self.put(0x02025368+0x2e2,100,2)
  self.player=self.alloc(0xbc);sp=self.alloc(0x80);self.put(self.player+0x38,sp);self.put(sp+0x14,68<<16);self.put(sp+0x18,148<<16)
  self.put(0x02025ff0+0x186c,self.player)
  self.root=self.actor(0x64+attribute*2 if attribute<9 else 0x76)
  u.hook_add(UC_HOOK_CODE,self.hook)
 def get(self,a,n=4,signed=False):return int.from_bytes(self.u.mem_read(a,n),'little',signed=signed)
 def put(self,a,v,n=4):self.u.mem_write(a,int(v&((1<<(n*8))-1)).to_bytes(n,'little'))
 def alloc(self,n):
  p=self.heap;self.heap+=(n+15)&~15;self.u.mem_write(p,bytes(n));return p
 def actor(self,id):
  p=self.alloc(0xbc);self.put(p,id,2);self.put(p+0x22,0xffff,2);self.put(p+0x7c,self.player)
  fn=struct.unpack_from('<I',ROM,0x66c1b8+id*4)[0]
  self.actors.append((p,fn));self.spawn.append((self.tick,id,hex(fn)));return p
 def ret(self,v=0):self.u.reg_write(UC_ARM_REG_R0,v);self.u.reg_write(UC_ARM_REG_PC,self.u.reg_read(UC_ARM_REG_LR))
 def hook(self,u,a,size,data):
  if a==0x03007e00:u.emu_stop();return
  if a not in (0x0800168c,0x0800355c,0x08016190,0x0806d2d0,0x0808449c,0x0806d2a0,0x08001480,0x08005e80,0x080161f0,0x0806d7b4):return
  r=[u.reg_read(k)for k in REG]
  if a==0x0800168c:
   p=self.alloc(r[2]);self.put(r[0]+0x3c+r[3]*16,p);self.ret(p)
  elif a==0x0800355c:
   p=self.alloc(0x80);self.put(p+4,256,2);self.put(p+6,256,2);self.put(p+0x2a,0xc0,1);self.ret(p)
  elif a==0x08016190:self.ret(self.alloc(0x80))
  elif a in (0x0806d2d0,0x0808449c):self.dead.add(r[0]);self.ret()
  elif a in (0x0806d2a0,0x08001480):
   p=self.actor(r[1]);self.put(p+0x28,r[0]);self.ret(p)
  elif a in (0x08005e80,0x080161f0,0x0806d7b4):self.ret()
  if a==0x03007e00:u.emu_stop()
 def run(self,n=384):
  frames=[]
  for self.tick in range(n):
   for p,fn in list(self.actors):
    if p in self.dead:continue
    u=self.u;u.reg_write(UC_ARM_REG_SP,0x03007c00);u.reg_write(UC_ARM_REG_LR,0x03007e01);u.reg_write(UC_ARM_REG_R0,p)
    try:u.emu_start(fn|1,0x03007e00,count=100000)
    except Exception as e:raise RuntimeError(f'attr={self.attribute} tick={self.tick} actor={p:x} fn={fn:x} pc={u.reg_read(UC_ARM_REG_PC):x} {e}')from e
    if u.reg_read(UC_ARM_REG_PC)!=0x03007e00:raise RuntimeError(f'instruction limit {u.reg_read(UC_ARM_REG_PC):x}')
   draws=[]
   for p,fn in self.actors:
    sp=self.get(p+0x38)
    if p in self.dead or not sp:continue
    bank=self.get(sp+0x24);frame=self.get(sp+0x28,2)
    if bank:
     draws.append(dict(id=self.get(p,2),instance=p,bank=bank,frame=frame,x=self.get(sp+0x14,4,True),y=self.get(sp+0x18,4,True),flags=self.get(sp+0x1c),sx=self.get(sp+4,2),sy=self.get(sp+6,2),angle=self.get(sp+8,2)))
   frames.append(draws)
  return dict(attribute=self.attribute,rom_sha1=hashlib.sha1(ROM).hexdigest(),spawn=self.spawn,frames=frames)
if __name__=='__main__':
 out=hodpaths.legacy('modding/build/cotm_summon_trace');out.mkdir(parents=True,exist_ok=True)
 for i in map(int,sys.argv[1:] or range(10)):
  t=Trace(i);r=t.run();(out/f'{i}.json').write_text(json.dumps(r,separators=(',',':')));print(i,len(t.actors),sum(map(len,r['frames'])),r['spawn'][:4],flush=True)
