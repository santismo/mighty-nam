#!/usr/bin/env python3
"""Exact chain ELF startup, RAM swaps, rejection and warm restart tests."""
import argparse,json,hashlib,zlib,struct
from pathlib import Path
from link_image import elf_identity
from test_link_stock_chain import ChainMachine,build,v,preset_fixture,model_slot
from test_link_firmware import packet
p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','elf']:p.add_argument(name,type=Path)
p.add_argument('models',type=Path,nargs='+');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,identity=elf_identity(a.elf)))
rows=[];expected=None
for fill in [0,0xa5,0xff]:
 m=ChainMachine(fill=fill)
 assert m.words()==[0x4e4c4b31,1,1,0,0,0,0,0,0,0,0,0]
 m.audio();assert m.words()[7:10]==[0,0,0]
 for ch in [0,1]:
  assert m.ingress([bytes.fromhex('f0435800f7')],ch)[0][0][4:12]==elf_identity(a.elf).encode()
  assert m.exchange(packet(1),ch)[2]==0
 m.u.mem_write(m.preset,bytes(preset_fixture([1,2,4,6,7,8,9])))
 for idx,path in enumerate(a.models):
  slot=model_slot(path);m.upload(slot,100+idx,idx%2)
  assert m.words()[5:7]==[zlib.crc32(slot),idx+1]
  values=[]
  for i in range(320):values+=m.process(i)
  assert max(map(abs,values))>1e-6,'Vacuous chain output'
  assert m.exchange(packet(4,100+idx))[0]==0 and m.words()[6]==idx+1
  if idx==0:
   if expected is None:expected=values
   else:assert values==expected,'Cold RAM pattern changed output'
  rows.append({'fill':fill,'model':path.name,'generation':idx+1,'output_peak':max(map(abs,values))})
 before=m.words()[5:7]
 assert m.exchange(packet(2,777,data=struct.pack('<II',8192,zlib.crc32(slot))))[0]==0
 assert m.exchange(packet(3,777,0,slot[:256]))[0]==0
 assert m.exchange(packet(4,777))[0]==6 and m.words()[5:7]==before
 assert m.exchange(packet(5,777))[0]==0
 # Warm restart runs real C runtime and stock DSP init again with boot stubs.
 m.restart();assert m.words()==[0x4e4c4b31,1,1,0,0,0,0,0,0,0,0,0]
 assert m.exchange(packet(1))[2]==0
 m.audio();assert m.words()[9]==0
 m.u.mem_write(m.preset,bytes(preset_fixture([1,2,4,6,7,8,9])))
 m.upload(model_slot(a.models[0]),901);values=[]
 for i in range(320):values+=m.process(i)
 assert values==expected,'Warm restart changed output';m.guards()
 for ticks in [0,150,100000]:
  m.put(v.sym['mpp_link']+16,0);m.put(v.sym['mpp_link']+36,1)
  m.timer_ticks=ticks;m.audio()
  assert m.words()[4]==1 and m.words()[9]==0
  assert m.exchange(packet(1))[0]==0 and m.words()[9]==0
 print('PASS cold/warm/swap/timer',fill,flush=True)
report={'status':'PASS_NAMLNK02_LIFECYCLE','identity':elf_identity(a.elf),'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),
 'model_runs':rows,'cold_starts':3,'warm_restarts':3,'warm_cold_output_bit_identical':True,
 'incomplete_commit_preserves_active':True,'duplicate_commit_idempotent':True,'timer_fault_latches':True,
 'output_always_zero':True,'physical_device_access':False,
 'limits':['Virtual timer fixtures and intercepted peripheral setup; no actual clock/cache/deadline proof']}
report['status']=report['status'].replace('NAMLNK02',elf_identity(a.elf))
a.output.write_text(json.dumps(report,indent=2)+'\n')
