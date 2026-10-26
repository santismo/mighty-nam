"""Real receive assembler, stale CPU flash view, seven-color saves; offline only."""
import struct,zlib,hashlib,json,time
from unicorn import UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from integration import *
from seven_defaults import populate
start=time.monotonic();M,v,s,preset,input_block,model_slot=setup(True)
bank=TEST_BANK.read_bytes()
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
m=Cached(bank);m.service();m.initialize_usb();m.arm()
q=bytes.fromhex('f043587004024e507ef7');cases=0
for channel in [0,1]:
 for n in [9,10]:
  r=m.query(q,channel,length=n);assert r==[(bytes.fromhex('f04358700402017e001d02501a05f7'),channel)];cases+=1
 for split in range(len(q)+1):
  r=m.ingress([q[:split],q[split:]],channel,start=2045);assert r==[(bytes.fromhex('f04358700402017e001d02501a05f7'),channel)];cases+=1
assert m.page(127)==(0,0x4e300002)
print('Capability real receive path / both lengths / both transports PASS',flush=True)
def save(color,nonce):
 d=bytearray(m.u.mem_read(m.preset,128));d[84]=37;d[70]=20+color+(1 if nonce==300 else 0);m.u.mem_write(m.preset,bytes(d))
 m.call(v.sym['mpp_bank_model'],[]);address=m.u.reg_read(v.R[0]);capture=bytes(m.u.mem_read(address,8192))
 body=struct.pack('<4I',zlib.crc32(capture),zlib.crc32(d),1,8)+hashlib.sha256(capture).digest()+f'Color {color+1}'.encode().ljust(64,b'\0')
 return m.bank_request(2,color,body,channel=color%2,nonce=nonce),bytes(d)
# An AHB reset cannot evict CPU cachelines in this separate-view fixture.
m.invalidate=False;r,_=save(3,101);assert r[7]==3
assert m.page(25)[1]>>8&127==7
print('Stale CPU view reproduces slot-four I/O failure when invalidation is suppressed',flush=True)
m.invalidate=True;expected={}
for color in [3,4,5,6,0,1,2]:
 print('Saving color',color+1,flush=True);r,d=save(color,120+color);assert r[7]==0,(color,r[7]);expected[color]=d
 assert not m.page(124)[1]&0x80000000
assert m.page(25)[1]>>8&127==127
for color in [6,1,5,3,0,4,2]:
 assert m.bank_request(3,color,nonce=200+color)[7]==0;m.service()
 assert bytes(m.u.mem_read(m.preset,128))==expected[color]
print('Seven color saves and random recall with stale CPU read buffers PASS',flush=True)
before=bytes(m.backing);m.fail_write=True;r,_=save(3,300);assert r[7]==3 and bytes(m.backing)==before
assert m.page(124)[1]&0x80000000;m.fail_write=False
assert m.bank_request(3,3,nonce=301)[7]==0
assert bytes(m.u.mem_read(m.preset,128))==expected[3]
print('Failed write retains previous committed preset; diagnostics identifies failure PASS',flush=True)
# Same compiled binary validates all seven seeded records and physical scanner.
full=populate(bank);assert full[:3*16384]==bank[:3*16384]
m.backing[:len(full)]=full;m.u.mem_write(lo,full)
m.restart();m.service();assert m.page(25)[1]>>8&127==127
assert [m.button() for _ in range(7)]==[1,2,3,4,5,6,0]
assert m.words()[9]==1 and not m.words()[4]
print('Seven defaults, normal startup and seven-button cycle PASS',flush=True)
(HERE/'phone-paths.json').write_text(json.dumps(dict(status='PASS_NAMLNK30_R2_PHONE_PATHS',elf_sha256=sha(HERE/'build/extra.elf'),capability_cases=cases,seven_saves=True,seven_boot_defaults=True,button_cycle=True,failed_write_preserves_previous=True,cpu_cache_model=True,cache_cause_on_hardware_verified=False,invalidated_lines=m.invalidations,device_access=False,seconds=time.monotonic()-start),indent=2)+'\n')
