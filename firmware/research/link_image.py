"""Compose NAMLNK01 in memory. Preserves all original high-flash resources."""
import hashlib,struct
from elftools.elf.elffile import ELFFile
from candidate_image import build_candidate,require

def elf_identity(elf):
 with elf.open('rb') as f:
  e=ELFFile(f)
  symbol=e.get_section_by_name('.symtab').get_symbol_by_name('mpp_probe_identity')[0]
  section=e.get_section(symbol['st_shndx'])
  offset=symbol['st_value']-section['sh_addr']
  identity=section.data()[offset:offset+8].decode('ascii')
 require(identity in ('NAMLNK01','NAMLNK02','NAMLNK03','NAMLNK04','NAMLNK05','NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09','NAMLNK10','NAMLNK11','NAMLNK12'),'Unknown ELF identity')
 return identity

def build(stock,elf,identity='NAMLNK01'):
 if identity in ('NAMLNK10','NAMLNK11','NAMLNK12'):
  from preset_image import build as preset_build
  return preset_build(stock,elf)
 require(identity in ('NAMLNK01','NAMLNK02','NAMLNK03','NAMLNK04','NAMLNK05','NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09'),'Unknown experiment identity')
 candidate,symbols,plan=build_candidate(stock,elf,profile='a2-listening' if identity in ('NAMLNK07','NAMLNK08','NAMLNK09') else 'a2-reclaimed')
 out=bytearray(candidate)
 def jump(name):
  target=symbols[name]
  require(target&1 and 0x1a0a4<=target<0x1b488,'Bad link entry')
  return bytes.fromhex('dff800f0')+struct.pack('<I',target)
 patches=[
  (0x14bfc,bytes.fromhex('2de9fe4f05460e46'),jump('mpp_probe_audio'),'Silent A2 callback'),
  (0xac8a,bytes.fromhex('38b58cb014462d216846'),bytes.fromhex('00bf')+jump('mpp_probe_version'),'Exact '+identity+' identity'),
  (0x1f397,struct.pack('<I',0xa1d3),struct.pack('<I',symbols['mpp_probe_query']),'Custom RAM model protocol and bounded status reads')]
 if identity in ('NAMLNK03','NAMLNK04','NAMLNK05','NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09'):
  patches.append((0x12302,bytes.fromhex('2b464246394648461c34'),
   bytes.fromhex('00bf')+jump('mpp_fast_dispatch'),'Suspend settled bypassed stock effects; retain routing fades'))
 if identity in ('NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09'):
  target=symbols['mpp_track_dwt_reset']
  delta=(target&~1)-(0xbe48+4)
  require(target&1 and -(1<<24)<=delta<(1<<24) and delta%2==0,'Invalid reset hook BL')
  s=(delta>>24)&1;i1=(delta>>23)&1;i2=(delta>>22)&1
  branch=struct.pack('<HH',0xf000|(s<<10)|((delta>>12)&1023),
    0xd000|((1^(i1^s))<<13)|((1^(i2^s))<<11)|((delta>>1)&2047))
  from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
  decoded=list(Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(branch,0xbe48))
  require(len(decoded)==1 and decoded[0].mnemonic=='bl' and
    int(decoded[0].op_str.lstrip('#'),0)==(target&~1),'Reset BL encoding mismatch')
  patches.extend([
   (0xbe48,bytes.fromhex('75603368'),branch,'Preserve and count the known stock delay CYCCNT reset'),
   (0x205a8,struct.pack('<I',0x11d95),struct.pack('<I',symbols['mpp_link_irq']),
    'Enclose original audio IRQ body with raw timing; vector table unchanged')])
 if identity in ('NAMLNK07','NAMLNK08','NAMLNK09'):patches=patches[1:] # candidate_image already retires this entry
 for addr,expected,new,reason in patches:
  require(stock[addr:addr+len(expected)]==expected and len(expected)==len(new),'Stock patch mismatch')
  out[addr:addr+len(new)]=new
  plan['patches'].append(dict(offset=hex(addr),original=expected.hex(),replacement=new.hex(),reason=reason))
 require(out[symbols['mpp_probe_identity']:symbols['mpp_probe_identity']+8]==identity.encode(),'Identity mismatch')
 if identity in ('NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09'):
  require(out[0x202a8:0x205a8]==stock[0x202a8:0x205a8] and
    out[0x205ac:]==stock[0x205ac:],'Unexpected high startup/resource change')
 else:require(out[0x202a8:]==stock[0x202a8:],'Startup/resources changed')
 plan.update(identity=identity,candidate_sha256=hashlib.sha256(out).hexdigest(),
  changed_byte_count=sum(a!=b for a,b in zip(stock,out)),
  model_storage='RAM only; model re-upload needed after restart',all_high_resources_preserved=identity not in ('NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09'),
  audio_irq_trampoline_redirected=identity in ('NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09'),
  audio_output='muted until explicit RAM listen arm' if identity in ('NAMLNK07','NAMLNK08','NAMLNK09') else 'always zero',firmware_container_written=False,physical_device_access=False)
 return bytes(out),symbols,plan
