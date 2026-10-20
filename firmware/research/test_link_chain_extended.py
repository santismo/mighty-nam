#!/usr/bin/env python3
"""Concurrent ARM NAM/stock DSP then four-second delay/hall tail; never playback."""
import argparse,json,math,hashlib,time
from pathlib import Path
from link_image import elf_identity
from test_link_stock_chain import ChainMachine,Engine,library,build,v,preset_fixture,ORDER
from stock_chain_vm import GROUPS
p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','elf','library','model','output']:p.add_argument(name,type=Path)
a=p.parse_args();started=time.monotonic()
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,identity=elf_identity(a.elf)))
lib=library(str(a.library))
actual=ChainMachine(a.model,boundary_oracle=Engine(lib,a.model))
reference=ChainMachine(a.model,oracle=Engine(lib,a.model))
rows=[];offset=0
types={1:3,2:2,4:2,6:1,7:2,8:2,9:10}
def preset(enabled,order=ORDER,bypass=False):
 data=preset_fixture(enabled,types);data[89:100]=bytes(order);data[3]=65 if bypass else 1
 data[61:64]=bytes([70,55,40]);data[70:74]=bytes([65,10,50,60])
 for m in [actual,reference]:m.u.mem_write(m.preset,bytes(data))
def run_case(name,blocks,zero=False):
 global offset
 err=energy=ref_energy=peak=out_energy=0.;identical=True
 for i in range(blocks):
  n=offset+i
  inputs=[0.]*8 if zero else [.15*math.sin(2*math.pi*110*(n*8+j)/48000)+.03*math.sin(2*math.pi*333*(n*8+j)/48000) for j in range(8)]
  x=actual.process(n,inputs);y=reference.process(n,inputs)
  identical &= x==y
  err=max(err,max(abs(v-w) for v,w in zip(x,y)))
  energy+=sum((v-w)**2 for v,w in zip(x,y));ref_energy+=sum(w*w for w in y)
  out_energy+=sum(v*v for v in x);peak=max(peak,max(map(abs,x)))
 row={'case':name,'blocks':blocks,'seconds':blocks/6000,'peak':peak,
      'output_RMS':math.sqrt(out_energy/(blocks*8)),'peak_error':err,
      'relative_RMS_error':math.sqrt(energy/max(ref_energy,1e-30)),'bit_identical':identical}
 assert err<.001 and row['relative_RMS_error']<.001,row
 rows.append(row);offset+=blocks;print(json.dumps(row),flush=True)

preset([1,2,4,5,6,7,8,9])
run_case('Full stock chain with concurrent ARM NAM',4096)
for stage in GROUPS:
 assert actual.u.mem_read(GROUPS[stage][0]+1,1)[0]==types[stage],('Stock effect did not load',stage)
preset([1,2,4,5,6,7,8,9],[0,5,1,3,2,4,9,6,8,7,10])
run_case('NAM moved before drive, hall before delay',256)
preset([1,2,4,5,6,7,8,9],bypass=True);run_case('NAM bypass',128)
preset([1,2,4,5,6,7,8,9]);run_case('NAM resumed',256)
# NAM produces a DC response to zero input. Bypass it for a distinct wet-tail
# measurement after the live chain has excited the stock delay/hall buffers.
preset([7,8],bypass=True)
for i in range(8):run_case('Zero-input wet tail '+str(i+1),3000,zero=True)
tails=rows[-8:]
assert tails[2]['peak']>1e-6,'No wet tail after one second'
assert tails[-1]['output_RMS']<tails[1]['output_RMS'],'Wet tail did not decay'
result={'status':'PASS_EXTENDED_NAMLNK02_CHAIN_AND_TAIL','identity':elf_identity(a.elf),'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),
 'model':a.model.name,'cases':rows,'stock_types_verified':types,'total_samples':offset*8,
 'NAM_boundary_max_error':actual.max_boundary_error,'DMA_always_zero':True,
 'protected_state_writes':actual.violations,'stock_output_writers':[hex(x) for x in sorted(actual.output_writers)],
 'seconds_wall':time.monotonic()-started,'physical_device_access':False,
 'limits':['A15 instruction compatibility, not physical M7 timing or interrupt concurrency',
           'Four-second tail after NAM bypass; concurrent NAM tested separately above',
           'Representative effects/settings, not exhaustive effect combinations']}
result['status']=result['status'].replace('NAMLNK02',elf_identity(a.elf))
a.output.write_text(json.dumps(result,indent=2)+'\n')
