#!/usr/bin/env python3
"""Run early watchdog assembly and clock inspection in a semantic ARM VM.
No hardware APIs. Watchdog deadlines use register handshakes and read counts,
not actual bus clocks, elapsed watchdog time, or electrical reset behavior.
"""
import argparse,hashlib,json,struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 with a.elf.open('rb') as f:
  e=ELFFile(f);symbols={s.name:(s['st_value'],s['st_size']) for s in e.get_section_by_name('.symtab').iter_symbols()}
  loads=[(s['p_paddr'],s.data()) for s in e.iter_segments() if s['p_type']=='PT_LOAD' and s['p_filesz']]
  entry=e.header['e_entry']
 def sym(n):return symbols[n][0]
 def put(u,addr,value):u.mem_write(addr,struct.pack('<I',value&0xffffffff))
 def get(u,addr):return struct.unpack('<I',u.mem_read(addr,4))[0]
 cases=[];pair_gaps=[]
 blocked_pc=set()
 for name,(value,size) in symbols.items():
  if size and any(k in name for k in ['Rt1176Backend','Prototype','A2Lite','ModelReceiver']):
   blocked_pc.update(range(value&~1,(value&~1)+size,2))
 class VM:
  def __init__(self,cs3=0x64a0,cs4=0x64a0,wcr1=0x30,wcr2=0x30,fault=None,unlock_after=2,commit_after=3):
   self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);self.u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
   self.n=0;self.writes=[];self.mmio=[];self.fault=fault;self.torn=0;self.clock_reads=0
   self.rt={base:dict(cs=cs,initial=cs,key=0,key_instruction=0,phase='locked',reads=0,next_cs=0)
    for base,cs in [(0x40038000,cs3),(0x40c10000,cs4)]}
   self.legacy={0x40030000:wcr1,0x40034000:wcr2,0x40030008:1,0x40034008:1}
   self.unlock_after=unlock_after;self.commit_after=commit_after
   u=self.u
   for base,size in [(0,0x10000),(0x20000000,0x40000),(0x202c0000,0x1000),(0x40000000,0x1000000),(0xe000e000,0x2000)]:u.mem_map(base,size)
   for addr,data in loads:u.mem_write(addr,data)
   u.mem_write(0x20000000,b'\xa5'*0x40000);u.mem_write(0x202c0000,b'\x3c'*0x1000)
   for addr,value in [(0xe000ed08,0x20008000),(0xe000e004,6),(0xe000e010,7),
    (0xe000ef90,0x39),(0xe000ef94,0x49),(0x400e4044,0x55aaaa55),
    (0x40cc0000,0x400),(0x40cc0020,0x400),(0x40cc0024,0),(0x40c84200,0x20006068)]:put(u,addr,value)
   u.mem_protect(0,0x10000,UC_PROT_READ|UC_PROT_EXEC);u.reg_write(UC_ARM_REG_MSP,0xdead0000)
   # Restrict semantic read callbacks to device registers. Hooking unrelated
   # stack reads disturbs Thumb IT execution in this Unicorn runtime.
   u.hook_add(UC_HOOK_MEM_READ,self.read,begin=0x40000000,end=0x40ffffff)
   u.hook_add(UC_HOOK_MEM_WRITE,self.write);u.hook_add(UC_HOOK_CODE,self.code)
  def code(self,u,addr,size,unused):
   self.n+=1
   assert addr not in blocked_pc,('audio/model function unexpectedly executed',hex(addr))
  def read(self,u,access,addr,size,value,unused):
   if addr in self.legacy:
    assert size==2,(hex(addr),size);u.mem_write(addr,struct.pack('<H',self.legacy[addr]));return
   if addr in self.rt:
    assert size==4;s=self.rt[addr]
    if s['phase']=='unlocking':
     s['reads']+=1
     if self.fault!=(addr,'unlock') and s['reads']>=self.unlock_after:s['cs']|=0x800;s['phase']='unlocked'
    elif s['phase']=='committing':
     s['reads']+=1
     if self.fault!=(addr,'commit') and s['reads']>=self.commit_after:
      s['cs']=s['next_cs']|0x400|(s['initial']&0x4000);s['phase']='locked'
      if self.fault==(addr,'mismatch'):s['cs']|=0x80
    put(u,addr,s['cs']);return
   if addr in [0x40cc0000,0x40cc0020,0x40cc0024,0x40c84200]:
    self.clock_reads+=1
    if self.clock_reads==self.torn:put(u,addr,get(u,addr)^1)
  def write(self,u,access,addr,size,value,unused):
   self.writes.append((addr,size,value))
   if addr<0x40000000:
    assert ((sym('__data_start')<=addr and addr+size<=sym('__bss_end')) or
      (sym('__stack_bottom')<=addr and addr+size<=sym('__stack_top'))),('memory boundary',hex(addr))
    return
   self.mmio.append((addr,size,value))
   if addr>=0xe000e000:
    allowed={0xe000ed08,0xe000ed88,0xe000e010,0xe000ed04}
    allowed|={b+4*i for b in [0xe000e180,0xe000e280] for i in range(8)}
    assert addr in allowed and size==4,('core write',hex(addr));return
   if addr in [0x40030008,0x40034008]:
    assert size==2 and value==0
    if self.fault!=(addr,'pde'):self.legacy[addr]=0
    return
   for base,s in self.rt.items():
    if addr==base+4:
     assert size==4 and s['cs']&0x20 and s['cs']&0x80
     if s['cs']&0x2000:assert value==0xd928c520 and s['key']==0;s['key']=2
     elif s['key']==0:assert value==0xc520;s['key']=1;s['key_instruction']=self.n;return
     else:
      assert s['key']==1 and value==0xd928
      pair_gaps.append(self.n-s['key_instruction']);assert self.n-s['key_instruction']==1
      s['key']=2
     s['cs']&=~0x400;s['phase']='unlocking';s['reads']=0;return
    if addr==base:
     assert size==4 and s['phase']=='unlocked'
     # Only EN may change among configuration fields; status/W1C are zero.
     assert value==s['initial']&0xb37f,(hex(value),hex(s['initial']))
     s['next_cs']=value;s['phase']='committing';s['reads']=0;return
   raise AssertionError(('unexpected peripheral write',hex(addr),size,hex(value)))
  def run(self,target='mpp_diag_idle'):
   self.u.emu_start(entry,sym(target)&~1,count=300000)
   assert self.u.reg_read(UC_ARM_REG_PC)==sym(target)&~1,('unexpected stop',hex(self.u.reg_read(UC_ARM_REG_PC)))
  def peripherals(self):return [x for x in self.mmio if x[0]<0xe0000000]
  def ready(self):
   u=self.u;status=struct.unpack('<20I',u.mem_read(sym('mpp_diag_status'),80))
   assert status[:5]==(0x4d504447,2,2,0xff,0x4d505044),status
   assert get(u,sym('mpp_diag_clock'))==6 # unknown reference; never assume 600MHz
   assert get(u,sym('mpp_diag_clock')+24)==0
   assert u.reg_read(UC_ARM_REG_PRIMASK)==1 and u.reg_read(UC_ARM_REG_MSP)==sym('__stack_top')
   assert all(not s['cs']&0x880 and s['cs']&0x400 for s in self.rt.values())
   assert self.legacy[0x40030008]==self.legacy[0x40034008]==0
   for n in ['mpp_diag_app','mpp_diag_receiver']:assert not any(u.mem_read(sym(n),symbols[n][1]))
   assert bytes(u.mem_read(0x202c0000,0x1000))==b'\x3c'*0x1000
   gap=sym('__stack_bottom')-sym('__bss_end');assert bytes(u.mem_read(sym('__bss_end'),gap))==b'\xa5'*gap
   assert get(u,0x400e4044)==0x55aaaa55 and get(u,0x40cc0000)==0x400
  def failed(self,code,no_peripheral=False):
   self.run('mpp_diag_watchdog_failed');assert self.u.reg_read(UC_ARM_REG_R0)==code
   assert bytes(self.u.mem_read(sym('__bss_start'),sym('__bss_end')-sym('__bss_start')))==b'\xa5'*(sym('__bss_end')-sym('__bss_start'))
   if no_peripheral:assert not self.peripherals()
  def clock(self,reference=24000000):
   u=self.u;stop=sym('mpp_diag_idle')&~1;before=len(self.mmio)
   u.reg_write(UC_ARM_REG_R0,reference);u.reg_write(UC_ARM_REG_LR,stop|1)
   u.emu_start(sym('mpp_diag_read_clock'),stop,count=5000)
   assert u.reg_read(UC_ARM_REG_PC)==stop and len(self.mmio)==before
   result=struct.unpack('<7I',u.mem_read(sym('mpp_diag_clock'),28))
   if result[0]!=0:assert result[6]==0
   return result
 for c3,c4 in [(0x64a0,0x64a0),(0x44a0,0x44a0),(0x44a0,0x64a0),(0x64a0,0x44a0),(0xf7e7,0xd7e7)]:
  v=VM(cs3=c3,cs4=c4);v.run();v.ready();cases.append('command modes '+hex(c3)+'/'+hex(c4)+' and W1C flag preservation')
  assert all(s['cs']&0x4000 for s in v.rt.values())
 v=VM();v.run();v.ready();before=len(v.peripherals())
 for n in ['mpp_diag_app','mpp_diag_receiver']:v.u.mem_write(sym(n),b'\x77'*symbols[n][1])
 v.run();v.ready();assert len(v.peripherals())==before;cases.append('warm entry clears volatile models without rewriting disabled watchdogs')
 v=VM(cs3=0x400,cs4=0x2400);v.run();v.ready();assert len(v.peripherals())==2;cases.append('disabled watchdogs accepted with UPDATE locked')
 for kwargs,code,label in [({'wcr1':0x34},2,'WDOG1 enabled'),({'wcr2':0x34},3,'WDOG2 enabled'),
  ({'cs3':0x2480},4,'WDOG3 UPDATE locked'),({'cs4':0x2480},5,'WDOG4 UPDATE locked'),
  ({'cs3':0x20a0},6,'WDOG3 reconfiguration pending'),({'cs4':0x2ca0},6,'WDOG4 already unlocked'),
  ({'cs3':0},6,'disabled but unsettled WDOG3'),({'cs4':0x2800},6,'disabled but unlocked WDOG4')]:
  v=VM(**kwargs);v.failed(code,True);cases.append(label+' rejected without peripheral writes')
 for base,error in [(0x40038000,7),(0x40c10000,10)]:
  for mode,delta in [('unlock',0),('commit',1),('mismatch',2)]:
   v=VM(fault=(base,mode));v.failed(error+delta);cases.append(hex(base)+' '+mode+' fails before runtime initialization')
 for addr,code in [(0x40030008,13),(0x40034008,14)]:
  v=VM(fault=(addr,'pde'));v.failed(code);cases.append(hex(addr)+' power-down counter write rejected')
 v=VM(unlock_after=2048,commit_after=2048);v.run();v.ready();cases.append('handshakes succeed at final permitted reads')
 v=VM(unlock_after=2049);v.failed(7);cases.append('unlock past polling bound fails')
 v=VM(commit_after=2049);v.failed(8);cases.append('commit past polling bound fails')
 for reg,value,label in [(0xe000ed14,0x10000,'cache enabled'),(0xe000ed94,1,'MPU enabled')]:
  v=VM();put(v.u,reg,value);v.run('mpp_diag_rejected');assert not v.peripherals();cases.append(label+' prevented watchdog writes')
 # The prior synthetic DTCM value 0x39 declares only 64KiB, too small for
 # MSP 0x20036000. The new stackless guard rejects it before ANY memory write.
 for address,code,minimum,label in [(0xe000ef90,7,6,'ITCM'),(0xe000ef94,9,9,'DTCM')]:
  for size in range(16):
   v=VM();put(v.u,address,(size<<3)|1)
   if minimum<=size<=10:v.run();v.ready()
   else:
    v.run('mpp_diag_rejected');assert v.u.reg_read(UC_ARM_REG_R0)==code and not v.writes
    assert v.u.reg_read(UC_ARM_REG_MSP)==0xdead0000
   cases.append(label+' encoded size '+str(size)+' checked before stack use')
  v=VM();put(v.u,address,0x48);v.run('mpp_diag_rejected')
  assert v.u.reg_read(UC_ARM_REG_R0)==code-1 and not v.writes
  cases.append(label+' disabled rejected without memory writes')
 # Direct routine guard with a valid return sentinel; no stack or MMIO writes.
 for register,value in [(UC_ARM_REG_PRIMASK,0),(UC_ARM_REG_CONTROL,2),(UC_ARM_REG_IPSR,3),(UC_ARM_REG_FAULTMASK,1)]:
  v=VM();u=v.u;u.reg_write(UC_ARM_REG_PRIMASK,1);u.reg_write(register,value)
  u.reg_write(UC_ARM_REG_LR,sym('mpp_diag_idle')|1);u.emu_start(sym('mpp_startup_watchdogs'),sym('mpp_diag_idle'),count=100)
  assert u.reg_read(UC_ARM_REG_R0)==1 and not v.writes;cases.append('watchdog guard register '+str(register))
 v=VM();v.run();v.ready();r=v.clock();assert r[0]==0 and r[6]==624000000;cases.append('ARM clock decoder derives 624MHz from fixture')
 put(v.u,0x40c84200,0x2000e0c8);r=v.clock();assert r[0]==0 and r[6]==600000000;cases.append('ARM clock decoder derives 600MHz from fixture')
 put(v.u,0x40cc0000,0x401);put(v.u,0x40cc0020,0x401);r=v.clock();assert r[0]==0 and r[6]==300000000;cases.append('ARM root divider honored')
 assert v.clock(0)[0]==6 and v.clock(0xffffffff)[0]==7;cases.append('unknown/invalid reference never produces a frequency')
 v.torn=v.clock_reads+5;assert v.clock()[0]==2;cases.append('torn ARM clock snapshot rejected')
 v=VM();v.run();put(v.u,0x40cc0020,0x10000400);assert v.clock()[0]==2;cases.append('changing ARM clock root rejected')
 put(v.u,0x40cc0020,0x400);put(v.u,0x40c84200,0x60006068);assert v.clock()[0]==5;cases.append('gated ARM PLL rejected')
 report={'status':'PASS_STARTUP_CONTROL_ARM_VM','case_count':len(cases),'cases':cases,
  'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),
  'two_word_unlock_instruction_gaps':sorted(set(pair_gaps)),
  'model':'Semantic watchdog status/W1C/write-lock model; other registers are inert RAM',
  'clock_checks':'Executed linked Cortex-M7 decoder; numerical fixtures only',
  'physical_bus_deadlines_or_watchdog_expiry_emulated':False,'loader_handoff_validated':False,
  'audio_started':False,'device_access':False,'playback':False}
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
