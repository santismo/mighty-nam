#!/usr/bin/env python3
import argparse,json,math,time
from pathlib import Path
import candidate_vm as v
from stock_chain_vm import ORDER
from a2_stock_vm import A2Machine
from a2_oracle import library
p=argparse.ArgumentParser();p.add_argument('payload');p.add_argument('library');p.add_argument('models',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v.configure(a.payload,use_reclaimed=True);lib=library(a.library);res=[]
for path in a.models:
 start=time.perf_counter();m=A2Machine(lib,path);m.set_preset([1,2,4,5,6,7,8,9],{1:3,2:2,4:2,6:1,7:2,8:2,9:10})
 for b in range(1088):
  xs=[.15*math.sin(2*math.pi*110*(b*8+i)/48000)+.03*math.sin(2*math.pi*333*(b*8+i)/48000) for i in range(8)]
  control=0x41 if 1024<=b<1056 else 1
  order=ORDER if b<1024 else [0,5,1,3,2,9,4,6,7,8,10]
  m.block(xs,order,control)
  if b%256==0:print(path.name,'blocks',b,flush=True)
 stats=m.stats();stats.update(model=path.name,blocks=1088,samples=8704,seconds=8704/48000,wall_seconds=time.perf_counter()-start,a2_state_writes=m.a2_writes,a2_violations=m.a2_violations,a2_canaries=True,instrumentation='Exact stage boundaries, scoped writes, stock memory-helper checks; no basic-block or full instruction coverage',cpu_timing_proven=False,persistent_startup_tested=False)
 assert stats['max_nam_error']<2e-5 and not m.a2_violations
 res.append(stats);print(path.name,'PASS',stats['max_nam_error'],stats['wall_seconds'],flush=True)
 del m
r=dict(status='PASS',silent=True,device_access=False,installation='Host injects model-agnostic ARM module at synthetic 0x08000000 after stock boot; no firmware produced',models=res)
a.output.write_text(json.dumps(r,indent=2)+'\n')
