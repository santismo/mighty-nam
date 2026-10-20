#!/usr/bin/env python3
"""Bounded instruction count and stack observation, never a hardware clock."""
import argparse,json,hashlib,collections
from pathlib import Path
from link_image import elf_identity
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP
from test_link_stock_chain import ChainMachine,build,v,preset_fixture
p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','elf','model','output']:p.add_argument(name,type=Path)
a=p.parse_args();v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,identity=elf_identity(a.elf)))
class ProfileMachine(ChainMachine):
 entry=0
 def run(self,pc,*args,**kwargs):
  previous=self.entry;self.entry=pc
  try:return super().run(pc,*args,**kwargs)
  finally:self.entry=previous
m=ProfileMachine(a.model);rows=[]
for name,enabled,bypass in [('NAM only',[],False),('full stock chain',[1,2,4,5,6,7,8,9],False),('NAM bypass with full stock chain',[1,2,4,5,6,7,8,9],True)]:
 preset=preset_fixture(enabled);preset[3]=65 if bypass else 1
 m.u.mem_write(m.preset,bytes(preset))
 for i in range(256):m.process(i)
 counts=collections.Counter();lowest=[v.SP]
 def count(u,pc,size,user):
  phase='audio' if m.entry==0x14bfc else 'foreground'
  counts[phase+('/NAM' if v.code_start<=pc<v.code_end else '/stock')]+=1
  lowest[0]=min(lowest[0],u.reg_read(UC_ARM_REG_SP))
 h=m.u.hook_add(UC_HOOK_CODE,count)
 try:
  for i in range(4):m.process(256+i)
 finally:m.u.hook_del(h)
 rows.append({'case':name,'blocks':4,'instruction_events':dict(counts),
              'observed_stack_bytes':v.SP-lowest[0]})
 print(json.dumps(rows[-1]),flush=True)
a.output.write_text(json.dumps({'status':'PASS_BOUNDED_INSTRUCTION_PROFILE',
 'identity':elf_identity(a.elf),'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),'cases':rows,
 'metric':'Unicorn instruction events, not Cortex-M7 clock cycles',
 'physical_device_access':False,'deadline_proven':False},indent=2)+'\n')
