#!/usr/bin/env python3
"""Reproduce an emulator instrumentation artifact without hardware access."""
import argparse,hashlib,json
import unicorn
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
from candidate_image import STOCK_SHA,require
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
b=a.payload.read_bytes();require(hashlib.sha256(b).hexdigest()==STOCK_SHA,'Exact V1.5.6 required')
rows=[]
for kind in ['no_write_hook','global_write_hook','arena_only_write_hook']:
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A15)
 u.mem_map(0,0x40000);u.mem_write(0,b[:0x40000]);u.mem_map(0x20000000,0x40000)
 u.mem_write(0x20025000,b'\xa5'*0x400)
 for reg,value in [(UC_ARM_REG_SP,0x20035000),(UC_ARM_REG_LR,0x3fffd),(UC_ARM_REG_R0,0x20025000),(UC_ARM_REG_R1,32)]:u.reg_write(reg,value)
 if kind!='no_write_hook':
  region={'begin':0x202e4000,'end':0x202e5fff} if kind=='arena_only_write_hook' else {}
  u.hook_add(UC_HOOK_MEM_WRITE,lambda *args:None,**region)
 u.emu_start(0x5531,0x3fffc,count=200)
 good=u.reg_read(UC_ARM_REG_PC)==0x3fffc and bytes(u.mem_read(0x20025000,32))==bytes(32) and bytes(u.mem_read(0x20025020,16))==b'\xa5'*16
 require(good==(kind!='global_write_hook'),'Instrumentation behavior changed; revalidate harness')
 rows.append({'kind':kind,'returned_and_cleared_exactly_32_bytes':good,'ending_r0':hex(u.reg_read(UC_ARM_REG_R0)),'ending_r1':hex(u.reg_read(UC_ARM_REG_R1))})
result={'status':'PASS_EMULATOR_INSTRUMENTATION_REGRESSION','unicorn_version':unicorn.__version__,
 'cases':rows,'interpretation':'Global memory-write instrumentation alters this stock IT/STM loop in Unicorn 2.1.4. Restrict the ownership watcher to the protected arena. This is not a physical stock-firmware defect.',
 'scope':'Exact stock 32-byte clear routine, instruction model only','device_or_audio_access':False}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
