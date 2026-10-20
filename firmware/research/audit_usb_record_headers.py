#!/usr/bin/env python3
"""File-only comparison of public MP-3 record headers. No USB dependencies.
Checks observed bytes; does not infer the device's erase addresses or security.
"""
import argparse,json,hashlib,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nux_container_lab import Container,need
p=argparse.ArgumentParser(description=__doc__);p.add_argument('firmware',type=Path,nargs='+');p.add_argument('--output',required=True,type=Path);a=p.parse_args()
reports=[]
for path in a.firmware:
 c=Container(path.read_bytes());progress=[];nonzero=[]
 for i,r in enumerate(c.records[1:]):
  expected=1+((i+1)*99//(len(c.records)-1))
  if r[0]!=expected:progress.append(i)
  # Known fields: progress[0], operation[2:4], page index[12:16].
  unknown=bytes(r[j] for j in range(28) if j not in (0,2,3,12,13,14,15))
  if any(unknown):nonzero.append(i)
 need(not progress,'Progress field differs from proposed formula')
 need(not nonzero,'Unknown nonzero record header bytes')
 setup=c.records[0];triplet=struct.unpack_from('>III',setup,48)
 need(triplet==(0,len(c.payload),0),'Unexpected setup scalar fields')
 reports.append({'file':path.name,'container_sha256':hashlib.sha256(c.data).hexdigest(),'payload_sha256':hashlib.sha256(c.payload).hexdigest(),
 'records':len(c.records),'data_records':len(c.records)-1,'setup_product':bytes(x^255 for x in setup[28:36]).decode(),
 'setup_version':c.version,'setup_be32_at_48_52_56':list(triplet),
 'progress_formula':'1 + floor(99 * (zero_based_page_index + 1) / data_record_count)',
 'all_progress_bytes_match':True,'other_data_record_header_bytes_zero':True,
 'final_record_marker':'0xffffffff','per_page_checksum_in_28_byte_header_identified':False})
result={'status':'PASS_FILE_HEADER_CHARACTERIZATION_ONLY','files':reports,'device_or_audio_access':False,
 'inference':'The decoded MP-3 setup carries product/version/length and pages carry indices. These fields do not establish a physical flash destination or protected erase range.',
 'cross_product_reference':{'url':'https://github.com/opensensor/nux-effects/blob/28b7c3ab05a9e980530950c7c784b062ebf96cd3/tools/nux_dfu.py',
 'scope':'NCR-2 Core Deluxe, NOT MP-3','finding':'Its recovered factory protocol uses the same framing but documents its flash base as hardcoded inside that board bootloader. Its fixed 64-record progress formula does NOT match the MP-3 packages; the MP-3 headers match a length-normalized formula.',
 'transferable':'Host record structure comparison only','not_transferable':'Flash base, bootloader preservation, reset/footswitch entry, recovery binaries'},
 'limits':['No claim that MP-3 lacks integrity/security checks elsewhere','Host-side checks, EXTR section and device-side validation remain separate',
 'Matching HID identity and headers across products do not prove matching bootloader behavior','No MP-3 pre-application loader obtained; sealed USB recovery remains unproven']}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'files':len(reports),'records':sum(r['records'] for r in reports)}))
