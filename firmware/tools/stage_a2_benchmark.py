#!/usr/bin/env python3
"""Stage a local silent A2 experiment after offline tests. No device I/O."""
import argparse,json,sys
from pathlib import Path
from nux_container_lab import Container,need,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from a2_benchmark_image import build
from a2_storage import SLOT_OFFSET,SLOT_SIZE

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['stock_package','elf','model','test_report','protocol_report','output_dir']:p.add_argument(name,type=Path)
 a=p.parse_args();data=a.stock_package.read_bytes();tests=json.loads(a.test_report.read_text())
 protocol=json.loads(a.protocol_report.read_text())
 need(sha(data)=='95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6','Exact stock package required')
 need(tests['status']=='PASS_OFFLINE_BOUNDED_A2_BENCHMARK' and tests['elf_sha256']==sha(a.elf.read_bytes()),'Matching passing test report required')
 need(a.model.name in [x['model'] for x in tests['model_runs']],'Model name not represented in test run')
 need(protocol['status']=='PASS_A2_BENCHMARK_REAL_INGRESS_AND_MALFORMED_QUERIES' and protocol['elf_sha256']==sha(a.elf.read_bytes()) and protocol['model_sha256']==sha(a.model.read_bytes()),'Matching protocol/model test required')
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
 report={'status':'STAGED_EXPERIMENTAL_A2_BENCHMARK_NOT_INSTALLED','identity':'NAMA2B01','candidate_sha256':sha(packed),'stock_sha256':sha(data),
  'elf_sha256':sha(a.elf.read_bytes()),'model_source_sha256':sha(a.model.read_bytes()),'test_report_sha256':sha(a.test_report.read_bytes()),'protocol_report_sha256':sha(a.protocol_report.read_bytes()),
  'bytes':len(packed),'payload_changed_bytes':len(changed),'candidate_plan':plan,'round_trip_passed':True,'setup_and_all_record_headers_preserved':True,
  'vectors_and_startup_preserved':True,'only_high_resource_change':'8 KiB model slot in retired AMP12 data',
  'flash_ready':False,'physical_load_and_execution_verified':False,'audio_playback':False,'device_access':False,'uploader_included':False,
  'recovery_context':'NAMPB002 ran, restarted normally and returned to responsive blue mode. NAMPB001 failure was previously recovered by restoring stock. Neither result guarantees this new build or arbitrary-damage recovery.',
  'interpretation_limits':['Sparse synthetic batches are a processing-cost screen, not continuous live guitar processing.','DWT timestamps are uncalibrated; a concurrent reset may invalidate a span without detection.','No effects-chain deadline, complete-IRQ timing or DMA underrun proof is provided.','No on-device model transfer is implemented; one CRC-checked model is bundled.']}
 a.output_dir.mkdir(parents=True,exist_ok=True);target=a.output_dir/'MP3-silent-A2-NAMA2B01-UNVERIFIED.bin'
 need(not target.exists() or target.read_bytes()==packed,'Refusing to replace a different staged image')
 target.write_bytes(packed);(a.output_dir/'review.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ['status','candidate_sha256','bytes','payload_changed_bytes','flash_ready']},indent=2))
if __name__=='__main__':main()
