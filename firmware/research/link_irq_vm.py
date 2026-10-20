"""Whole software IRQ path with synthetic counters, stock DMA status and real DSP."""
from unicorn import UC_HOOK_MEM_READ
from test_link_stock_chain import ChainMachine,v

class IrqChainMachine(ChainMachine):
 def __init__(self,*args,**kwargs):
  self.synthetic_cycle=1000;self.irq_calls=0
  super().__init__(*args,**kwargs)
  self.put(0xe0001000,1)
  self.put(0x40070024,0x10001);self.put(0x4007002c,0)
  self.u.hook_add(UC_HOOK_MEM_READ,self.cycle_read,begin=0xe0001004,end=0xe0001007)
 def cycle_read(self,u,access,addr,size,value,unused):
  # Explicit fixture, unrelated to executed instructions or actual clock speed.
  self.synthetic_cycle=(self.synthetic_cycle+1000)&0xffffffff
  self.put(addr,self.synthetic_cycle)
 def call(self,entry,args):
  if entry==0x14bfc and len(args)==2 and args[0] in [0x20016800,0x20016880]:
   half=(args[0]-0x20016800)//128
   assert args[1]==0x20016900+128*half
   self.put(0x40071018,0x20016aa0+32*half)
   old=self.get(0x200147c8);count=self.get(v.sym['mpp_irq_stats']+4)
   self.put(0xe000ed04,16)
   try:self.run(0x205a4)
   finally:self.put(0xe000ed04,0)
   assert self.get(0x200147c8)==(old+8)&0xffffffff
   assert self.u.mem_read(0x4007001f,1)==b'\x10'
   assert self.get(v.sym['mpp_irq_stats']+4)==count+1,(
    count,[self.get(v.sym['mpp_irq_stats']+4*i) for i in range(10)],
    hex(self.get(0xe0001000)),self.get(v.sym['mpp_dwt_reset_epoch']))
   assert self.get(v.sym['mpp_irq_stats']+8)==0
   self.irq_calls+=1
  else:super().call(entry,args)
