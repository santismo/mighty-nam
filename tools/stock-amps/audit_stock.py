"""CPU-only stock-amp ownership audit. Never accesses devices/audio."""
from pathlib import Path
import struct, math, json
from unicorn import *
from unicorn.arm_const import *

from config import ROOT,HERE,PAYLOAD
STOCK=PAYLOAD.read_bytes()
SP=0x20035f00; STOP=0x3fffc
class Stock:
 def __init__(self):
  self.u=u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A15)
  for at,n in [(0,0x40000),(0x20000000,0x40000),(0x20200000,0x140000),(0x30040000,(len(STOCK)+4095)&~4095)]:u.mem_map(at,n)
  u.mem_write(0,STOCK[:0x40000]);u.mem_write(0x30040000,STOCK)
  u.reg_write(UC_ARM_REG_C1_C0_2,0xf00000);u.reg_write(UC_ARM_REG_FPEXC,0x40000000)
  self.call(0x22640);self.call(0x58b6)
 def call(self,at,args=(),stack=()):
  for r,x in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):self.u.reg_write(r,x)
  self.u.reg_write(UC_ARM_REG_SP,SP);self.u.reg_write(UC_ARM_REG_LR,STOP|1)
  if stack:self.u.mem_write(SP,struct.pack('<'+'I'*len(stack),*stack))
  self.u.emu_start(at|1,STOP,count=8000000)
  assert self.u.reg_read(UC_ARM_REG_PC)==STOP,hex(self.u.reg_read(UC_ARM_REG_PC))
 def init(self,i):
  self.u.mem_write(0x200039b0,bytes([i,50,50,50,50,50,50])+bytes(5)+bytes([i,i,0]))
  self.call(0x533c);self.call(0x5374)
  self.call(0x5148,[0x2000d44c,0x2000d4fc,0x20000374])
  self.call(0x5910,[i,0x202e4000,0x2031b000,0x2000d44c],[1])
 def block(self,i,index):
  x=[.016*math.sin((index*8+j)*.031) for j in range(8)]
  self.u.mem_write(0x20025000,struct.pack('<8f',*x))
  self.call(0x58f4,[i,0x20025000,0x20025100,0x202e4000],[0x2031b000,8])
  return struct.unpack('<8f',self.u.mem_read(0x20025100,32))

if __name__=='__main__':
 rows=[]
 for i in range(1,30):
  m=Stock();desc=struct.unpack_from('<8I',STOCK,0x1ab60+32*i)
  try:
   m.init(i);before=bytes(m.u.mem_read(0x202e4000,0x37000));peak=0
   for n in range(32):peak=max(peak,*map(abs,m.block(i,n)))
   after=bytes(m.u.mem_read(0x202e4000,0x37000));changed=[j for j,(a,b) in enumerate(zip(before,after)) if a!=b]
   row=dict(id=i,status='processed',resource_bytes=desc[1]+(desc[2]&255),arena_changed_bytes=len(changed),changed_range=[hex(0x202e4000+changed[0]),hex(0x202e4000+changed[-1]+1)] if changed else [],peak=peak)
   assert math.isfinite(peak) and peak>0
  except Exception as e:row=dict(id=i,status='blocked',reason=repr(e),pc=hex(m.u.reg_read(UC_ARM_REG_PC)))
  rows.append(row);print(row,flush=True)
 (HERE/'stock-audit.json').write_text(json.dumps(dict(rows=rows,scope='bounded 256 synthetic frames per original stock amp; no timing or hardware claim',device_access=False,host_audio_access=False),indent=2)+'\n')
