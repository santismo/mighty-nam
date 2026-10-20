#!/usr/bin/env python3
"""Count Unicorn instruction callbacks in saved stock DSP. No wall-time/CPU claims.

Two identical machines verify that the extra code hook does not change output.
The hook counts Unicorn-executed instruction events, not Cortex-M7 cycles. Some
conditional instructions can be elided by Unicorn. No memory-write hook is added.
"""
import argparse,collections,hashlib,json,math,struct,time
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from unicorn import UC_HOOK_CODE
import candidate_vm as v
from stock_chain_vm import NAMES
from a2_reclaimed_vm import configure,A2ReclaimedMachine
from a2_oracle import library

p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','library','model','elf']:p.add_argument(name,type=Path)
p.add_argument('--output',required=True,type=Path)
p.add_argument('--warmup-blocks',type=int,default=256)
p.add_argument('--first-preset-only',action='store_true')
p.add_argument('--single-machine',action='store_true',help='Skip twin replay; use only after the default instrumentation-equivalence test passes')
a=p.parse_args();assert a.warmup_blocks>=256
lib=library(str(a.library));plan=configure(a.payload,a.model,a.elf)
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
result=dict(status='RUNNING',silent=True,device_access=False,elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),candidate_sha256=plan['candidate_sha256'],metric='Unicorn instruction-hook events, not hardware cycles or real-time throughput',block_frames=8,sample_rate=48000,block_deadline_us=8/48000*1e6,cases=[])
def save():a.output.write_text(json.dumps(result,indent=2)+'\n')
def signal(b):return [.15*math.sin(2*math.pi*110*(8*b+i)/48000)+.03*math.sin(2*math.pi*333*(8*b+i)/48000) for i in range(8)]
class Counter:
 def __init__(self,m):self.m=m;self.pc=collections.Counter();self.stage=collections.Counter();self.sizes={}
 def hook(self,u,pc,size,user):
  self.pc[pc]+=1;self.sizes[pc]=size
  stage='background' if self.m.phase=='background' else NAMES[self.m.pending['stage']] if self.m.pending else 'dispatcher_or_boundary'
  self.stage[stage]+=1
 def report(self):
  mn=collections.Counter();nam=collections.Counter();hot=[]
  for pc,n in self.pc.items():
   ins=next(md.disasm(bytes(self.m.u.mem_read(pc,self.sizes[pc])),pc),None)
   assert ins is not None,(hex(pc),self.sizes[pc])
   mn[ins.mnemonic]+=n
   if v.code_start<=pc<v.code_end:nam[ins.mnemonic]+=n
   hot.append(dict(pc=hex(pc),count=n,instruction=ins.mnemonic+' '+ins.op_str,in_nam=v.code_start<=pc<v.code_end))
  return dict(total=sum(self.pc.values()),nam_code=sum(nam.values()),stages=dict(self.stage),mnemonics=dict(mn),nam_mnemonics=dict(nam),hottest=sorted(hot,key=lambda x:x['count'],reverse=True)[:32])
def measured(m,plain,blocks,control,label,start):
 c=Counter(m);h=m.u.hook_add(UC_HOOK_CODE,c.hook);m.u.ctl_remove_cache(0,0x40000);ys=[]
 try:
  for b in range(start,start+blocks):
   x=signal(b);y=m.block(x,control=control)
   if plain is not None:assert y==plain.block(x,control=control),'Profiling changed output'
   ys+=y
 finally:m.u.hook_del(h);m.u.ctl_remove_cache(0,0x40000)
 row=c.report();row.update(label=label,blocks=blocks,control=control,output_bit_identical_to_uninstrumented=True if plain is not None else None,output_sha256=hashlib.sha256(struct.pack('<'+'f'*len(ys),*ys)).hexdigest(),max_nam_error=m.max_nam_error)
 print(label,row['total'],row['nam_code'],flush=True);return row
save();started=time.perf_counter()
try:
 for label,types in [('studio_drive_chorus_digital_hall',{1:3,2:2,4:2,6:1,7:2,8:2,9:10}),('comp_drive_mod_delay_reverb_last',{1:1,2:13,4:2,6:13,7:5,8:6,9:10})]:
  m=A2ReclaimedMachine(lib,a.model);plain=None if a.single_machine else A2ReclaimedMachine(lib,a.model)
  for machine in [m]+([plain] if plain is not None else []):machine.set_preset([1,2,4,5,6,7,8,9],types)
  warm_hash=hashlib.sha256()
  for b in range(a.warmup_blocks):
   x=signal(b);y=m.block(x);warm_hash.update(struct.pack('<'+'f'*len(y),*y))
   if plain is not None:assert y==plain.block(x)
   if (b+1)%3000==0:print('Warmup',label,(b+1)/6000,'simulated seconds',flush=True)
  n=a.warmup_blocks
  rows=[measured(m,plain,4,1,'steady',n),measured(m,plain,1,0x41,'first_bypass_with_reset',n+4),measured(m,plain,1,1,'first_reenable_with_reset',n+5),measured(m,plain,4,1,'steady_after_reenable',n+6)]
  assert not m.violations and not m.model_access_violations
  result['cases'].append(dict(preset=label,types=types,warmup_blocks=n,warmup_output_sha256=warm_hash.hexdigest(),measurements=rows,stock_stats=m.stats()));save()
  if a.first_preset_only:break
 result['status']='PASS_INSTRUCTION_PROFILE' if a.single_machine else 'PASS_INSTRUCTION_PROFILE_AND_INSTRUMENTATION_EQUIVALENCE'
except Exception as e:result['status']='FAILED';result['error']=repr(e);raise
finally:result['wall_seconds_not_target_timing']=time.perf_counter()-started;save()
