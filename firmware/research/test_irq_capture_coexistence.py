#!/usr/bin/env python3
"""Overlay placement, cold/warm zeroing and 40 stock effects; offline only."""
import argparse,json,struct,math,hashlib,time
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
import candidate_vm as v
from a2_reclaimed_vm import configure,A2ReclaimedMachine
from a2_oracle import library
from stock_chain_vm import GROUPS,NAMES
p=argparse.ArgumentParser();p.add_argument('payload');p.add_argument('library');p.add_argument('model');p.add_argument('capture_elf');p.add_argument('--output',required=True);a=p.parse_args()
configure(a.payload,a.model);lib=library(a.library);out=bytearray(v.candidate);code=[]
with Path(a.capture_elf).open('rb') as stream:
 e=ELFFile(stream);symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
 for s in e.iter_sections():
  if s['sh_flags']&2 and s['sh_type']!='SHT_NOBITS' and s['sh_size']:
   lo=s['sh_addr'];data=s.data();assert v.code_end<=lo<lo+len(data)<=0x1b488;out[lo:lo+len(data)]=data;code.append((lo,lo+len(data)))
assert struct.unpack_from('<I',out,0x205a8)[0]==0x11d95
struct.pack_into('<I',out,0x205a8,symbols['mpp_capture_irq']);v.candidate=bytes(out)
STATE=symbols['mpp_irq_capture'];assert STATE>=v.state_end+32 and STATE+52<=0x2031c000
r=Path(__file__).resolve().parents[1];overlays=json.loads((r/'artifacts/reclaimed-overlay-audit.json').read_text())['overlays'];refs=[]
for o in overlays:
 offset=int(o['payload_offset'],16);data=v.stock[offset:offset+o['bytes']]
 for j in range(0,len(data)-3):
  value=struct.unpack_from('<I',data,j)[0]
  if 0x400f0000<=value<0x400f0028 or STATE<=value<STATE+52:refs.append({'source':hex(offset+j),'value':hex(value)})
assert not refs
# Timing is dormant. Physical IRQs are not emulated in this effects-chain test.
rows=[];start=time.monotonic();maxerror=0
for stage,(base,count) in GROUPS.items():
 m=A2ReclaimedMachine(lib,a.model,fill=0xa5,observe_blocks=True)
 assert bytes(m.u.mem_read(STATE,52))==bytes(52)
 for lo,hi in code:assert bytes(m.u.mem_read(lo,hi-lo))==v.candidate[lo:hi]
 touches=[]
 def touch(u,access,addr,size,value,user):touches.append(hex(addr));raise AssertionError('Unexpected GPT2 access')
 def foreign_read(u,access,addr,size,value,user):raise AssertionError('Stock data read from capture code')
 m.u.mem_map(0x400f0000,0x1000)
 m.u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,touch,begin=0x400f0000,end=0x400f0027)
 for lo,hi in code:m.u.hook_add(UC_HOOK_MEM_READ,foreign_read,begin=lo,end=hi-1)
 canary=bytes([0x5b])*52;m.u.mem_write(STATE,canary)
 def blocks(n,seed):
  for b in range(n):m.block([.16*math.sin(((b+seed)*8+i)*.071) for i in range(8)])
 m.set_preset([stage]);blocks(136,0)
 for model in range(1,count+1):
  m.set_preset([stage],{stage:model});before=dict(m.overlay_blocks);blocks(48,model*48)
  assert m.u.mem_read(base+1,1)[0]==model
  ptr=m.get(base+{1:0x1c,2:0x34,6:0x34,7:0x24,8:0x1c}[stage]);overlay=hex(ptr&~0xfff);delta=m.overlay_blocks[overlay]-before.get(overlay,0)
  assert delta>0 or (stage==1 and model==3)
  assert bytes(m.u.mem_read(STATE,52))==canary
  rows.append({'stage':NAMES[stage],'model':model,'overlay_blocks':delta})
 maxerror=max(maxerror,m.max_nam_error)
 m.u.mem_write(STATE,b'\xff'*52);m.warm_restart();assert bytes(m.u.mem_read(STATE,52))==bytes(52)
 assert not touches and not m.violations and not m.model_access_violations
 print(NAMES[stage],count,'PASS',flush=True)
result={'status':'PASS_OFFLINE_CAPTURE_PLACEMENT_WITH_40_EFFECTS','device_access':False,'playback':False,'effect_variants':len(rows),'cases':rows,'cold_runtime_zero_tests':len(GROUPS),'warm_runtime_zero_tests':len(GROUPS),'known_overlay_scans':len(overlays),'unaligned_GPT2_or_capture_state_literal_hits':refs,'unexpected_GPT2_accesses_in_exercised_effects':0,'capture_state_preserved_during_stock_effects':True,'max_nam_reference_error':maxerror,'canonical_a2_elf_unchanged':True,'in_memory_overlay_sha256':hashlib.sha256(v.candidate).hexdigest(),'physical_interrupt_test':False,'wall_seconds':time.monotonic()-start,'limits':['Stock effects execute; timing wrapper is exercised separately with callback stubbed.','Runtime startup/peripheral initialization uses the existing bounded stubs.','No whole-program, other-core or bootloader ownership proof.','No physical timing or USB recovery proof.']}
Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','effect_variants','cold_runtime_zero_tests','warm_runtime_zero_tests','max_nam_reference_error','wall_seconds']}))
