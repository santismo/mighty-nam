"""Bounded offline ARM emulation. Peripheral addresses map to ordinary VM RAM.
No USB, audio, system calls or physical MMIO forwarding. Simulated register
writes describe firmware intent, not electrical/timing validation.
"""
import hashlib,json,struct
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
import argparse
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
b=args.payload.read_bytes()
if hashlib.sha256(b).hexdigest()!='a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990': raise ValueError('Unexamined payload')
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
u.mem_map(0,0x100000);u.mem_write(0,b[:0x100000]);u.mem_protect(0,0x100000,UC_PROT_READ|UC_PROT_EXEC)
u.mem_map(0x20000000,0x400000);u.mem_map(0x40000000,0x1000000);u.mem_map(0xe0000000,0x100000)
STOP=0x40000
stubs={}; calls=[]; writes=[]
def hook(uc,a,size,user):
 if a in stubs:
  args=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  event={'function':hex(a),'kind':stubs[a],'args':[hex(v) for v in args]}
  if a==0xda34:event['data']=bytes(uc.mem_read(args[2],args[3])).hex()
  if a==0x87a0:event['config']=bytes(uc.mem_read(args[0],20)).hex(' ')
  calls.append(event);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def write(uc,access,a,size,value,user):
 if a>=0x40000000:writes.append({'pc':hex(uc.reg_read(UC_ARM_REG_PC)),'address':hex(a),'bytes':size,'value':hex(value)})
u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_MEM_WRITE,write)
def call(a):
 u.reg_write(UC_ARM_REG_SP,0x20080000);u.reg_write(UC_ARM_REG_LR,STOP|1)
 u.emu_start(a|1,STOP,count=5000000)
 assert u.reg_read(UC_ARM_REG_PC)==STOP,f'instruction budget exhausted at {u.reg_read(UC_ARM_REG_PC):x}'
call(0x2025c)
# No MMIO was mapped to actual hardware; stock init only copies/zeros VM RAM.
stubs.update({0xbe34:'delay_abstract_units',0xda34:'codec_i2c_write',0xdb06:'codec_i2c_read_skipped'})
call(0x116c0)
codec_calls=list(calls);calls.clear();codec_gpio=list(writes);writes.clear()
call(0x10b68)
pins=list(writes);writes.clear()
stubs.update({0x87a0:'audio_pll_init_not_executed',0xede4:'dmamux_clock_init_not_executed'})
call(0x11984)
def regs(base,offsets):return {hex(o):hex(struct.unpack('<I',u.mem_read(base+o,4))[0]) for o in offsets}
tcds=[]
for a in (0x20016aa0,0x20016ac0,0x20016ae0,0x20016b00):
 t=bytes(u.mem_read(a,32));v=struct.unpack('<IhHIiIhHIHH',t)
 tcds.append(dict(zip(('saddr','soff','attr','nbytes','slast','daddr','doff','citer','dlast_sga','csr','biter'),v)))
result={'scope':'Saved V1.5.6 emulated on Mac; peripheral cells start at zero; PLL/delays/I2C are stubs; no electrical validation',
 'payload_sha256':hashlib.sha256(b).hexdigest(),'codec_calls':codec_calls,'codec_gpio_writes':codec_gpio,'audio_calls':calls,'pinmux_writes':pins,
 'sai_registers':regs(0x40404000,[8,12,16,20,24,28,0x60,0x88,0x8c,0x90,0x94,0x98,0x9c,0xe0]),
 'dma_register_writes':writes,'memory_tcds':tcds,'dma_irq_vector':hex(struct.unpack_from('<I',b,16*4)[0])}
args.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('sai_registers','memory_tcds','audio_calls','dma_irq_vector')},indent=2))
