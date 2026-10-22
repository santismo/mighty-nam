#!/usr/bin/env python3
"""NAMLNK10 ARM startup, copies, real protocol, preset hook and persistence.
Flash peripheral calls are modeled at exact stock driver boundaries; this does
not prove physical erase/program behavior or MPU/cache configuration.
"""
import argparse,json,struct,zlib,hashlib,sys
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
from test_link_listening import ListeningMachine,v,preset_fixture,Engine,library
from test_link_firmware import pack,unpack
from a2_storage import model_slot
from preset_image import build,BANK,BANK_END,FLASH

class PresetMachine(ListeningMachine):
 def __init__(self,flash=None,fill=0,path=None,oracle=None,boundary_oracle=None):
  self.saved_flash=flash;self.flash_operations=[];self.fail_write=False
  self.broadcasts=[]
  self.mclass_ops={};self.primask=0
  super().__init__(path=path,oracle=oracle,boundary_oracle=boundary_oracle,fill=fill)
  # ChainMachine already installs erase/program hooks after removing its
  # expensive global instruction observer. Add only the missing read hook.
  self.u.hook_add(UC_HOOK_CODE,self.code,begin=0xc080,end=0xc080)
  self.u.hook_add(UC_HOOK_CODE,self.code,begin=0xb5c6,end=0xb5c6)
  self.u.hook_add(UC_HOOK_MEM_READ,self.resource_read,begin=BANK,end=0x303ac000-1)
  # The established FPU harness uses Unicorn's A15 model. Explicitly model
  # only its unsupported M-profile interrupt mask instructions; no DSP or
  # storage control flow is skipped.
  from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
  code=next(r for r in v.plan['elf_regions'] if r['name']=='.banktext')
  start=int(code['start'],16)
  decoder=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
  # Decode function ranges independently: inline literal pools are not code
  # and can stop a linear sweep before the backend's mask instructions.
  from elftools.elf.elffile import ELFFile
  with open(v.elf_path,'rb') as f:
   elf=ELFFile(f)
   functions=[(s['st_value']&~1,s['st_size']) for s in elf.get_section_by_name('.symtab').iter_symbols()
    if s['st_info']['type']=='STT_FUNC' and start<=(s['st_value']&~1)<start+code['bytes']]
  instructions=[]
  for address,length in functions:
   decoder.skipdata=True
   instructions.extend(decoder.disasm(bytes(self.u.mem_read(address,length)),address))
  for ins in instructions:
   if ins.mnemonic in ('mrs','msr') and 'primask' in ins.op_str or ins.mnemonic in ('cpsid','cpsie'):
    self.mclass_ops[ins.address]=(ins.mnemonic,ins.op_str,ins.size)
    self.u.hook_add(UC_HOOK_CODE,self.code,begin=ins.address,end=ins.address)
 def boot(self,*args,**kwargs):
  if not getattr(self,'preset_flash_mapped',False):
   self.u.mem_map(FLASH,(len(v.stock)+4095)&~4095,UC_PROT_READ)
   self.u.mem_write(FLASH,v.candidate)
   if self.saved_flash is not None:self.u.mem_write(BANK,self.saved_flash)
   self.u.mem_protect(0x20308000,0xc000,UC_PROT_ALL)
   self.preset_flash_mapped=True
  super().boot(*args,**kwargs)
 def resource_read(self,u,access,addr,size,value,unused):
  assert v.in_code(u.reg_read(UC_ARM_REG_PC)),('Foreign stock reader of retired storage',hex(u.reg_read(UC_ARM_REG_PC)),hex(addr))
 def run(self,pc,end=v.STOP,limit=6000000):
  try:return super().run(pc,end,max(limit,40000000))
  except UcError:
   here=self.u.reg_read(UC_ARM_REG_PC)
   print('EMU failure PC',hex(here),'bytes',bytes(self.u.mem_read(here,8)).hex(),flush=True)
   raise
 def code(self,u,pc,size,unused):
  if self.phase=='probe' and pc==0xb5c6:
   self.broadcasts.append((u.reg_read(UC_ARM_REG_R0),u.reg_read(UC_ARM_REG_R1)))
   u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  if pc in self.mclass_ops:
   mnemonic,operands,length=self.mclass_ops[pc]
   if mnemonic=='mrs':u.reg_write(globals()['UC_ARM_REG_'+operands.split(',')[0].upper()],self.primask)
   elif mnemonic=='msr':self.primask=u.reg_read(globals()['UC_ARM_REG_'+operands.split(',')[1].strip().upper()])
   else:self.primask=1 if mnemonic=='cpsid' else 0
   u.reg_write(UC_ARM_REG_PC,(pc+length)|1);return
  if self.phase=='probe' and pc in (0xc080,0xbfa4,0xc034):
   assert self.primask==1 and not self.words()[9], 'Flash access requires interrupted audio and masked IRQs'
   r0,r1,r2=[u.reg_read(r) for r in v.R[:3]]
   if pc==0xc080:
    assert (BANK<=r1 and r1+r2<=BANK_END and r2==8192) or (v.plan['identity'] in ('NAMLNK18','NAMLNK19','NAMLNK20','NAMLNK21','NAMLNK22','NAMPIT01','NAMDMP01','NAMDMP02','NAMACP01') and 0x303a4000<=r1 and r1+r2<=0x303a6000 and r2==256)
    assert v.state_start<=r0 and r0+r2<=v.state_end
    u.mem_write(r0,bytes(u.mem_read(r1,r2)));result=0
   else:
    addr=r0 if pc==0xbfa4 else r1;n=4096 if pc==0xbfa4 else 256-(addr&255)
    assert (BANK<=addr and addr+n<=BANK_END) or (v.plan['identity'] in ('NAMLNK18','NAMLNK19','NAMLNK20','NAMLNK21','NAMLNK22','NAMPIT01','NAMDMP01','NAMDMP02','NAMACP01') and 0x303a4000<=addr and addr+n<=0x303a6000),(hex(pc),hex(addr),n)
    if pc==0xbfa4:assert addr%4096==0
    else:assert n in (4,256) and v.state_start<=r0 and r0+n<=v.state_end
    self.flash_operations.append((pc,addr,n));result=1 if self.fail_write else 0
    if not result:
     data=b'\xff'*n if pc==0xbfa4 else bytes(u.mem_read(r0,n))
     if pc==0xc034:
      before=bytes(u.mem_read(addr,n));assert all((x&y)==y for x,y in zip(before,data))
     u.mem_write(addr,data)
   u.reg_write(UC_ARM_REG_R0,result);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  if self.phase=='probe' and pc==0xae80:
   data,n,ch=[u.reg_read(r) for r in v.R[:3]]
   if n==326 or v.plan['identity'] in ('NAMLNK13','NAMLNK14','NAMLNK15','NAMLNK16','NAMLNK17','NAMLNK18','NAMLNK19','NAMLNK20','NAMLNK21','NAMLNK22','NAMPIT01','NAMDMP01','NAMDMP02','NAMACP01') and n<=56:
    self.messages.append((bytes(u.mem_read(data,n)),ch));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  super().code(u,pc,size,unused)
 def write(self,u,access,addr,n,val,user):
  # The NAMLNK20 dispatcher passes only this explicit scratch to stock DSP.
  # Retain all other retired-RAM write guards.
  audio=v.sym.get('_ZN12_GLOBAL__N_15audioE',0)
  if v.plan['identity']=='NAMLNK20' and self.phase=='probe' and audio<=addr and addr+n<=audio+128:return
  super().write(u,access,addr,n,val,user)
 def service(self):self.call(0x57c0,[])
 def button(self):
  self.u.reg_write(UC_ARM_REG_R4,0x20005ad0)
  self.run(0x120f0,end=0x12132)
  selected=self.u.mem_read(self.get(0x20005ad8)+2,1)[0]
  assert self.broadcasts[-2:]==[(selected,0),(selected,1)]
  self.service();return selected
 def bank_request(self,op,slot,body=b'',channel=0,nonce=10):
  raw=bytearray(struct.pack('<IBBBB I HBB',0x3031504e,1,op,slot,0,nonce,len(body),0,0)+body)
  raw+=struct.pack('<I',zlib.crc32(raw));message=bytes.fromhex('f043587004024e5301')+pack(raw)+b'\xf7'
  replies=self.ingress([message],channel,start=2045);assert len(replies)==1
  wire=replies[0][0]
  if wire[6:9]==b'NR\x01':
   generation=wire[9:11];parts=wire[15:-1];total=wire[13]+128*wire[14]
   assert wire[11]==0 and len(wire)<=56
   for page in range(1,wire[12]):
    request=bytes([240,67,88,112,4,2,78,82,1])+generation+bytes([page,247])
    part=self.ingress([request],channel)[0][0]
    assert part[9:11]==generation and part[11]==page and len(part)<=56
    parts+=part[15:-1]
   assert len(parts)==total;wire=b'\xf0'+parts+b'\xf7'
  assert wire[:9]==message[:9] and replies[0][1]==channel
  reply=unpack(wire[9:-1]);assert len(reply)==276 and reply[5]==op|128 and reply[6]==slot
  assert struct.unpack_from('<I',reply,272)[0]==zlib.crc32(reply[:272])
  return reply

def main():
 p=argparse.ArgumentParser();p.add_argument('payload',type=Path);p.add_argument('elf',type=Path);p.add_argument('models',nargs=2,type=Path);p.add_argument('--library',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 bundle=build(a.payload.read_bytes(),a.elf);v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=a.elf
 m=PresetMachine();m.service();assert m.page(25)==(0,0x010000ff)
 slots=[model_slot(path) for path in a.models];expected=[]
 for i in range(7):
  model=slots[i%2];m.upload(model,100+i)
  fx=preset_fixture([1,2,4,5,6,7,8,9]);fx[20]=10+i*5;fx=bytes(fx);m.u.mem_write(m.preset,fx)
  body=struct.pack('<4I',zlib.crc32(model),zlib.crc32(fx),1,8)+hashlib.sha256(model).digest()+('Color '+str(i+1)).encode().ljust(64,b'\0')
  reply=m.bank_request(2,i,body,channel=i%2);assert reply[7]==0 and reply[14]==i and reply[15]==(1<<(i+1))-1
  assert m.page(23)==(0,2);expected.append((zlib.crc32(model),fx))
  writes=len(m.flash_operations);assert m.bank_request(2,i,body)[7]==0 and len(m.flash_operations)==writes
  print('saved color',i+1,'duplicate did not write',flush=True)
 # Actual stock preset entry, then foreground callback: model+effects follow
 # the same request that the physical PRESET handler makes, without the app.
 m.arm()
 for i in [0,1,2,3,4,5,6,0]:
  m.call(0xb38a,[i]);assert not m.words()[9];m.service()
  assert m.words()[5]==expected[i][0] and bytes(m.u.mem_read(m.preset,128))==expected[i][1]
  assert m.page(25)==(0,0x01007f00|i) and m.page(23)==(0,3)
  # Both DMA halves stay zero during the existing settling period.
  m.process(0);m.process(1);m.guards()
 # The actual stock PRESET-button branch honors the occupied mask, wraps, and
 # broadcasts stock selection. This is function execution, not GPIO proof.
 for i in [1,2,3,4,5,6,0]:
  assert m.button()==i and m.words()[5]==expected[i][0]
  assert bytes(m.u.mem_read(m.preset,128))==expected[i][1]
 print('stock button branch: seven colors and wrap passed',flush=True)
 flash=bytes(m.u.mem_read(BANK,BANK_END-BANK));rows=[]
 for fill in [0,0xa5,0xff]:
  n=PresetMachine(flash,fill);n.service()
  assert n.page(25)==(0,0x01007f00) and n.words()[5]==expected[0][0]
  assert bytes(n.u.mem_read(n.preset,128))==expected[0][1] and n.page(23)==(0,3)
  n.restart();n.service();assert n.words()[5]==expected[0][0] and n.page(23)==(0,3)
  rows.append(fill);print('cold/warm retained bank',fill,flush=True)
 sparse=bytearray(flash)
 for i in [1,2,4,5,6]:sparse[i*16384:(i+1)*16384]=b'\xff'*16384
 n=PresetMachine(bytes(sparse));n.service()
 assert [n.button(),n.button()]==[3,0]
 print('stock button skips empty colors',flush=True)
 accuracy=[];lib=library(str(a.library))
 for i,path in enumerate(a.models):
  assert m.bank_request(3,i)[7]==0
  m.boundary_oracle=Engine(lib,path);m.max_boundary_error=0.;m.boundary_samples=0
  peak=0.
  for block in range(1300):peak=max(peak,max(map(abs,m.process(block))))
  assert m.boundary_samples>=800 and 0<peak<=.109375
  accuracy.append(dict(model=path.name,blocks=1300,NAM_samples=m.boundary_samples,peak=peak,max_error=m.max_boundary_error))
  print('saved model through full stock chain',accuracy[-1],flush=True)
 before=bytes(m.u.mem_read(BANK,BANK_END-BANK));m.fail_write=True
 m.u.mem_write(m.preset+20,b'\x25');fx=bytes(m.u.mem_read(m.preset,128))
 body=struct.pack('<4I',m.words()[5],zlib.crc32(fx),1,8)+bytes(32)+b'Failed save'.ljust(64,b'\0')
 assert m.bank_request(2,0,body)[7]==3 and bytes(m.u.mem_read(BANK,BANK_END-BANK))==before
 report=dict(status='PASS_'+bundle[2]['identity']+'_ARM_PRESET_RUNTIME',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),
  seven_slots=True,model_count=2,exact_model_and_effect_recall=True,stock_selection_hook=True,stock_button_branch=True,button_skips_empty=True,cold_patterns=rows,warm_restarts=3,accuracy=accuracy,
  duplicate_saves_do_not_write=True,failed_driver_write_preserves_saved_data=True,flash_operations=len(m.flash_operations),
  flash_bounds=[hex(BANK),hex(BANK_END)],device_access=False,audio_access=False,
  limits=['Stock flash functions stubbed with bounded NOR semantics; physical drivers unverified','Copied-code cache/MPU behavior unverified on hardware','Hook exercised; no physical button/LED observation'])
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
if __name__=='__main__':main()
