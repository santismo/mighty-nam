#!/usr/bin/env python3
"""Prove working-set preparation reads the intended model data without writes."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from test_link_stock_chain import ChainMachine,build,v
from link_image import elf_identity
from test_link_firmware import packet
p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','elf']:p.add_argument(name,type=Path)
p.add_argument('models',nargs='+',type=Path)
p.add_argument('--output',type=Path,required=True);a=p.parse_args()
identity=elf_identity(a.elf)
assert identity in ('NAMLNK05','NAMLNK06')
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,identity))
entry=v.sym['_ZNK3mpp6A2Lite17prime_working_setEv'];model=v.sym['_ZL5model']
kernels=[6]*14+[15,15]+[6]*7
dilations=[1,3,7,17,41,101,239,1,3,7,17,41,101,239,1,13,1,3,7,17,41,101,239]
rows=[]
for path in a.models:
 m=ChainMachine(path)
 for label,blocks in [('loaded',0),('history populated',61)]:
  for i in range(blocks):m.process(i)
  before=bytes(m.u.mem_read(v.state_start,v.state_end-v.state_start))
  positions=struct.unpack('<23I',m.u.mem_read(model+83924,92))
  expected=set(range(model,model+7484,4))
  head=model+83732;expected.update(range(head,head+192,4))
  hi=0
  for k,d,pos in zip(kernels,dilations,positions):
   length=(k-1)*d+1
   for frame in range(8):
    col=(pos+frame+1)%length
    for tap in range(k):
     for c in range(3):expected.add(model+7484+4*(hi+3*col+c))
     col=(col+d)%length
   hi+=3*length
  reads=set();writes=[]
  def read(u,access,addr,size,value,user):
   assert model<=addr and addr+size<=model+84024
   reads.update(range(addr,addr+size,4))
  def write(u,access,addr,size,value,user):writes.append((addr,size))
  r=m.u.hook_add(UC_HOOK_MEM_READ,read,begin=model,end=model+84023)
  w=m.u.hook_add(UC_HOOK_MEM_WRITE,write,begin=v.state_start,end=v.state_end-1)
  try:m.call(entry,[model])
  finally:m.u.hook_del(r);m.u.hook_del(w)
  assert not writes and before==bytes(m.u.mem_read(v.state_start,v.state_end-v.state_start))
  assert expected<=reads,('Missing working-set reads',len(expected-reads))
  # Extra reads are only positions and the ready flag.
  assert reads-expected<=set(range(model+83924,model+84024,4))
  # HELLO also computes the active slot's checksum. It must finish before
  # priming, and the engine must still be stopped when priming runs.
  active_seen=[False];primed=[False]
  def slot_read(u,access,addr,size,value,user):
   assert not primed[0],'Receiver scan after model preparation'
   active_seen[0]=True
  def prime_enter(u,pc,size,user):
   assert active_seen[0] and m.words()[9]==0
   primed[0]=True
  receiver=v.sym['_ZL8receiver']
  r=m.u.hook_add(UC_HOOK_MEM_READ,slot_read,begin=receiver,end=receiver+8191)
  h=m.u.hook_add(UC_HOOK_CODE,prime_enter,begin=entry&~1,end=entry&~1)
  engine_before=bytes(m.u.mem_read(model,84024))
  try:assert m.exchange(packet(1))[0]==0
  finally:m.u.hook_del(r);m.u.hook_del(h)
  assert primed[0] and m.words()[9]==1
  assert engine_before==bytes(m.u.mem_read(model,84024))
  rows.append({'model':path.name,'case':label,'distinct_float_words':len(expected),
               'entire_NAM_arena_unchanged':True,'writes_to_NAM_arena':0})
  print(json.dumps(rows[-1]),flush=True)
result={'status':'PASS_'+identity+'_READ_ONLY_WORKING_SET','identity':identity,
 'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),'cases':rows,
 'future_frames_covered':8,'model_state_unchanged':True,'physical_device_access':False,
 'preparation_after_receiver_scan_before_resume':True,
 'cache_behavior_proven':False,'limits':['Emulator validates addresses/state, not M7 cache timing',
 'Read work during bypass is included in the unchanged whole-chain timer guard']}
a.output.write_text(json.dumps(result,indent=2)+'\n')
