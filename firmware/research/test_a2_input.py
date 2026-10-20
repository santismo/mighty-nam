#!/usr/bin/env python3
"""Silent live-input firmware regression. No physical device or playback APIs."""
import argparse,json,struct,zlib,hashlib,time
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
import candidate_vm as v
from a2_input_image import build
from a2_storage import SLOT_OFFSET,SLOT_SIZE,HEADER_SIZE,BYTES
from a2_oracle import library,Engine
from test_a2_continuous import ContinuousMachine

class InputMachine(ContinuousMachine):
 def __init__(self,fill=0):
  self.rx_words=None
  super().__init__(fill)
 def meters(self):return list(struct.unpack('<6I',self.u.mem_read(v.sym['mpp_input'],24)))
 def callback(self,half=0):
  n=self.words()[8]
  raw=self.rx_words if self.rx_words is not None else [value for i in range(8) for value in [0x01020304+i,-0x02030405-i,0x11111111+i,(((n*8+i)&255)-128)*(1<<22)]]
  data=struct.pack('<32i',*raw);self.u.mem_write(0x20016800+128*half,data)
  super().callback(half)
  assert self.u.mem_read(0x20016800+128*half,128)==data
 def batch(self,index,half=0):
  self.field(3,59999+index);self.callback(half)
 def restart(self):
  self.rx_words=None
  super().restart()
 def accelerate(self):
  # Only the long mocked-DSP scheduling test uses these exact code hooks.
  # All MMIO/state guards remain active; startup and model accuracy use the
  # original per-instruction observation path.
  self.u.hook_del(self.code_hook)
  for pc in [0x15638,v.sym['_ZN3mpp6A2Lite7processEPKfPfj']&~1,0xae24,0xae80,0x117d8,0x10952,0x109ac]:
   self.u.hook_add(UC_HOOK_CODE,self.code,begin=pc,end=pc)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('elf',type=Path);p.add_argument('library');p.add_argument('models',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 start=time.monotonic();lib=library(a.library);cases=[];model_rows=[]
 def configure(model):v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,model))
 for model_path in a.models:
  configure(model_path);prefix=None
  for fill in [0,0xa5,0xff]:
   m=InputMachine(fill);assert m.words()[:9]==[0x4d504232,3,1,0,0,0,0,0,0]
   for channel in [0,1]:
    q=bytes.fromhex('f0435800f7')
    for split in range(6):assert m.ingress([q[:split],q[split:]],channel,start=2046)[0][0][4:12]==b'NAMA2I01'
    for page in range(32):assert m.page(page,channel)==(0,m.words()[page])
    for page,addr in enumerate([0x400ec000,0x400ec004,0x400ec010,0x400ec00c,0x40cc0700,0x40cc0720,0x40cc0724,0x40cc6800],48):assert m.page(page,channel)==(0,m.get(addr))
    for page in [62,63,127]:assert m.page(page,channel)==(1,0)
   for channel in [0,1]:
    for page in range(56,62):assert m.page(page,channel)==(0,0)
   m.callback();assert m.words()[8]==0 and m.service_calls==1
   oracle=Engine(lib,model_path);ys=[];error=0
   for i in range(16 if fill==0 else 2):
    m.batch(i,i%2);y=list(struct.unpack('<8f',m.u.mem_read(v.sym['mpp_bench_output'],32)))
    ref=oracle.run(m.inputs[-1]);error=max(error,max(abs(x-z) for x,z in zip(y,ref)));ys+=y
   assert error<2e-5 and max(map(abs,ys))>1e-6 and m.words()[9]==m.words()[16]==0
   if prefix is None:prefix=ys[:16]
   else:assert ys[:16]==prefix
   m.restart();m.batch(0);assert list(struct.unpack('<8f',m.u.mem_read(v.sym['mpp_bench_output'],32)))==prefix[:8]
   assert m.words()[8]==1 and m.words()[4]==0;m.guards();assert not m.mmio_writes
   model_rows.append({'model':model_path.name,'model_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),'fill':hex(fill),'max_reference_error':error,'cold_warm_output_identical':True})
   print(model_path.name,hex(fill),'model/boot/silent buffers PASS',flush=True)
  cases.append('Both transport selectors, split version packets, fixed pages, three cold fills and warm restarts: '+model_path.name)
 configure(a.models[0]);clean=v.candidate;m=InputMachine();m.mock_process=True;m.accelerate()
 # Every scheduled batch is consecutive after the initial warmup; no arbitrary
 # count manipulation is used for the stop-after-180000 assertion.
 for i in range(239999):m.callback(i%2)
 assert m.words()[8]==180000 and m.words()[17]==2 and m.service_calls==239999
 before=m.words()[8:32]
 for i in range(130):m.callback(i%2)
 assert m.words()[8:32]==before
 assert m.inputs==[[(float(((j*8+i)&255)-128))/512 for i in range(8)] for j in range(180000)]
 cases.append('Real callback schedule: 59,999 warmup callbacks, 180,000 consecutive live-input A2 batches, then stop; deterministic input')
 # Invalid pointers never touch the output or housekeeping.
 count=m.service_calls;before=bytes(m.u.mem_read(0x20016900,256))
 for pair in [(0,0),(0x20016800,0x20016980),(0x20016880,0x20016900),(0x20016800,0x20016904)]:m.call(0x14bfc,pair)
 assert m.service_calls==count and m.words()[4]==4 and m.u.mem_read(0x20016900,256)==before
 assert m.words()[17]==4
 runs=m.words()[8];m.callback();assert m.words()[8]==runs
 cases.append('Unexpected DMA pairs cannot write memory or invoke housekeeping')
 m=InputMachine();m.mock_process=True
 # Extremes and mixed channels through the real input converter and live path.
 m=InputMachine();m.mock_process=True
 edge=[-2147483648,2147483647,-1,0,1,-256,256,0x7f000000]
 for shift in range(8):
  m.restart();raw=[edge[(f+c+shift)%8] for f in range(8) for c in range(4)];m.rx_words=raw
  m.u.mem_write(0x20016800,struct.pack('<32i',*raw))
  m.call(0x14fd8,[0x20016800,0x20028000])
  stock=list(struct.unpack('<32f',m.u.mem_read(0x20028000,128)))
  m.batch(0)
  assert m.inputs[-1]==stock[24:32]
  assert m.meters()[:4]==[max(abs(raw[4*f+c]) for f in range(8)) for c in range(4)]
  assert m.meters()[4]==sum(abs(raw[4*f+3])>=0x7f000000 for f in range(8))
  assert m.meters()[5]==struct.unpack('<I',struct.pack('<f',stock[31]))[0]
  frozen=m.meters();m.field(17,2);m.rx_words=[0]*32;m.callback(1);assert m.meters()==frozen
  for page in range(56,62):assert m.page(page)==(0,frozen[page-56])
 m.restart();m.rx_words=[0]*32;m.batch(0);assert m.inputs[-1]==[0]*8 and m.meters()==[0]*6
 cases.append('Q31 extremes match the real stock converter bit for bit; slot 3 selection; four peak meters; clip count; completion freezes meters')
 clock_cases=[('normal',[100,200],[1,1],[1<<24]*2,False),('wrap',[0xfffffff0,0x30],[1,1],[1<<24]*2,False),('stopped',[100,100],[1,1],[1<<24]*2,True),('reverse',[100,90],[1,1],[1<<24]*2,True),('disabled',[100,200],[0,0],[1<<24]*2,True),('missing_counter',[100,200],[0x2000001]*2,[1<<24]*2,True),('changed_control',[100,200],[1,0],[1<<24]*2,True),('trace_disabled',[100,200],[1,1],[0,0],True),('trace_changed',[100,200],[1,1],[1<<24,0],True)]
 for label,cyc,ctrl,demcr,invalid in clock_cases:
  m.restart();m.cycle_pair=cyc;m.ctrl_pair=ctrl;m.demcr_pair=demcr;m.batch(0)
  assert m.words()[9]==int(invalid) and m.words()[8]==1,(label,m.words())
  if not invalid:assert m.words()[10:14]==[(cyc[1]-cyc[0])&0xffffffff]*4
 cases.append('Raw DWT checks: valid wrap and seven invalid counter/control cases')
 m.restart();m.cycle_pair=[100,200];m.ctrl_pair=[1,1];m.demcr_pair=[1<<24]*2;m.field(13,0xfffffff0);m.batch(0);assert m.words()[13:15]==[84,1]
 m.restart();m.mock_nan=True;m.batch(0);assert m.words()[16]==8 and m.words()[17]==3;m.batch(1);assert m.words()[8]==1
 cases.append('64-bit cycle sum carry; nonfinite model output stops further processing while output stays zero')
 # Independent timer-body bookkeeping and fail-closed guards.
 m=InputMachine();m.mock_process=True
 for ticks,invalid,limit in [(1,False,False),(149,False,False),(150,False,True),(99999,False,True),(0,True,False),(100000,True,False),(0xffffffff,True,False)]:
  m.restart();m.timer_ticks=ticks;m.batch(0)
  w=m.words();assert w[23]==invalid and w[29]==limit and w[24]==ticks,(ticks,w)
  assert w[17]==(4 if invalid or limit else 1)
  assert m.timer_writes==[(0x1166a,0x47),(0x11682,0x46)]
  if invalid or limit:m.batch(1,1);assert m.words()[8]==1
 for address,value in [(0x400ec000,0x47),(0x400ec004,22),(0x400ec00c,0),(0x400ec010,99999),(0x2000e48c,25000000)]:
  m.restart();m.put(address,value);m.batch(0)
  assert m.words()[8]==0 and m.words()[23]==1 and m.words()[17]==4 and not m.timer_writes
 m.restart();m.stop_control=0x47;m.batch(0);assert m.words()[17]==4 and m.words()[23]==1
 m.restart();m.field(27,0xfffffff0);m.batch(0);assert m.words()[27:29]==[64,1]
 m.restart();m.batch(0,0);m.batch(1,0);assert m.words()[22]==1 and m.words()[17]==4
 m.batch(2,1);assert m.words()[8]==2
 cases.append('GPT1 zero/wrapped/over-limit/configuration faults stop DSP; 150-tick limit; sum carry; repeated half stops DSP')
 for label,status in [('header',1),('crc',2),('nan_weights',3)]:
  b=bytearray(clean)
  if label=='header':b[SLOT_OFFSET]=0
  elif label=='crc':b[SLOT_OFFSET+HEADER_SIZE+200]^=1
  else:
   struct.pack_into('<I',b,SLOT_OFFSET+HEADER_SIZE+16,0x7fc00000)
   struct.pack_into('<I',b,SLOT_OFFSET+20,zlib.crc32(b[SLOT_OFFSET+HEADER_SIZE:SLOT_OFFSET+HEADER_SIZE+BYTES]))
  v.candidate=bytes(b);m=InputMachine(0xa5);m.batch(0);assert m.words()[7]==status and m.words()[17]==3 and m.words()[8]==0 and m.words()[2]==1
  assert m.ingress([bytes.fromhex('f0435800f7')])[0][0][4:12]==b'NAMA2I01'
 cases.append('Bad header, CRC and CRC-valid NaN weights leave status responsive and outputs zero')
 v.candidate=clean;m=InputMachine();m.mock_process=True
 # Actual stock IRQ acknowledgement/selection remains intact with the new code.
 m.field(3,59999)
 for half in [0,1]:
  m.put(0x40071018,0x20016aa0+32*half);m.put(0x4007101c,0);m.put(0x4007121c,0);m.put(0x40070024,0x10001);m.put(0x4007002c,0);m.u.mem_write(0x4007001f,b'\xff');m.put(0x200147c8,100)
  m.u.mem_write(0x20016900,b'\xa5'*256);m.run(0x11d94)
  assert m.u.mem_read(0x20016900+128*half,128)==bytes(128) and m.get(0x200147c8)==108 and m.u.mem_read(0x4007001f,1)==b'\x10'
 assert m.words()[8]==2 and m.words()[22]==0 and len(m.timer_writes)==4
 assert not m.mmio_writes;m.guards();cases.append('Saved stock DMA ISR processes both consecutive halves, preserves ACK and sample count')
 report={'status':'PASS_OFFLINE_BOUNDED_A2_LIVE_INPUT','elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),'cases':cases,'model_runs':model_rows,'physical_device_access':False,'audio_playback':False,'hardware_cycles_measured':False,'wall_seconds':time.monotonic()-start,'limits':['A15 compatibility executes the unchanged A2 floating-point code; real M7 timing/cache/interrupts are not simulated.','DWT values are synthetic. Concurrent counter resets are not comprehensively detected.','ADC/LED helpers and USB transmitter are intercepted.','A2 executes for accuracy cases; the long scheduling and fault cases substitute its output to test the wrapper cheaply.','Power-up transients and electrical silence are unmeasured.','GPT1 values are synthetic, and half alternation cannot detect an even number of lost releases. No hardware timing is established by this emulator.']}
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'case_groups':len(cases),'model_runs':len(model_rows),'wall_seconds':report['wall_seconds']}),flush=True)
if __name__=='__main__':main()
