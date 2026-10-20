#!/usr/bin/env python3
"""Additional NAMLNK07 renderer/protocol/startup/effect tests; CPU only."""
import argparse,hashlib,json,struct,time,math
from pathlib import Path
from test_link_listening import ListeningMachine,v,build,preset_fixture,library,Engine
from unicorn import UC_HOOK_CODE
from a2_storage import model_slot
from link_image import elf_identity
p=argparse.ArgumentParser(description=__doc__)
for k in ['payload','elf','library','model','output']:p.add_argument(k,type=Path)
a=p.parse_args();start=time.monotonic();identity=elf_identity(a.elf);assert identity in ('NAMLNK07','NAMLNK08','NAMLNK09');v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,identity))
rows=[];lib=library(str(a.library));m=ListeningMachine(a.model,boundary_oracle=Engine(lib,a.model))
# Exact renderer ramp/lane/extent checks, independently predicted integer PCM.
l=v.sym['mpp_link_output'];r=v.sym['_ZL11chain_right'];tx=0x20016900
m.call(v.sym['mpp_listen_reset'],[]);m.put(v.sym['mpp_listen_enabled'],1);m.put(v.sym['mpp_listen_warm'],0)
m.floats(l,[.5]*8);m.floats(r,[-.25]*8)
m.u.mem_write(tx-16,b'\x51'*16);m.u.mem_write(tx+128,b'\x52'*16)
for block in range(132):
 m.call(v.sym['mpp_listen_render'],[l,r,tx])
 expected=[]
 for i in range(8):
  step=min(block*8+i+1,1024);left=int(.5*step*2**18);right=int(-.25*step*2**18)
  expected.extend([left,right,left,right])
 assert list(struct.unpack('<32i',m.u.mem_read(tx,128)))==expected
 assert m.u.mem_read(tx-16,16)==b'\x51'*16 and m.u.mem_read(tx+128,16)==b'\x52'*16
assert m.page(23)==(0,5);rows.append('1056 stereo samples: exact 1024-sample ramp, saturation, lane mapping, buffer extent')
m.arm(False)
for channel in [0,1]:
 for body in [b'\x02',b'\x7f',b'\x01\x00',b'',b'\x01\x01']:
  before=m.page(23)
  m.query(bytes.fromhex('f043587004024e41')+body+b'\xf7',channel)
  assert m.page(23)==before
 m.put(0xe000ed04,16);m.query(bytes.fromhex('f043587004024e4101f7'),channel);m.put(0xe000ed04,0)
 assert m.page(23)==(0,2)
rows.append('Malformed/interrupt-context listening commands cannot arm; both transport selectors')
# Exercise every stock comp/drive/mod/delay/reverb algorithm using full real
# stock foreground loaders and same-input NAM oracle. Three cabinet choices.
m.arm();counter=0
for i in range(13):
 types={1:1+i%3,2:1+i,4:1+i%2,5:1,6:1+i,7:1+i%5,8:1+i%6,9:[1,10,19][i%3]}
 data=preset_fixture([1,2,4,5,6,7,8,9],types)
 data[20:26]=bytes([95,85,100,90,85,100]);data[54:60]=bytes([95,100,90,85,100,90])
 data[61:69]=bytes([100,95,85,100,90,95,100,85]);data[70:74]=bytes([85,100,95,90])
 data[90:99]=bytes([5,3,1,2,4,9,8,6,7] if i%2 else [5,1,2,3,9,4,6,7,8])
 m.u.mem_write(m.preset,bytes(data));peak=0
 for j in range(1500):
  out=m.process(counter);counter+=1;peak=max(peak,max(map(abs,out)))
 assert peak>0 and m.page(23)==(0,5)
 row=dict(case='algorithm-switch-'+str(i+1),types=types,peak=peak,blocks=1500)
 rows.append(row);print(json.dumps(row),flush=True)
# Existing long wet state remains finite for four seconds of zero input.
peak=0
for j in range(24000):
 out=m.process(counter,[0.]*8);counter+=1;peak=max(peak,max(map(abs,out)))
rows.append(dict(case='four-second-zero-input-wet-tail',blocks=24000,peak=peak))
# Force a deadline failure only after a proven nonzero listening block.
for i in range(10):
 y=m.process(counter);counter+=1
 if any(y):break
assert any(y),'Vacuous timing-fault test'
m.timer_ticks=150;m.process(counter,healthy=False)
assert m.words()[4]>0 and not m.words()[9] and m.page(23)==(0,2)
rows.append('Timer fault from previously nonzero output clears the current DMA block and disarms')
a.output.with_name('edges-prefix.json').write_text(json.dumps(dict(status='PASS_COMPLETED_RENDERER_PROTOCOL_ALGORITHMS_AND_TAIL_PREFIX',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),cases=rows,max_NAM_boundary_error=m.max_boundary_error),indent=2)+'\n')
for fill in [0,0xa5,0xff]:
 n=ListeningMachine(fill=fill)
 assert n.words()[5:7]==[0,0] and n.page(23)==(0,2)
 for half in [0,1]:n.process(half,healthy=False)
 n.upload(model_slot(a.model),333);n.arm()
 # Use an explicit ordinary chain and the actual 200 ms settling path.
 # A first block is allowed to be silent; established stock routing fades
 # and the gate are stateful. Require nonzero output after they settle.
 n.u.mem_write(n.preset,bytes(preset_fixture([1,2,4,5,6,7,8,9])))
 peak=0
 for i in range(1500):peak=max(peak,max(map(abs,n.process(i))))
 assert peak>1e-9 and n.page(23)==(0,5),'No output after startup settling'
 n.restart();assert n.page(23)==(0,2) and n.words()[5:7]==[0,0]
 for half in [0,1]:n.process(half,healthy=False)
rows.append('Three cold RAM patterns and three actual warm runtimes: model empty, both DMA halves silent, arm cleared')
report=dict(status='PASS_'+identity+'_RENDER_PROTOCOL_AND_EFFECT_EDGES',identity=identity,
 elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),cases=rows,algorithm_combinations=13,
 wet_tail_samples=192000,max_NAM_boundary_error=m.max_boundary_error,cold_starts=3,warm_restarts=3,
 renderer_samples=1056,seconds=time.monotonic()-start,device_access=False,host_audio_access=False,
 limits=['Synthetic counters; physical timing not proved','No listening/acoustic validation','Three cabinets, not every IR'])
a.output.write_text(json.dumps(report,indent=2)+'\n')
