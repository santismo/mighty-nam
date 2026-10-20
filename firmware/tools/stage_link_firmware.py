#!/usr/bin/env python3
"""Create a local silent link test image after exact-ELF offline checks. No device access."""
import argparse,json,sys
from pathlib import Path
from nux_container_lab import Container,need,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from link_image import build
p=argparse.ArgumentParser(description=__doc__)
for name in ['stock_package','elf','test_report','native_wire_report','output_dir']:p.add_argument(name,type=Path)
a=p.parse_args();stock=a.stock_package.read_bytes();tests=json.loads(a.test_report.read_text());native=json.loads(a.native_wire_report.read_text())
need(sha(stock)=='95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6','Exact V1.5.6 stock package required')
elf_sha=sha(a.elf.read_bytes())
need(tests.get('status')=='PASS_LINK_FIRMWARE_OFFLINE' and tests['elf_sha256']==elf_sha,'Matching firmware checks required')
need(len(tests['model_runs'])>=6 and all(x['silent_dma'] and x['max_reference_error']<2e-5 for x in tests['model_runs']),'Accuracy and restart checks missing')
need(native.get('status')=='PASS_DART_SWIFT_STOCK_ARM_LINK' and native['elf_sha256']==elf_sha and len(native['traces'])>=2,'Matching Mac wire checks required')
original=Container(stock);need(original.rebuild_same_length(original.payload)==stock,'Stock round trip failed')
payload,_,plan=build(original.payload,a.elf);packed=original.rebuild_same_length(payload);decoded=Container(packed)
need(decoded.payload==payload and decoded.rebuild_same_length(decoded.payload)==packed,'Candidate round trip failed')
need(len(packed)==len(stock) and decoded.records[0]==original.records[0],'Setup record or length changed')
need(len(decoded.records)==len(original.records) and all(x[:28]==y[:28] for x,y in zip(decoded.records,original.records)),'Record headers changed')
spans=[(int(s['start'],16),int(s['end_exclusive'],16)) for s in plan['elf_regions'] if s['name']!='.bss']
spans += [(int(p['offset'],16),int(p['offset'],16)+len(bytes.fromhex(p['replacement']))) for p in plan['patches']]
changed=[i for i,(x,y) in enumerate(zip(original.payload,payload)) if x!=y]
need(all(any(lo<=i<hi for lo,hi in spans) for i in changed),'Unplanned payload changes')
need(payload[:0x400]==original.payload[:0x400] and payload[0x202a8:]==original.payload[0x202a8:],'Vectors/startup/resources changed')
a.output_dir.mkdir(parents=True,exist_ok=True);target=a.output_dir/'MP3-silent-link-NAMLNK01-UNVERIFIED.bin'
need(not target.exists() or target.read_bytes()==packed,'Refusing to replace a different staged image')
target.write_bytes(packed)
report={'status':'STAGED_SILENT_LINK_NOT_INSTALLED','identity':'NAMLNK01','elf_sha256':elf_sha,'candidate_sha256':sha(packed),'bytes':len(packed),'stock_sha256':sha(stock),'payload_changed_bytes':len(changed),'candidate_plan':plan,'tests_sha256':sha(a.test_report.read_bytes()),'native_wire_tests_sha256':sha(a.native_wire_report.read_bytes()),'vectors_startup_resources_record_headers_preserved':True,'model_storage':'volatile RAM; empty after restart','output':'always zero','physical_device_tested':False,'general_use_ready':False,'full_signal_chain_control':False,'USB_recovery_for_this_image_verified':False,'full_bootloader_backup':False,'audio_playback':False}
(a.output_dir/'review.json').write_text(json.dumps(report,indent=2)+'\n')
manifest={'schema':'nam-plug-release-1','target':'NUX-MP3','firmware':{'identity':'NAMLNK01','sha256':sha(packed),'bytes':len(packed)},'restore':{'sha256':sha(stock),'bytes':len(stock)},'loader':{'vid':0x9527,'pid':0xc157,'identifier':'20220615'},'mode':'experimental-silent-RAM-model-link'}
(a.output_dir/'release.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','candidate_sha256','bytes','payload_changed_bytes']},indent=2))
