#!/usr/bin/env python3
"""Execute owned reset/startup/audio code in ARM VM; no NUX image loaded."""
import argparse,hashlib,json,struct,random,time
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
from a2_oracle import library,Engine,extract
p=argparse.ArgumentParser();p.add_argument('elf',type=Path);p.add_argument('reference');p.add_argument('model',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
with a.elf.open('rb') as f:
 e=ELFFile(f);symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()};entry=e.header['e_entry']
 loads=[(s['p_paddr'],s.data()) for s in e.iter_segments() if s['p_type']=='PT_LOAD' and s['p_filesz']]
assert entry==symbols['mpp_lab_reset']
j=extract(json.loads(a.model.read_text()));weights=struct.pack('<1871f',*j['weights']);lib=library(a.reference)
MAIL=symbols['mpp_vm_mailbox'];DMA=symbols['mpp_vm_dma'];STOP=0x0800ff00;cases=[]
def put(u,addr,v):u.mem_write(addr,struct.pack('<I',v&0xffffffff))
def get(u,addr):return struct.unpack('<I',u.mem_read(addr,4))[0]
def call(u,name):
 u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(symbols[name]|1,STOP,count=4000000);assert u.reg_read(UC_ARM_REG_PC)==STOP,(name,hex(u.reg_read(UC_ARM_REG_PC)))
def status(u):call(u,'mpp_vm_status');return struct.unpack('<7I',u.mem_read(u.reg_read(UC_ARM_REG_R0),28))
def boot(u):
 u.reg_write(UC_ARM_REG_SP,0x2001fff0);u.emu_start(entry, symbols['mpp_lab_idle'],count=4000000)
 assert u.reg_read(UC_ARM_REG_PC)==symbols['mpp_lab_idle'],hex(u.reg_read(UC_ARM_REG_PC))
 assert get(u,symbols['mpp_data_cookie'])==0x4d505031
 assert get(u,0xe000ed08)==symbols['mpp_vectors']
 assert u.reg_read(UC_ARM_REG_PRIMASK)==1
 assert not any(u.mem_read(DMA+256,256))
def setup(lock_after=1,control=0,fail=0,nack=0,step=100,tag=0x4d50564d):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
 for base,size in [(0x08000000,0x10000),(0x20000000,0x20000),(0x202c0000,0x5000),(0xe000e000,0x2000)]:u.mem_map(base,size)
 for addr,data in loads:u.mem_write(addr,data)
 # Poison destination RAM, stack and DMA to prove the reset path initializes it.
 u.mem_write(0x20000000,b'\xa5'*0x20000);u.mem_write(DMA,b'\xa5'*640)
 u.mem_write(MAIL,struct.pack('<12I',tag,0,lock_after,control,fail,nack,step,1871,0,0,0,0)+weights)
 u.mem_write(DMA+640,b'\x3c'*32)
 u.mem_protect(0x08000000,0x10000,UC_PROT_READ|UC_PROT_EXEC)
 return u
start=time.perf_counter();u=setup();boot(u);assert status(u)==(2,0,0,0,0,0,0);cases.append('cold reset data/BSS/DMA initialization')
assert struct.unpack('<2I',u.mem_read(0x08000000,8))==(symbols['__stack_top'],entry)
oracle=Engine(lib,a.model);rng=random.Random(700);blocks=[];outputs=[];maxerr=0
for b in range(128):
 words=[];xs=[]
 for i in range(8):
  q=rng.randrange(-2**29,2**29);xs.append(struct.unpack('<f',struct.pack('<f',q/2**31))[0]);words.extend([q,0x70000000,-0x70000000,0])
 half=b&1;u.mem_write(DMA+128*half,struct.pack('<32i',*words));u.mem_write(MAIL+32,struct.pack('<3I',b,half,half));call(u,'mpp_vm_audio_irq')
 assert get(u,MAIL+44)==1 and not any(u.mem_read(DMA+256,256))
 out=struct.unpack('<8f',u.mem_read(symbols['mpp_vm_diagnostic'],32));ref=oracle.run(xs);maxerr=max(maxerr,max(abs(x-y) for x,y in zip(out,ref)));blocks.append(words);outputs.append(out)
assert maxerr<2e-5;assert status(u)==(2,0,128,1024,100,128,0);cases.append('128 A2 callbacks vs official NAM with zero TX')
# Restart without reloading the ELF or model mailbox; reset must clear history.
put(u,symbols['mpp_data_cookie'],0);u.mem_write(DMA+256,b'\xff'*256);boot(u);assert status(u)==(2,0,0,0,0,0,0)
for b in range(8):
 half=b&1;u.mem_write(DMA+128*half,struct.pack('<32i',*blocks[b]));u.mem_write(MAIL+32,struct.pack('<3I',b,half,half));call(u,'mpp_vm_audio_irq');assert struct.unpack('<8f',u.mem_read(symbols['mpp_vm_diagnostic'],32))==outputs[b]
cases.append('warm reset restores data and A2 history bit-identically')
assert bytes(u.mem_read(DMA+640,32))==b'\x3c'*32
stack=bytes(u.mem_read(symbols['__stack_bottom'],0x4000));first=next(i for i,v in enumerate(stack) if v!=0xa5);stack_used=0x4000-first;assert first>=1024
for name,kw,error in [('PLL lock timeout',{'lock_after':0},3),('codec NACK',{'nack':4},4),('hardware-port failure',{'fail':3},1),('invalid model mailbox',{'tag':0},5)]:
 v=setup(**kw);boot(v);s=status(v);assert s[0]==3 and s[1]==error,(name,s);cases.append(name)
for name,step in [('timer stopped',0),('deadline reached',1000)]:
 v=setup(step=step);boot(v);call(v,'mpp_vm_audio_irq');assert status(v)[:2]==(3,8);assert not any(v.mem_read(DMA+256,256));cases.append(name)
v=setup(control=0x20002000);boot(v);assert status(v)[0]==2;cases.append('already-running PLL reconfiguration')
v=setup();put(v,0xe000ed14,0x10000);v.emu_start(entry,symbols['mpp_lab_handoff_rejected'],count=1000);assert v.reg_read(UC_ARM_REG_PC)==symbols['mpp_lab_handoff_rejected'];cases.append('unsupported cache-enabled handoff rejected before runtime')
report={'status':'PASS_OWNED_ARM_RESET_AND_AUDIO_PROTOTYPE','cases':cases,'case_count':len(cases),'a2_frames':1024,'max_reference_error':maxerr,'tolerance':2e-5,'warm_reset_comparison_frames':64,'stack_high_water_bytes_observed':stack_used,'stack_reserved_bytes':0x4000,'dma_guard_intact':True,'tx_always_zero':True,'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),'model_sha256':hashlib.sha256(a.model.read_bytes()).hexdigest(),'stock_firmware_loaded':False,'peripheral_MMIO_mapped':False,'core_system_registers_simulated':True,'peripheral_backend':'RAM-only test port; real board port remains unfinished','irq_invoked_as_function_not_hardware_exception':True,'hardware_timing_measured':False,'device_access':False,'playback':False,'elapsed_seconds':time.perf_counter()-start}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
