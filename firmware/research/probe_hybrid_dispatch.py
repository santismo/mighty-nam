#!/usr/bin/env python3
"""Offline-only stock V1.5.6 dispatcher + compiled ARM NAM integration test.
Other stock effects are explicitly replaced by pass-through VM stubs; this is
NOT full firmware/audio emulation. No peripherals, USB or audio devices mapped.
"""
import argparse, hashlib, json, math, random, struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *

p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path)
p.add_argument('output',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[1];b=a.payload.read_bytes()
SHA='a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990'
def check(ok,msg):
    if not ok: raise AssertionError(msg)
check(hashlib.sha256(b).hexdigest()==SHA,'Unexamined stock payload')
# Unicorn's M7 model rejects FP64 instructions despite this target's DP FPU.
# Use A15's compatible Thumb/VFP instruction execution for this bounded call
# test. This does NOT emulate M7 exceptions, MPU/cache behavior or timing.
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A15)
u.mem_map(0,0x100000);u.mem_write(0,b[:0x100000]);u.mem_protect(0,0x100000,UC_PROT_READ|UC_PROT_EXEC)
u.mem_map(0x20000000,0x400000,UC_PROT_READ|UC_PROT_WRITE)
u.mem_map(0x08000000,0x10000);u.mem_map(0x21000000,0x10000,UC_PROT_READ|UC_PROT_WRITE)
u.reg_write(UC_ARM_REG_C1_C0_2,0xf00000);u.reg_write(UC_ARM_REG_FPEXC,0x40000000)
with (root/'artifacts/hybrid-vm-only.elf').open('rb') as f:
    e=ELFFile(f);sym={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
    check(not [s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'],'Unresolved symbols')
    sections=[]
    for s in e.iter_sections():
        if not s['sh_flags']&2:continue
        sections.append({'name':s.name,'address':hex(s['sh_addr']),'bytes':s['sh_size']})
        if s['sh_type']!='SHT_NOBITS': u.mem_write(s['sh_addr'],s.data())
u.mem_protect(0x08000000,0x10000,UC_PROT_READ|UC_PROT_EXEC)
def put32(addr,val):u.mem_write(addr,struct.pack('<I',val))
def get32(addr):return struct.unpack('<I',u.mem_read(addr,4))[0]
def floats(addr,values):u.mem_write(addr,struct.pack('<'+'f'*len(values),*values))
def readfloats(addr,n=8):return list(struct.unpack('<'+'f'*n,u.mem_read(addr,n*4)))
STOP=0x40000;SP=0x20080000
regs=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
preserved=[UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]
fpregs=[getattr(__import__('unicorn.arm_const',fromlist=['']),f'UC_ARM_REG_D{i}') for i in range(8,16)]
def call(addr,args=(),limit=2000000):
    for r,v in zip(regs,args):u.reg_write(r,v)
    for i,r in enumerate(preserved):u.reg_write(r,0x12340000+i)
    for i,r in enumerate(fpregs):u.reg_write(r,0x3ff0000000000000+i)
    u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1)
    try:u.emu_start(addr|1,STOP,count=limit)
    except UcError as ex:raise RuntimeError(f'ARM emulation failed at {u.reg_read(UC_ARM_REG_PC):#x}') from ex
    check(u.reg_read(UC_ARM_REG_PC)==STOP,'Instruction budget exceeded')
    check(u.reg_read(UC_ARM_REG_SP)==SP,'Unbalanced stack')
    check(all(u.reg_read(r)==0x12340000+i for i,r in enumerate(preserved)),'Callee-saved integer registers')
    check(all(u.reg_read(r)==0x3ff0000000000000+i for i,r in enumerate(fpregs)),'Callee-saved FP registers')
# Stock IAR initialization uses a private ABI; it is not one of our ABI tests.
u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1)
u.emu_start(0x2025d,STOP,count=5000000);check(u.reg_read(UC_ARM_REG_PC)==STOP,'Stock init incomplete')
source_table=[list(struct.unpack('<3I',u.mem_read(0x2000052c+12*i,12))) for i in range(11)]
check(source_table[3][1]==0x5579,'Amp candidate source pointer changed')

# Independent double-precision LSTM oracle, not the compiled C++ implementation.
model=json.loads((root/'models/lstm.nam').read_text());w=model['weights'];h=model['config']['hidden_size'];bias=4*h*(h+1)
class Reference:
    def __init__(self):self.h=w[bias+4*h:bias+5*h].copy();self.c=w[bias+5*h:bias+6*h].copy()
    def process(self,xs):
        out=[]
        sigmoid=lambda x:1/(1+math.exp(-x))
        for x in xs:
            g=[w[bias+r]+w[r*(h+1)]*x+sum(w[r*(h+1)+c+1]*self.h[c] for c in range(h)) for r in range(4*h)]
            self.c=[sigmoid(g[h+i])*self.c[i]+sigmoid(g[i])*math.tanh(g[2*h+i]) for i in range(h)]
            self.h=[sigmoid(g[3*h+i])*math.tanh(self.c[i]) for i in range(h)]
            out.append(w[bias+7*h]+sum(w[bias+6*h+i]*self.h[i] for i in range(h)))
        return out

planes=[0x21008040+i*0x100 for i in range(4)]
for addr in planes:u.mem_write(addr-16,b'\xa5'*64)
call(sym['mpp_hybrid_reset']);check(get32(sym['mpp_hybrid_ready'])==1,'Model not ready')
put32(sym['mpp_hybrid_enabled'],1)
ref=Reference();rng=random.Random(46);maxerr=0
for block in range(128):
    xs=[struct.unpack('<f',struct.pack('<f',rng.uniform(-1,1)))[0] for _ in range(8)]
    floats(planes[0],xs);floats(planes[1],[-x for x in xs])
    call(sym['mpp_hybrid_amp'],planes)
    ys=readfloats(planes[2]);maxerr=max(maxerr,max(abs(x-y) for x,y in zip(ys,ref.process(xs))))
    check(ys==readfloats(planes[3]),'Mono output duplicated incorrectly')
check(maxerr<2e-6,'ARM NAM differs from reference')
for addr in planes:
    check(bytes(u.mem_read(addr-16,16))==b'\xa5'*16 and bytes(u.mem_read(addr+32,16))==b'\xa5'*16,'Buffer overrun')

# Bypass, crossed aliases, error muting, reset reproducibility.
put32(sym['mpp_hybrid_enabled'],0)
left=[i/16 for i in range(8)];right=[-x for x in left]
floats(planes[0],left);floats(planes[1],right)
call(sym['mpp_hybrid_amp'],[planes[0],planes[1],planes[1],planes[0]])
check(readfloats(planes[1])==left and readfloats(planes[0])==right,'Bypass/alias mismatch')
put32(sym['mpp_hybrid_enabled'],1);floats(planes[0],[math.nan]*8)
call(sym['mpp_hybrid_amp'],planes)
check(readfloats(planes[2])==[0]*8 and get32(sym['mpp_hybrid_faults'])==1,'Invalid input not muted')

# Use real stock reorder routine and dispatcher. Other effects are explicit
# pass-through stubs because their startup/resources have not been emulated.
stock_fx={x[1]&~1:i for i,x in enumerate(source_table)};trace=[]
def hook(uc,pc,size,user):
    if pc==(sym['mpp_hybrid_amp']&~1):trace.append(3)
    if pc in stock_fx:
        i=stock_fx[pc];check(i!=3,'Original amp unexpectedly called');trace.append(i)
        x,y,ox,oy=[uc.reg_read(r) for r in regs]
        l=bytes(uc.mem_read(x,32));r=bytes(uc.mem_read(y,32))
        uc.mem_write(ox,l);uc.mem_write(oy,r);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
# The direct test has already translated the NAM code. Invalidate those cached
# blocks so the newly installed trace hook sees calls into the same function.
u.ctl_remove_cache(0x08000000,0x08010000)
put32(0x20000554,sym['mpp_hybrid_amp']|1) # VM RAM only; never patches saved stock firmware.
preset=0x20030000;put32(0x20005ad0,preset)
floats(0x20005c50,[1.0]*0x40a) # Controlled test fade curve, not stock curve initialization.
orders=[list(range(11)),[10,8,3,1,0,9,2,4,5,7,6]];dispatch_errors=[]
for order in orders:
    u.mem_write(preset+0x59,bytes(order));u.mem_write(0x200005b0,b'\xff'*12)
    floats(0x2000d9c8,[1]*8);call(sym['mpp_hybrid_reset']);ref=Reference()
    for repeat in range(2):
        xs=[0.15*math.sin((repeat*8+i)*.23) for i in range(8)];floats(0x2000d6c8,xs);floats(0x2000d6e8,xs)
        xs=readfloats(0x2000d6c8);trace.clear();call(0x122d0)
        check(trace==order,f'Stock chain order changed: {trace}, expected {order}')
        expected=ref.process(xs);slot=order.index(3)
        check(get32(0x200005c8+28*slot)==(sym['mpp_hybrid_amp']|1),'Reorder lost NAM pointer')
        end=0x200005c8+28*10;outptr=get32(end+16)
        err=max(abs(x-y) for x,y in zip(readfloats(outptr),expected));dispatch_errors.append(err)
        check(err<2e-6,'Stock dispatcher output mismatch')
result={'status':'PASS_OFFLINE_ONLY','payload_sha256':SHA,'device_or_audio_access':False,
 'emulator_cpu_model':'A15 Thumb/VFP instruction compatibility; not M7 system emulation',
 'arm_math_host_stubs':False,'fixture_hidden_size':h,'direct_arm_samples':1024,
 'direct_max_abs_error_vs_double_reference':maxerr,'stock_dispatch_max_abs_error':max(dispatch_errors),
 'tested_orders':orders,'checks':['ARM LSTM with real compiled musl math','r4-r11/d8-d15 and stack preservation',
 'buffer canaries','bypass with crossed aliases','nonfinite input silence/reset','stock chain reorder and dispatch'],
 'synthetic_elf_sections':sections,'stock_source_table':source_table,
 'scope_limits':['H3 correctness fixture only','Other ten stock stages are pass-through stubs',
 'Fade curve forced to unity for controlled dispatch test','No physical code/state placement or timing proven',
 'No persistent firmware patch, startup, loader or recovery test']}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
