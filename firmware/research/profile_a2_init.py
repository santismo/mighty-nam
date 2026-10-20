#!/usr/bin/env python3
"""Measure the load-time instruction tradeoff offline; not an MCU timing test."""
import argparse,collections,hashlib,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from elftools.elf.elffile import ELFFile
import candidate_vm as v
from a2_reclaimed_vm import configure,A2ReclaimedMachine
from a2_oracle import library
p=argparse.ArgumentParser();p.add_argument('payload',type=Path);p.add_argument('library');p.add_argument('model',type=Path);p.add_argument('elfs',type=Path,nargs=2);p.add_argument('--output',type=Path,required=True);a=p.parse_args();lib=library(a.library);rows=[]
for elf in a.elfs:
 configure(a.payload,a.model,elf);m=A2ReclaimedMachine(lib,a.model);m.phase='explicit-init-profile';counts=collections.Counter()
 def hook(u,pc,size,user):counts[pc]+=1
 h=m.u.hook_add(UC_HOOK_CODE,hook,begin=v.code_start,end=v.code_end-1);m.u.ctl_remove_cache(0,0x40000)
 m.u.mem_write(v.state_start,b'\xa5'*(v.state_end-v.state_start))
 try:m.run(0x5778)
 finally:m.u.hook_del(h);m.u.ctl_remove_cache(0,0x40000)
 assert m.get(v.sym['mpp_hybrid_ready'])==1 and m.get(v.sym['mpp_a2_load_status'])==0
 functions={}
 with elf.open('rb') as f:
  for s in ELFFile(f).get_section_by_name('.symtab').iter_symbols():
   if s['st_info']['type']=='STT_FUNC' and s['st_size']:
    start=s['st_value']&~1;functions[s.name]=sum(n for pc,n in counts.items() if start<=pc<start+s['st_size'])
 rows.append(dict(elf=elf.name,sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),nam_initialization_instruction_events=sum(counts.values()),functions=functions,ready=True,load_status=0))
 print(elf.name,sum(counts.values()),flush=True)
a.output.write_text(json.dumps(dict(status='PASS',device_access=False,audio_playback=False,metric='Unicorn instruction events during explicit AMP init, not clock cycles',runs=rows),indent=2)+'\n')
