"""Actual saved stock DSP in a bounded CPU-only simulation. No device APIs.
The base harness retains its historical bypass option; this class executes all
11 stock dispatch stages, their overlays, shared-table initialization and reloads.
"""
import math, struct, collections
from unicorn import UC_PROT_ALL, UC_PROT_READ, UC_HOOK_CODE, UC_HOOK_BLOCK
from unicorn.arm_const import UC_ARM_REG_LR
import candidate_vm as v

NAMES=['unused_wah','compressor','drive','NAM','EQ','gate','modulation','delay','reverb','cabinet','unused_sr']
ORDER=[0,5,1,2,3,9,4,6,7,8,10]
# Confirmed from each callback's preset-byte load and state-base literal.
# V1.5.6 has five delay models; later app definitions also list Phi Delay (6).
GROUPS={1:(0x200037e8,3),2:(0x20003a7c,13),6:(0x20004110,13),7:(0x20003a08,5),8:(0x200041d8,6)}

def preset_fixture(enabled=(),types=None):
 p=bytearray([50]*128);p[:11]=bytes([0x41]*11);p[3]=1
 for stage in enabled:p[stage]=1
 for stage,model in (types or {}).items():p[stage]=model|(p[stage]&0x40)
 for idx,count in [(11,2),(14,4),(19,6),(26,8),(35,12),(48,4),(53,6),(60,8),(69,4),(74,6),(81,2)]:p[idx]=count
 # Low gate threshold, zero tempo-sync flags, 120 BPM, ordinary routing.
 p[49]=0;p[85:89]=bytes([0,0,120,0]);p[89:100]=bytes(ORDER)
 return p

class StockChainMachine(v.Machine):
 def __init__(self,fill=0,reference_amp=False,fast=False,reference_factory=None,nam_tolerance=2e-6,observe_blocks=True,amp_entry=None,expected_ready=1,flash_observer=None):
  self.reference_factory=reference_factory or v.Reference;self.nam_tolerance=nam_tolerance;self.amp_entry=amp_entry
  self.pending=None;self.reference=self.reference_factory();self.last_control=None
  self.reference_amp=reference_amp;self.max_nam_error=0.;self.nam_samples=0
  self.stage_stats={i:{'calls':0,'peak_in':0.,'peak_out':0.,'max_change':0.} for i in range(11)}
  self.overlay_instructions=collections.Counter();self.copies=set();self.last_outputs={}
  super().__init__(fill,expected_ready=expected_ready);self.real_effects=True
  self.u.mem_protect(0x24000,0x1c000,UC_PROT_ALL)
  self.u.mem_map(0x20240000,0x80000)
  self.u.mem_map(0x30040000,(len(v.stock)+4095)&~4095,UC_PROT_READ);self.u.mem_write(0x30040000,v.candidate)
  if flash_observer is not None:flash_observer(self)
  for addr in [0x40c60000,0x40c5c000,0x40c68000,0x40071000]:self.u.mem_map(addr,0x1000)
  self.put(0x40071074,0x08000000)
  self.stubs.difference_update({0xe98c,0x10b08})
  # Retain real routing fade tables copied by stock 0x10b08.
  self.boot(unity_fades=False)
  self.fast=fast;self.observe_blocks=observe_blocks;self.previous_block=None;self.overlay_blocks=collections.Counter()
  if fast:
   # Same bytecode, memory guards and boundary oracle. Observe basic-block
   # transitions rather than every instruction; retain exact entry/return hooks.
   self.u.hook_del(self.code_hook)
   for pc in set(self.fx)|{0x5578,0x1230e,0x5488,0x54a8,0x5530}:
    self.u.hook_add(UC_HOOK_CODE,self.code,begin=pc,end=pc)
   self.block_hook=self.u.hook_add(UC_HOOK_BLOCK,self.block_trace) if observe_blocks else None
   self.u.ctl_remove_cache(0,0x40000)
 def block_trace(self,u,pc,size,user):
  if self.count_stack:self.minimum_sp=min(self.minimum_sp,u.reg_read(v.UC_ARM_REG_SP))
  if 0x39000<=pc<0x3e000:self.overlay_blocks[hex(pc&~0xfff)]+=1
  if v.code_start<=pc<v.code_end and (self.previous_block is None or not v.code_start<=self.previous_block<v.code_end):
   if pc not in {v.sym['mpp_stock_amp_init']&~1,v.sym['mpp_stock_amp_process']&~1}:
    self.foreign_code_entries.append({'from':hex(self.previous_block) if self.previous_block else None,'to':hex(pc)})
    raise v.Collision('Unexpected block entry into reclaimed code')
  self.previous_block=pc
 def code(self,u,pc,size,user):
  if self.phase!='runtime' and pc in (0x5488,0x54a8,0x5530):
   dest,src,n=[u.reg_read(r) for r in v.R[:3]];n=src if pc==0x5530 else n
   v.require(n<=0x100000,'Unexpected stock memory operation size')
   v.require(not(dest<v.code_end and dest+n>v.code_start),'Stock copy/clear overlaps NAM code')
   v.require(not(dest<v.state_watch_end and dest+n>0x202e4000),'Stock copy/clear overlaps NAM RAM')
   self.copies.add((dest,None if pc==0x5530 else src,n))
  if self.phase=='audio':
   if 0x39000<=pc<0x3e000:self.overlay_instructions[hex(pc&~0xfff)]+=1
   if self.pending and pc==self.pending['return']:
    p=self.pending;self.pending=None;out=self.read(p['ol'])+self.read(p['or'])
    v.require(all(math.isfinite(x) for x in out),'Non-finite stock stage output')
    s=self.stage_stats[p['stage']];s['calls']+=1
    s['peak_in']=max(s['peak_in'],max(map(abs,p['in'])))
    s['peak_out']=max(s['peak_out'],max(map(abs,out)))
    s['max_change']=max(s['max_change'],max(abs(x-y) for x,y in zip(p['in'],out)))
    self.last_outputs[p['stage']]=out
    if p['stage']==3:
     err=max(abs(x-y) for x,y in zip(out,p['expected']));self.max_nam_error=max(self.max_nam_error,err)
     v.require(err<self.nam_tolerance,'NAM differs from independent reference at the real chain boundary')
     self.nam_samples+=8
   if pc==0x5578 or pc in self.fx:
    stage=3 if pc==0x5578 else self.fx[pc]
    v.require(self.pending is None,'Nested/unfinished stock stage')
    il,ir,ol,orr=[u.reg_read(r) for r in v.R];xs=self.read(il)+self.read(ir)
    p={'stage':stage,'in':xs,'ol':ol,'or':orr,'return':u.reg_read(UC_ARM_REG_LR)&~1}
    if stage==3:
     control=u.mem_read(self.preset+3,1)[0]
     if control!=self.last_control:self.reference=self.reference_factory();self.last_control=control
     expected=xs if control&0x40 else self.reference.run(xs[:8])*2
     p['expected']=expected
     if self.reference_amp:
      self.floats(ol,expected[:8]);self.floats(orr,expected[8:]);self.trace.append(3)
      self.pending=p;u.reg_write(v.UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
    self.pending=p
    if stage==3 and self.amp_entry is not None:
     self.trace.append(3);u.reg_write(v.UC_ARM_REG_PC,self.amp_entry);return
  super().code(u,pc,size,user)
 def set_preset(self,enabled=(),types=None):self.u.mem_write(self.preset,bytes(preset_fixture(enabled,types)))
 def block(self,xs,order=ORDER,control=1):
  self.phase='audio';_,out=self.dispatch(order,xs,control)
  v.require(self.pending is None,'Stage did not return to dispatcher')
  self.phase='background';before=bytes(self.u.mem_read(v.state_start,v.state_end-v.state_start))
  self.run(0xe9ae,limit=3000000);self.background();self.guards()
  v.require(before==bytes(self.u.mem_read(v.state_start,v.state_end-v.state_start)),'Background changed NAM')
  self.phase='audio';return out
 def outer_block(self,xs,order=ORDER,control=1):
  """Stock mono input wrapper 0xe934 and master-volume wrapper 0xe8f8.
  Does not include ADC/DAC, SAI, DMA, interrupts or USB mixing.
  """
  self.u.mem_write(self.preset+3,bytes([control]));self.u.mem_write(self.preset+89,bytes(order))
  self.floats(0x20025000,xs);self.floats(0x2000d9c8,[1.]*8)
  for reg,value in zip(v.R[:3],[0x20025000,0x20025100,0x20025200]):self.u.reg_write(reg,value)
  self.phase='audio';self.trace=[];self.count_stack=True;self.run(0xe934);self.count_stack=False
  v.require(self.trace==order and self.pending is None,'Outer stock wrapper dispatch mismatch')
  out=self.read(0x20025100)+self.read(0x20025200)
  v.require(all(math.isfinite(x) for x in out),'Non-finite master-volume output')
  self.phase='background';self.run(0xe9ae);self.background();self.guards();self.phase='audio'
  return out
 def stats(self):
  return {'nam_samples':self.nam_samples,'max_nam_error':self.max_nam_error,
   'stage_stats':{NAMES[i]:s for i,s in self.stage_stats.items()},
   'stock_overlay_instruction_counts':dict(self.overlay_instructions),
   'stock_overlay_basic_block_counts':dict(self.overlay_blocks),
   'instrumentation':('block transitions + exact boundaries' if self.observe_blocks else 'exact boundaries only') if self.fast else 'every instruction',
   'minimum_observed_sp':hex(self.minimum_sp),'observed_stack_bytes':v.SP-self.minimum_sp,
   'forbidden_state_writes':self.violations,'unexpected_code_entries':self.foreign_code_entries,'foreign_code_data_reads':self.foreign_code_reads}
