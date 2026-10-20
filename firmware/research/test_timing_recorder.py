#!/usr/bin/env python3
"""Build and compare host / ARM timing logic using synthetic stamps only."""
import argparse,ctypes as C,hashlib,json,random,struct,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
import ziglang
ap=argparse.ArgumentParser();ap.add_argument('build_dir');ap.add_argument('--output',required=True);a=ap.parse_args()
r=Path(__file__).resolve().parents[1];b=Path(a.build_dir).resolve();b.mkdir(parents=True,exist_ok=True)
src=r/'target/telemetry/timing_recorder.c';inc=src.parent
libpath=b/'libtiming.dylib';obj=b/'timing.o';elf=b/'timing-offline-only.elf'
subprocess.run(['clang','-O2','-std=c11','-Wall','-Wextra','-Werror','-dynamiclib',str(src),'-o',str(libpath)],check=True)
subprocess.run(['clang','--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-O2','-ffreestanding','-fno-builtin','-std=c11','-Wall','-Wextra','-Werror','-c',str(src),'-o',str(obj)],check=True)
link=b/'timing.ld';link.write_text('ENTRY(mpp_timing_observe)\nSECTIONS { . = 0x10000; .text : { *(.text*) *(.rodata*) } .ARM.exidx : { *(.ARM.exidx*) } /DISCARD/ : { *(.comment*) } }\n')
z=Path(ziglang.__path__[0])/'zig'
subprocess.run([str(z),'cc','-target','thumb-freestanding-eabi','-mcpu=cortex_m7','-nostdlib','-Wl,-e,mpp_timing_observe','-Wl,-T,'+str(link),str(obj),'-o',str(elf)],check=True)
class Config(C.Structure):_fields_=[(x,C.c_uint32) for x in ['cpu','ref','deadline','reserve','maxspan','tolerance']]
class Stamp(C.Structure):_fields_=[(x,C.c_uint32) for x in ['cycle','ref','reset','clock','seq','release','flags']]
class Stats(C.Structure):_fields_=[(x,C.c_uint32) for x in ['samples','valid','rejected','flags','initialized','lastseq','lastreset','lastclock','maxcycles','maxduration','maxresponse','maxlate','deadlines','headrooms']]
lib=C.CDLL(str(libpath));f=lib.mpp_timing_observe;f.argtypes=[C.POINTER(t) for t in [Stats,Config,Stamp,Stamp]];f.restype=C.c_uint32
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7);u.mem_map(0x10000,0x10000);u.mem_map(0x20000000,0x10000)
with elf.open('rb') as stream:
 e=ELFFile(stream);sym={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
 imports=[s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'];assert not imports
 regions=[]
 for s in e.iter_sections():
  if s['sh_flags']&2:
   assert s['sh_type']!='SHT_NOBITS';u.mem_write(s['sh_addr'],s.data());regions.append({'name':s.name,'bytes':s['sh_size']})
STOP=0x1fffc

def call(name,args):
 for reg,val in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(reg,val)
 u.reg_write(UC_ARM_REG_SP,0x2000ff00);u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(sym[name]|1,STOP,count=10000);assert u.reg_read(UC_ARM_REG_PC)==STOP
 return u.reg_read(UC_ARM_REG_R0)

cfg=Config(600000000,24000000,4000,800,20000,50) # synthetic 8/48k, 20% reserve
checks=[]
def check(name,start,end,expect,cfg=cfg,stats=None):
 s=stats or Stats();before=bytes(s)
 addrs=[0x20000000,0x20000100,0x20000200,0x20000300]
 for addr,value in zip(addrs,[before,bytes(cfg),bytes(start),bytes(end)]):u.mem_write(addr,value)
 host=f(C.byref(s),C.byref(cfg),C.byref(start),C.byref(end));arm=call('mpp_timing_observe',addrs)
 assert host==arm==expect,(name,host,arm,expect)
 assert bytes(s)==bytes(u.mem_read(addrs[0],C.sizeof(s))),name
 checks.append(name);return s

def stamps(ticks=1000,late=0,seq=10,base=100000,cycles=1000000):
 return (Stamp(cycles,base+late,0,0,seq,base,1),Stamp((cycles+25*ticks)&0xffffffff,(base+late+ticks)&0xffffffff,0,0,seq,base,1))
a0,b0=stamps();s=check('nominal full-block interval',a0,b0,0);assert s.valid==1 and s.maxcycles==25000
for name,ticks,late,expected in [('deadline exact',4000,0,384),('deadline exceeded',4001,0,384),('headroom exact',3200,0,256),('headroom below',3199,0,0),('late IRQ completion misses deadline',2000,2100,384)]:
 x,y=stamps(ticks,late);check(name,x,y,expected)
x,y=stamps(base=0xfffffe00,cycles=0xfffff000);check('reference and cycle wrap',x,y,0)
x,y=stamps();y.reset=1;check('observed DWT reset epoch',x,y,4)
x,y=stamps();y.clock=1;check('clock change within interval',x,y,8)
x,y=stamps();x.flags=0;check('unverified clock backend',x,y,2)
x,y=stamps();y.cycle=100;check('untracked counter reset rejected by reference ratio',x,y,64)
x,y=stamps();y.cycle=x.cycle;check('stalled cycle counter',x,y,96)
x,y=stamps();y.ref=x.ref;check('stalled reference counter',x,y,96)
x,y=stamps();y.seq+=1;check('sequence changes during callback',x,y,16)
x,y=stamps();y.release+=1;check('inconsistent release timestamp',x,y,16)
x,y=stamps(seq=12);check('missing hardware block',x,y,16,stats=s)
x,y=stamps(seq=13);s=check('subsequent good sample cannot erase failure',x,y,0,stats=s);assert s.flags&16
x,y=stamps();x.clock=y.clock=1;z=Stats();z.initialized=1;z.lastseq=9;check('clock changes between intervals',x,y,8,stats=z)
x,y=stamps();bad=Config(600000000,24000000,4000,4000,20000,50);check('invalid reserve configuration',x,y,1,cfg=bad)
x,y=stamps();z=Stats();z.samples=0xffffffff;check('sample count saturation',x,y,512,stats=z)
x,y=stamps();x.release=x.ref+1;y.release=x.release;check('future release rejected',x,y,32)
x,y=stamps(ticks=20001);check('ambiguous or out-of-range span',x,y,32)
x,y=stamps(seq=0);z=Stats();z.initialized=1;z.lastseq=0xffffffff;check('hardware sequence wrap',x,y,0,stats=z)
# Independent arithmetic oracle, a continuous stream that includes both wraps.
rng=random.Random(137);s=Stats();base=0xffff0000;cycle=0xffff0000
for n in range(2000):
 ticks=rng.randrange(1,5000);late=rng.randrange(0,1500)
 x,y=stamps(ticks,late,n,base,cycle);x.ref&=0xffffffff;y.ref&=0xffffffff
 response=ticks+late;expected=(128 if response>=4000 else 0)|(256 if response>=3200 else 0)
 s=check('random '+str(n),x,y,expected,stats=s)
 base=(base+8000)&0xffffffff;cycle=(cycle+200000)&0xffffffff
assert s.valid==2000 and s.rejected==0
# Every TX slot is cleared after a synthetic nonzero DSP output; guards survive.
buf=(C.c_uint32*34)(*[0xa5a5a5a5]*34)
lib.mpp_timing_zero_tx32(C.cast(C.byref(buf,4),C.POINTER(C.c_uint32)))
assert list(buf)==[0xa5a5a5a5]+[0]*32+[0xa5a5a5a5]
u.mem_write(0x20001000,b'\xa5'*136);call('mpp_timing_zero_tx32',[0x20001004]);assert bytes(u.mem_read(0x20001000,136))==bytes(buf)
report={'status':'PASS_OFFLINE_ONLY','device_access':False,'audio_playback':False,'host_arm_matching_cases':len(checks),'edge_cases':checks[:-2000],'random_cases':2000,'tx_words_cleared':32,'tx_guard_bytes_intact':8,'stats_bytes':C.sizeof(Stats),'regions':regions,'undefined_symbols':imports,'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'simulated_clock_hz':600000000,'simulated_reference_hz':24000000,'simulated_deadline_ticks':4000,'hardware_timing_measured':False,'integrated_into_a2_image':False,'limits':['Pure recorder logic only; no target clock, reset epoch, DMA sequence or telemetry transport backend.','Independent reference timer ownership and capture overhead remain unverified.','ARM execution checks logic equivalence, not cycle timing.','32-word zeroing does not establish analog/USB silence without integration.']}
Path(a.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
