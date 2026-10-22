"""V3 compiled full-chain, protocol, buffer and malformed-input regression.
All samples, flash and USB completion live in emulator memory. No device I/O.
"""
import argparse,sys,json,hashlib,struct,math
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('generated',type=Path);p.add_argument('payload',type=Path);p.add_argument('elf',type=Path);p.add_argument('model',type=Path);p.add_argument('library',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
sys.path.insert(0,str(a.generated/'research'))
from test_usb_nam import UsbMachine,v,preset_fixture,input_block,Engine,library,model_slot
from test_link_firmware import packet,sysex
from preset_image import build
from unicorn import UC_HOOK_CODE
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf));v.elf_path=a.elf
m=UsbMachine(boundary_oracle=Engine(library(str(a.library)),a.model));m.service();m.upload(model_slot(a.model),140,channel=1);m.initialize_usb()
# Real V3 receive-ring assembler: F7-inclusive lengths, fragments, ring wrap.
requests=[bytes.fromhex('f0435800f7'),bytes.fromhex('f043587004024e5000f7')]
for ch in [0,1]:
 for q in requests:
  for split in range(len(q)+1):
   rows=m.ingress([q[:split],q[split:]],ch,start=2045);assert len(rows)==1 and rows[0][1]==ch
  assert m.ingress([q[:-1]],ch)==[]
  assert len(m.ingress([q+q],ch))==2
 for q in [bytes.fromhex('f043587004024e50f7'),bytes.fromhex('f043587004024e50')+bytes(340)+b'\xf7']:
  assert m.ingress([q],ch)==[]
rows=[];counter=0
for label,enabled,types,order in [
 ('NAM only',[],{},[5,1,2,3,9,4,6,7,8]),
 ('NAM and Spring',[8],{8:4},[5,1,2,3,9,4,6,7,8]),
 ('full stock and cut EQ',[1,2,4,5,6,7,8,9],{4:4,8:4},[5,1,2,3,9,4,6,7,8]),
 ('reordered heavy chain',[1,2,4,5,6,7,8,9],{1:3,2:13,4:3,6:5,7:3,8:5,9:10},[5,3,1,2,4,9,8,6,7]),
 ('V3 Phi Delay',[7],{7:6},[5,1,2,3,9,4,6,7,8]),
 ('all bypassed',[],{},[5,1,2,3,9,4,6,7,8]),
]:
 settings=preset_fixture(enabled,types);settings[84]=37;settings[70:74]=bytes([20,20,50,0]);settings[90:99]=bytes(order)
 if label=='all bypassed':settings[3]=65
 m.u.mem_write(m.preset,bytes(settings));m.arm();peak=0
 for i in range(1320):
  y=m.process(counter,input_block(counter));counter+=1;peak=max(peak,max(map(abs,y)))
 expected=[id for id in order if not settings[id]&64]
 calls=[];known={m.get(0x20000530+id*12)&~1:id for id in range(11)};known.pop(0x55b4,None);known[v.sym['mpp_stock_amp_process']&~1]=3
 known[v.sym['mpp_cut_eq_process']&~1]=4;known.pop(0xc03a,None)
 hooks=[m.u.hook_add(UC_HOOK_CODE,lambda u,pc,n,id:calls.append(id),id,begin=addr,end=addr) for addr,id in known.items()]
 m.process(counter,input_block(counter));counter+=1
 for h in hooks:m.u.hook_del(h)
 assert calls==expected,(label,calls,expected)
 assert m.stats()[0]==len(expected) and m.words()[4]==0 and peak>1e-7
 rows.append(dict(case=label,executed_nodes=calls,peak=peak,NAM_max_error=m.max_boundary_error));print(label,'PASS',flush=True)
# Independent per-type background-loader sweep: actual V3 stock DSP, guards.
for stage,count in [(1,3),(2,13),(4,3),(6,13),(7,6),(8,6),(9,20)]:
 for typ in range(1,count+1):
  settings=preset_fixture([stage],{stage:typ});settings[84]=37;m.u.mem_write(m.preset,bytes(settings))
  for i in range(4):m.process(counter,input_block(counter));counter+=1
  m.guards();assert m.words()[4]==0
 print('stock type/load sweep',stage,count,'PASS',flush=True)
# Buffer writes execute through the firmware protocol and persist globally.
for n in [32,16,8]:
 q=bytes([240,67,88,112,4,2,78,66,n,247]);m.ingress([q],1)
 assert m.page(24)[1]&255==n
 m.restart();m.service();assert m.page(24)[1]&255==n
print('global buffer restart PASS',flush=True)
a.output.write_text(json.dumps(dict(status='PASS_OFFLINE_NAMLNK23_RUNTIME',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),stock_sha256=hashlib.sha256(a.payload.read_bytes()).hexdigest(),cases=rows,callbacks=counter,V3_SysEx_F7_inclusive_and_fragmentation=True,global_buffers_restarted=[32,16,8],stock_type_loader_cases=64,guard_failures=0,device_access=False,host_audio_access=False,limitations=['Timing counters, hardware peripherals, USB completion and flash are modeled','Stock effect loader sweep checks guarded switching; representative chains also settle and render','Not a physical latency or recovery proof']),indent=2)+'\n')
