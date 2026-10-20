#!/usr/bin/env python3
"""NAMLNK07 CPU-only listening path: DMA, real stock chain, faults, restarts.
Writes only JSON. No audio device, playback, USB, flash container or updater.
"""
import argparse,hashlib,json,math,struct,time
from pathlib import Path
from unicorn import UC_HOOK_CODE
from link_irq_vm import IrqChainMachine
from test_link_stock_chain import v,build,preset_fixture,Engine,library
from test_link_firmware import packet
from a2_storage import model_slot
from link_image import elf_identity

class ListeningMachine(IrqChainMachine):
 def arm(self,on=True):
  self.ingress([bytes([0xf0,0x43,0x58,0x70,4,2,ord('N'),ord('A'),int(on),0xf7])])
  error,state=self.page(23);assert error==0 and (state&1)==int(on)
 def process(self,index,inputs=None,healthy=True):
  xs=inputs if inputs is not None else [.19*math.sin((index*8+i)*.063)+.07*math.sin((index*8+i)*.177) for i in range(8)]
  q=[int(x*2**31) for x in xs];half=index%2
  rx=0x20016800+128*half;tx=0x20016900+128*half
  other=0x20016900+128*(1-half);sentinel=bytes(self.u.mem_read(other,128))
  self.u.mem_write(rx,struct.pack('<32i',*[a for x in q for a in [0,0,0,x]]))
  self.u.mem_write(tx,b'\x7f'*128);self.call(0x14bfc,[rx,tx])
  assert bytes(self.u.mem_read(other,128))==sentinel,'Other DMA half changed'
  words=list(struct.unpack('<32i',self.u.mem_read(tx,128)))
  assert words[0::4]==words[2::4] and words[1::4]==words[3::4],'Not stock L/R/L/R'
  assert all(abs(x)<=234881024 for x in words),'Output exceeded padded ceiling'
  muted=not self.get(v.sym['mpp_listen_enabled']) or self.get(v.sym['mpp_listen_warm']) or not self.words()[9]
  if muted:assert words==[0]*32,'Muted/settling/fault leaked DMA output'
  before=bytes(self.u.mem_read(v.state_start,v.state_end-v.state_start))
  self.run(0xe9ae,limit=3000000)
  assert bytes(self.u.mem_read(v.state_start,v.state_end-v.state_start))==before
  self.guards()
  if healthy:assert self.words()[4]==0 and self.words()[9]==1,self.words()
  return [x*2**-31 for x in words[0::4]+words[1::4]]

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in ['payload','elf','library','model','second_model','output']:p.add_argument(key,type=Path)
 a=p.parse_args();start=time.monotonic();identity=elf_identity(a.elf);assert identity in ('NAMLNK07','NAMLNK08','NAMLNK09')
 v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,identity))
 lib=library(str(a.library));rows=[];counter=0
 for model in [a.model,a.second_model]:
  actual=ListeningMachine(model,boundary_oracle=Engine(lib,model))
  ref=ListeningMachine(model,oracle=Engine(lib,model))
  assert actual.page(23)==(0,2)
  for m in [actual,ref]:
   m.process(0);assert not m.get(v.sym['mpp_listen_enabled']);m.arm()
  cases=[
   ('all-stock-effects',[1,2,4,5,6,7,8,9],{},[5,1,2,3,9,4,6,7,8],False),
   ('heavy-settings',[1,2,4,5,6,7,8,9],{1:3,2:13,6:5,7:3,8:5,9:10},[5,1,2,3,9,4,6,7,8],True),
   ('dry-bypass',[5,7,8],{1:1,2:13,6:13,7:3,8:5,9:1},[5,1,2,3,9,4,6,7,8],True),
   ('change-asleep',[5,7,8],{1:3,2:2,6:5,7:5,8:5,9:10},[5,1,2,3,9,4,6,7,8],True),
   ('resume-all',[1,2,4,5,6,7,8,9],{1:3,2:2,6:5,7:5,8:5,9:10},[5,1,2,3,9,4,6,7,8],True),
   ('reordered',[1,2,4,5,6,7,8,9],{1:3,2:2,6:5,7:5,8:5,9:10},[5,3,1,2,4,9,8,6,7],False),
  ]
  for name,enabled,types,order,heavy in cases:
   data=preset_fixture(enabled,types);data[90:99]=bytes(order)
   if heavy:
    data[20:26]=bytes([95,85,100,90,85,100]);data[54:60]=bytes([95,100,90,85,100,90])
    data[61:69]=bytes([100,95,85,100,90,95,100,85]);data[70:74]=bytes([85,100,95,90])
   for m in [actual,ref]:m.u.mem_write(m.preset,bytes(data))
   error=peak=energy=refenergy=0.;silent=0
   for i in range(1500):
    y=actual.process(counter);z=ref.process(counter);counter+=1
    if not any(y):silent+=1
    error=max(error,max(abs(x-w) for x,w in zip(y,z)));peak=max(peak,max(map(abs,y)))
    energy+=sum((x-w)**2 for x,w in zip(y,z));refenergy+=sum(w*w for w in z)
   relative=math.sqrt(energy/max(refenergy,1e-30))
   assert peak>1e-9,(name,'No listening output after settling')
   assert silent>=1199 and actual.page(23)==(0,5),(silent,actual.page(23))
   assert error<.001 and relative<.001,(name,error,relative)
   rows.append(dict(model=model.name,case=name,blocks=1500,silent_blocks=silent,
    peak_Q31_normalized=peak,peak_reference_error=error,relative_RMS_error=relative,
    max_NAM_boundary_error=actual.max_boundary_error))
   print(json.dumps(rows[-1]),flush=True)
  # Transfer status itself must disarm, avoiding accidental playback through a
  # subsequent model replacement. Re-arm remains an explicit separate action.
  actual.exchange(packet(1));assert actual.page(23)==(0,2)
  actual.process(counter);actual.arm()
  # Warm restart really executes stock runtime and clears the model/arm.
  actual.restart();assert actual.words()[5:7]==[0,0] and actual.page(23)==(0,2)
  actual.process(counter,healthy=False)
  # Failed arming without a model cannot start output.
  actual.ingress([bytes.fromhex('f043587004024e4101f7')]);assert actual.page(23)==(0,2)
  actual.upload(model_slot(model),202);actual.arm()
  # Artificial timing fault is a functional guard test, not measured timing.
  actual.timer_ticks=150;actual.process(counter,healthy=False)
  assert actual.words()[4]>0 and actual.words()[9]==0 and actual.page(23)==(0,2)
  actual.process(counter+1,healthy=False)
 # Fault injection after the stock global-volume wrapper, on the right side.
 m=ListeningMachine(a.model);m.arm();m.put(v.sym['mpp_listen_warm'],0)
 entry=v.sym['mpp_output_protect']&~1
 h=m.u.hook_add(UC_HOOK_CODE,lambda u,p,s,x:m.floats(v.sym['_ZL11chain_right'],[float('nan')]*8),begin=entry,end=entry)
 try:m.process(0,healthy=False)
 finally:m.u.hook_del(h)
 assert m.words()[4]>0 and m.words()[9]==0 and m.page(23)==(0,2)
 report=dict(status='PASS_'+identity+'_BOUNDED_LISTENING_CPU_TESTS',identity=identity,
  elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),cases=rows,seconds=time.monotonic()-start,
  checks=['Default mute','Explicit arm','Both DMA halves; stock stereo lane mapping','200 ms muted effect settling',
   '21.3 ms fade to -18.06 dB pad','Stock global volume path','Same-input NAM reference',
   'Heavy dry resume and reordering','Model transfer disarms','Warm restart disarms and clears model',
   'Timing and right-channel nonfinite faults clear DMA before release'],
  physical_device_access=False,host_audio_access=False,
  limits=['Synthetic timer: no performance proof','No physical output/volume or listening validation',
   'Bounded combinations; not all models/effect settings','No flash container created'])
 a.output.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
