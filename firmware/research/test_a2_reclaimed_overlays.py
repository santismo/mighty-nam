#!/usr/bin/env python3
"""Expanded A2 RAM/model storage versus all 40 observed stock effect variants."""
import argparse,json,struct,time,math
from pathlib import Path
import candidate_vm as v
from a2_reclaimed_vm import configure,A2ReclaimedMachine
from a2_oracle import library
from a2_storage import SLOT_ADDRESS,SLOT_SIZE
from stock_chain_vm import GROUPS,NAMES
p=argparse.ArgumentParser();p.add_argument('payload',type=Path);p.add_argument('library');p.add_argument('model',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();lib=library(a.library);plan=configure(a.payload,a.model)
root=Path(__file__).resolve().parents[1];overlays=json.loads((root/'artifacts/reclaimed-overlay-audit.json').read_text())['overlays'];hits=[]
for o in overlays:
 offset=int(o['payload_offset'],16);data=v.stock[offset:offset+o['bytes']]
 for i in range(0,len(data)-3,4):
  word=struct.unpack_from('<I',data,i)[0]
  if 0x202e4000<=word<v.state_watch_end or SLOT_ADDRESS<=word<SLOT_ADDRESS+SLOT_SIZE:hits.append(dict(source=hex(offset+i),word=hex(word)))
assert not hits,hits
result=dict(status='RUNNING',silent=True,device_access=False,static_overlay_count=len(overlays),static_expanded_ram_or_model_slot_hits=hits,cases=[],groups={});start=time.perf_counter()
def save():a.output.write_text(json.dumps(result,indent=2)+'\n')
def run(m,n,offset=0):
 ys=[]
 for b in range(n):ys+=m.block([.16*math.sin(((b+offset)*8+i)*.071) for i in range(8)])
 return ys
save()
try:
 for stage,(base,count) in GROUPS.items():
  m=A2ReclaimedMachine(lib,a.model,observe_blocks=True);m.set_preset([stage]);run(m,136)
  for model in range(1,count+1):
   m.set_preset([stage],{stage:model});before=dict(m.overlay_blocks);ys=run(m,48,model*48)
   assert m.u.mem_read(base+1,1)[0]==model
   pointer=m.get(base+{1:0x1c,2:0x34,6:0x34,7:0x24,8:0x1c}[stage]);overlay=hex(pointer&~0xfff)
   delta=m.overlay_blocks[overlay]-before.get(overlay,0)
   assert delta>0 or (stage==1 and model==3)
   result['cases'].append(dict(stage=NAMES[stage],model=model,overlay=overlay,observed_overlay_blocks=delta,output_peak=max(map(abs,ys)),max_nam_error=m.max_nam_error))
  assert not m.violations and not m.model_access_violations and not m.foreign_code_entries and not m.foreign_code_reads
  result['groups'][NAMES[stage]]=dict(stats=m.stats(),model_access_violations=m.model_access_violations,model_reads=m.model_reads);save();print(NAMES[stage],count,'models PASS',flush=True)
 result['status']='PASS_A2_RECLAIMED_40_STOCK_OVERLAYS'
except Exception as e:result['status']='FAILED';result['error']=repr(e);raise
finally:result['wall_seconds']=time.perf_counter()-start;save()
print(result['status'],result['wall_seconds'])
