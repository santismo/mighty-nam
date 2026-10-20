#!/usr/bin/env python3
"""Execute public stock MPU setup and flash wrappers with inert peripheral model.
No USB/flash/audio access. Controller completion and flash contents are modeled.
"""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
p=argparse.ArgumentParser();p.add_argument('payload',type=Path);p.add_argument('elf',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
b=a.payload.read_bytes();assert hashlib.sha256(b).hexdigest()=='a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990'
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
for addr,size in [(0,0x40000),(0x20000000,0x40000),(0x202e4000,0x40000),(0x400cc000,0x1000),(0xe0000000,0x100000)]:u.mem_map(addr,size)
u.mem_write(0,b[:0x40000]);regions={};selected=0;cache=[]
def wr(addr,value):u.mem_write(addr,struct.pack('<I',value))
def rd(addr):return struct.unpack('<I',u.mem_read(addr,4))[0]
def mpu_write(u,kind,addr,size,value,unused):
 global selected
 if addr==0xe000ed9c:
  assert value&16;selected=value&15;regions[selected]={'base':value&~31}
 if addr==0xe000eda0:regions[selected]['attributes']=value
 if 0xe000ef50<=addr<=0xe000ef80:cache.append((addr,value))
h=u.hook_add(UC_HOOK_MEM_WRITE,mpu_write,begin=0xe000ed94,end=0xe000ef80)
def call(entry,args=()):
 for r,value in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2],args):u.reg_write(r,value)
 u.reg_write(UC_ARM_REG_SP,0x20035000);u.reg_write(UC_ARM_REG_LR,0x3fff1)
 u.emu_start(entry|1,0x3fff0,count=100000)
 assert u.reg_read(UC_ARM_REG_PC)==0x3fff0
 return u.reg_read(UC_ARM_REG_R0)
call(0xeb34);assert rd(0xe000ed94)==5 and rd(0xe000ed14)&0x30000==0x30000
for row in regions.values():
 row['bytes']=1<<(((row['attributes']>>1)&31)+1)
 row['executable']=not bool(row['attributes']&(1<<28))
 row['full_access']=(row['attributes']>>24)&7==3
matches=[(i,r) for i,r in regions.items() if r['attributes']&1 and r['base']<=0x20308000 and 0x20314000<=r['base']+r['bytes']]
index,region=max(matches);assert index==7 and region['executable'] and region['full_access']
u.hook_del(h)
# Use the actual fallback driver's write-enable and busy-poll routines. Their
# FlexSPI IP transfers are modeled at 0xd638; no outer wrapper is skipped.
wr(0x20009b38+0x28,0xc0f5);wr(0x20009b38+0x24,0xc0f9)
transfers=[];fail_sequence=None

def transfer(u,pc,size,unused):
 assert u.reg_read(UC_ARM_REG_R0)==0x400cc000
 q=u.reg_read(UC_ARM_REG_R1);raw=bytes(u.mem_read(q,16));addr,port,kind,seq,count,data,n=struct.unpack('<IBBBBII',raw)
 assert port==0 and count==1
 transfers.append((addr,kind,seq,data,n))
 failed=seq==fail_sequence
 if not failed and kind==2:
  if seq==0:u.mem_write(data,b'\x5a'*n)
  else:
   assert seq==5 and n==1;u.mem_write(data,b'\0')
 u.reg_write(UC_ARM_REG_R0,int(failed));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
def reset_read(u,kind,addr,size,value,unused):
 # FlexSPI software reset self-clears in this peripheral fixture.
 if addr==0x400cc000:wr(addr,rd(addr)&~1)
u.hook_add(UC_HOOK_CODE,transfer,begin=0xd638,end=0xd638)
u.hook_add(UC_HOOK_MEM_READ,reset_read,begin=0x400cc000,end=0x400cc003)
rows=[]
for address in [0x30384000,0x3039f000]:
 transfers.clear();assert call(0xbfa4,[address])==0
 assert [t[2] for t in transfers]==[4,1,5]
 assert transfers[1][:3]==(address&0x0fffffff,0,1)
 rows.append({'operation':'erase','address':hex(address),'sequence':1})
for address,n in [(0x30384000,256),(0x30385ffc,4),(0x3039fffc,4)]:
 transfers.clear();assert call(0xc034,[0x202e5000,address])==0
 assert [t[2] for t in transfers]==[4,3,5]
 assert transfers[1]==(address&0x0fffffff,3,3,0x202e5000,n)
 rows.append({'operation':'program','address':hex(address),'bytes':n})
for address in [0x30384000,0x3039e000]:
 transfers.clear();assert call(0xc080,[0x202e5000,address,8192])==0
 assert transfers==[(address&0x0fffffff,2,0,0x202e5000,8192)]
 assert bytes(u.mem_read(0x202e5000,8192))==b'\x5a'*8192
 rows.append({'operation':'read','address':hex(address),'bytes':8192})
for entry,args,seq in [(0xbfa4,[0x30384000],1),(0xc034,[0x202e5000,0x30384000],3),(0xc080,[0x202e5000,0x30384000,8192],0),(0xbfa4,[0x30384000],4)]:
 fail_sequence=seq;transfers.clear();assert call(entry,args)==1
 assert transfers[-1][2]==seq
# The saved fallback LUT's erase sequence is opcode20 (4KiB), not opcodeD8.
assert struct.unpack_from('<I',b,0x1fe08+16)[0]==0x08180420
report=dict(status='PASS_NAMLNK10_STOCK_STORAGE_CONTRACT',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),
 stock_sha256=hashlib.sha256(b).hexdigest(),MPU_routine='0xeb34',copied_code_region=index,region=region,
 stock_MPU_allows_code_execution=True,real_stock_wrapper_cases=rows,error_propagation_cases=4,
 fallback_LUT_sector_opcode='0x20',flash_controller_modeled=True,device_access=False,audio_access=False,
 limits=['Exact stock MPU routine executed; actual cache coherency and instruction fetch still need hardware check',
 'FlexSPI IP transfer completion and busy status modeled; physical chip identification, erase/program behavior and endurance not verified'])
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
