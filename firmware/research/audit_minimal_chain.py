"""Offline callback audit: fresh minimal chain versus used-then-bypassed tails.

Counts dispatch entries, not hardware cycles or end-to-end latency. Never
connects to USB/audio. Records whether any bypassed effects actually run.
"""
import argparse, json, hashlib, struct
from pathlib import Path
from collections import Counter
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R6
from elftools.elf.elffile import ELFFile
from test_preset_runtime import PresetMachine, build, preset_fixture, v
p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','elf','model','baseline16','report']:p.add_argument(name,type=Path)
a=p.parse_args();bundle=build(a.payload.read_bytes(),a.elf)
v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=a.elf
m=PresetMachine(path=a.model);m.arm()
data=preset_fixture([8],{8:4});data[70:74]=bytes([20,20,50,0]);m.u.mem_write(m.preset,bytes(data))
for i in range(1350):m.process(i,[0.]*8)
counts=Counter();fx=[0]
def dispatch(u,pc,size,_):
 remaining=u.reg_read(UC_ARM_REG_R6);stage=u.mem_read(m.preset+100-remaining,1)[0];counts[stage]+=1
h=m.u.hook_add(UC_HOOK_CODE,dispatch,begin=0x1230c,end=0x1230c)
f=m.u.hook_add(UC_HOOK_CODE,lambda *args:fx.__setitem__(0,fx[0]+1),begin=v.sym['mpp_fx_before']&~1,end=v.sym['mpp_fx_before']&~1)
for i in range(64):m.process(1350+i)
fresh=dict(counts);assert all(counts[x]==0 for x in [1,2,4,5,6,7,9]) and counts[3]==64 and counts[8]==64 and fx[0]==0
# Deliberately use gate/delay as well, then bypass all three tail-sensitive effects.
for stage in [5,7]:data[stage]&=63
m.u.mem_write(m.preset,bytes(data))
for i in range(64):m.process(1500+i)
for stage in [5,7,8]:data[stage]|=64
m.u.mem_write(m.preset,bytes(data))
for i in range(1300):m.process(1600+i)
counts.clear()
for i in range(64):m.process(3000+i)
used=dict(counts);assert all(counts[x]==64 for x in [3,5,7,8]);m.guards()
# Confirm the actual linked hot NAM code and constants, not just compiler flags.
def hot(path):
 with path.open('rb') as stream:
  e=ELFFile(stream);out={}
  for sym in e.get_section_by_name('.symtab').iter_symbols():
   if sym.name in ['_ZN3mpp6A2Lite7processEPKfPfj','_ZN3mpp6A2Lite7kernelsE','_ZN3mpp6A2Lite9dilationsE'] or sym.name.endswith('kernelsE') or sym.name.endswith('dilationsE'):
    sec=e.get_section(sym['st_shndx']);at=(sym['st_value']&~1)-sec['sh_addr'];blob=sec.data()[at:at+sym['st_size']]
    out[sym.name]={'address':hex(sym['st_value']),'bytes':sym['st_size'],'sha256':hashlib.sha256(blob).hexdigest()}
  return out
old,new=hot(a.baseline16),hot(a.elf);assert len(new)==3 and old==new,(old,new)
report=dict(status='PASS_NAMLNK18_MINIMAL_CHAIN_AUDIT',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),blocks_per_observation=64,fresh_NAM_spring_callback_counts=fresh,unused_bypassed_stock_callbacks=0,idle_custom_FX_calls=fx[0],used_then_bypassed_callback_counts=used,used_tail_policy_unchanged=True,NAMLNK16_hot_code_tables_restored_exactly=True,hot_symbols=new,hardware_cycles_measured=False,physical_latency_measured=False,device_access=False,host_audio_access=False,next_step='Per-type safe reset/drain for used stock gate/delay/reverb; do not freeze histories after an arbitrary timeout.')
a.report.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
