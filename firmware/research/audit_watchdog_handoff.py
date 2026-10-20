#!/usr/bin/env python3
"""Audit saved stock startup with WDOG1/2 WDE write-once behavior modeled.
Files and VM only. No full watchdog expiry, external reset, USB or audio model.
"""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_CPU_ARM_CORTEX_M7,UC_ARM_REG_SP,UC_ARM_REG_PC
import capstone as cs

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('payloads',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 known={'a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990','e971240a1e333003804cfd154e5ee053026254bbf09b11499e8b4968d3600752'}
 d=cs.Cs(cs.CS_ARCH_ARM,cs.CS_MODE_THUMB|cs.CS_MODE_MCLASS);cases=[]
 for path in a.payloads:
  payload=path.read_bytes();sha=hashlib.sha256(payload).hexdigest();assert sha in known
  stack,entry=struct.unpack_from('<II',payload)
  ins=list(d.disasm(payload[entry&~1:(entry&~1)+24],entry&~1))
  stop=next(i.address for i in ins if i.mnemonic=='cpsie')
  for enabled in [False,True]:
   u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
   for addr,size in [(0,0x100000),(0x20000000,0x40000),(0x40000000,0x1000000),(0xe0000000,0x100000)]:u.mem_map(addr,size)
   u.mem_write(0,payload[:0x100000]);u.reg_write(UC_ARM_REG_SP,0x20030000)
   for addr,value in [(0xe000ed80,(127<<13)|(3<<3)|1),(0x40038000,0x24a0),(0x40c10000,0x24a0),(0xe000e010,7)]:u.mem_write(addr,struct.pack('<I',value))
   state={0x40030000:0x30|(4 if enabled else 0),0x40034000:0x30|(4 if enabled else 0)};writes=[]
   def read(uc,access,addr,size,value,user):
    if addr in state:
     assert size==2;uc.mem_write(addr,struct.pack('<H',state[addr]))
   def write(uc,access,addr,size,value,user):
    if addr in state:
     assert size==2;old=state[addr];state[addr]=(value&0xffff)|(old&4)
     writes.append({'address':hex(addr),'attempted':hex(value),'modeled_after':hex(state[addr])})
   u.hook_add(UC_HOOK_MEM_READ,read,begin=0x40030000,end=0x40034003)
   u.hook_add(UC_HOOK_MEM_WRITE,write,begin=0x40030000,end=0x40034003)
   u.emu_start(entry,stop,count=200000)
   assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==stack
   assert all(bool(x&4)==enabled for x in state.values())
   if enabled:assert len(writes)==2 and all(int(x['attempted'],16)&4==0 for x in writes)
   else:assert not writes
   cases.append({'payload':path.name,'sha256':sha,'initial_legacy_watchdogs_enabled':enabled,
    'reached_end_of_system_init':True,'legacy_watchdogs_still_enabled':enabled,'writes':writes})
 report={'status':'PASS_STOCK_WATCHDOG_HANDOFF_AUDIT','cases':cases,
  'finding':'Both public SystemInit routines continue after attempting to clear WDE when it is already set. A write-once model correctly leaves WDE set. Therefore the earlier inert-register audit does not prove watchdog shutdown; inherited loader state or an ongoing service policy is required.',
  'chip_rule':'i.MX RT1170 RM Rev.5 sections 78.6.1.2 and 78.3.2.1',
  'factory_loader_executed':False,'watchdog_expiration_or_actual_reset_emulated':False,
  'device_access':False,'playback':False}
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
