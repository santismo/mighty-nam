#!/usr/bin/env python3
"""Model separate flash backing and stale AHB read buffers; no hardware I/O."""
import argparse,json,sys,struct,zlib,hashlib
from pathlib import Path
from unicorn import UC_HOOK_MEM_READ
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'hardware'))
from harness import setup
p=argparse.ArgumentParser()
for n in ['baseline','payload','output','bank']:p.add_argument(n,type=Path)
a=p.parse_args();M,v,s,preset,input_block,model_slot=setup(a.baseline,a.payload,a.output)
identity=json.loads((a.output/'build/build.json').read_text())['identity']
lo,hi=0x30384000,0x303a6000
class Stale(M):
 def __init__(self,*args,**kw):
  self.backing=None;super().__init__(*args,**kw)
  self.backing=bytearray(self.u.mem_read(lo,hi-lo));self.refreshes=0
  def reset(u,kind,address,size,value,unused):
   if self.flexspi_resets>self.refreshes:
    u.mem_write(lo,bytes(self.backing));self.refreshes=self.flexspi_resets
  self.u.hook_add(UC_HOOK_MEM_READ,reset,begin=0x400cc000,end=0x400cc003)
 def code(self,u,pc,n,user):
  if self.backing is not None and self.phase=='probe' and pc in (0x841c,0x84ac):
   r0,r1=[u.reg_read(r) for r in v.R[:2]];addr=r0 if pc==0x841c else r1
   count=4096 if pc==0x841c else 256-(addr&255)
   cached=bytes(u.mem_read(lo,hi-lo));u.mem_write(lo,bytes(self.backing))
   result=super().code(u,pc,n,user)
   self.backing[:]=u.mem_read(lo,hi-lo)
   # Erase includes SWRESET in stock code; low-level page program does not.
   if pc==0x84ac:u.mem_write(lo,cached)
   return result
  return super().code(u,pc,n,user)
m=Stale(flash=a.bank.read_bytes());m.service();assert m.page(25)[1]>>8&127==7
def save(color,nonce):
 data=bytearray(preset([8],{8:4}));data[84]=37;data[70:74]=bytes([20+color+(1 if nonce==403 else 0),20,50,0]);m.u.mem_write(m.preset,bytes(data))
 body=struct.pack('<4I',m.words()[5],zlib.crc32(data),1,8)+bytes(32)+f'Seven slot test {color}'.encode().ljust(64,b'\0')
 return m.bank_request(2,color,body,channel=color%2,nonce=nonce),bytes(data)
reply,data=save(3,43)
if identity=='NAMLNK28':
 assert reply[7]==3,reply[7]
 report=dict(status='REPRODUCED_N28_SLOT_FOUR_STALE_AHB_ERROR',error=reply[7],device_access=False)
else:
 assert reply[7]==0,reply[7]
 expected={3:data}
 for color in [4,5,6,0,1,2]:
  reply,data=save(color,100+color);assert reply[7]==0,(color,reply[7]);expected[color]=data
 assert reply[15]==127 and m.refreshes>=7*33
 for color in [6,1,5,3,0,4,2]:
  assert m.bank_request(3,color,nonce=200+color)[7]==0
  assert bytes(m.u.mem_read(m.preset,128))==expected[color]
 m.restart();m.service();assert m.page(25)[1]>>8&127==127
 assert [m.button() for _ in range(7)]==[1,2,3,4,5,6,0]
 # Driver error must not destroy the previously committed copy.
 before=bytes(m.backing);m.fail_write=True
 reply,_=save(3,403);assert reply[7]==3 and bytes(m.backing)==before
 m.fail_write=False;assert m.bank_request(3,3,nonce=404)[7]==0
 assert bytes(m.u.mem_read(m.preset,128))==expected[3]
 report=dict(status='PASS_SEVEN_PRESETS_STALE_AHB',elf_sha256=hashlib.sha256((a.output/'build/loop-startup-test.elf').read_bytes()).hexdigest(),
  seven_slots=True,USB_BLE=True,random_recall=True,restart_and_button_cycle=True,failed_write_preserves_previous=True,
  refreshes=m.refreshes,driver_model='NOR backing separate from stale AHB view',hardware_verified=False,device_access=False)
(a.output/'seven-presets.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
