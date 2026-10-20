#!/usr/bin/env python3
"""M7 timing-hook ABI and synthetic-counter tests; never accesses hardware."""
import argparse,hashlib,json,random,struct
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
from link_image import build,elf_identity
from test_link_stock_chain import ChainMachine,v

p=argparse.ArgumentParser(description=__doc__)
for key in ['payload','elf','output']:p.add_argument(key,type=Path)
a=p.parse_args()
identity=elf_identity(a.elf);assert identity in ['NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09']
image,sym,plan=build(a.payload.read_bytes(),a.elf,identity)
STOP=0x3fffc;SP=0x20035f00;DWT=0xe0001000
state=sym['mpp_irq_stats'];epoch=sym['mpp_dwt_reset_epoch']
snapshot=sym['mpp_irq_snapshot_words']
def get(u,addr):return struct.unpack('<I',u.mem_read(addr,4))[0]
def put(u,addr,val):u.mem_write(addr,struct.pack('<I',val&0xffffffff))
def stats(u):return list(struct.unpack('<10I',u.mem_read(state,40)))
def call(u,addr,args=()):
 for reg,val in zip([UC_ARM_REG_R0,UC_ARM_REG_R1],args):u.reg_write(reg,val)
 u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,STOP|1)
 u.emu_start(addr|1,STOP,count=100000)
 assert u.reg_read(UC_ARM_REG_PC)==STOP and u.reg_read(UC_ARM_REG_SP)==SP
def setup():
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
 for addr,size in [(0,0x40000),(0x20000000,0x40000),(0x202e4000,0x38000),
                   (0x40070000,0x2000),(DWT,0x1000)]:u.mem_map(addr,size)
 u.mem_write(0,image[:0x2356c])
 # Real status helper sees both pending channels; real ISR acknowledges them.
 put(u,0x40070024,0x10001);put(u,0x4007002c,0)
 put(u,DWT,1)
 return u
rows=[]
def trial(label,start=100,end=1000,ctrl=1,after=1,reset=False,initial=None,half=0,flags=0):
 u=setup()
 if initial:u.mem_write(state,struct.pack('<10I',*initial))
 put(u,DWT,ctrl);put(u,0x40071018,0x20016aa0+32*half)
 put(u,0x200147c8,100)
 reads=[];callbacks=[];writes=[]
 def read(uc,access,addr,size,value,user):
  value=[start,end][len(reads)];reads.append(value);put(uc,DWT+4,value)
 def body(uc,pc,size,user):
  callbacks.append([uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)])
  put(uc,DWT,after)
  if reset:put(uc,epoch,get(uc,epoch)+1)
  uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def write(uc,access,addr,size,value,user):writes.append((addr,size,value))
 u.hook_add(UC_HOOK_MEM_READ,read,begin=DWT+4,end=DWT+7)
 u.hook_add(UC_HOOK_CODE,body,begin=0x14bfc,end=0x14bfc)
 u.hook_add(UC_HOOK_MEM_WRITE,write,begin=DWT,end=DWT+0xfff)
 saved={reg:0x20010000+i*16 for i,reg in enumerate(range(UC_ARM_REG_R4,UC_ARM_REG_R11+1))}
 for reg,val in saved.items():u.reg_write(reg,val)
 call(u,0x205a4)
 assert all(u.reg_read(k)==x for k,x in saved.items())
 assert callbacks==[[0x20016800+128*half,0x20016900+128*half]]
 assert get(u,0x200147c8)==108 and bytes(u.mem_read(0x4007001f,1))==b'\x10'
 assert not writes and len(reads)==2
 s=stats(u);assert s[3]==flags,(label,s)
 if flags:
  assert s[1]==(initial or [0]*10)[1]
  assert s[2]==min(0xffffffff,(initial or [0]*10)[2]+1)
 else:
  assert s[1]==(initial or [0]*10)[1]+1 and s[4]==(end-start)&0xffffffff
  assert s[5]==max((initial or [0]*10)[5],s[4])
 assert s[0]==((initial or [0]*10)[0]+2)&0xffffffff
 rows.append(label)
 return u
trial('ordinary whole stock IRQ body, DMA half0')
trial('DMA half1',half=1)
trial('32-bit DWT wrap',start=0xfffffff0,end=400)
trial('disabled DWT',ctrl=0,after=0,flags=1)
trial('CTRL changed during handler',after=3,flags=1)
trial('known reset with plausible positive duration',start=10,end=20,reset=True,flags=2)
trial('stalled counter',end=100,flags=4)
trial('ambiguous long span',end=0x80000064,flags=4)
trial('accepted count saturation',initial=[0,0xffffffff,0,0,0,0,0,0,0,0],flags=8)
trial('rejected count saturation',initial=[0,0,0xffffffff,0,0,0,0,0,0,0],flags=8)
trial('publication sequence wrap',initial=[0xfffffffe]+[0]*9)
trial('same maximum still increments accepted count',initial=[2,1,0,0,900,900,1,1,0,0])
trial('lower duration retains previous maximum',initial=[2,1,0,0,2000,2000,1,1,0,0])
rng=random.Random(6006)
for i in range(128):
 start=rng.randrange(2**32);trial('random wrap '+str(i),start,(start+rng.randrange(1,100000))&0xffffffff)
# Execute the actual replacement BL/displaced instructions, preserve live regs/flags.
u=setup();put(u,epoch,0xffffffff);put(u,DWT+4,567)
regs={r:0x12340000+i for i,r in enumerate(range(UC_ARM_REG_R0,UC_ARM_REG_R12+1))}
regs[UC_ARM_REG_R5]=0;regs[UC_ARM_REG_R6]=DWT
for reg,val in regs.items():u.reg_write(reg,val)
u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_APSR,0xa0000000)
u.emu_start(0xbe49,0xbe4c,count=1000)
assert u.reg_read(UC_ARM_REG_PC)==0xbe4c and u.reg_read(UC_ARM_REG_SP)==SP
assert all(u.reg_read(k)==val for k,val in regs.items() if k!=UC_ARM_REG_R3)
assert u.reg_read(UC_ARM_REG_R3)==1 and get(u,DWT+4)==0 and get(u,epoch)==0
assert u.reg_read(UC_ARM_REG_APSR)&0xf0000000==0xa0000000
rows.append('stock reset BL preserves displaced behavior, live regs, flags; epoch wrap')
# Snapshot before capture, freeze, interleaved publication/retry, bounded busy.
u=trial('snapshot source')
out=0x20030000
call(u,sym['mpp_irq_page'],[13,out]);assert u.reg_read(UC_ARM_REG_R0)==3
call(u,sym['mpp_irq_page'],[12,out]);assert u.reg_read(UC_ARM_REG_R0)==0 and get(u,out)==0x54494d31
frozen=stats(u)
put(u,state+4,1000)
for i,expected in enumerate(frozen):
 call(u,sym['mpp_irq_page'],[13+i,out]);assert u.reg_read(UC_ARM_REG_R0)==0 and get(u,out)==expected
for pg in [0,11,23,127,0xffffffff]:
 call(u,sym['mpp_irq_page'],[pg,out]);assert u.reg_read(UC_ARM_REG_R0)==1
for interrupts in [1,3]:
 calls=[0]
 def preempt(uc,access,addr,size,value,user):
  if calls[0]<interrupts:
   calls[0]+=1;put(uc,state,get(uc,state)+2);put(uc,state+4,get(uc,state+4)+1)
 h=u.hook_add(UC_HOOK_MEM_READ,preempt,begin=state+8,end=state+11)
 call(u,sym['mpp_irq_page'],[12,out]);u.hook_del(h)
 assert calls[0]==interrupts and u.reg_read(UC_ARM_REG_R0)==(0 if interrupts==1 else 2)
 if interrupts==1:assert list(struct.unpack('<10I',u.mem_read(snapshot,40)))==stats(u)
 else:
  call(u,sym['mpp_irq_page'],[13,out]);assert u.reg_read(UC_ARM_REG_R0)==3
rows.append('snapshot immutable; preemption retries; bounded busy and unsupported errors')
# Real stock runtime and private page transport, including poisoned warm starts.
v.configure(a.payload,True,candidate_bundle=(image,sym,plan))
for fill in [0,0xa5,0xff]:
 m=ChainMachine(fill=fill)
 assert stats(m.u)==[0]*10 and get(m.u,epoch)==0
 assert m.page(13)==(3,0)
 assert m.page(12)==(0,0x54494d31)
 for i in range(10):assert m.page(13+i)==(0,0)
 for i in range(12):assert m.page(i)==(0,m.words()[i])
 for i in range(25 if identity=='NAMLNK09' else (24 if identity in ('NAMLNK07','NAMLNK08') else 23),128):assert m.page(i)==(1,0)
 if identity in ('NAMLNK07','NAMLNK08','NAMLNK09'):assert m.page(23)==(0,2)
 values=[0xfffffffe,123,4,2,0x12345678,0x7fffffff,0x40000001,0x40000001,17,17]
 m.u.mem_write(state,struct.pack('<10I',*values))
 assert m.page(12)==(0,0x54494d31)
 m.put(state+4,456) # latched pages must not follow live counters
 for ch in [0,1]:
  for i,value in enumerate(values):assert m.page(13+i,ch)==(0,value)
 m.u.mem_write(state,b'\xa5'*40);put(m.u,epoch,123)
 m.restart()
 assert stats(m.u)==[0]*10 and get(m.u,epoch)==0 and m.page(13)==(3,0)
 m.guards()
rows.append('three cold patterns and warm starts clear telemetry; both status ranges bounded')
report={'status':'PASS_'+identity+'_IRQ_TIMING_OFFLINE','identity':identity,
 'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),'cases':len(rows),'named_cases':[r for r in rows if not r.startswith('random wrap')],
 'random_wrap_cases':128,'stock_IRQ_body_and_status_helper_executed':True,
 'model_callback_stubbed_in_M7_ABI_cases':True,'stock_DMA_ack_preserved':True,
 'raw_counter_synthetic':True,'timer_writes_by_capture':0,'known_reset_behavior_preserved':True,
 'snapshot_coherent_and_bounded':True,'physical_device_access':False,'audio_playback':False,
 'candidate_plan':plan,'limits':['No real CPU timing, exception entry/return or DMA release latency measured.',
 'Only the identified stock delay reset writer is instrumented; unknown positive counter discontinuities cannot be ruled out.',
 'The new wrapper excludes its own pre-timestamp prologue and post-timestamp accounting.']}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','cases','snapshot_coherent_and_bounded']}))
