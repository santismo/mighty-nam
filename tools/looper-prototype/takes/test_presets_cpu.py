"""Execute NAM-only preset saving against a separately cached CPU/NOR view.
Synthetic cache model; hardware cause and timing remain unverified.
"""
import argparse,sys,struct,zlib,hashlib,json,time
from pathlib import Path
from unicorn import UC_HOOK_MEM_WRITE,UC_HOOK_CODE
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'hardware'))
from harness import setup
p=argparse.ArgumentParser()
for n in ['baseline','payload','output','bank']:p.add_argument(n,type=Path)
p.add_argument('--expect-stale',action='store_true')
a=p.parse_args();start=time.monotonic();M,v,s,preset,input_block,model_slot=setup(a.baseline,a.payload,a.output)
bank=a.bank.read_bytes()
lo,hi=0x30384000,0x303a6000
class Cached(M):
 def __init__(self,*args,**kw):
  self.backing=None;self.invalidate=True;self.invalidations=0;self.pending_lines=set()
  super().__init__(*args,**kw)
  self.backing=bytearray(self.u.mem_read(lo,hi-lo))
  def invalidate(u,kind,address,size,value,unused):
   if self.invalidate and address==0xe000ef5c and lo<=value<hi:
    assert value%32==0
    self.pending_lines.add(value);self.invalidations+=1
  self.u.hook_add(UC_HOOK_MEM_WRITE,invalidate,begin=0xe000ef5c,end=0xe000ef5f)
  def apply_lines(u,pc,n,user):
   for at in self.pending_lines:u.mem_write(at,bytes(self.backing[at-lo:at-lo+32]))
   self.pending_lines.clear()
  self.u.hook_add(UC_HOOK_CODE,apply_lines,begin=s['mpp_loop_read']&~1,end=s['mpp_loop_read']&~1)
 def code(self,u,pc,n,user):
  if self.backing is not None and self.phase=='probe' and pc in (0x841c,0x84ac):
   cached=bytes(u.mem_read(lo,hi-lo));u.mem_write(lo,bytes(self.backing))
   result=super().code(u,pc,n,user);self.backing[:]=u.mem_read(lo,hi-lo)
   u.mem_write(lo,cached);return result
  return super().code(u,pc,n,user)
m=Cached(flash=bank);m.service();m.initialize_usb();m.arm()
def save(color,nonce):
 d=bytearray(m.u.mem_read(m.preset,128));d[84]=37;d[70]=(nonce+color)%60;m.u.mem_write(m.preset,bytes(d))
 m.call(v.sym['mpp_bank_model'],[]);address=m.u.reg_read(v.R[0]);capture=bytes(m.u.mem_read(address,8192))
 body=struct.pack('<4I',zlib.crc32(capture),zlib.crc32(d),1,8)+hashlib.sha256(capture).digest()+f'Color {color+1}'.encode().ljust(64,b'\0')
 return m.bank_request(2,color,body,channel=color%2,nonce=nonce),bytes(d)
# Reproduce the reported error when CPU cache maintenance is absent.
m.invalidate=False;r,_=save(3,101);assert r[7]==3
assert m.page(25)[1]>>8&127==7
print('Negative control: slot 4 fails with stale CPU view',flush=True)
m.invalidate=True;expected={};saves=0
for round in range(3):
 for color in [3,4,5,6,0,1,2]:
  r,d=save(color,120+round*7+color)
  if a.expect_stale:
   assert r[7]==3;print('Original NAMLNK29 reproduces stale-view save failure',flush=True);sys.exit(0)
  assert r[7]==0,(color,r[7]);expected[color]=d;saves+=1
 assert m.page(25)[1]>>8&127==127
 for color in [6,1,5,3,0,4,2]:
  assert m.bank_request(3,color,nonce=200+round*7+color)[7]==0;m.service()
  assert bytes(m.u.mem_read(m.preset,128))==expected[color]
 print('Round',round+1,'all seven saves, overwrite/recall PASS',flush=True)
before=bytes(m.backing);m.fail_write=True;r,_=save(3,300)
assert r[7]==3 and bytes(m.backing)==before;m.fail_write=False
assert m.bank_request(3,3,nonce=301)[7]==0
assert bytes(m.u.mem_read(m.preset,128))==expected[3]
# Refresh the simulated CPU on reboot; actual flash backing retains records.
m.u.mem_write(lo,bytes(m.backing));m.restart();m.service()
assert m.page(25)[1]>>8&127==127
assert [m.button() for _ in range(7)]==[1,2,3,4,5,6,0]
assert m.words()[9]==1 and not m.words()[4]
report=dict(status='PASS_NAMLNK29_SEVEN_CPU_CACHE',elf_sha256=hashlib.sha256((a.output/'build/loop-startup-test.elf').read_bytes()).hexdigest(),saves=saves,seven_saves=True,USB_BLE=True,overwrite_and_random_recall=True,button_cycle=True,restart=True,failed_write_preserves_previous=True,original_failure_reproduced=True,cpu_cache_model=True,cache_cause_on_hardware_verified=False,invalidated_lines=m.invalidations,device_access=False,seconds=time.monotonic()-start)
(a.output/'seven-presets-cpu.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
