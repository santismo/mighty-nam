#!/usr/bin/env python3
"""Execute the complete linked entry in an isolated ARM VM, never a device.

MMIO registers are inert RAM. Tests validate compiled control flow, startup
copies, bounds and register-access policy, not watchdog/cache/DMA hardware.
"""
import argparse,hashlib,json,struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE,UC_HOOK_CODE,UC_PROT_READ,UC_PROT_EXEC
from unicorn.arm_const import *

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('elf',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 with a.elf.open('rb') as f:
  elf=ELFFile(f);symbols={s.name:(s['st_value'],s['st_size']) for s in elf.get_section_by_name('.symtab').iter_symbols()}
  loads=[(s['p_paddr'],s.data()) for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_filesz']]
  entry=elf.header['e_entry']
 def sym(n):return symbols[n][0]
 def put(u,addr,value):u.mem_write(addr,struct.pack('<I',value))
 def get(u,addr):return struct.unpack('<I',u.mem_read(addr,4))[0]
 cases=[];forbidden_calls=[];all_mmio_writes=set()
 blocked_functions=[(v&~1,(v&~1)+n,name) for name,(v,n) in symbols.items() if n and any(x in name for x in ['Rt1176Backend','Prototype','A2Lite','ModelReceiver'])]
 # Function code MUST be retained by the linker; otherwise the integration
 # claim could accidentally be a dead-stripped stub.
 assert all(any(x in n for _,_,n in blocked_functions) for x in ['Rt1176Backend','Prototype','A2Lite','ModelReceiver'])
 assert entry==sym('mpp_diag_reset') and entry&1
 permitted_core={0xe000ed08,0xe000ed88,0xe000e010,0xe000ed04}
 permitted_core|={base+4*i for base in [0xe000e180,0xe000e280] for i in range(8)}
 def setup():
  u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
  for base,size in [(0,0x10000),(0x20000000,0x40000),(0x202c0000,0x1000),(0x40000000,0x1000000),(0xe000e000,0x2000)]:u.mem_map(base,size)
  for base,data in loads:u.mem_write(base,data)
  u.mem_write(0x20000000,b'\xa5'*0x40000);u.mem_write(0x202c0000,b'\x3c'*0x1000)
  for addr,value in [(0xe000ed08,0x20008000),(0xe000e004,6),(0xe000e010,7),
   (0xe000ef90,0x39),(0xe000ef94,0x39),(0x400e4044,0x55aaaa55),(0x40cc0000,0x12345678),
   (0x40030000,4),(0x40034000,4),(0x40038000,0x80),(0x40c10000,0x2080)]:put(u,addr,value)
  u.mem_protect(0,0x10000,UC_PROT_READ|UC_PROT_EXEC)
  # Invalid inherited stack: supported entry must replace it before touching it.
  u.reg_write(UC_ARM_REG_MSP,0xdead0000)
  writes=[]
  def on_write(uc,access,addr,size,value,user):
   writes.append((addr,size,value))
   if addr>=0x40000000:
    assert addr in permitted_core and size==4,('unexpected MMIO write',hex(addr),size)
    all_mmio_writes.add(addr)
   else:
    assert ((sym('__data_start')<=addr and addr+size<=sym('__bss_end')) or
            (sym('__stack_bottom')<=addr and addr+size<=sym('__stack_top'))),('out of owned ranges',hex(addr))
  def on_code(uc,addr,size,user):
   for lo,hi,name in blocked_functions:
    if lo<=addr<hi:
     forbidden_calls.append(name);raise AssertionError(('driver called from diagnostic entry',name))
  u.hook_add(UC_HOOK_MEM_WRITE,on_write);u.hook_add(UC_HOOK_CODE,on_code)
  return u,writes
 def run(u,target='mpp_diag_idle'):
  u.emu_start(entry,sym(target)&~1,count=400000)
  assert u.reg_read(UC_ARM_REG_PC)==sym(target)&~1,('instruction budget',hex(u.reg_read(UC_ARM_REG_PC)))
 def check_ready(u,banks=7):
  status=struct.unpack('<20I',u.mem_read(sym('mpp_diag_status'),80))
  assert status[:8]==(0x4d504447,1,2,0xff,0x4d505044,84164,16404,640),status
  assert status[8:16]==(0,0,0,0x39,0x39,0x55aaaa55,0x12345678,banks)
  assert status[16:]==(4,4,0x80,0x2080)
  assert u.reg_read(UC_ARM_REG_PRIMASK)==1
  assert get(u,0xe000ed08)==0 and get(u,0xe000e010)==0
  assert get(u,0xe000ed88)&0xf00000==0xf00000
  assert u.reg_read(UC_ARM_REG_MSP)==sym('__stack_top')
  for n in ['mpp_diag_app','mpp_diag_receiver']:
   assert not any(u.mem_read(sym(n),symbols[n][1])),n
  assert bytes(u.mem_read(0x202c0000,0x1000))==b'\x3c'*0x1000
  gap=sym('__stack_bottom')-sym('__bss_end')
  assert bytes(u.mem_read(sym('__bss_end'),gap))==b'\xa5'*gap
  assert get(u,sym('__stack_bottom'))==0x5354414b
  assert bytes(u.mem_read(sym('__stack_top'),0x400))==b'\xa5'*0x400
  for addr,val in [(0x400e4044,0x55aaaa55),(0x40cc0000,0x12345678),(0x40030000,4),(0x40034000,4),(0x40038000,0x80),(0x40c10000,0x2080)]:assert get(u,addr)==val
 u,writes=setup();run(u);check_ready(u);cases.append('cold entry with poisoned RAM and invalid inherited MSP')
 assert struct.unpack('<256I',u.mem_read(0,1024))==(sym('__stack_top'),entry)+tuple([sym('mpp_diag_fault')]*254)
 cases.append('complete vector table and linked entry address')
 stack=bytes(u.mem_read(sym('__stack_bottom')+4,0x6000-4))
 used=len(stack)-next(i for i,v in enumerate(stack) if v!=0xa5)
 # Warm software re-entry with cache/MPU still off, without reloading code/data.
 for n in ['mpp_diag_app','mpp_diag_receiver','mpp_diag_status']:
  u.mem_write(sym(n),b'\xe7'*symbols[n][1])
 put(u,sym('mpp_diag_data_cookie'),0)
 # The helper enabled CPACR but did not enable caches or change the clock.
 run(u);check_ready(u);cases.append('supported warm re-entry restores data/BSS and empties volatile models')
 for name,reg,value,reason in [
  ('I-cache enabled',0xe000ed14,0x20000,3),('D-cache enabled',0xe000ed14,0x10000,3),
  ('both caches enabled',0xe000ed14,0x30000,3),('MPU enabled',0xe000ed94,1,4)]:
  v,w=setup();put(v,reg,value);run(v,'mpp_diag_rejected')
  assert v.reg_read(UC_ARM_REG_R0)==reason and not w,(name,w)
  cases.append(name+' rejected before RAM or MMIO writes')
 for name,register,value,reason in [
  ('Handler mode',UC_ARM_REG_IPSR,3,1),('unprivileged Thread mode',UC_ARM_REG_CONTROL,1,2),
  ('PSP Thread mode',UC_ARM_REG_CONTROL,2,2),('FAULTMASK set',UC_ARM_REG_FAULTMASK,1,5)]:
  v,w=setup();v.reg_write(register,value);run(v,'mpp_diag_rejected')
  assert v.reg_read(UC_ARM_REG_R0)==reason and not w,(name,w)
  cases.append(name+' rejected before RAM or MMIO writes')
 for banks in [1,8]:
  v,w=setup();put(v,0xe000e004,banks-1);run(v);check_ready(v,banks)
  nvic=[x for x in w if 0xe000e180<=x[0]<0xe000e1a0 or 0xe000e280<=x[0]<0xe000e2a0]
  assert len(nvic)==2*banks and all(x[2]==0xffffffff for x in nvic)
  cases.append(str(banks)+' NVIC banks cleared without unmasking interrupts')
 v,w=setup();put(v,0xe000e004,8);run(v)
 assert get(v,sym('mpp_diag_status')+8)==3
 assert not any(x[0] in permitted_core-{0xe000ed08} for x in w)
 cases.append('unsupported NVIC bank count prevents core helper writes')
 # Direct branch to the fault handler, not emulation of exception entry/stacking.
 v,w=setup();v.reg_write(UC_ARM_REG_IPSR,3)
 v.emu_start(sym('mpp_diag_fault'),sym('mpp_diag_fault_park'),count=100)
 assert v.reg_read(UC_ARM_REG_PC)==sym('mpp_diag_fault_park') and not w
 assert v.reg_read(UC_ARM_REG_R0)==3 and v.reg_read(UC_ARM_REG_PRIMASK)==1
 cases.append('fault handler parks without C calls or stack/data writes')
 report={'status':'PASS_OFFLINE_LINKED_ENTRY','cases':cases,'case_count':len(cases),
  'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),'entry_stack_high_water_bytes_observed':used,
  'stack_reserved_bytes':0x6000,'dma_reservation_untouched':True,
  'clock_watchdogs_flexram_preserved':True,'audio_model_and_receiver_calls_from_entry':forbidden_calls,
  'mmio_write_addresses':sorted(hex(x) for x in all_mmio_writes),
  'peripheral_registers_inert_VM_RAM':True,'fault_exception_stacking_emulated':False,
  'physical_memory_ownership_verified':False,'hardware_timing_measured':False,
  'device_access':False,'playback':False}
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
