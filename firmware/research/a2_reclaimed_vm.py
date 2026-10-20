"""Reclaimed A2 tests use application-byte edits and read-only resource storage.
No synthetic executable region, host AMP redirect or post-boot model injection.
"""
from pathlib import Path
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_PC
import candidate_vm as v
from stock_chain_vm import StockChainMachine
from a2_storage import SLOT_ADDRESS,SLOT_SIZE
from a2_reclaimed_image import build
from a2_oracle import Engine

def configure(payload,model,elf=None):
 root=Path(__file__).resolve().parents[1]
 bundle=build(Path(payload).read_bytes(),Path(elf) if elf else root/'artifacts/a2-reclaimed-v1-lab-only.elf',model)
 v.configure(payload,True,candidate_bundle=bundle)
 return v.plan
class A2ReclaimedMachine(StockChainMachine):
 def __init__(self,lib,model,fill=0,expected_ready=1,observe_blocks=False,reference_amp=False):
  self.model_reads=0;self.model_read_bytes=0;self.model_access_violations=[]
  self.factory=lambda:Engine(lib,model)
  def observe(m):
   m.u.hook_add(UC_HOOK_MEM_READ,m.storage_read,begin=SLOT_ADDRESS,end=SLOT_ADDRESS+SLOT_SIZE-1)
   m.u.hook_add(UC_HOOK_MEM_WRITE,m.storage_write,begin=SLOT_ADDRESS,end=SLOT_ADDRESS+SLOT_SIZE-1)
  super().__init__(fill=fill,fast=True,reference_amp=reference_amp,reference_factory=self.factory,nam_tolerance=2e-5,observe_blocks=observe_blocks,expected_ready=expected_ready,flash_observer=observe)
 def storage_read(self,u,access,address,size,value,user):
  pc=u.reg_read(UC_ARM_REG_PC)
  if not(v.code_start<=pc<v.code_end):
   self.model_access_violations.append(dict(kind='read',pc=hex(pc),address=hex(address)));raise v.Collision('Stock reader touched reclaimed model storage')
  self.model_reads+=1;self.model_read_bytes+=size
 def storage_write(self,u,access,address,size,value,user):
  self.model_access_violations.append(dict(kind='write',pc=hex(u.reg_read(UC_ARM_REG_PC)),address=hex(address)));raise v.Collision('CPU attempted model-storage write')
 def warm_restart(self,poison=True):
  before=bytes(self.u.mem_read(SLOT_ADDRESS,SLOT_SIZE));reads=self.model_reads
  if poison:self.u.mem_write(v.state_start,b'\x5a'*(v.state_end-v.state_start))
  self.pending=None;self.previous_block=None;self.last_control=None;self.reference=self.factory()
  # Restore full boot observation/stubs while running the unchanged common
  # stock runtime again. Exact boundary hooks remain inactive during audio-free boot.
  handle=self.u.hook_add(UC_HOOK_CODE,self.code)
  self.u.ctl_remove_cache(0,0x40000)
  try:self.boot(unity_fades=False)
  finally:self.u.hook_del(handle);self.u.ctl_remove_cache(0,0x40000)
  v.require(before==bytes(self.u.mem_read(SLOT_ADDRESS,SLOT_SIZE)),'Restart changed model storage')
  v.require(self.model_reads>reads,'Restart did not reload model storage')
  return self.model_reads-reads
