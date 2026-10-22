"""Exact public V3.0.5 Original hybrid image, in memory only; never device I/O."""
import hashlib,struct
from elftools.elf.elffile import ELFFile
from candidate_image import require
from audit_reclaimed_code import audit as code_audit
STOCK_SHA='e971240a1e333003804cfd154e5ee053026254bbf09b11499e8b4968d3600752'
FLASH=0x30040000;BANK=0x30384000;BANK_END=0x303a0000;SOURCE=0x303a6000

def build(stock,elf,**unused):
 require(hashlib.sha256(stock).hexdigest()==STOCK_SHA,'Exact public V3.0.5 Original payload required')
 ca=code_audit(stock)
 descriptors=[struct.unpack_from('<8I',stock,0x1ab60+32*i) for i in range(30)]
 owners=[i for i,d in enumerate(descriptors) if d[1] and d[3]<0x303ac000 and d[3]+d[1]>BANK]
 require(owners==[12] and descriptors[12][3]<=BANK and descriptors[12][3]+descriptors[12][1]>=0x303ac000,'Retired AMP storage ownership')
 refs=[(i,struct.unpack_from('<I',stock,i)[0]) for i in range(0,len(stock)-3,4) if BANK<=struct.unpack_from('<I',stock,i)[0]<0x303ac000]
 require(refs==[(0x2312c,0x303851b7)],'Unclassified stock storage reference')
 # This one aligned word is compressed C-initializer data, not a pointer.
 # Execute the unchanged decompressor and require an observed data read there,
 # no resulting retired-storage pointer, and the established initialized hash.
 from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_READ
 from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.mem_map(0,0x100000);u.mem_write(0,stock[:0x100000])
 u.mem_map(0x20000000,0x400000);u.mem_write(0x20000000,b'\xa5'*0x400000)
 reads=[]
 u.hook_add(UC_HOOK_MEM_READ,lambda u,k,a,n,v,x:reads.append((u.reg_read(UC_ARM_REG_PC),a,n)),begin=0x2312c,end=0x2312f)
 u.reg_write(UC_ARM_REG_SP,0x20080000);u.reg_write(UC_ARM_REG_LR,0x40001);u.emu_start(0x22641,0x40000,count=5000000)
 require(u.reg_read(UC_ARM_REG_PC)==0x40000 and reads,'Compressed-data classification not reproduced')
 ram=bytes(u.mem_read(0x20000000,0x40000))
 require(hashlib.sha256(ram).hexdigest()=='ef63d9923157937962ff44d67f94e59c047a6078abd0972c8ebd7014c9b0e921','C runtime changed')
 require(not any(BANK<=struct.unpack_from('<I',ram,i)[0]<0x303ac000 for i in range(0,len(ram)-3,4)),'Runtime storage reference')
 out=bytearray(stock);regions=[];spans=[];patches=[]
 with elf.open('rb') as f:
  e=ELFFile(f);syms=list(e.get_section_by_name('.symtab').iter_symbols());symbols={s.name:s['st_value'] for s in syms}
  require(not [s.name for s in syms if s.name and s['st_shndx']=='SHN_UNDEF'],'Unresolved symbols')
  ident=e.get_section_by_name('.symtab').get_symbol_by_name('mpp_probe_identity')[0];sec=e.get_section(ident['st_shndx']);at=ident['st_value']-sec['sh_addr']
  require(sec.data()[at:at+8]==b'NAMLNK23','Public-base firmware identity required')
  for s in e.iter_sections():
   if not s['sh_flags']&2 or not s['sh_size']:continue
   start=s['sh_addr'];end=start+s['sh_size'];offset=start
   row=dict(name=s.name,start=hex(start),end_exclusive=hex(end),bytes=s['sh_size'])
   if s['sh_type']=='SHT_NOBITS':require(0x202e4020<=start<end<=0x2030f000,'BSS bounds')
   else:
    if s.name=='.banktext':
     require(start==0x2030f000 and end<=0x20314000 and symbols['__bank_load']==SOURCE,'Copied code bounds');offset=SOURCE-FLASH;row['load_address']=hex(SOURCE)
    else:require(0x1c45c<=start<end<=0x1d830 or s.name in ('.retired_audio','.ARM.exidx') and 0x1c0e8<=start<end<=0x1c270,'Retired low code bounds')
    out[offset:offset+s['sh_size']]=s.data();spans.append((offset,offset+s['sh_size']))
   regions.append(row)
 for a,b in [(BANK,BANK_END),(0x303a4000,0x303a6000)]:out[a-FLASH:b-FLASH]=b'\xff'*(b-a);spans.append((a-FLASH,b-FLASH))
 def patch(at,replacement,why):
  old=stock[at:at+len(replacement)];out[at:at+len(replacement)]=replacement;spans.append((at,at+len(replacement)));patches.append(dict(offset=hex(at),original=old.hex(),replacement=replacement.hex(),reason=why))
 def jump(at,name):
  target=symbols[name];require(target&1,'Thumb target')
  # Literal must be word aligned; a halfword-entry prefix preserves all registers.
  pad=b'\x00\xbf' if at%4 else b''
  patch(at,pad+bytes.fromhex('dff800f0')+struct.pack('<I',target),name)
 for at,name in [(0x55b4,'mpp_stock_amp_process'),(0x581a,'mpp_stock_amp_init'),(0xe19c,'mpp_probe_audio'),(0x5868,'mpp_bank_service'),(0x6a38,'mpp_stock_preset_select'),(0x1088c,'mpp_probe_version'),(0xb23c,'mpp_active_dispatch')]:jump(at,name)
 require(struct.unpack_from('<I',stock,0x21243)[0]==0x151b3 and stock[0x21242]==4,'Command 4 dispatch layout')
 patch(0x21243,struct.pack('<I',symbols['mpp_probe_query']),'Private command handler')
 require(struct.unpack_from('<I',stock,0x229b0)[0]==0x95a5,'Audio IRQ trampoline')
 patch(0x229b0,struct.pack('<I',symbols['mpp_link_irq']),'IRQ wrapper')
 for at,name in [(0x6498,'mpp_track_dwt_reset'),(0x8c96,'mpp_codec_startup_write')]:
  delta=(symbols[name]&~1)-(at+4);require(symbols[name]&1 and -(1<<24)<=delta<(1<<24) and not delta%2,'Branch range')
  s=(delta>>24)&1;i1=(delta>>23)&1;i2=(delta>>22)&1
  patch(at,struct.pack('<HH',0xf000|(s<<10)|((delta>>12)&1023),0xd000|((1^(i1^s))<<13)|((1^(i2^s))<<11)|((delta>>1)&2047)),name)
 require(stock[0x6498:0x649c]==bytes.fromhex('75603368'),'Counter displaced instructions')
 require(out[:0x400]==stock[:0x400] and len(out)==len(stock),'Vector/extent changed')
 require(all(any(a<=i<b for a,b in spans) for i,(x,y) in enumerate(zip(stock,out)) if x!=y),'Change outside allowlist')
 plan=dict(identity='NAMLNK23',mode='IN_MEMORY_OFFLINE_ONLY',elf_regions=regions,patches=patches,stock_sha256=STOCK_SHA,elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(out).hexdigest(),retired_code_audit=ca,compressed_initializer_reference=dict(offset='0x2312c',raw_word='0x303851b7',reads=reads,initialized_DTCM_sha256=hashlib.sha256(ram).hexdigest(),resulting_storage_pointers=0),preset_ownership=dict(owners=owners,base=hex(BANK),end=hex(BANK_END),slots=7,copies=2,record_bytes=8192),copied_code=dict(source=hex(SOURCE),destination='0x2030f000',bytes=next(r['bytes'] for r in regions if r['name']=='.banktext')),changed_spans=spans,original_vector_table_preserved=True,device_access=False,flash_container_created=False)
 return bytes(out),symbols,plan
