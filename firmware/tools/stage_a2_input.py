#!/usr/bin/env python3
"""Stage a local silent A2 experiment after offline tests. No device I/O."""
import argparse,json,sys
from pathlib import Path
from nux_container_lab import Container,need,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from a2_input_image import build
from a2_storage import SLOT_OFFSET,SLOT_SIZE

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['stock_package','elf','model','test_report','protocol_report','output_dir']:p.add_argument(name,type=Path)
 a=p.parse_args();data=a.stock_package.read_bytes();tests=json.loads(a.test_report.read_text())
 protocol=json.loads(a.protocol_report.read_text())
 need(sha(data)=='95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6','Exact stock package required')
 need(tests['status']=='PASS_OFFLINE_BOUNDED_A2_LIVE_INPUT' and tests['elf_sha256']==sha(a.elf.read_bytes()),'Matching passing test report required')
 need(sum(x['model_sha256']==sha(a.model.read_bytes()) and x['cold_warm_output_identical'] and x['max_reference_error']<2e-5 for x in tests['model_runs'])>=3,'Exact model must pass all three cold/warm accuracy runs')
 need(protocol['status']=='PASS_A2_INPUT_REAL_INGRESS_AND_MALFORMED_QUERIES' and protocol['elf_sha256']==sha(a.elf.read_bytes()) and protocol['model_sha256']==sha(a.model.read_bytes()),'Matching protocol/model test required')
 original=Container(data);need(original.rebuild_same_length(original.payload)==data,'Stock round trip failed')
 payload,_,plan=build(original.payload,a.elf,a.model);packed=original.rebuild_same_length(payload);decoded=Container(packed)
 need(decoded.payload==payload and decoded.rebuild_same_length(decoded.payload)==packed,'Candidate round trip failed')
 need(len(packed)==len(data) and decoded.records[0]==original.records[0],'Setup record or file length changed')
 need(len(decoded.records)==len(original.records) and all(x[:28]==y[:28] for x,y in zip(decoded.records,original.records)),'Record headers changed')
 spans=[(int(s['start'],16),int(s['end_exclusive'],16)) for s in plan['elf_regions'] if s['name']!='.bss']
 spans += [(int(p['offset'],16),int(p['offset'],16)+len(bytes.fromhex(p['replacement']))) for p in plan['patches']]
 spans.append((SLOT_OFFSET,SLOT_OFFSET+SLOT_SIZE))
 changed=[i for i,(x,y) in enumerate(zip(original.payload,payload)) if x!=y]
 need(all(any(lo<=i<hi for lo,hi in spans) for i in changed),'Unplanned payload changes')
 need(payload[:0x400]==original.payload[:0x400] and payload[0x202a8:SLOT_OFFSET]==original.payload[0x202a8:SLOT_OFFSET] and payload[SLOT_OFFSET+SLOT_SIZE:]==original.payload[SLOT_OFFSET+SLOT_SIZE:],'Startup/vector/resource preservation failed')
 report={'status':'STAGED_EXPERIMENTAL_A2_LIVE_INPUT_NOT_INSTALLED','identity':'NAMA2I01','candidate_sha256':sha(packed),'stock_sha256':sha(data),
  'elf_sha256':sha(a.elf.read_bytes()),'model_source_sha256':sha(a.model.read_bytes()),'test_report_sha256':sha(a.test_report.read_bytes()),'protocol_report_sha256':sha(a.protocol_report.read_bytes()),
  'bytes':len(packed),'payload_changed_bytes':len(changed),'candidate_plan':plan,'round_trip_passed':True,'setup_and_all_record_headers_preserved':True,
  'vectors_and_startup_preserved':True,'only_high_resource_change':'8 KiB model slot in retired AMP12 data',
  'ready_for_bounded_hardware_trial':True,'general_use_ready':False,'physical_load_and_execution_verified':False,'audio_playback':False,'device_access':False,'uploader_included':False,
  'recovery_context':'NAMPB001 was recovered with exact stock after a failed application boot. NAMPB002 and NAMA2B01 returned to blue mode. NAMA2C01 completed two continuous trials across a normal restart; its blue-mode return remains to be checked. These specific observations do not guarantee this new build or arbitrary-damage recovery.',
  'interpretation_limits':['180,000 consecutive batches use raw signed Q31 slot 3 after 59,999 warmup callbacks. All output remains zero. Four input peak meters are included. Physical guitar mapping and input calibration are unverified; stock input conditioning and effects are bypassed.','DWT timestamps are uncalibrated; a concurrent reset may invalidate a span without detection.','Stock GPT1 times the callback body including housekeeping and zeroing, but excludes IRQ entry/exit and result accounting. Timer ticks remain conditional on the stock clock. Half alternation cannot detect an even number of missed releases.','No on-device model transfer is implemented; one CRC-checked model is bundled.']}
 a.output_dir.mkdir(parents=True,exist_ok=True);target=a.output_dir/'MP3-silent-A2-NAMA2I01-UNVERIFIED.bin'
 need(not target.exists() or target.read_bytes()==packed,'Refusing to replace a different staged image')
 target.write_bytes(packed);(a.output_dir/'review.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ['status','candidate_sha256','bytes','payload_changed_bytes','ready_for_bounded_hardware_trial']},indent=2))
if __name__=='__main__':main()
