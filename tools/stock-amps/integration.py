from pathlib import Path
import sys,struct,copy,hashlib,json
from elftools.elf.elffile import ELFFile
from build import HERE,ROOT,BASE,LOOP,PAYLOAD,STOCK_FILE,TEST_BANK,symbols,sha
sys.path.insert(0,str(ROOT/'tools/looper-prototype/hardware'))
import harness,image
original_build=image.build
def extension(stock,base,loop,identity='NAMLNK30'):
 data,s,plan=original_build(stock,base,loop,identity)
 original=data;data=bytearray(data);s=dict(s);plan=copy.deepcopy(plan)
 elf=HERE/'build/extra.elf';extra=symbols(elf);allowed=[]
 old_regions=list(plan['elf_regions'])
 with elf.open('rb') as f:
  for sec in ELFFile(f).iter_sections():
   if not sec['sh_flags']&2 or not sec['sh_size']:continue
   lo=sec['sh_addr'];hi=lo+sec['sh_size'];name=sec.name
   assert not any(max(lo,int(r['start'],16))<min(hi,int(r['end_exclusive'],16)) for r in old_regions),(name,'runtime overlap')
   row=dict(name=name,start=hex(lo),end_exclusive=hex(hi),bytes=sec['sh_size'])
   if name=='.text':
    assert lo==0x2031a020 and hi<=0x2031afe0;at=0x303ab000-0x30040000;row['name']='.stockamptext';row['load_address']='0x303ab000'
   elif name=='.extra_boot':assert lo==0x1d7c4 and hi<=0x1d830;at=lo
   elif name=='.master_zero':assert lo==0x1c238 and hi<=0x1c270;at=lo
   elif name=='.tone':assert lo==0x20319d00 and hi<=0x20319d80;at=None;row['name']='.bss'
   elif name=='.bss':assert lo==0x20319c00 and hi<=0x20319fe0;at=None
   else:raise AssertionError(name)
   if at is not None:
    for r in old_regions:
     if 'load_address' in r:
      start=int(r['load_address'],16)-0x30040000
      assert not max(at,start)<min(at+sec['sh_size'],start+r['bytes'])
    data[at:at+sec['sh_size']]=sec.data();allowed.append((at,at+sec['sh_size']))
   plan['elf_regions'].append(row)
 def jump(at,target):
  assert target&1
  b=(b'\x00\xbf' if at%4 else b'')+bytes.fromhex('dff800f0')+struct.pack('<I',target)
  data[at:at+len(b)]=b;allowed.append((at,at+len(b)))
 def base_jump(name,new):jump(0x366000+s[name]-1-0x2030f000,extra[new])
 jump(0x581a,extra['mpp_extra_startup']);jump(0x5868,extra['mpp_extra_service'])
 base_jump('_ZN3mpp2fx5validEPKh','mpp_extra_valid');base_jump('mpp_fx_graph_process','mpp_extra_process')
 data[0x21243:0x21247]=struct.pack('<I',extra['mpp_extra_query']);allowed.append((0x21243,0x21247))
 assert stock[0x65d8:0x65dc]==bytes.fromhex('56f82270')
 delta=(extra['mpp_master_zero']&~1)-(0x65d8+4);sign=(delta>>24)&1;i1=(delta>>23)&1;i2=(delta>>22)&1
 data[0x65d8:0x65dc]=struct.pack('<HH',0xf000|(sign<<10)|((delta>>12)&1023),0xd000|((1^(i1^sign))<<13)|((1^(i2^sign))<<11)|((delta>>1)&2047));allowed.append((0x65d8,0x65dc))
 # Relocate the Brit 800 resource out of the bank/code extent, using only
 # bytes supplied by the user. The destination is an audited stock zero run.
 def resource(at,content):
  assert original[at:at+len(content)]==bytes(len(content)),hex(at)
  data[at:at+len(content)]=content;allowed.append((at,at+len(content)))
 resource(0xb00000,stock[0x340000:0x36c428])
 wrapper_rows=json.loads((HERE/'wrappers/manifest.json').read_text())
 audit=json.loads((HERE/'audit_writes.json').read_text());metas=[]
 for id in range(1,30):
  d=struct.unpack_from('<8I',stock,0x1ab60+id*32)
  source=0x30b40000 if id==12 else d[3] or 0x2031b000
  tone=next((int(w['lo'],16)-24 for w in audit[id-1]['writes'] if w['pc']=='0x4e4'),0xffffffff)
  if id<26:
   row=wrapper_rows[id-1];code=(HERE/f'wrappers/{id}.bin').read_bytes()
   resource(0xb40000+(id-1)*0x800,code)
   total=2166136261
   for byte in code:total=((total^byte)*16777619)&0xffffffff
   metas.append(struct.pack('<6I',len(code),row['init'],row['process'],source,tone,total))
  else:metas.append(struct.pack('<6I',0,d[7],d[6],source,tone,0))
  for off in {4:[0x84,0x8e0c],22:[0x236c4,0x2c3ec]}.get(id,[]):
   at=source-0x30040000+off;data[at:at+4]=bytes(4);allowed.append((at,at+4))
 resource(0xb50000,b''.join(metas))
 plan['elf_regions'].append(dict(name='.amp_wrapper',start='0x2031a800',end_exclusive='0x2031afe0',bytes=0x7e0))
 assert all(any(lo<=i<hi for lo,hi in allowed) for i,(a,b) in enumerate(zip(original,data)) if a!=b)
 assert data[:0x400]==stock[:0x400] and data[0x22618:0x229ac]==stock[0x22618:0x229ac]
 s.update({k:v for k,v in extra.items() if k.startswith('mpp_extra') or k in ['mpp_master_zero','mpp_amp_tone']})
 # Bootstrap boundary alias only. NAM inference/state addresses are unchanged.
 s['mpp_stock_amp_init']=extra['mpp_extra_startup']
 plan.update(stock_amp_extension=True,extra_sha256=sha(elf),extra_changed_spans=allowed)
 return bytes(data),s,plan

def setup(candidate=True):
 image.build=extension if candidate else original_build
 M,v,s,*rest=harness.setup(BASE,PAYLOAD,LOOP,identity='NAMLNK30' if candidate else None)
 if not candidate:return M,v,s,*rest
 class Extended(M):
  def __init__(self,*args,**kwargs):
   from unicorn import Uc,UC_HOOK_MEM_READ
   original_hook=Uc.hook_add
   def scoped_hook(u,kind,callback,user_data=None,begin=1,end=0,*extra):
    # Unicorn 2.1.4 changes execution under even a no-op read observer in
    # this dynamically copied Thumb wrapper. Keep all other RAM/code guards.
    # observer_wrapper.py reproduces against the identical unobserved binary.
    if kind==UC_HOOK_MEM_READ and begin==0x2031a800 and end==0x2031afdf:return None
    return original_hook(u,kind,callback,user_data,begin,end,*extra)
   Uc.hook_add=scoped_hook
   try:super().__init__(*args,**kwargs)
   finally:Uc.hook_add=original_hook
  def boot(self,*args,**kwargs):
   self.u.mem_protect(0x2031a000,0x1000,7)
   super().boot(*args,**kwargs)
 return Extended,v,s,*rest
