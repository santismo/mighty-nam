"""A2 module injected by the host into a synthetic executable region AFTER stock boot.
This tests ARM DSP + stock routing/effects, not persistent startup/firmware placement.
"""
import struct,json
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_R0,UC_ARM_REG_R1
import candidate_vm as v
from stock_chain_vm import StockChainMachine
from a2_oracle import Engine,extract
class A2Machine(StockChainMachine):
 def __init__(self,lib,path,observe_blocks=False):
  root=Path(__file__).resolve().parents[1]
  with (root/'artifacts/a2-lite-vm-only.elf').open('rb') as f:
   e=ELFFile(f);sections=[(s['sh_addr'],s['sh_size'],s['sh_type'],s.data()) for s in e.iter_sections() if s['sh_flags']&2]
   sy={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols() if s.name}
  self.a2_symbols=sy;self.a2_violations=[];self.a2_writes=0;self.a2_lo=0x202e6020;self.a2_hi=0x202fa860
  super().__init__(fast=True,reference_factory=lambda:Engine(lib,path),nam_tolerance=2e-5,observe_blocks=observe_blocks,amp_entry=sy['mpp_a2_process'])
  self.u.mem_map(0x08000000,0x10000)
  for addr,size,kind,data in sections:self.u.mem_write(addr,bytes(size) if kind=='SHT_NOBITS' else data)
  self.u.mem_write(self.a2_lo-16,b'\xa2'*16);self.u.mem_write(self.a2_hi,b'\x2a'*32)
  self.u.hook_add(UC_HOOK_MEM_WRITE,self.a2_write,begin=self.a2_lo-16,end=self.a2_hi+31)
  weights=extract(json.loads(Path(path).read_text()))['weights'];self.u.mem_map(0x08100000,0x2000)
  self.u.mem_write(0x08100000,struct.pack('<1871f',*weights))
  self.u.reg_write(UC_ARM_REG_R0,0x08100000);self.u.reg_write(UC_ARM_REG_R1,1871);self.phase='load_a2';self.run(sy['mpp_a2_load'],limit=500000)
  v.require(self.u.reg_read(UC_ARM_REG_R0)==1,'ARM A2 load failed');self.phase='audio';self.a2_guards()
 def a2_write(self,u,access,addr,size,value,user):
  pc=u.reg_read(UC_ARM_REG_PC)
  if not(0x08000000<=pc<0x08001000 and self.a2_lo<=addr and addr+size<=self.a2_hi):
   self.a2_violations.append(dict(pc=hex(pc),address=hex(addr),size=size));raise v.Collision('Foreign writer in A2 RAM')
  self.a2_writes+=1
 def a2_guards(self):
  v.require(bytes(self.u.mem_read(self.a2_lo-16,16))==b'\xa2'*16,'A2 lower guard damaged')
  v.require(bytes(self.u.mem_read(self.a2_hi,32))==b'\x2a'*32,'A2 upper guard damaged')
 def block(self,*args,**kwargs):
  out=super().block(*args,**kwargs);self.a2_guards();return out
