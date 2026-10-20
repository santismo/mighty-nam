#!/usr/bin/env python3
"""Exercise the bounded silent A2 screen, not hardware timing. No device APIs."""
import argparse,json,struct,zlib,hashlib,time
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
import candidate_vm as v
from a2_benchmark_image import build
from a2_storage import SLOT_OFFSET,SLOT_SIZE,HEADER_SIZE,BYTES
from a2_oracle import library,Engine
from test_stock_probe import ProbeMachine,REGISTERS

class BenchMachine(ProbeMachine):
 def __init__(self,fill=0):
  self.messages=[];self.mmio_writes=[];self.reads=[];self.ingress_lengths=[]
  self.mock_process=False;self.mock_nan=False;self.inputs=[];self.service_calls=0
  self.cycle_pair=[100,200];self.ctrl_pair=[1,1];self.demcr_pair=[1<<24,1<<24];self.clock_reads={}
  v.Machine.__init__(self,fill)
  self.u.mem_map(0x30040000,(len(v.candidate)+4095)&~4095);self.u.mem_write(0x30040000,v.candidate)
  self.u.mem_protect(0x30040000,(len(v.candidate)+4095)&~4095,UC_PROT_READ)
  self.u.mem_map(0x40000000,0x1000000);self.u.mem_map(0xe0000000,0x100000)
  for addr,value in zip(REGISTERS,[0x411fc272,0x70210,5,0x53,0x53,0,0xaa03,0,0x400,0x400,0,0x200060a6,0,0xf00000,0x2520,0x2520]):self.put(addr,value)
  self.u.hook_add(UC_HOOK_MEM_WRITE,self.peripheral_write,begin=0x40000000,end=0x4007001e)
  self.u.hook_add(UC_HOOK_MEM_WRITE,self.peripheral_write,begin=0x40070020,end=0x40ffffff)
  self.u.hook_add(UC_HOOK_MEM_WRITE,self.peripheral_write,begin=0xe0000000,end=0xe00fffff)
  self.u.hook_add(UC_HOOK_MEM_READ,self.read_register,begin=0x40000000,end=0x40ffffff)
  self.u.hook_add(UC_HOOK_MEM_READ,self.read_register,begin=0xe0000000,end=0xe00fffff)
  self.boot(unity_fades=False);self.phase='probe';self.run(0xac1e)
 def code(self,u,pc,size,unused):
  if self.phase=='probe' and pc==0x15638:self.service_calls+=1
  if self.phase=='probe' and pc==(v.sym['_ZN3mpp6A2Lite7processEPKfPfj']&~1):
   inp,out,n=[u.reg_read(x) for x in v.R[1:]];assert n==8
   self.inputs.append(list(struct.unpack('<8f',u.mem_read(inp,32))))
   if self.mock_process:
    u.mem_write(out,struct.pack('<8f',*([float('nan') if self.mock_nan else .125]*8)))
    u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  super().code(u,pc,size,unused)
 def read_register(self,u,access,address,size,value,unused):
  if address in [0xe0001000,0xe0001004,0xe000edfc]:
   pair={0xe0001000:self.ctrl_pair,0xe0001004:self.cycle_pair,0xe000edfc:self.demcr_pair}[address]
   i=self.clock_reads.get(address,0);self.clock_reads[address]=i+1;self.put(address,pair[i%2]);return
  super().read_register(u,access,address,size,value,unused)
 def words(self):return list(struct.unpack('<23I',self.u.mem_read(v.sym['mpp_bench'],92)))
 def field(self,n,value):self.put(v.sym['mpp_bench']+4*n,value)
 def callback(self,half=0):
  self.u.mem_write(0x20016900,b'\xa5'*256);self.clock_reads={}
  self.call(0x14bfc,[0x20016800+128*half,0x20016900+128*half])
  assert self.u.mem_read(0x20016900+128*half,128)==bytes(128)
  assert self.u.mem_read(0x20016900+128*(1-half),128)==b'\xa5'*128
 def batch(self,index,half=0):
  self.field(3,6015+64*index);self.callback(half)
 def restart(self):
  self.u.mem_write(v.state_start,b'\x5a'*(v.state_end-v.state_start))
  self.boot(unity_fades=False);self.phase='probe';self.run(0xac1e);self.inputs=[]

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('elf',type=Path);p.add_argument('library');p.add_argument('models',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 start=time.monotonic();lib=library(a.library);cases=[];model_rows=[]
 def configure(model):v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,model))
 for model_path in a.models:
  configure(model_path);prefix=None
  for fill in [0,0xa5,0xff]:
   m=BenchMachine(fill);assert m.words()[:9]==[0x4d504232,1,1,0,0,0,0,0,0]
   for channel in [0,1]:
    q=bytes.fromhex('f0435800f7')
    for split in range(6):assert m.ingress([q[:split],q[split:]],channel,start=2046)[0][0][4:12]==b'NAMA2B01'
    for page in range(23):assert m.page(page,channel)==(0,m.words()[page])
    for page in [23,24,31,48,127]:assert m.page(page,channel)==(1,0)
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
   model_rows.append({'model':model_path.name,'fill':hex(fill),'max_reference_error':error,'cold_warm_output_identical':True})
   print(model_path.name,hex(fill),'model/boot/silent buffers PASS',flush=True)
  cases.append('Both transport selectors, split version packets, fixed pages, three cold fills and warm restarts: '+model_path.name)
 configure(a.models[0]);clean=v.candidate;m=BenchMachine();m.mock_process=True
 # Every scheduled batch is bounded, with idle callbacks between; no arbitrary
 # count manipulation is used for the stop-after-512 assertion.
 for i in range(38720):m.callback(i%2)
 assert m.words()[8]==512 and m.words()[17]==2 and m.service_calls==38720
 before=m.words()[8:23]
 for i in range(130):m.callback(i%2)
 assert m.words()[8:23]==before
 assert m.inputs==[[(float(((j*8+i)&255)-128))/512 for i in range(8)] for j in range(512)]
 cases.append('Real callback schedule: warmup, 64-callback spacing, 512 batches then stop; deterministic nonzero input')
 # Invalid pointers never touch the output or housekeeping.
 count=m.service_calls;before=bytes(m.u.mem_read(0x20016900,256))
 for pair in [(0,0),(0x20016800,0x20016980),(0x20016880,0x20016900),(0x20016800,0x20016904)]:m.call(0x14bfc,pair)
 assert m.service_calls==count and m.words()[4]==4 and m.u.mem_read(0x20016900,256)==before
 cases.append('Unexpected DMA pairs cannot write memory or invoke housekeeping')
 clock_cases=[('normal',[100,200],[1,1],[1<<24]*2,False),('wrap',[0xfffffff0,0x30],[1,1],[1<<24]*2,False),('stopped',[100,100],[1,1],[1<<24]*2,True),('reverse',[100,90],[1,1],[1<<24]*2,True),('disabled',[100,200],[0,0],[1<<24]*2,True),('missing_counter',[100,200],[0x2000001]*2,[1<<24]*2,True),('changed_control',[100,200],[1,0],[1<<24]*2,True),('trace_disabled',[100,200],[1,1],[0,0],True),('trace_changed',[100,200],[1,1],[1<<24,0],True)]
 for label,cyc,ctrl,demcr,invalid in clock_cases:
  m.restart();m.cycle_pair=cyc;m.ctrl_pair=ctrl;m.demcr_pair=demcr;m.batch(0)
  assert m.words()[9]==int(invalid) and m.words()[8]==1,(label,m.words())
  if not invalid:assert m.words()[10:14]==[(cyc[1]-cyc[0])&0xffffffff]*4
 cases.append('Raw DWT checks: valid wrap and seven invalid counter/control cases')
 m.restart();m.cycle_pair=[100,200];m.ctrl_pair=[1,1];m.demcr_pair=[1<<24]*2;m.field(13,0xfffffff0);m.batch(0);assert m.words()[13:15]==[84,1]
 m.restart();m.mock_nan=True;m.batch(0);assert m.words()[16]==8 and m.words()[17]==3;m.batch(1);assert m.words()[8]==1
 cases.append('64-bit cycle sum carry; nonfinite model output stops further processing while output stays zero')
 for label,status in [('header',1),('crc',2),('nan_weights',3)]:
  b=bytearray(clean)
  if label=='header':b[SLOT_OFFSET]=0
  elif label=='crc':b[SLOT_OFFSET+HEADER_SIZE+200]^=1
  else:
   struct.pack_into('<I',b,SLOT_OFFSET+HEADER_SIZE+16,0x7fc00000)
   struct.pack_into('<I',b,SLOT_OFFSET+20,zlib.crc32(b[SLOT_OFFSET+HEADER_SIZE:SLOT_OFFSET+HEADER_SIZE+BYTES]))
  v.candidate=bytes(b);m=BenchMachine(0xa5);m.batch(0);assert m.words()[7]==status and m.words()[17]==3 and m.words()[8]==0 and m.words()[2]==1
  assert m.ingress([bytes.fromhex('f0435800f7')])[0][0][4:12]==b'NAMA2B01'
 cases.append('Bad header, CRC and CRC-valid NaN weights leave status responsive and outputs zero')
 v.candidate=clean;m=BenchMachine();m.mock_process=True
 # Actual stock IRQ acknowledgement/selection remains intact with the new code.
 for half in [0,1]:
  m.put(0x40071018,0x20016aa0+32*half);m.put(0x4007101c,0);m.put(0x4007121c,0);m.put(0x40070024,0x10001);m.put(0x4007002c,0);m.u.mem_write(0x4007001f,b'\xff');m.put(0x200147c8,100)
  m.u.mem_write(0x20016900,b'\xa5'*256);m.run(0x11d94)
  assert m.u.mem_read(0x20016900+128*half,128)==bytes(128) and m.get(0x200147c8)==108 and m.u.mem_read(0x4007001f,1)==b'\x10'
 assert not m.mmio_writes;m.guards();cases.append('Saved stock DMA ISR selects both halves, preserves ACK and sample count')
 report={'status':'PASS_OFFLINE_BOUNDED_A2_BENCHMARK','elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),'cases':cases,'model_runs':model_rows,'physical_device_access':False,'audio_playback':False,'hardware_cycles_measured':False,'wall_seconds':time.monotonic()-start,'limits':['A15 compatibility executes the unchanged A2 floating-point code; real M7 timing/cache/interrupts are not simulated.','DWT values are synthetic. Concurrent counter resets are not comprehensively detected.','ADC/LED helpers and USB transmitter are intercepted.','A2 executes for accuracy cases; the long scheduling and fault cases substitute its output to test the wrapper cheaply.','Power-up transients and electrical silence are unmeasured.','This cost screen is sparse; it cannot prove continuous eight-frame deadlines or detect every missed DMA release.']}
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'case_groups':len(cases),'model_runs':len(model_rows),'wall_seconds':report['wall_seconds']}),flush=True)
if __name__=='__main__':main()
