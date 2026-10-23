"""Read-only files + bounded ARM emulator RAM audit; never writes a real device."""
import argparse,json,sys,hashlib,struct,zlib
from pathlib import Path
from collections import defaultdict
p=argparse.ArgumentParser()
for n in ['work','payload','models','output']:p.add_argument(n,type=Path)
a=p.parse_args();sys.path[:0]=[str(a.work/'generated/research'),str(a.work/'generated/tools')]
from test_usb_nam import UsbMachine,v,preset_fixture,input_block,model_slot
from preset_image import build
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_CODE,UC_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR
from elftools.elf.elffile import ELFFile
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
elf=a.work/'build/nam-link-offline.elf';raw=a.payload.read_bytes();bundle=build(raw,elf);v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=elf
models=sorted(a.models.glob('*-lite.nam'));assert len(models)==3
regions=[('M4 RAM alias / stock DSP',0x20200000,0x20240000),('OCRAM1',0x20240000,0x202c0000),('OCRAM2 below custom arena',0x202c0000,0x202e4000),('OCRAM2 beyond copied code',0x20314000,0x20340000)]
m=UsbMachine();m.service();m.upload(model_slot(models[0]),901);m.initialize_usb();m.arm()
for i in range(1320):m.process(i,input_block(i))
phase='idle';pages=defaultdict(lambda:dict(reads=0,writes=0,phases=set(),pcs=set()))
def watch(u,kind,addr,n,val,user):
 for page in range(addr//256,(addr+n-1)//256+1):
  r=pages[page*256];r['writes' if kind==UC_MEM_WRITE else 'reads']+=1;r['phases'].add(phase)
  if len(r['pcs'])<8:r['pcs'].add(u.reg_read(UC_ARM_REG_PC))
for _,lo,hi in regions:m.u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,watch,begin=lo,end=hi-1)
counter=1320;cases=[]
for stage,count in [(1,3),(2,14),(4,4),(5,1),(6,13),(7,5),(8,6),(9,20)]:
 for typ in range(1,count+1):
  phase=f'load {stage}:{typ}';data=bytearray(preset_fixture([stage],{stage:typ}));data[84]=37;m.u.mem_write(m.preset,bytes(data))
  for _ in range(8):m.process(counter,input_block(counter));counter+=1
  m.guards();assert m.words()[4]==0;cases.append([stage,typ])
 print('audited loader group',stage,count,flush=True)
# Render a bounded sample after full settling for representative long-delay/reverb chains.
for label,enabled,types in [('spring',[8],{8:4}),('delay reverb',[7,8],{7:3,8:5}),('full',[1,2,4,5,6,7,8,9],{2:14,4:4,8:4})]:
 phase=label;data=bytearray(preset_fixture(enabled,types));data[84]=37;m.u.mem_write(m.preset,bytes(data));m.arm()
 for _ in range(1450):m.process(counter,input_block(counter));counter+=1
 assert m.words()[4]==0;print('audited chain',label,flush=True)
# Save three distinct public model presets and invoke real recall paths.
for color,model in enumerate(models):
 phase=f'model transfer {color}';slot=model_slot(model);m.upload(slot,1000+color);data=bytearray(preset_fixture([8] if color else [],{8:4}));data[84]=37;m.u.mem_write(m.preset,bytes(data))
 body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(data),1,8)+hashlib.sha256(slot).digest()+f'RAM audit {color}'.encode().ljust(64,b'\0')
 phase=f'save {color}';assert m.bank_request(2,color,body,nonce=1100+color)[7]==0
flash_reads=[];masked=[0,0,0]
def instructions(u,pc,size,user):
 masked[2]+=1
 if m.primask:masked[0]+=1;masked[1]=max(masked[1],masked[0])
 else:masked[0]=0
 if pc==0x84f8:flash_reads.append(dict(phase=phase,bytes=u.reg_read(v.R[2]),IRQs_masked=bool(m.primask)))
h=m.u.hook_add(UC_HOOK_CODE,instructions)
for color in [0,1,2,0]:
 phase=f'recall {color}';assert m.bank_request(3,color,nonce=1200+color)[7]==0;m.service()
m.u.hook_del(h)
# Confirm loaded capture resumes rendering; the separate loop mixer is tested elsewhere.
phase='after recall'
for _ in range(1400):m.process(counter,input_block(counter));counter+=1
assert m.words()[4]==0
# Static evidence: literal-pool references are leads, not proof (data can decode as code).
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True;md.skipdata=True;refs=[]
for ins in md.disasm(raw[0x400:0x22618],0x400):
 if ins.id and ins.mnemonic.startswith('ldr') and len(ins.operands)>1:
  op=ins.operands[1]
  if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC:
   at=((ins.address+4)&~3)+op.mem.disp
   if 0<=at<=len(raw)-4:
    val=struct.unpack_from('<I',raw,at)[0]
    if 0x20200000<=val<0x20400000:refs.append(dict(pc=hex(ins.address),literal=hex(at),value=hex(val)))
with elf.open('rb') as f:
 e=ELFFile(f);objects=sorted([dict(name=s.name,address=hex(s['st_value']),bytes=s['st_size']) for s in e.get_section_by_name('.symtab').iter_symbols() if s['st_info']['type']=='STT_OBJECT' and s['st_size'] and 0x202e4000<=s['st_value']<0x2030f000],key=lambda x:x['bytes'],reverse=True)
summary=[]
for name,lo,hi in regions:
 touched=[p for p in pages if lo<=p<hi];runs=[];start=None
 for page in range(lo,hi,256):
  if page not in pages:
   if start is None:start=page
  elif start is not None:runs.append([hex(start),hex(page),page-start]);start=None
 if start is not None:runs.append([hex(start),hex(hi),hi-start])
 summary.append(dict(name=name,start=hex(lo),end=hex(hi),observed_pages=len(touched),observed_bytes_rounded_to_256=len(touched)*256,largest_unobserved_span=max(runs,key=lambda x:x[2]) if runs else None,unobserved_is_not_free=True))
# Verified zero-initialization descriptor: (length,address), terminated by zero.
zeroed=[]
for off in range(0x226b4,0x2270c,8):
 size,address=struct.unpack_from('<2I',raw,off);zeroed.append(dict(start=hex(address),bytes=size,end=hex(address+size)))
report=dict(cold_start_zeroed_spans=zeroed,unobserved_total_bytes=sum((hi-lo)-sum(lo<=p<hi for p in pages)*256 for _,lo,hi in regions),status='COMPLETED_OFFLINE_RAM_OWNERSHIP_AUDIT',elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),stock_payload_sha256=hashlib.sha256(raw).hexdigest(),regions=summary,custom_objects=objects,static_RAM_literal_leads=refs,observed_pages=[dict(address=hex(k),**{n:(sorted(v) if n=='phases' else [hex(x) for x in sorted(v)] if n=='pcs' else v) for n,v in row.items()}) for k,row in sorted(pages.items())],loader_cases=cases,callbacks=counter,actual_model_recalls=[0,1,2,0],preset_read_calls=flash_reads,max_contiguous_modeled_IRQ_masked_instructions=masked[1],interrupt_count_is_not_physical_time=True,hardware_RAM_reserved=False,device_access=False,host_audio_access=False,limitations=['CPU observation of bounded stock paths, not hardware bus-master ownership proof.','Startup/peripherals/cache/USB completion and flash reads have modeled behavior.','Unobserved pages cannot be allocated until static ownership, initialization, MPU/cache and DMA uses are resolved.','M4 RAM and flexible OCRAM aliases must not be double-counted.','Stock preset reads still mask interrupts; continuous hardware loop playback is not established.'])
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
