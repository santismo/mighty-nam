"""Reusable bounded CPU harness; no USB, audio or physical device access.
Call configure once per process before constructing a Machine.
"""
import json, math, struct
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
from candidate_image import build_candidate, require

def configure(payload, use_reclaimed=False, candidate_bundle=None):
 global root,stock,candidate,sym,plan,state_start,state_end,code_start,code_end,code_regions
 global default_copy_end,model,w,h,bias,reclaimed,state_watch_end
 reclaimed=use_reclaimed;root=Path(__file__).resolve().parents[1];stock=Path(payload).read_bytes()
 candidate,sym,plan=candidate_bundle if candidate_bundle is not None else build_candidate(stock,root/('artifacts/reclaimed-v1-lab-only.elf' if reclaimed else 'artifacts/candidate-v1-lab-only.elf'),profile='reclaimed' if reclaimed else 'gap')
 state_region=next(x for x in plan['elf_regions'] if x['name']=='.bss')
 state_start=int(state_region['start'],16);state_end=int(state_region['end_exclusive'],16)
 state_watch_end=max(0x202e6000,(state_end+32+4095)&~4095)
 code_end=max(int(x['end_exclusive'],16) for x in plan['elf_regions'] if x['name']!='.bss')
 code_start=min(int(x['start'],16) for x in plan['elf_regions'] if x['name']!='.bss')
 code_regions=[(int(x['start'],16),int(x['end_exclusive'],16)) for x in plan['elf_regions'] if x['name']!='.bss']
 default_copy_end=0x2356c if reclaimed else 0x40000
 model=json.loads((root/'models/lstm.nam').read_text());w=model['weights'];h=model['config']['hidden_size'];bias=4*h*(h+1)

def in_code(pc):return pc is not None and any(a<=pc<b for a,b in code_regions)

class Reference:
 def __init__(self):self.h=w[bias+4*h:bias+5*h].copy();self.c=w[bias+5*h:bias+6*h].copy()
 def run(self,xs):
  ys=[];sig=lambda v:1/(1+math.exp(-v))
  for x in xs:
   g=[w[bias+r]+w[r*(h+1)]*x+sum(w[r*(h+1)+j+1]*self.h[j] for j in range(h)) for r in range(4*h)]
   self.c=[sig(g[h+j])*self.c[j]+sig(g[j])*math.tanh(g[2*h+j]) for j in range(h)]
   self.h=[sig(g[3*h+j])*math.tanh(self.c[j]) for j in range(h)]
   ys.append(w[bias+7*h]+sum(w[bias+6*h+j]*self.h[j] for j in range(h)))
  return ys

R=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
STOP=0x3fffc;SP=0x20035f00
class Collision(Exception):pass
class Machine:
 def __init__(self,fill,copy_end=None,missing_patch=None,omit_module=False,expected_ready=1):
  self.expected_ready=expected_ready
  if copy_end is None:copy_end=default_copy_end
  self.u=u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A15)
  u.mem_map(0,0x40000);u.mem_write(0,candidate[:copy_end])
  if omit_module:
   for a,b in code_regions:u.mem_write(a,b'\0'*(b-a))
  if missing_patch is not None:u.mem_write(missing_patch,stock[missing_patch:missing_patch+2])
  u.mem_protect(0,0x40000,UC_PROT_READ|UC_PROT_EXEC)
  if reclaimed:u.mem_protect(0x24000,0x1c000,UC_PROT_READ)
  for start,size in [(0x20000000,0x40000),(0x20200000,0x40000),(0x202c0000,0x80000)]:
   u.mem_map(start,size,UC_PROT_READ|UC_PROT_WRITE);u.mem_write(start,bytes([fill])*size)
  u.reg_write(UC_ARM_REG_C1_C0_2,0xf00000);u.reg_write(UC_ARM_REG_FPEXC,0x40000000)
  self.phase='runtime';self.boot_events=[];self.trace=[];self.violations=[];self.nam_writes=0;self.minimum_sp=SP
  self.fx={};self.real_effects=False;self.guard=False;self.count_stack=False;self.foreign_code_reads=[];self.extra_stubs=set()
  self.foreign_code_entries=[];self.last_pc=None
  self.stubs={0xe77c,0xeb34,0x10b68,0x10d68,0xe398,0x11620,0xbe8c,0xba70,
    0xdc24,0x116c0,0xca64,0xb296,0x115c2,0x1175c,0x11984,0xccc6,0x1151a,0xe5d0,0xb960,
    0x10b2c,0x10b08,0xe98c,0xb198,0xafb4,0xe002}
  self.code_hook=u.hook_add(UC_HOOK_CODE,self.code)
  # Unicorn 2.1.4 mishandles the stock IT/STM clear loop under a global write
  # hook. Restrict instrumentation to the arena being protected. See the
  # standalone test_unicorn_memclear_watch.py regression/negative control.
  u.hook_add(UC_HOOK_MEM_WRITE,self.write,begin=0x202e4000,end=state_watch_end-1)
  if reclaimed:
   for a,b in code_regions:u.hook_add(UC_HOOK_MEM_READ,self.code_read,begin=a,end=b-1)
 def put(self,addr,value):self.u.mem_write(addr,struct.pack('<I',value))
 def get(self,addr):return struct.unpack('<I',self.u.mem_read(addr,4))[0]
 def floats(self,addr,values):self.u.mem_write(addr,struct.pack('<'+'f'*len(values),*values))
 def read(self,addr):return list(struct.unpack('<8f',self.u.mem_read(addr,32)))
 def code(self,u,pc,size,user):
  if reclaimed and in_code(pc) and (self.last_pc is None or not in_code(self.last_pc)):
   if pc not in {sym['mpp_stock_amp_init']&~1,sym['mpp_stock_amp_process']&~1}:
    self.foreign_code_entries.append({'from':hex(self.last_pc) if self.last_pc is not None else None,'to':hex(pc)})
    raise Collision('Unexpected stock entry into reclaimed code')
  self.last_pc=pc
  if pc in self.extra_stubs:
   u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  if self.count_stack:self.minimum_sp=min(self.minimum_sp,u.reg_read(UC_ARM_REG_SP))
  if self.phase=='boot':
   if pc in [0x5778,sym['mpp_stock_amp_init']&~1,0x11984]:self.boot_events.append(hex(pc))
   if pc==0x11984:require(self.get(sym['mpp_hybrid_ready'])==self.expected_ready,'NAM not initialized before audio setup')
   if pc in self.stubs:
    u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  if self.phase=='audio':
   if pc==0x5578:self.trace.append(3)
   if pc in self.fx:
    self.trace.append(self.fx[pc])
    if self.real_effects:return
    x,y,ox,oy=[u.reg_read(r) for r in R]
    left=bytes(u.mem_read(x,32));right=bytes(u.mem_read(y,32));u.mem_write(ox,left);u.mem_write(oy,right)
    u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 def write(self,u,access,addr,size,value,user):
  if addr<state_watch_end and addr+size>0x202e4000 and self.phase!='runtime':
   pc=u.reg_read(UC_ARM_REG_PC)
   if not (in_code(pc) and state_start<=addr and addr+size<=state_end):
    self.violations.append({'pc':hex(pc),'address':hex(addr),'bytes':size})
    raise Collision('Non-NAM writer touched candidate state')
   self.nam_writes+=1
 def code_read(self,u,access,addr,size,value,user):
  pc=u.reg_read(UC_ARM_REG_PC)
  if not in_code(pc):
   self.foreign_code_reads.append({'pc':hex(pc),'address':hex(addr),'bytes':size})
   raise Collision('Stock path read reclaimed code as data')
 def run(self,pc,end=STOP,limit=2000000):
  self.last_pc=None
  self.u.reg_write(UC_ARM_REG_SP,SP);self.u.reg_write(UC_ARM_REG_LR,STOP|1)
  self.u.emu_start(pc|1,end,count=limit)
  require(self.u.reg_read(UC_ARM_REG_PC)==end,'Instruction budget exhausted')
 def boot(self,unity_fades=True):
  self.phase='runtime';self.run(0x2025c,limit=5000000)
  require(self.get(0x20000554)==0x5579,'Stock source descriptor was changed')
  self.fx={self.get(0x20000530+i*12)&~1:i for i in range(11) if i!=3}
  # In the reclaimed profile both guards lie inside the retired AMP arena.
  # The historical gap profile's lower guard precedes that arena and is only
  # used by its narrower startup test, which stubs other-effect initialization.
  self.u.mem_write(state_start-16,b'\xc3'*16);self.u.mem_write(state_end,b'\x3c'*32)
  self.phase='boot';self.boot_events=[];self.run(0xe5f8,end=0xe65a)
  require(self.boot_events==['0x5778',hex(sym['mpp_stock_amp_init']&~1),'0x11984'],'Wrong startup ordering')
  require(self.get(sym['mpp_hybrid_ready'])==self.expected_ready,'NAM init failed')
  require(self.get(0x20000554)==0x5579,'Unexpected RAM descriptor patch')
  self.preset=self.get(0x20005ad0);require(0x20000000<=self.preset<0x20040000,'Stock preset pointer missing')
  if unity_fades:self.floats(0x20005c50,[1.0]*0x40a)
  self.phase='audio'
 def guards(self):
  require(bytes(self.u.mem_read(state_start-16,16))==b'\xc3'*16,'State lower guard corrupted')
  require(bytes(self.u.mem_read(state_end,32))==b'\x3c'*32,'State upper guard corrupted')
 def dispatch(self,order,xs,control=1):
  self.u.mem_write(self.preset+3,bytes([control]));self.u.mem_write(self.preset+0x59,bytes(order))
  self.floats(0x2000d9c8,[1]*8);self.floats(0x2000d6c8,xs);self.floats(0x2000d6e8,[-x for x in xs])
  x=self.read(0x2000d6c8);self.trace=[];self.count_stack=True;self.run(0x122d0);self.count_stack=False
  require(self.trace==order,'Dispatcher order mismatch')
  require(self.get(0x200005c8+28*order.index(3))==0x5579,'Reorder changed original AMP entry')
  out=self.read(self.get(0x200005c8+28*10+16));self.guards()
  return x,out
 def background(self):
  before=bytes(self.u.mem_read(state_start,state_end-state_start));self.run(0x57c0)
  require(before==bytes(self.u.mem_read(state_start,state_end-state_start)),'Background changed NAM state')
