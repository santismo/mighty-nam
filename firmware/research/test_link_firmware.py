#!/usr/bin/env python3
"""Saved stock startup/USB byte-ring/DMA with the real ARM link and A2 code."""
import argparse,hashlib,json,struct,zlib
from pathlib import Path
from unicorn.arm_const import *
import candidate_vm as v
from test_stock_probe import ProbeMachine
from link_image import build
from a2_storage import model_slot
from a2_oracle import library,Engine

PREFIX=bytes.fromhex('f043587004024e4c01')
def pack(data):
 out=bytearray()
 for i in range(0,len(data),7):
  group=data[i:i+7];out.append(sum((b>>7)<<k for k,b in enumerate(group)));out.extend(b&127 for b in group)
 return bytes(out)
def unpack(data):
 out=bytearray()
 for i in range(0,len(data),8):
  group=data[i:i+8];out.extend(b|(((group[0]>>k)&1)<<7) for k,b in enumerate(group[1:]))
 return bytes(out)
def packet(op,session=0,offset=0,data=b''):
 header=struct.pack('<IBBHIII',0x314c504d,1,op,len(data),session,offset,zlib.crc32(data))
 return header+struct.pack('<I',zlib.crc32(header))+data
def sysex(data):return PREFIX+pack(data)+b'\xf7'

class LinkMachine(ProbeMachine):
 def __init__(self,fill=0):
  self.timer_ticks=77
  self.real_transmitter=False;self.transport_packets=[]
  super().__init__(fill)
  for addr,value in [(0x400ec000,0x46),(0x400ec004,23),(0x400ec00c,1),(0x400ec010,100000),(0x2000e48c,24000000)]:
   self.put(addr,value)
 def words(self):return list(struct.unpack('<12I',self.u.mem_read(v.sym['mpp_link'],48)))
 def run(self,pc,end=v.STOP,limit=6000000):
  # COMMIT checks the entire slot, switches banks and initializes the engine.
  # This is a foreground operation; audio callbacks remain zero while paused.
  return super().run(pc,end,limit)
 def read_register(self,u,access,address,size,value,unused):
  if address in [0xe000ed04,0x400ec000,0x400ec004,0x400ec00c,0x400ec010]:return
  super().read_register(u,access,address,size,value,unused)
 def code(self,u,pc,size,unused):
  if self.phase=='probe':
   if pc==0xae80:
    data,n,ch=[u.reg_read(r) for r in v.R[:3]]
    assert n in [15,45,65],n
    self.messages.append((bytes(u.mem_read(data,n)),ch))
    if self.real_transmitter:return # Execute the actual stock USB-MIDI encoder.
    u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
   if pc in [0xbbcc,0xbc00] and self.real_transmitter:
    data,n=[u.reg_read(r) for r in v.R[:2]]
    self.transport_packets.append(bytes(u.mem_read(data,n)))
    u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
   if pc in [0x11662,0x11670]:
    if pc==0x11670:self.put(0x2000e490,self.timer_ticks)
    u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  super().code(u,pc,size,unused)
 def exchange(self,raw,channel=0,split=None):
  msg=sysex(raw)
  rows=self.ingress([msg] if split is None else [msg[:split],msg[split:]],channel,start=2045)
  assert len(rows)==1 and rows[0][1]==channel
  reply=rows[0][0];assert reply[:9]==PREFIX and reply[-1]==247,reply.hex()
  result=unpack(reply[9:-1])
  assert len(result)==48 and result[5]==(raw[5]|128)
  assert result[8:12]==raw[8:12]
  assert struct.unpack_from('<I',result,20)[0]==zlib.crc32(result[:20])
  assert struct.unpack_from('<I',result,16)[0]==zlib.crc32(result[24:])
  return struct.unpack('<6I',result[24:])
 def upload(self,slot,session,channel=0):
  assert self.exchange(packet(2,session,data=struct.pack('<II',8192,zlib.crc32(slot))),channel)[0]==0
  for offset in range(0,8192,256):
   reply=self.exchange(packet(3,session,offset,slot[offset:offset+256]),channel)
   assert reply[:2]==(0,offset+256)
  assert self.exchange(packet(4,session),channel)[0]==0
 def audio(self,half=0):
  samples=[value for i in range(8) for value in [0,0,0,(i-4)*(1<<24)]]
  rx=0x20016800+128*half;tx=0x20016900+128*half
  self.u.mem_write(rx,struct.pack('<32i',*samples));self.u.mem_write(tx,b'\x7f'*128)
  self.call(0x14bfc,[rx,tx])
  assert self.u.mem_read(tx,128)==bytes(128)
  return [x*2**-31 for x in samples[3::4]],list(struct.unpack('<8f',self.u.mem_read(v.sym['mpp_link_output'],32)))

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['payload','elf','reference_library']:p.add_argument(name,type=Path)
 p.add_argument('models',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf))
 oracle_lib=library(str(a.reference_library));rows=[];checks=[]
 for fill in [0,0xa5,0xff]:
  m=LinkMachine(fill);assert m.words()==[0x4e4c4b31,1,1,0,0,0,0,0,0,0,0,0]
  m.audio();assert m.words()[7]==0
  for channel in [0,1]:
   assert m.ingress([bytes.fromhex('f0435800f7')],channel)[0][0][4:12]==b'NAMLNK01'
   assert m.exchange(packet(1),channel)==(0,0,0,8192,256,3)
   for page,value in enumerate(m.words()):assert m.page(page,channel)==(0,value)
  for index,path in enumerate(a.models):
   slot=model_slot(path);session=100+index
   m.upload(slot,session,index%2);assert m.words()[5:7]==[zlib.crc32(slot),index+1]
   assert m.words()[9]==1
   oracle=Engine(oracle_lib,path);error=0
   for half in [0,1,0,1]:
    xs,ys=m.audio(half);ref=oracle.run(xs)
    error=max(error,max(abs(x-y) for x,y in zip(ys,ref)))
   assert error<2e-5,error
   before=m.words()[6]
   assert m.exchange(packet(4,session))[0]==0 and m.words()[6]==before
   m.guards()
   rows.append(dict(model=path.name,fill=fill,max_reference_error=error,silent_dma=True))
  m.boot(unity_fades=False);m.phase='probe';m.run(0xac1e)
  assert m.words()==[0x4e4c4b31,1,1,0,0,0,0,0,0,0,0,0]
  assert m.exchange(packet(1))[2]==0;m.guards()
  print('cold/warm and model swaps passed:',fill,flush=True)
 checks.append('Three initial RAM patterns; real startup; two model swaps; duplicate commit; warm reset clears models')
 m=LinkMachine();slot=model_slot(a.models[0]);m.upload(slot,1)
 first=m.words()[5:7]
 for split in range(len(sysex(packet(1)))+1):assert m.exchange(packet(1),split=split)[0]==0
 # Split a full 330-byte message across every possible byte boundary.
 begin=packet(2,2,data=struct.pack('<II',8192,zlib.crc32(slot)))
 assert m.exchange(begin)[0]==0
 chunk=packet(3,2,0,slot[:256])
 for split in range(len(sysex(chunk))+1):assert m.exchange(chunk,split=split)[0]==0
 assert m.exchange(packet(4,2))[0]==6
 assert m.exchange(packet(5,2))[0]==0 and m.words()[5:7]==first
 checks.append('Both channels, ring wrap, every split of hello and max-size data; incomplete commit preserves active model')
 corrupt=bytearray(slot);corrupt[32]^=1
 assert m.exchange(packet(2,3,data=struct.pack('<II',8192,zlib.crc32(corrupt))))[0]==0
 for off in range(0,8192,256):assert m.exchange(packet(3,3,off,corrupt[off:off+256]))[0]==0
 assert m.exchange(packet(4,3))[0]==5 and m.words()[5:7]==first
 assert m.exchange(packet(5,3))[0]==0
 before=m.words()
 m.put(0xe000ed04,16)
 assert not m.ingress([sysex(packet(1))])
 assert m.words()[10]==before[10]+1 and m.words()[5:10]==before[5:10]
 m.put(0xe000ed04,0)
 for ticks in [0,150,100000]:
  # Exercise each fault from a running engine, not an already stopped one.
  m.put(v.sym['mpp_link']+4*4,0);m.put(v.sym['mpp_link']+9*4,1)
  m.timer_ticks=ticks;m.audio();assert m.words()[9]==0 and m.words()[4]==1
  assert m.exchange(packet(1))[0]==0 and m.words()[9]==0
 checks.append('Inner checksum failure leaves model active; interrupt-context commands rejected; invalid timing stops DSP')
 # Noncanonical final mask and high-bit wire bytes never reach the receiver.
 good=sysex(packet(1));bad=bytearray(good);bad[-5]|=64
 assert not m.query(bad,entry=v.sym['mpp_probe_query'])
 for n in list(range(9))+[330,0xffffffff]:
  assert not m.query(good,entry=v.sym['mpp_probe_query'],length=n)
 m.guards();assert not m.mmio_writes
 checks.append('Malformed lengths and noncanonical 7-bit encoding rejected; state guards and no unexpected MMIO writes')
 m=LinkMachine();m.real_transmitter=True
 for channel in [0,1]:
  assert m.exchange(packet(1),channel)[0]==0
  raw=m.messages[-1][0];encoded=m.transport_packets[-1]
  if channel==0:
   expected=bytearray()
   for off in range(0,len(raw),3):
    part=raw[off:off+3]
    expected+=bytes([4 if off+3<len(raw) else 4+len(part)])+part+bytes(3-len(part))
   assert encoded==expected and len(encoded)==88
  else:assert encoded==raw and len(encoded)==65
 checks.append('Stock transmitter encodes the complete 65-byte reply into 88 USB-MIDI bytes; serial transport preserves the frame')
 result={'status':'PASS_LINK_FIRMWARE_OFFLINE','identity':'NAMLNK01','elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),
  'model_runs':rows,'checks':checks,'max_sysex_request_bytes':330,'output_always_zero':True,
  'physical_device_tested':False,'peripheral_setup_and_usb_transmitter_emulated':True,
  'timer_services_stubbed':True,'deadline_proven':False}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
