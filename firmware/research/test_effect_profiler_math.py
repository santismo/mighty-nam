#!/usr/bin/env python3
"""Execute NAMLNK11 DWT math, command and snapshot bounds with synthetic counters."""
import argparse,hashlib,json,random,struct
from pathlib import Path
from link_image import elf_identity
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
with a.elf.open('rb') as f:
 e=ELFFile(f);sections=[(s['sh_addr'],s.data()) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_type']!='SHT_NOBITS'];sym={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
S=sym['mpp_profile_stats']+3*32;SEQ=sym['mpp_profile_sequence'];DWT=0xe0001000;SP=0x20035000;STOP=0x3fff0;STUB=0x3ffe0
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
for start,size in [(0,0x40000),(0x20000000,0x40000),(0x202e4000,0x40000),(DWT,0x1000)]:u.mem_map(start,size)
for start,data in sections:u.mem_write(start,data)
u.mem_write(STUB,bytes.fromhex('7047'))
def put(at,value):u.mem_write(at,struct.pack('<I',value&0xffffffff))
def get(at):return struct.unpack('<I',u.mem_read(at,4))[0]
put(0x20005ad0,0x20030000);u.mem_write(0x20030003,b'\x41')
def call(entry,args=()):
 for r,x in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(r,x)
 u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(entry|1,STOP,count=100000)
 assert u.reg_read(UC_ARM_REG_PC)==STOP and u.reg_read(UC_ARM_REG_SP)==SP
 return u.reg_read(UC_ARM_REG_R0)
rows=[]
def trial(label,start=100,end=1000,ctrl=1,after=1,reset=False,initial=None,flags=0):
 call(sym['mpp_profile_control'],[126]);put(SEQ,0)
 if initial:u.mem_write(S,struct.pack('<8I',*initial))
 put(DWT,ctrl);put(sym['mpp_dwt_reset_epoch'],0);reads=[];writes=[]
 def read(uc,access,addr,size,value,unused):
  put(DWT+4,[start,end][len(reads)]);reads.append(addr)
 def callback(uc,pc,size,unused):
  put(DWT,after)
  if reset:put(sym['mpp_dwt_reset_epoch'],1)
 def write(uc,access,addr,size,value,unused):writes.append((addr,value))
 hs=[u.hook_add(UC_HOOK_MEM_READ,read,begin=DWT+4,end=DWT+7),u.hook_add(UC_HOOK_CODE,callback,begin=STUB,end=STUB),u.hook_add(UC_HOOK_MEM_WRITE,write,begin=DWT,end=DWT+0xfff)]
 saved={r:0x20010000+i*16 for i,r in enumerate(range(UC_ARM_REG_R4,UC_ARM_REG_R11+1))}
 for r,x in saved.items():u.reg_write(r,x)
 u.mem_write(SP,struct.pack('<2I',0x20031000,0x20031100))
 try:call(sym['mpp_profile_dispatch'],[3,STUB|1,0x20031200,0x20031300])
 finally:
  for h in hs:u.hook_del(h)
 assert not writes and len(reads)==2
 assert all(u.reg_read(r)==x for r,x in saved.items())
 r=list(struct.unpack('<8I',u.mem_read(S,32)));old=initial or [0]*8
 assert r[0]==min(old[0]+1,0xffffffff) and r[7]==old[7]|flags,(label,r)
 assert r[5]==min(old[5]+1,0xffffffff) and r[6]==old[6]
 if flags:assert r[1]==old[1] and r[2]==min(old[2]+1,0xffffffff) and r[3:5]==old[3:5]
 else:assert r[1]==old[1]+1 and r[2]==old[2] and r[3:5]==[(end-start)&0xffffffff,max(old[4],(end-start)&0xffffffff)]
 assert get(SEQ)==2
 rows.append(label)
trial('ordinary');trial('wrap',0xfffffff0,400);trial('disabled',ctrl=0,after=0,flags=1)
trial('CTRL changed',after=3,flags=1);trial('reset epoch',reset=True,flags=2)
trial('stalled',end=100,flags=4);trial('half-range ambiguity',end=0x80000064,flags=4)
trial('count saturated',initial=[0xffffffff,7,5,500,9000,0xffffffff,0,0],flags=8)
trial('lower max',initial=[2,2,0,123,9000,0,0,0]);trial('same max',initial=[2,2,0,900,900,0,0,0])
rng=random.Random(11)
for i in range(128):
 start=rng.randrange(2**32);trial('random wrap '+str(i),start,(start+rng.randrange(1,1000000))&0xffffffff)
output=0x20032000
assert call(sym['mpp_profile_page'],[27,output])==3
assert call(sym['mpp_profile_page'],[26,output])==0 and get(output)==0x46585031
frozen=[]
for page in range(27,117):assert call(sym['mpp_profile_page'],[page,output])==0;frozen.append(get(output))
put(S,456)
for page,value in enumerate(frozen,27):assert call(sym['mpp_profile_page'],[page,output])==0 and get(output)==value
for page in [0,25,117,127,0xffffffff]:assert call(sym['mpp_profile_page'],[page,output])==1
for interruptions in [1,3]:
 n=[0]
 def preempt(uc,access,addr,size,value,unused):
  if n[0]<interruptions:n[0]+=1;put(SEQ,get(SEQ)+2)
 h=u.hook_add(UC_HOOK_MEM_READ,preempt,begin=sym['mpp_profile_stats'],end=sym['mpp_profile_stats']+3)
 u.ctl_remove_cache(sym['mpp_profile_page']&~1,(sym['mpp_profile_page']&~1)+512)
 result=call(sym['mpp_profile_page'],[26,output]);u.hook_del(h)
 assert result==(0 if interruptions==1 else 2) and n[0]==interruptions,(interruptions,result,n,get(SEQ))
 if result:assert call(sym['mpp_profile_page'],[27,output])==3
report=dict(status='PASS_'+elf_identity(a.elf)+'_PROFILER_COUNTER_ABI',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),counter_cases=len(rows),callees_and_stack_preserved=True,no_counter_writes=True,wrap_reset_disabled_saturation_checked=True,snapshot_preemption_retry_and_busy_checked=True,device_access=False,audio_access=False)
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report)
