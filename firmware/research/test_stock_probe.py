#!/usr/bin/env python3
"""Execute the diagnostic through saved stock init, dispatcher and DMA IRQ.
Peripheral setup and the final USB transmitter are intercepted, not modeled.
No physical device APIs or audio playback.
"""
import argparse,hashlib,json,struct,random
from pathlib import Path
from unicorn import *
from unicorn.arm_const import *
import candidate_vm as v
from stock_probe_image import build

REGISTERS=[0xe000ed00,0xe000ed14,0xe000ed94,0xe000ef90,0xe000ef94,
 0x400e4048,0x400e4040,0x400e4044,0x40cc0000,0x40cc0020,0x40cc0024,
 0x40c84200,0xe000ed08,0xe000ed88,0x40038000,0x40c10000]
VALUES=[0x411fc272,0x30010,0,0x39,0x39,0x00aa0000,7,0x55aaaa55,
 0x400,0x400,0,0x2000e0c8,0,0xf00000,0x2420,0x2420]

class ProbeMachine(v.Machine):
 def __init__(self,fill):
  self.messages=[];self.mmio_writes=[];self.reads=[];self.ingress_lengths=[]
  super().__init__(fill)
  self.u.mem_map(0x40000000,0x1000000);self.u.mem_map(0xe0000000,0x100000)
  for addr,value in zip(REGISTERS,VALUES):self.put(addr,value)
  # This Unicorn build corrupts Thumb IT state when a write callback watches
  # the stock conditional DMA ACK. Exclude that byte and verify its final
  # value separately; no change is made to stock IRQ instructions.
  self.u.hook_add(UC_HOOK_MEM_WRITE,self.peripheral_write,begin=0x40000000,end=0x4007001e)
  self.u.hook_add(UC_HOOK_MEM_WRITE,self.peripheral_write,begin=0x40070020,end=0x40ffffff)
  self.u.hook_add(UC_HOOK_MEM_WRITE,self.peripheral_write,begin=0xe0000000,end=0xe00fffff)
  self.u.hook_add(UC_HOOK_MEM_READ,self.read_register,begin=0x40000000,end=0x40ffffff)
  self.u.hook_add(UC_HOOK_MEM_READ,self.read_register,begin=0xe0000000,end=0xe00fffff)
  self.boot(unity_fades=False)
  self.phase='probe';self.run(0xac1e)
 def code(self,u,pc,size,unused):
  if pc==0xae24 and self.phase=='probe':self.ingress_lengths.append(u.reg_read(UC_ARM_REG_R1))
  if pc==0xae80 and self.phase=='probe':
   data,n,channel=[u.reg_read(r) for r in v.R[:3]]
   assert n in (15,45)
   self.messages.append((bytes(u.mem_read(data,n)),channel))
   u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  # Keep the actual stock service timers/button-hold tick, but intercept its
  # ADC and LED helpers. This CPU harness has no physical ADC/GPIO behavior.
  if self.phase=='probe' and pc in [0x117d8,0x10952,0x109ac]:
   u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  if self.phase in ('runtime','boot'):super().code(u,pc,size,unused)
 def peripheral_write(self,u,access,address,size,value,unused):
  self.mmio_writes.append((address,size,value))
  raise AssertionError(('unexpected MMIO write',hex(address),size,value))
 def read_register(self,u,access,address,size,value,unused):
  self.reads.append(address)
  assert address in REGISTERS or (self.phase=='probe' and address in [0x40071018,0x4007101c,0x4007121c,0x40070024,0x4007002c]),(hex(address),hex(u.reg_read(UC_ARM_REG_PC)))
 def words(self):return list(struct.unpack('<23I',self.u.mem_read(v.sym['mpp_probe'],92)))
 def call(self,entry,args):
  for reg,value in zip(v.R,args):self.u.reg_write(reg,value)
  self.run(entry)
 def query(self,request,channel=1,entry=0xae24,length=None):
  before=len(self.messages);self.u.mem_write(0x20030000,bytes(request))
  self.call(entry,[0x20030000,len(request)-1 if length is None else length,channel])
  return self.messages[before:]
 def ingress(self,chunks,channel=1,start=0):
  """Run the saved stock receive-ring assembler, including F7 handling."""
  assert 0<=start<2048
  ring=0x20031000;self.u.mem_write(ring,struct.pack('<III',start,start,0)+bytes(2048))
  before=len(self.messages)
  for chunk in chunks:
   assert len(chunk)<2048
   write=self.get(ring);assert write==self.get(ring+4)
   for byte in chunk:
    self.u.mem_write(ring+12+write,bytes([byte]));write=(write+1)%2048
   self.put(ring,write);self.call(0xbd50,[ring,channel])
   assert self.get(ring+4)==write
  return self.messages[before:]
 def page(self,page,channel=1):
  request=bytes([0xf0,0x43,0x58,0x70,4,2,ord('N'),ord('P'),page,0xf7])
  rows=self.query(request,channel);assert len(rows)==1
  msg,ch=rows[0];assert ch==channel and msg[:6]==bytes([0xf0,0x43,0x58,0x70,4,2]) and msg[-1]==0xf7
  body=msg[6:14];assert body[:2]==bytes([1,page]) and max(body)<128
  assert body[7]<16
  return body[2],sum(body[3+i]<<(i*7) for i in range(5))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('elf',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 bundle=build(a.payload.read_bytes(),a.elf);v.configure(a.payload,True,candidate_bundle=bundle)
 cases=[]
 for fill in [0,0xa5,0xff]:
  m=ProbeMachine(fill);assert m.words()==[0x4d505031,1,1,0,0,0,0]+VALUES
  assert not m.mmio_writes;m.guards();cases.append('cold initialization fill '+hex(fill))
  for channel in [0,1]:
   rows=m.query(bytes.fromhex('f0435800f7'),channel);assert len(rows)==1
   msg,ch=rows[0];assert len(msg)==45 and ch==channel and msg[4:12]==b'NAMPB002' and msg[36:44]==b'PLUGPRO\0'
   for page,value in enumerate(m.words()):assert m.page(page,channel)==(0,value)
   for page,value in enumerate(VALUES,32):assert m.page(page,channel)==(0,value)
  cases.append('real stock version and private dispatch, both transport selectors '+hex(fill))
  for channel in [0,1]:
   version=bytes.fromhex('f0435800f7');query=bytes.fromhex('f043587004024e5000f7')
   for request in [version,query]:
    for split in range(len(request)+1):
     rows=m.ingress([request[:split],request[split:]],channel,start=2045)
     assert len(rows)==1 and rows[0][1]==channel
     assert m.ingress_lengths[-1]==len(request)-1
     if request==version:assert rows[0][0][4:12]==b'NAMPB002'
     else:assert rows[0][0][:9]==bytes.fromhex('f04358700402010000')
   assert not m.ingress([version[:-1]],channel)
   rows=m.ingress([version+query+version],channel)
   assert len(rows)==3 and [len(x[0]) for x in rows]==[45,15,45]
  cases.append('actual receive-ring ingress: both channels, every split, wrap, incomplete and concatenated messages '+hex(fill))
  # Every reserved page produces a bounded explicit unsupported response.
  for page in range(23,128):
   if 32<=page<48:continue
   assert m.page(page)==(1,0)
  cases.append('reserved pages rejected '+hex(fill))
  # Stored initialization snapshots stay fixed; live register pages change.
  for i,address in enumerate(REGISTERS):
   m.put(address,0xffffffff);assert m.page(i+7)==(0,VALUES[i]);assert m.page(32+i)==(0,0xffffffff)
  cases.append('snapshot versus live reads and full 32-bit wire range '+hex(fill))
  for half in range(2):
   m.u.mem_write(0x200167f0,b'\x71'*16+bytes(range(256))+b'\xa7'*256+b'\x72'*16)
   before=bytes(m.u.mem_read(0x200167f0,544));m.put(0x40071018,0x20016aa0+32*half)
   m.put(0x4007101c,0);m.put(0x4007121c,0);m.put(0x40070024,0x10001);m.put(0x4007002c,0)
   m.u.mem_write(0x4007001f,b'\xff')
   m.put(0x200147c8,100);m.run(0x11d94)
   after=bytes(m.u.mem_read(0x200167f0,544));expected=bytearray(before);start=272+128*half;expected[start:start+128]=bytes(128)
   assert after==expected and m.get(0x200147c8)==108
   assert m.u.mem_read(0x4007001f,1)==b'\x10'
   assert m.words()[5:7]==[0x20016800+128*half,0x20016900+128*half]
  assert m.words()[3]==2 and m.words()[4]==0;m.guards()
  cases.append('actual stock IRQ selects both zeroed 128-byte halves, ack preserved '+hex(fill))
  for args in [[0,0],[0x20016800,0x20016980],[0x20016880,0x20016900],[0x20016800,0x20016904]]:
   before=bytes(m.u.mem_read(0x200167f0,544));m.call(v.sym['mpp_probe_audio'],args)
   assert bytes(m.u.mem_read(0x200167f0,544))==before
  assert m.words()[4]==4 and m.words()[3]==2
  cases.append('unexpected DMA pointers cannot write memory '+hex(fill))
  # Counters saturate rather than silently wrap.
  m.put(v.sym['mpp_probe']+3*4,0xffffffff);m.put(v.sym['mpp_probe']+4*4,0xffffffff)
  m.call(v.sym['mpp_probe_audio'],[0x20016800,0x20016900]);m.call(v.sym['mpp_probe_audio'],[0,0])
  assert m.words()[3:5]==[0xffffffff,0xffffffff]
  cases.append('counter saturation '+hex(fill))
  # Warm runtime/init after poisoned state uses the same real stock path.
  m.u.mem_write(v.state_start,b'\x5a'*(v.state_end-v.state_start))
  for addr,value in zip(REGISTERS,VALUES):m.put(addr,value)
  m.boot(unity_fades=False);m.phase='probe';m.run(0xac1e)
  assert m.words()==[0x4d505031,1,1,0,0,0,0]+VALUES;m.guards()
  cases.append('warm stock initialization rebuilds probe and query bindings '+hex(fill))
 # Reject malformed requests by executing the new handler directly, avoiding
 # claims about bounds checks in the unchanged proprietary outer parser.
 m=ProbeMachine(0xa5);base=bytes.fromhex('f043587004024e5000f7');negative=0
 for length in list(range(9))+[10,11,255,0xffffffff]:
  assert not m.query(base,entry=v.sym['mpp_probe_query'],length=length);negative+=1
 for i in range(10):
  if i==8:continue
  for value in range(256):
   if value==base[i]:continue
   b=bytearray(base);b[i]=value
   assert not m.query(b,entry=v.sym['mpp_probe_query']);negative+=1
 for value in range(128,256):
  b=bytearray(base);b[8]=value;assert not m.query(b,entry=v.sym['mpp_probe_query']);negative+=1
 for channel in [2,127,0xffffffff]:assert not m.query(base,channel,entry=v.sym['mpp_probe_query']);negative+=1
 cases.append('malformed reads rejected: '+str(negative))
 # Write-side command 4 still reaches the unmodified stock default.
 q=bytearray(base);q[5]=1;rows=m.query(q);assert len(rows)==1 and rows[0][0][4:6]==bytes([127,2])
 cases.append('write-side binding remains default')
 assert not m.mmio_writes
 # Independently execute new code in Cortex-M7 mode. The complete stock DSP
 # initialization harness above uses A15 compatibility for its VFP routines.
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
 for addr,size in [(0,0x40000),(0x20000000,0x40000),(0x202e4000,0x2000),(0x40000000,0x1000000),(0xe0000000,0x100000)]:u.mem_map(addr,size)
 u.mem_write(0,v.candidate[:0x2356c]);u.mem_write(0x202e4000,b'\xa5'*0x2000)
 # M7 trampoline tests isolate new code. The A15 full-runtime/control tests
 # execute the stock housekeeping service; this small fixture stubs it.
 def m7_housekeeping(uc,pc,size,unused):
  if pc==0x15638:uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,m7_housekeeping)
 for addr,value in zip(REGISTERS,VALUES):u.mem_write(addr,struct.pack('<I',value))
 def call_m7(pc,args=()):
  for reg,value in zip(v.R,args):u.reg_write(reg,value)
  u.reg_write(UC_ARM_REG_MSP,v.SP);u.reg_write(UC_ARM_REG_LR,v.STOP|1)
  u.emu_start(pc|1,v.STOP,count=100000);assert u.reg_read(UC_ARM_REG_PC)==v.STOP
 call_m7(v.sym['mpp_stock_amp_init'])
 assert list(struct.unpack('<23I',u.mem_read(v.sym['mpp_probe'],92)))==[0x4d505031,1,1,0,0,0,0]+VALUES
 for half in [0,1]:
  u.mem_write(0x20016900,b'\x95'*256)
  call_m7(0x14bfc,[0x20016800+128*half,0x20016900+128*half])
  assert u.mem_read(0x20016900+128*half,128)==bytes(128)
  assert u.mem_read(0x20016900+128*(1-half),128)==b'\x95'*128
 cases.append('Cortex-M7 executes initialization and both aligned audio trampolines')
 m7_messages=[]
 def m7_send(uc,pc,size,unused):
  if pc==0xae80:
   addr,n,channel=[uc.reg_read(r) for r in v.R[:3]];m7_messages.append((bytes(uc.mem_read(addr,n)),channel))
   uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,m7_send)
 u.mem_write(0x20030000,bytes.fromhex('f0435800f7'));call_m7(0xac8a,[0x20030000,4,1])
 assert m7_messages[-1][0][4:12]==b'NAMPB002'
 u.mem_write(0x20030000,base);call_m7(v.sym['mpp_probe_query'],[0x20030000,9,1])
 assert m7_messages[-1][0][:9]==bytes.fromhex('f04358700402010000') and len(m7_messages[-1][0])==15
 cases.append('Cortex-M7 executes halfword-aligned version trampoline and stock reply builder')
 report={'status':'PASS_OFFLINE_STOCK_DIAGNOSTIC_BRIDGE','case_count':len(cases),'cases':cases,
  'malformed_requests':negative,'candidate_plan':v.plan,'physical_device_access':False,'audio_playback':False,
  'actual_code_executed':['Stock C runtime and DSP initialization with peripheral setup intercepted','Stock byte-ring assembler, command registration, dispatcher, selected handlers and reply builder','Stock DMA ISR and status helper with inert DMA registers and diagnostic zero callback','Stock housekeeping software timers and button-hold tick; ADC/LED helpers intercepted'],
  'limits':['Factory loader/SystemInit not executed by this harness','Stock DSP init uses A15 compatibility mode; new code also separately executes in M7 mode with housekeeping intercepted','Register fixtures are synthetic; no physical clock/cache/bus timing','USB transmitter and housekeeping ADC/LED helpers intercepted before hardware','The DMA ACK byte is excluded from write hooks due to a Unicorn Thumb IT-state defect; final ACK checked separately','No NAM included in this diagnostic; does not measure NAM timing','Silent samples do not establish electrical mute or absence of power-up pops','The physical NAMPB001 trial failed; NAMPB002 has not been installed or physically tested','Missing housekeeping is investigated in the separate control regression; this is not a physical freeze diagnosis']}
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'case_count':len(cases),'malformed_requests':negative}))
if __name__=='__main__':main()
