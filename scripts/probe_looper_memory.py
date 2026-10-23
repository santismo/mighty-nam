"""Bounded retired-AMP tail conflict probe. Emulator only; not an allocation proof."""
import argparse,sys,json,hashlib,struct,zlib
from pathlib import Path
p=argparse.ArgumentParser()
for name in ['work','payload','model','output']:p.add_argument(name,type=Path)
a=p.parse_args();sys.path[:0]=[str(a.work/'generated/research'),str(a.work/'generated/tools')]
from test_usb_nam import UsbMachine,v,preset_fixture,input_block,model_slot
from preset_image import build
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR
elf=a.work/'build/nam-link-offline.elf';v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),elf));v.elf_path=elf
m=UsbMachine();m.service();slot=model_slot(a.model);m.upload(slot,345);m.arm();m.initialize_usb()
for i in range(1320):m.process(i,input_block(i))
lo,hi=0x20314000,0x2031b000;sentinel=bytes([0xa7])*(hi-lo);m.u.mem_write(lo,sentinel)
phase='init';accesses={};cases=[]
def track(u,kind,addr,size,value,user):
 key=(phase,kind,u.reg_read(UC_ARM_REG_PC),u.reg_read(UC_ARM_REG_LR))
 row=accesses.setdefault(key,dict(count=0,first=addr,last=addr+size-1))
 row['count']+=1;row['first']=min(row['first'],addr);row['last']=max(row['last'],addr+size-1)
m.u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,track,begin=lo,end=hi-1)
counter=1320
for stage,count in [(1,3),(2,14),(4,4),(5,1),(6,13),(7,5),(8,6),(9,20)]:
 for typ in range(1,count+1):
  phase=f'stock loader {stage}:{typ}';settings=bytearray(preset_fixture([stage],{stage:typ}));settings[84]=37
  m.u.mem_write(m.preset,bytes(settings))
  for i in range(8):m.process(counter,input_block(counter));counter+=1
  m.guards();assert m.words()[4]==0;cases.append(dict(stage=stage,type=typ,sentinel_intact=bytes(m.u.mem_read(lo,hi-lo))==sentinel))
 print('loader sweep',stage,count,flush=True)
phase='full chain render';settings=bytearray(preset_fixture([1,2,4,5,6,7,8,9],{2:14,4:4,8:4}));settings[84]=37;m.u.mem_write(m.preset,bytes(settings));m.arm()
for i in range(1400):m.process(counter,input_block(counter));counter+=1
render_intact=bytes(m.u.mem_read(lo,hi-lo))==sentinel
settings=bytes(m.u.mem_read(m.preset,128));body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(settings),1,8)+hashlib.sha256(slot).digest()+b'Looper memory probe'.ljust(64,b'\0')
phase='preset save';assert m.bank_request(2,0,body,nonce=444)[7]==0
phase='preset recall';assert m.bank_request(3,0,nonce=445)[7]==0;m.service()
recall_intact=bytes(m.u.mem_read(lo,hi-lo))==sentinel
phase='cold restart';m.restart();m.service();restart_intact=bytes(m.u.mem_read(lo,hi-lo))==sentinel
report=dict(status='COMPLETED_OFFLINE_LOOPER_MEMORY_PROBE',elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),range=[hex(lo),hex(hi)],bytes=hi-lo,PCM16_mono_seconds=(hi-lo)/96000,ADPCM4_mono_seconds_before_overhead=(hi-lo)/24000,loader_cases=cases,full_chain_sentinel_intact=render_intact,save_recall_sentinel_intact=recall_intact,cold_restart_sentinel_intact=restart_intact,accesses=[dict(phase=k[0],access=k[1],pc=hex(k[2]),lr=hex(k[3]),**v) for k,v in accesses.items()],production_allocation=False,device_access=False,host_audio_access=False,limitations=['Bounded stock-loader and render coverage; not proof of ownership or complete DSP coverage.','USB/Bluetooth DMA and peripheral accesses are modeled, not real bus masters.','This is too small for a useful multi-second PCM loop.','Loop playback cannot continue through a masked interrupt; flash-read stalls are not timed here.'])
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
