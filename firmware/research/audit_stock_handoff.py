#!/usr/bin/env python3
"""Execute saved public reset/SystemInit offline, stopping before C runtime.
Peripheral cells are RAM; this does not execute the missing factory loader.
"""
import argparse,hashlib,json,struct
from pathlib import Path
import capstone as cs
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS
from unicorn.arm_const import UC_CPU_ARM_CORTEX_M7,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_PRIMASK
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payloads',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
known={'a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990','e971240a1e333003804cfd154e5ee053026254bbf09b11499e8b4968d3600752'}
d=cs.Cs(cs.CS_ARCH_ARM,cs.CS_MODE_THUMB|cs.CS_MODE_MCLASS);results=[]
for path in a.payloads:
 b=path.read_bytes();sha=hashlib.sha256(b).hexdigest();assert sha in known
 sp,entry=struct.unpack_from('<II',b);reset=entry&~1
 instructions=list(d.disasm(b[reset:reset+24],reset))
 assert [i.mnemonic for i in instructions]==['cpsid','ldr','ldr','str','ldr','msr','ldr','blx','cpsie','ldr','bx']
 stop=next(i.address for i in instructions if i.mnemonic=='cpsie')
 system_init,runtime=struct.unpack_from('<II',b,reset+32)
 for warm in (False,True):
  for command32 in (False,True):
   u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
   for start,size in [(0,0x100000),(0x20000000,0x40000),(0x40000000,0x1000000),(0xe0000000,0x100000)]:u.mem_map(start,size)
   u.mem_write(0,b[:0x100000]);u.mem_write(0x20000000,bytes([0xa5])*0x40000)
   def wr(addr,v):u.mem_write(addr,struct.pack('<I',v))
   def rd(addr):return struct.unpack('<I',u.mem_read(addr,4))[0]
   wr(0xe000ed14,0x30000 if warm else 0);wr(0xe000ed80,(127<<13)|(3<<3)|1)
   for base in (0x40038000,0x40c10000):wr(base,0x80|(0x2000 if command32 else 0))
   wr(0x40030000,4);wr(0x40034000,4);wr(0xe000e010,7);wr(0xe000ed08,0x20008000)
   wr(0x400e4070,0xffffffff);wr(0x400e4044,0x55aaaa55);wr(0x40cc0000,0x12345678)
   u.reg_write(UC_ARM_REG_SP,0x20030000)
   u.emu_start(entry,stop,count=200000)
   assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==sp
   assert rd(0xe000ed08)==0 and rd(0xe000ed14)==0x30010 and rd(0xe000ed88)==0xf00000
   assert rd(0xe000e010)==6 and rd(0x40030000)&4==0 and rd(0x40034000)&4==0
   assert rd(0x40038000)&0xa0==0x20 and rd(0x40c10000)&0xa0==0x20
   assert rd(0x400e4070)==0xffffdfff and rd(0x400e4044)==0x55aaaa55 and rd(0x40cc0000)==0x12345678
   assert u.reg_read(UC_ARM_REG_PRIMASK)==1
   u.emu_start(stop|1,stop+2,count=1);assert u.reg_read(UC_ARM_REG_PRIMASK)==0
   results.append({'file':path.name,'sha256':sha,'initial_cache_enabled':warm,'rtwdog_command32':command32,'vector_sp':hex(sp),'reset':hex(entry),'system_init':hex(system_init),'c_runtime':hex(runtime),'final_vtor':'0x0','final_ccr':'0x30010','fpu_access':'enabled','systick_enabled':False,'watchdog_register_enable_bits_cleared':True,'usb_cache_gpr_bit_cleared':True,'cpu_root_and_flexram_gpr17_unchanged':True,'interrupts_enabled_before_c_runtime':True})
report={'status':'PASS_SAVED_STOCK_RESET_AUDIT','cases':results,'case_count':len(results),'actual_factory_loader_executed':False,'nux_application_main_executed':False,'scope':'Saved reset and SystemInit only; MMIO is inert VM RAM; watchdog acceptance/cache effects are not electrically emulated.','established_application_contract':['Vectors at payload offset zero; initial MSP 0x20036000 in both public versions','Reset sets VTOR=0 and loads MSP from address zero','SystemInit enables FPU and I/D caches, disables modeled watchdog/SysTick enable bits, clears GPR28 CACHE_USB','SystemInit does not alter modeled CPU clock root or FlexRAM GPR17','Stock enables interrupts before its C runtime; our helper deliberately keeps them masked'],'not_established':['Loader code before app entry','Image copy length/source/destination policy','Loader flash erase bounds or protection','Actual inherited clocks/MPU/cache/FlexRAM/NVIC/DMA state','Reset/PRESET processing in missing loader','Recovery after corrupt app or reset vector'],'device_access':False,'playback':False}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'cases':len(results),'factory_loader_executed':False}))
