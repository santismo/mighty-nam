#!/usr/bin/env python3
"""Offline byte/record rollback coverage. This is NOT a USB restoration test."""
import argparse,hashlib,json,sys
from pathlib import Path
from a2_reclaimed_image import build
from a2_storage import SLOT_OFFSET,SLOT_SIZE
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nux_container_lab import Container
p=argparse.ArgumentParser();p.add_argument('stock_package',type=Path);p.add_argument('model',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();r=Path(__file__).resolve().parents[1]
c=Container(a.stock_package.read_bytes());stock=c.payload;candidate,sym,plan=build(stock,r/'artifacts/a2-reclaimed-v1-lab-only.elf',a.model)
regions=[(0x5578,0x5580,'AMP callback'),(0x5778,0x5780,'AMP init'),(0x57c0,0x57c2,'AMP background retirement'),(0x1a0a4,0x1b488,'Retired AMP code'),(SLOT_OFFSET,SLOT_OFFSET+SLOT_SIZE,'Retired AMP data model slot')]
changed=[i for i,(a,b) in enumerate(zip(stock,candidate)) if a!=b]
assert all(any(lo<=i<hi for lo,hi,_ in regions) for i in changed)
restored=bytearray(candidate)
for lo,hi,label in regions:restored[lo:hi]=stock[lo:hi]
assert restored==stock
# Reuse the stock record framing only in memory. No custom .bin is written.
rebuilt=c.rebuild_same_length(candidate);decoded=Container(rebuilt)
assert decoded.payload==candidate and len(rebuilt)==len(c.data)
assert all(x[:28]==y[:28] for x,y in zip(c.records,decoded.records))
pages=sorted({i//512 for i in changed})
assert all(c.records[page+1][28:]==stock[page*512:(page+1)*512] for page in pages)
res=dict(status='PASS_OFFLINE_RESTORE_BYTE_COVERAGE_ONLY',device_access=False,audio_playback=False,custom_image_written=False,custom_image_acceptance_proven=False,usb_restore_proven=False,stock_package_sha256=hashlib.sha256(c.data).hexdigest(),stock_payload_sha256=hashlib.sha256(stock).hexdigest(),candidate_sha256=plan['candidate_sha256'],changed_bytes=len(changed),changed_payload_pages=pages,all_changed_pages_in_original_stock_package=True,payload_length_unchanged=True,stock_record_headers_unchanged=True,in_memory_container_roundtrip=True,in_memory_rollback_restores_original_payload_sha256=True,regions=[dict(start=hex(lo),end=hex(hi),purpose=label,stock_sha256=hashlib.sha256(stock[lo:hi]).hexdigest(),candidate_sha256=hashlib.sha256(candidate[lo:hi]).hexdigest()) for lo,hi,label in regions],interpretation='The stock download contains original bytes for every byte this candidate changes. Actual USB restore still requires a surviving reachable loader with verified write/erase boundaries; container roundtrip is not acceptance proof.')
a.output.write_text(json.dumps(res,indent=2)+'\n');print(json.dumps({k:res[k] for k in ['status','changed_bytes','changed_payload_pages','usb_restore_proven']}))
