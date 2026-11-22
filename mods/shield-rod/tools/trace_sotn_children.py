"""Capture original weapon child routines; isolated PSX scene, deterministic seed."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import json,struct,sys,math
from pathlib import Path
from trace_sotn_shields import Trace,source,u,UC_MIPS_REG_A0,UC_MIPS_REG_SP,UC_MIPS_REG_RA,UC_MIPS_REG_PC,UC_MIPS_REG_V0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3
ROOT=source.ROOT
class ChildTrace(Trace):
 def hook(self,uc,pc,n,data):
  self.recent=(getattr(self,"recent",[])+[hex(pc)])[-12:]
  args=[uc.reg_read(r) for r in (UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3)]
  value=0;handled=True
  if pc==0x80016EEC:value=math.isqrt(args[0])
  elif pc==0x801D080C and hasattr(self,'trace_target'):value=0x801E3000
  elif pc==0x801D0810:
   value=0xffffffff
   if hasattr(self,'trace_target'):
    x,y=struct.unpack('<ii',self.get(args[0],8));tx,ty=self.trace_target
    value=round(math.atan2(y/65536-ty,tx-x/65536)*4096/(2*math.pi))&0xfff
  elif pc==0x80017E3C:self.matrix=struct.unpack('<9h',self.get(args[0],18))
  elif pc==0x80017ECC:self.translation=struct.unpack('<3i',self.get(args[0]+20,12))
  elif pc==0x8001805C:self.focal=args[0]
  elif pc==0x8001803C:self.center=args[:2]
  elif pc in (0x800182DC,0x8001833C):
   def transform(at):
    v=struct.unpack('<3h',self.get(at,6));m=self.matrix;t=self.translation
    return [((sum(m[i*3+j]*v[j] for j in range(3)))>>12)+t[i] for i in range(3)]
   if pc==0x800182DC:
    xyz=transform(args[0]);self.put(args[1],struct.pack('<3i',*xyz));self.w32(args[2],0)
   else:
    sp=uc.reg_read(UC_MIPS_REG_SP);outputs=[self.r32(sp+16+i*4) for i in range(6)]
    for at,out in zip(args,outputs):
     x,y,z=transform(at);cx,cy=self.center;f=self.focal
     self.w16(out,max(-1024,min(1023,cx+x*f//max(1,z))));self.w16(out+2,max(-1024,min(1023,cy+y*f//max(1,z))))
    self.w32(outputs[4],0);self.w32(outputs[5],0);value=max(0,z)//4
  else:handled=False
  if handled:
   uc.reg_write(UC_MIPS_REG_V0,value);uc.reg_write(UC_MIPS_REG_PC,uc.reg_read(UC_MIPS_REG_RA));return
  if 0x800186AC<=pc<0x80019000 or 0x800190AC<=pc<0x80019400 or 0x80017CDC<=pc<0x80017D0C:return
  super().hook(uc,pc,n,data)
 def run(self,entry,entity):
  self.w32(0x8006C3B8,entity);self.uc.reg_write(UC_MIPS_REG_A0,entity)
  self.uc.reg_write(UC_MIPS_REG_SP,0x801FF000);self.uc.reg_write(UC_MIPS_REG_RA,0x801F0000)
  self.w32(0x8003C998,self.frame);
  try:self.uc.emu_start(entry,0x801F0000,count=200000)
  except Exception:
   print("Failed PC",hex(self.uc.reg_read(UC_MIPS_REG_PC)),"frame",self.frame,self.recent,flush=True);raise
def capture(slot,facing,variant=0,event_index=0,function=9,homing=False):
 data=json.loads((ROOT/f'modding/build/sotn_spell_traces/{slot:02}_{facing}.json').read_text())
 factories=[e for e in data['events'] if 'factory' in e and (e['factory']&0xfff)!=55]
 start=factories[event_index]['frame']+(variant*6 if slot==29 else 0);t=ChildTrace(slot);parent=t.entity;child=parent+0x1000
 if homing:t.trace_target=(240,128)
 t.w16(t.player+0x14,facing);t.put(parent,bytes.fromhex(data['frames'][start]['entity']));t.w16(parent+0x26,1)
 t.put(child,t.get(parent,8));t.w16(child+0x14,facing);t.w16(child+0x26,1)
 t.w16(child+0x30,variant<<8 if slot==10 else 0x100 if slot==25 else variant);t.rand=1+(event_index if slot==25 else variant)*977;t.w32(child+0x8c,parent)
 frames=[]
 for age in range(600):
  t.frame=start+age
  if t.frame<len(data['frames']):t.put(parent,bytes.fromhex(data['frames'][t.frame]['entity']));t.w16(parent+0x26,1)
  else:t.put(parent,bytes(0xbc))
  t.run(t.r32(source.V+function*4),child);t.animate(child);ent=t.get(child,0xbc)
  phase=struct.unpack_from('<H',ent,0x2c)[0]
  if age and not phase:break
  frames.append({'entity':ent.hex(),'prims':[t.get(0x80086FEC+j*52,52).hex() for j in range(t.prim_used)]})
 else:
  if not homing:raise RuntimeError(f'child {slot} did not terminate')
 return {'slot':slot,'facing':facing,'variant':variant,'function':function,'start':start,'code_sha256':data['code_sha256'],'frames':frames,'events':t.events,'homing_scene':homing,'primitive_init':'zero-v2'}
if __name__=='__main__':
 out=hodpaths.legacy('modding/build/sotn_child_traces');out.mkdir(exist_ok=True)
 if '--all' in sys.argv:
  # Include secondary routines such as Herald's 23 feather children, not
  # only each weapon's main child entry. Preserve the original factory event.
  paths=sorted(out.glob('*.json'))
  for p in paths:
   old=json.loads(p.read_text());slot=old['slot'];facing=old['facing'];variant=old['variant']
   parent=json.loads((ROOT/f'modding/build/sotn_spell_traces/{slot:02}_{facing}.json').read_text())
   factories=[e for e in parent['events'] if 'factory' in e and (e['factory']&0xfff)!=55]
   start=old['start']-(variant*6 if slot==29 else 0)
   event=next(i for i,e in enumerate(factories) if e['frame']==start)
   r=capture(slot,facing,variant,event_index=event,function=old.get('function',9),homing=slot==27 and ('--homing' in sys.argv or old.get('homing_scene',False)))
   p.write_text(json.dumps(r,separators=(',',':')))
   print(p.name,len(r['frames']),flush=True)
 else:
  slot=int(sys.argv[1]);variants=range(3) if slot==29 else range(2) if slot in (10,27) else range(8) if slot==26 else range(32) if slot==24 else range(1)
  for facing in (0,1):
   for variant in variants:
    p=out/f'{slot:02}_{facing}_{variant}.json'
    if p.exists() and '--refresh' not in sys.argv:continue
    r=capture(slot,facing,variant,event_index=1 if slot==23 else 0,homing=slot==27 and '--homing' in sys.argv);p.write_text(json.dumps(r,separators=(',',':')))
    print(slot,facing,variant,len(r['frames']),flush=True)
