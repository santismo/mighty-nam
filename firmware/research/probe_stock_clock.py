#!/usr/bin/env python3
"""Bounded stock audio-PLL emulation; every register is virtual RAM.
Analog-interface operations and delays are logged stubs. PLL lock is a test
input, not a measured outcome. No USB/audio/live device access.
"""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
b=a.payload.read_bytes();sha=hashlib.sha256(b).hexdigest()
if sha!='a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990':raise ValueError('Unexamined payload')
def run(warm,locks):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
 u.mem_map(0,0x100000);u.mem_write(0,b[:0x100000]);u.mem_protect(0,0x100000,UC_PROT_READ|UC_PROT_EXEC)
 u.mem_map(0x20000000,0x400000);u.mem_map(0x40c84000,0x1000)
 u.reg_write(UC_ARM_REG_SP,0x20080000);u.reg_write(UC_ARM_REG_LR,0x40001)
 u.emu_start(0x2025d,0x40000,count=5000000)
 if u.reg_read(UC_ARM_REG_PC)!=0x40000:raise AssertionError('Runtime initializer failed')
 config=bytes(u.mem_read(0x20009b20,20));events=[];writes=[]
 control=0x40c84300
 u.mem_write(control,struct.pack('<I',0x20002000 if warm else 0))
 def code(uc,pc,size,user):
  kinds={0x8ed4:'pll_ldo_enable_stub',0x93b8:'analog_write_stub',0x93c8:'analog_modify_stub',0x90ac:'delay_stub'}
  if pc in kinds:
   args=[uc.reg_read(r) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]]
   ev={'pc':hex(pc),'kind':kinds[pc],'args':args[:2 if pc==0x90ac else 1 if pc==0x8ed4 else 4 if pc==0x93c8 else 3]}
   if pc==0x93c8:ev['bit_shift']=struct.unpack('<I',uc.mem_read(uc.reg_read(UC_ARM_REG_SP),4))[0]
   events.append(ev);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  # Explicitly emulate a successful physical lock only in positive cases.
  if pc==0x8830 and locks:
   v=struct.unpack('<I',uc.mem_read(control,4))[0];uc.mem_write(control,struct.pack('<I',v|0x20000000))
 def write(uc,access,addr,size,value,user):writes.append({'address':hex(addr),'value':hex(value),'pc':hex(uc.reg_read(UC_ARM_REG_PC))})
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write,begin=control,end=control+3)
 u.reg_write(UC_ARM_REG_R0,0x20009b20);u.reg_write(UC_ARM_REG_SP,0x20080000);u.reg_write(UC_ARM_REG_LR,0x40001)
 u.emu_start(0x87a1,0x40000,count=20000)
 pc=u.reg_read(UC_ARM_REG_PC);returned=pc==0x40000
 if returned!=locks:raise AssertionError('Unexpected lock behavior')
 return {'warm_start':warm,'simulated_lock':locks,'returned':returned,'final_pc':hex(pc),'config_hex':config.hex(' '),'events':events,'virtual_control_writes':writes}
cases=[run(False,True),run(True,True),run(False,False)]
c=bytes.fromhex(cases[0]['config_hex']);loop,post=c[:2];num,den=struct.unpack_from('<II',c,4)
pll=24000000*(loop+num/den)/(2**post);root=pll/16;bclk=root/4;fs=bclk/128
result={'status':'PASS_OFFLINE_ONLY','payload_sha256':sha,'cases':cases,
 'conditional_frequency_calculation':{'assumed_reference_hz':24000000,'loop_divider':loop,'post_divider_encoding':post,
 'numerator':num,'denominator':den,'pll_hz':pll,'sai_root_hz':root,'bit_clock_hz':bclk,'frame_rate_hz':fs,
 'offset_from_48000_ppm':(fs/48000-1)*1e6,'measured':False},
 'findings':['Stock cold-start and already-locked branches reproduced with analog operations stubbed',
 'A missing lock leaves the saved stock routine polling; emulator instruction budget stops the test',
 'No timeout was observed on this lock-poll path',
 'PLL reference accuracy and any runtime trimming remain unverified'],
 'device_or_audio_access':False}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'frequency':result['conditional_frequency_calculation'],'cases':[{k:c[k] for k in ['warm_start','simulated_lock','returned','final_pc']} for c in cases]},indent=2))
