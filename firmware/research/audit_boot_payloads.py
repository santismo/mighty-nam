#!/usr/bin/env python3
"""Read-only boot-image clues. Pattern absence is never loader/recovery proof."""
import argparse,hashlib,json,re,struct
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payloads',type=Path,nargs='+');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
allowed={'a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990','e971240a1e333003804cfd154e5ee053026254bbf09b11499e8b4968d3600752'}
reports=[]
for file in a.payloads:
 b=file.read_bytes();sha=hashlib.sha256(b).hexdigest()
 if sha not in allowed:raise ValueError('Unexamined input')
 vectors=[]
 for pos in range(0,len(b)-256,256):
  sp,pc=struct.unpack_from('<II',b,pos)
  if not (0x20000000<=sp<0x20400000 and sp%8==0 and pc&1 and (pc&~1)<0x40000):continue
  entries=struct.unpack_from('<62I',b,pos+8)
  count=sum(1 for x in entries if x&1 and 0x100<(x&~1)<0x40000)
  if count>=8:vectors.append({'offset':hex(pos),'stack':hex(sp),'reset':hex(pc),'plausible_low_thumb_entries':count})
 signatures={label:[hex(m.start()) for m in re.finditer(re.escape(sig),b)] for label,sig in {
  'FCB_tag_bytes':b'FCFB','IVT_v41_header_bytes':bytes.fromhex('d1002041'),
  'setup_identity_plaintext':b'PLUGXDFU','DFU_product_plaintext':b'MIGHTY PLUG PRO DFU'}.items()}
 reports.append({'file':file.name,'sha256':sha,'bytes':len(b),'vector_candidates_256_byte_alignment':vectors,
 'signature_hits':signatures,'fill_runs_first_256KiB':[{'start':hex(m.start()),'end_exclusive':hex(m.end()),'bytes':len(m.group()),'fill':m.group()[0]} for m in re.finditer(b'\x00{512,}|\xff{512,}',b[:0x40000])]})
result={'mode':'READ_ONLY_FILES_NO_DEVICE_ACCESS','reports':reports,'interpretation':[
 'An application vector table at offset zero is consistent across both versions',
 'Early zero fill offers a candidate location for a later experiment, not proven executable/free device memory',
 'Actual pre-application copy extent, mappings, validation, erase bounds and recovery entry remain unknown',
 'These limited signature/vector scans cannot rule out an encoded or nonstandard loader'],
 'loadable_custom_firmware':False,'usb_recovery_proven':False}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
