#!/usr/bin/env python3
"""Bounded whole-IRQ instruction/stack observations, never a CPU timing claim."""
import argparse,collections,hashlib,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP
from link_irq_vm import IrqChainMachine,v
from link_image import build
from stock_chain_vm import preset_fixture
p=argparse.ArgumentParser(description=__doc__)
for k in ['payload','elf','model','output']:p.add_argument(k,type=Path)
a=p.parse_args()
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,'NAMLNK06'))
class Machine(IrqChainMachine):
 entry=0
 def run(self,pc,*args,**kwargs):
  previous=self.entry;self.entry=pc
  try:return super().run(pc,*args,**kwargs)
  finally:self.entry=previous
m=Machine(a.model);rows=[]
for label,enabled,types,bypass in [
 ('NAM only',[],{},False),
 ('All stock blocks, ordinary settings',[1,2,4,5,6,7,8,9],{},False),
 ('High drive, detune, modulation delay and shimmer',[1,2,4,5,6,7,8,9],{1:3,2:13,4:2,6:5,7:3,8:5,9:10},False),
 ('NAM bypass, same heavy effects',[1,2,4,5,6,7,8,9],{1:3,2:13,4:2,6:5,7:3,8:5,9:10},True)]:
 data=preset_fixture(enabled,types);data[3]=65 if bypass else 1
 if types:
  data[20:26]=bytes([95,85,100,90,85,100])
  data[54:60]=bytes([95,100,90,85,100,90])
  data[61:69]=bytes([100,95,85,100,90,95,100,85])
  data[70:74]=bytes([85,100,95,90])
 m.u.mem_write(m.preset,bytes(data))
 for i in range(128):m.process(i)
 counts=collections.Counter();low=[v.SP];per_irq=[]
 def count(u,pc,size,user):
  scope='audio_IRQ' if m.entry==0x205a4 else 'foreground'
  counts[scope]+=1
  if scope=='audio_IRQ':low[0]=min(low[0],u.reg_read(UC_ARM_REG_SP))
 h=m.u.hook_add(UC_HOOK_CODE,count)
 try:
  for i in range(8):
   before=counts['audio_IRQ'];m.process(128+i);per_irq.append(counts['audio_IRQ']-before)
 finally:m.u.hook_del(h)
 row={'case':label,'blocks':8,'instruction_events':dict(counts),
      'per_IRQ_instruction_events':per_irq,'observed_IRQ_stack_bytes':v.SP-low[0]}
 rows.append(row);print(json.dumps(row),flush=True)
report={'status':'PASS_BOUNDED_NAMLNK06_IRQ_PROFILE','identity':'NAMLNK06',
 'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),'cases':rows,
 'metric':'Emulator instruction events, not M7 cycles or microseconds',
 'maximum_observed_IRQ_stack_bytes':max(x['observed_IRQ_stack_bytes'] for x in rows),
 'physical_device_access':False,'audio_playback':False,'deadline_proven':False,
 'limits':['Short sampled windows do not establish worst-case cost for time-varying effects.',
 'No exception stack, real interrupt preemption, cache/bus behavior or physical DMA is included.']}
a.output.write_text(json.dumps(report,indent=2)+'\n')
