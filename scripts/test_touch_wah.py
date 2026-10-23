"""Retained NUX V3 Touch Wah + NAM, eight-frame emulator tests. No device I/O."""
import argparse,sys,json,hashlib,math,struct,zlib
from pathlib import Path
p=argparse.ArgumentParser()
for name in ['work','payload','model','library','output']:p.add_argument(name,type=Path)
a=p.parse_args();sys.path[:0]=[str(a.work/'generated/research'),str(a.work/'generated/tools')]
from test_usb_nam import UsbMachine,v,preset_fixture,input_block,Engine,library,model_slot
from preset_image import build
from unicorn import UC_HOOK_MEM_WRITE,UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR
elf=a.work/'build/nam-link-offline.elf';bundle=build(a.payload.read_bytes(),elf)
v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=elf
m=UsbMachine();m.service();slot=model_slot(a.model);m.upload(slot,920)
m.boundary_oracle=Engine(library(str(a.library)),a.model);m.arm();m.initialize_usb()
# Unassigned tail of the retired AMP arena, beyond copied code. A sentinel
# here is a bounded conflict probe, not a production allocation or ownership proof.
lo,hi=0x20314000,0x2031b000
m.u.mem_write(lo,b'\xa7'*(hi-lo));writes={};reads={};phase='initialized'
def track(collection):
 def hook(u,kind,addr,n,value,user):
  key=(phase,u.reg_read(UC_ARM_REG_PC),u.reg_read(UC_ARM_REG_LR))
  row=collection.setdefault(key,dict(count=0,first=addr,last=addr+n-1))
  row['count']+=1;row['first']=min(row['first'],addr);row['last']=max(row['last'],addr+n-1)
 return hook
m.u.hook_add(UC_HOOK_MEM_WRITE,track(writes),begin=lo,end=hi-1)
m.u.hook_add(UC_HOOK_MEM_READ,track(reads),begin=lo,end=hi-1)
rows=[];counter=0;waveforms=[]
for mode,direction in [(0,0),(1,0),(2,0),(3,0),(1,1)]:
 phase=f'touch {mode} direction {direction}'
 data=bytearray(preset_fixture([2,8],{2:14,8:4}));data[84]=37
 data[20:25]=bytes([mode,35,90,direction,60]);data[70:74]=bytes([20,20,50,0])
 m.u.mem_write(m.preset,bytes(data));m.arm();samples=[]
 for i in range(1400):
  x=[.12*math.exp(-6*((i*8+j)%6000)/6000)*math.sin((i*8+j)*.041) for j in range(8)]
  y=m.process(counter,x);counter+=1
  assert all(math.isfinite(q) and abs(q)<=.8751 for q in y)
  if i>=1300:samples+=y
 assert m.words()[4]==0 and m.stats()[2]==3 and max(map(abs,samples))>1e-8
 rows.append(dict(type=mode,direction=direction,peak=max(map(abs,samples)),callbacks=1400,NAM_error=m.max_boundary_error))
 waveforms.append(samples);print('Touch Wah',mode,direction,'PASS',flush=True)
assert all(waveforms[i]!=waveforms[0] for i in range(1,len(waveforms)))
# Save the live Touch Wah chain, replace it in RAM, recall, then cold-restart.
settings=bytes(m.u.mem_read(m.preset,128));body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(settings),1,8)+hashlib.sha256(slot).digest()+b'Touch Wah test'.ljust(64,b'\0')
phase='save';assert m.bank_request(2,0,body,nonce=211)[7]==0
phase='recall';m.u.mem_write(m.preset+2,b'\x41');assert m.bank_request(3,0,nonce=212)[7]==0;m.service()
assert m.u.mem_read(m.preset+2,1)[0]==14
phase='restart';m.restart();m.service();assert m.u.mem_read(m.preset+2,1)[0]==14
# Bypassed Touch Wah must equal the previous drive with that block bypassed.
m.boundary_oracle=None
outputs=[]
for typ in [1,14]:
 phase=f'bypass restart {typ}'
 m.restart();m.service();phase=f'bypass run {typ}';data=bytearray(preset_fixture([]));data[2]=64|typ;data[84]=37
 m.u.mem_write(m.preset,bytes(data));m.arm();samples=[]
 for i in range(1400):
  y=m.process(i,input_block(i))
  if i>=1350:samples+=y
 assert m.stats()[2]==1 and m.words()[4]==0;outputs.append(samples)
assert outputs[0]==outputs[1]
report=dict(status='PASS_OFFLINE_TOUCH_WAH',elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),identity=bundle[2]['identity'],cases=rows,saved_and_recalled=True,finite_audio=True,bypass_sample_exact=True,device_access=False,host_audio_access=False,physical_deadlines_verified=False,tail_RAM_probe=dict(start=hex(lo),end=hex(hi),bytes=hi-lo,writes=[dict(phase=k[0],pc=hex(k[1]),lr=hex(k[2]),**r) for k,r in writes.items()],reads=[dict(phase=k[0],pc=hex(k[1]),lr=hex(k[2]),**r) for k,r in reads.items()],scope='Touch Wah variants, NAM and Spring; incomplete stock/USB/DMA coverage',production_allocation=False))
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
