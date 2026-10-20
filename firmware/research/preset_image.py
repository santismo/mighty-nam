"""NAMLNK10 in-memory image and exact retired-resource ownership checks."""
import hashlib,struct,json
from pathlib import Path
from elftools.elf.elffile import ELFFile
from candidate_image import STOCK_SHA,require
from audit_reclaimed_code import audit as code_audit
from audit_retired_audio import audit as audio_audit
FLASH=0x30040000;BANK=0x30384000;BANK_END=0x303a0000;SOURCE=BANK_END

def build(stock,elf):
 require(hashlib.sha256(stock).hexdigest()==STOCK_SHA,'Exact stock image required')
 code_audit(stock);retired=audio_audit(stock)
 descriptors=[struct.unpack_from('<8I',stock,0x18428+32*i) for i in range(30)]
 owners=[i for i,d in enumerate(descriptors) if d[1] and d[3]<0x303ac000 and d[3]+d[1]>BANK]
 require(owners==[12],'Preset/code extent must have only retired AMP owner12')
 require(descriptors[12][3]<=BANK and descriptors[12][3]+descriptors[12][1]>=0x303ac000,'Retired resource too small')
 references=[(i,struct.unpack_from('<I',stock,i)[0]) for i in range(0,len(stock)-3,4) if BANK<=struct.unpack_from('<I',stock,i)[0]<0x303ac000]
 require(not references,'Unclassified aligned reference into preset/code storage')
 overlays=json.loads((Path(__file__).resolve().parents[1]/'artifacts/reclaimed-overlay-audit.json').read_text())['overlays']
 require(all(not(int(o['saved_source_address'],16)<0x303ac000 and int(o['saved_source_address'],16)+o['bytes']>BANK) for o in overlays),'Effect overlay overlaps preset storage')
 out=bytearray(stock);regions=[];patches=[];spans=[]
 with elf.open('rb') as f:
  e=ELFFile(f);syms=list(e.get_section_by_name('.symtab').iter_symbols());symbols={s.name:s['st_value'] for s in syms}
  require(not [s.name for s in syms if s.name and s['st_shndx']=='SHN_UNDEF'],'Unresolved symbols')
  for s in e.iter_sections():
   if not s['sh_flags']&2 or not s['sh_size']:continue
   start=s['sh_addr'];end=start+s['sh_size'];offset=start
   row=dict(name=s.name,start=hex(start),end_exclusive=hex(end),bytes=s['sh_size'])
   if s['sh_type']=='SHT_NOBITS':require(0x202e4020<=start<end<=0x20308000,'BSS bounds')
   else:
    if s.name=='.banktext':
     require(start==0x20308000 and end<=0x20314000 and symbols['__bank_load']==SOURCE,'Copied code bounds')
     offset=SOURCE-FLASH;row['load_address']=hex(SOURCE)
    else:require(0x1a0a4<=start<end<=0x1b488 or (s.name in ('.retired_audio','.ARM.exidx') and 0x14c04<=start<end<=0x14f08),'Low code bounds')
    out[offset:offset+s['sh_size']]=s.data();spans.append((offset,offset+s['sh_size']))
   regions.append(row)
 # A first installation starts with empty records. A future firmware update
 # needs an app bank backup/restore; this is not a preserve-on-update format.
 out[BANK-FLASH:BANK_END-FLASH]=b'\xff'*(BANK_END-BANK);spans.append((BANK-FLASH,BANK_END-FLASH))
 def jump(name):
  target=symbols[name];require(target&1,'Thumb entry required')
  return bytes.fromhex('dff800f0')+struct.pack('<I',target)
 def patch(at,expected,replacement,why):
  require(stock[at:at+len(expected)]==expected and len(expected)==len(replacement),'Patch mismatch '+hex(at))
  out[at:at+len(expected)]=replacement;spans.append((at,at+len(expected)))
  patches.append(dict(offset=hex(at),original=expected.hex(),replacement=replacement.hex(),reason=why))
 for at,old,name in [(0x5578,'2de9fe4f80469246','mpp_stock_amp_process'),(0x5778,'80b501200c490870','mpp_stock_amp_init'),(0x14bfc,'2de9fe4f05460e46','mpp_probe_audio')]:patch(at,bytes.fromhex(old),jump(name),name)
 # These two stock paths are separately decoded in the storage/button audit.
 patch(0x57c0,bytes.fromhex('80b5')+stock[0x57c2:0x57c8],jump('mpp_bank_service'),'Replace retired AMP background service with deferred preset recall')
 # 0xb38a is halfword-aligned. Pad to the next word before the literal jump.
 patch(0xb38a,stock[0xb38a:0xb394],bytes.fromhex('00bf')+jump('mpp_stock_preset_select'),'Stock PRESET/program-change recall and early-boot compatibility')
 patch(0xac8a,bytes.fromhex('38b58cb014462d216846'),bytes.fromhex('00bf')+jump('mpp_probe_version'),'NAMLNK10 identity')
 patch(0x1f397,struct.pack('<I',0xa1d3),struct.pack('<I',symbols['mpp_probe_query']),'Bounded model/preset protocol')
 patch(0x12302,bytes.fromhex('2b464246394648461c34'),bytes.fromhex('00bf')+jump('mpp_fast_dispatch'),'Existing fast bypass')
 target=symbols['mpp_track_dwt_reset'];delta=(target&~1)-(0xbe48+4)
 require(target&1 and -(1<<24)<=delta<(1<<24) and delta%2==0,'Reset branch range')
 s=(delta>>24)&1;i1=(delta>>23)&1;i2=(delta>>22)&1
 branch=struct.pack('<HH',0xf000|(s<<10)|((delta>>12)&1023),0xd000|((1^(i1^s))<<13)|((1^(i2^s))<<11)|((delta>>1)&2047))
 patch(0xbe48,bytes.fromhex('75603368'),branch,'Existing counter-reset tracking')
 patch(0x205a8,struct.pack('<I',0x11d95),struct.pack('<I',symbols['mpp_link_irq']),'Existing IRQ wrapper')
 require(out[:0x400]==stock[:0x400] and len(out)==len(stock),'Vector/extent changed')
 require(all(any(a<=i<b for a,b in spans) for i,(x,y) in enumerate(zip(stock,out)) if x!=y),'Change outside allowlist')
 plan=dict(identity='NAMLNK10',mode='IN_MEMORY_OFFLINE_ONLY',elf_regions=regions,patches=patches,
  stock_sha256=STOCK_SHA,elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(out).hexdigest(),
  retired_audio_audit=retired,preset_ownership=dict(owners=owners,base=hex(BANK),end=hex(BANK_END),copies=2,slots=7,record_bytes=8192),
  copied_code=dict(source=hex(SOURCE),destination='0x20308000',bytes=next(r['bytes'] for r in regions if r['name']=='.banktext')),
  changed_spans=spans,physical_storage_driver_verified=False,physical_button_verified=False,physical_RAM_code_execution_verified=False,
  original_vector_table_preserved=True,device_access=False,flash_container_created=False)
 return bytes(out),symbols,plan
