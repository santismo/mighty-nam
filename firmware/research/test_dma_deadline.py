"""Execute the compiled DMA guard with synthetic peripheral timing, offline only."""
import argparse,hashlib,json,struct,math
from pathlib import Path
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from test_preset_runtime import PresetMachine,v,preset_fixture,model_slot
from preset_image import build

class GuardMachine(PresetMachine):
 def __init__(self,*args,**kwargs):
  self.cycle_step=100;self.cycle_values=None;self.late=False
  super().__init__(*args,**kwargs)
  self.u.hook_add(UC_HOOK_CODE,self.finish,begin=v.sym['mpp_dma_finish']&~1,end=v.sym['mpp_dma_finish']&~1)
 def cycle_read(self,u,access,addr,size,value,unused):
  self.synthetic_cycle=(self.cycle_values.pop(0) if self.cycle_values else self.synthetic_cycle+self.cycle_step)&0xffffffff
  self.put(addr,self.synthetic_cycle)
 def finish(self,*args):
  if self.late:self.put(0x40071200,self.get(0x40071200)+64)
 def snapshot(self,half=0,prior=False,occupancy=24):
  target=0x20016900+128*half;other=target^128
  for at,value in [(0x40071200,other+64 if prior else target),(0x40071214,(1 if prior else 2)<<16),
   (0x40071218,0x20016ae0+32*(half if prior else 1-half)),(0x40071018,0x20016aa0+32*half),
   (0x40071010,other-256),(0x40404040,occupancy<<16),(0x4040400c,8),(0x40404008,0),(0x40404088,0)]:self.put(at,value)
 def process(self,index,inputs=None,healthy=True):
  self.snapshot(index%2)
  return super().process(index,inputs,healthy)
 def stats(self):return [self.get(v.sym['mpp_dma_stats']+i*4) for i in range(8)]

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['payload','elf','model','report']:p.add_argument(name,type=Path)
 a=p.parse_args();bundle=build(a.payload.read_bytes(),a.elf,allow_dma_prototype=True)
 assert bundle[2]['identity']=='NAMDMP02'
 try:build(a.payload.read_bytes(),a.elf)
 except ValueError as e:assert 'offline-only' in str(e)
 else:raise AssertionError('Prototype accepted by release builder')
 v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=a.elf
 m=GuardMachine();src=v.sym['mpp_dma_pcm'];target=0x20016900;pattern=struct.pack('<32i',*range(32))
 m.u.mem_write(src,pattern);rows=[]
 def unit(name,reason=0,half=0,prior=False,occupancy=24,change=None,reads=None,cycles=None,mask=0,zero=False):
  nonlocal target
  target=0x20016900+half*128
  m.cycle_values=None;m.cycle_step=100;m.put(0xe0001000,1);m.put(v.sym['mpp_dwt_reset_epoch'],0)
  m.put(v.sym['mpp_irq_stats'],1);m.u.mem_write(v.sym['mpp_dma_stats'],bytes(32));m.snapshot(half,prior,occupancy)
  m.call(v.sym['mpp_driver_capture'],[0,0]);m.primask=mask
  m.u.mem_write(target,b'\x55'*128);other=bytes(m.u.mem_read(target^128,128));before_play=m.page(23)
  if change:change(m)
  if cycles:m.cycle_values=[(m.synthetic_cycle+x)&0xffffffff for x in cycles]
  writes=[];peripheral=[];hooks=[]
  hooks.append(m.u.hook_add(UC_HOOK_MEM_WRITE,lambda u,acc,at,n,val,x:writes.append((at,n)),begin=target,end=target+127))
  hooks.append(m.u.hook_add(UC_HOOK_MEM_WRITE,lambda u,acc,at,n,val,x:peripheral.append(at),begin=0x40000000,end=0x41000000))
  if reads:hooks.append(m.u.hook_add(UC_HOOK_MEM_READ,reads))
  m.call(v.sym['mpp_dma_commit'],[target,0 if zero else src,1]);s=m.stats()
  for hook in hooks:m.u.hook_del(hook)
  assert s[4]==reason,(name,s)
  assert s[0]==int(reason!=0) and m.primask==mask,(name,s,m.primask)
  assert s[7]==int(reason==9)
  assert m.page(23)==before_play and not peripheral and bytes(m.u.mem_read(target^128,128))==other
  if reason not in (0,9):assert not writes and bytes(m.u.mem_read(target,128))==b'\x55'*128
  else:assert len(writes)==32 and bytes(m.u.mem_read(target,128))==(bytes(128) if zero else pattern)
  rows.append(dict(case=name,reason=reason,stores=len(writes),primask_restored=True))
 for half in (0,1):
  for prior in (False,True):
   for mask in (0,1):unit(f'valid-{half}-{prior}-{mask}',half=half,prior=prior,mask=mask)
 unit('zero-prefill',zero=True)
 unit('not-in-IRQ',1,change=lambda m:m.put(v.sym['mpp_irq_stats'],2))
 unit('counter-disabled',2,change=lambda m:m.put(0xe0001000,0))
 unit('counter-reset',2,change=lambda m:m.put(v.sym['mpp_dwt_reset_epoch'],1))
 unit('elapsed-limit',2,cycles=[100001])
 unit('cursor-already-fetched',3,change=lambda m:m.put(0x40071200,target+64))
 unit('wrong-next',3,change=lambda m:m.put(0x40071218,0))
 unit('wrong-citer',3,change=lambda m:m.put(0x40071214,1<<16))
 unit('wrong-rx-half',4,change=lambda m:m.put(0x40071018,0x20016ac0))
 unit('wrong-rx-cursor',4,change=lambda m:m.put(0x40071010,0))
 unit('wrong-watermark',5,change=lambda m:m.put(0x4040400c,16))
 unit('fifo-requesting',5,occupancy=8)
 unit('fifo-invalid',5,occupancy=33)
 unit('TX-error',5,change=lambda m:m.put(0x40404008,0x40000))
 unit('RX-error',5,change=lambda m:m.put(0x40404088,0x80000))
 unit('four-word-boundary-rejected',6,occupancy=12)
 unit('five-word-margin-accepted',occupancy=13)
 count=[0]
 def moved(u,acc,at,n,value,x):
  if at==0x40071200:
   count[0]+=1
   if count[0]==2:m.put(at,target+64)
 unit('DMA-moves-during-snapshot',7,reads=moved)
 unit('snapshot-budget-exhausted',8,cycles=[100,2148])
 unit('snapshot-budget-edge',cycles=[100,2147,4195])
 unit('post-copy-overrun-detected-not-undone',9,cycles=[100,200,4196])
 # Natural unsigned DWT wrap is legal if the epoch and interval agree.
 m.synthetic_cycle=0xffffff00;unit('counter-wrap')
 # Saturation and no runtime command resets the fallback latch.
 for index in (0,3):m.put(v.sym['mpp_dma_stats']+index*4,0xffffffff)
 m.put(v.sym['mpp_irq_stats'],0);m.call(v.sym['mpp_dma_commit'],[target,src,0])
 assert m.stats()[3]==0xffffffff
 m.call(v.sym['mpp_driver_control'],[0]);assert m.stats()[0]==1
 # A rejected early prefill also leaves the entire old half untouched. An
 # already queued block cannot be recalled after a late processing fault.
 m.cycle_values=None;m.cycle_step=100;m.snapshot();m.put(v.sym['mpp_irq_stats'],1)
 m.call(v.sym['mpp_driver_capture'],[0,0]);m.u.mem_write(0x20016900,pattern)
 m.put(0x40071200,0x20016940)
 m.call(v.sym['mpp_dma_prefill'],[0x20016900,1]);assert bytes(m.u.mem_read(0x20016900,128))==pattern
 m.call(v.sym['mpp_dma_finish'],[0x20016900,0]);assert bytes(m.u.mem_read(0x20016900,128))==pattern
 m.snapshot();m.call(v.sym['mpp_driver_capture'],[0,0]);m.call(v.sym['mpp_dma_prefill'],[0x20016900,0])
 assert bytes(m.u.mem_read(0x20016900,128))==bytes(128)
 m.call(v.sym['mpp_dma_commit'],[0x20016904,src,0]);assert m.stats()[4]==1
 print('guard decision matrix',len(rows),'PASS',flush=True)
 # Real DSP/renderer/whole IRQ, both halves and all output queue sizes. Force
 # a late current commit only after a valid early fallback was installed.
 integrated=[]
 for size in (8,16,32):
  m=GuardMachine(path=a.model);m.call(v.sym['mpp_buffer_set'],[size]);m.arm()
  data=preset_fixture([8],{8:4});data[70:74]=bytes([20,20,50,0]);m.u.mem_write(m.preset,bytes(data))
  protected=[];last=None
  for i in range(1360):
   out=m.process(i,[.08*math.sin((i*8+j)*.071) for j in range(8)])
   protected.append(m.read(v.sym['mpp_link_output'])+m.read(v.sym['_ZL11chain_right']))
   if i>=1350:assert out==[int(x*2**28)*2**-31 for x in protected[i-(size//8-1)]]
   last=bytes(m.u.mem_read(v.sym['mpp_dma_pcm'],128))
  assert m.stats()[0]==0 and m.stats()[1]==1360 and m.stats()[2]==1360
  runs=m.words()[7];m.late=True;m.process(1360)
  assert bytes(m.u.mem_read(0x20016900,128))==last and m.stats()[0]==1
  m.late=False
  for i in range(1361,1393):
   prior=bytes(m.u.mem_read(v.sym['mpp_dma_pcm'],128));commits=m.stats()[2]
   m.process(i)
   assert bytes(m.u.mem_read(0x20016900+128*(i%2),128))==prior and m.stats()[2]==commits
  assert m.words()[7]==runs+33 and m.words()[4]==0 and m.get(v.sym['mpp_listen_enabled'])==1
  m.restart();assert m.stats()==[0]*8
  m.upload(model_slot(a.model),222);m.arm();m.process(0);assert m.stats()[0]==0
  integrated.append(dict(buffer=size,blocks=1394,late_current_preserves_complete_previous=True,latch_until_restart=True,DSP_continues=True))
  print('full IRQ',size,'PASS',flush=True)
 a.report.write_text(json.dumps(dict(status='PASS_OFFLINE_DMA_GUARD',identity='NAMDMP02',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),
  unit_cases=rows,integrated=integrated,device_access=False,host_audio_access=False,flash_container_created=False,
  physical_deadline_proven=False,limitations=['Synthetic counters and stationary or injected DMA cursors, not a bus timing proof',
  'A transaction exceeding the assumed store budget is detected after writes and cannot be undone',
  'Fast-to-fallback transition can repeat one block; this is not a seamless latency transition',
  'Early prefill rejection leaves the old whole half in place; future eligible callbacks retry the fallback']),indent=2)+'\n')
if __name__=='__main__':main()
