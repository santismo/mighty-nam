#!/usr/bin/env python3
"""Create a LOCAL REVIEW CANDIDATE from the user's exact stock package.
No USB/HID dependencies and no uploader. Matching a container format does not
establish device acceptance, protected erase boundaries or sealed recovery.
Never substitute a different NUX product, build, or an installed-image dump.
"""
import argparse,hashlib,json,sys
from pathlib import Path
from nux_container_lab import Container,need,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from stock_probe_image import build

def stage(stock_path,elf_path,out_dir):
 data=stock_path.read_bytes()
 need(sha(data)=='95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6',
      'Exact public MP3_V1.5.6_Original(VT).bin template required')
 original=Container(data);need(original.rebuild_same_length(original.payload)==data,'Stock round trip failed')
 payload,symbols,plan=build(original.payload,elf_path)
 packed=original.rebuild_same_length(payload);decoded=Container(packed)
 need(decoded.payload==payload,'Candidate decode does not match patched payload')
 need(len(packed)==len(data) and decoded.records[0]==original.records[0],'Setup/header changed')
 need(all(x[:28]==y[:28] for x,y in zip(decoded.records,original.records)),'Record header changed')
 need(decoded.rebuild_same_length(decoded.payload)==packed,'Candidate round trip failed')
 # Every changed byte must be in a linked code section or explicit patch.
 spans=[(int(s['start'],16),int(s['end_exclusive'],16)) for s in plan['elf_regions'] if s['name']!='.bss']
 spans += [(int(p['offset'],16),int(p['offset'],16)+len(bytes.fromhex(p['replacement']))) for p in plan['patches']]
 changed=[i for i,(a,b) in enumerate(zip(original.payload,payload)) if a!=b]
 need(all(any(lo<=i<hi for lo,hi in spans) for i in changed),'Unplanned payload change')
 need(payload[:0x400]==original.payload[:0x400] and payload[0x202a8:]==original.payload[0x202a8:],
      'Vector/reset/runtime/resource preservation failed')
 result={'status':'STAGED_UNVERIFIED_CONTAINER_FOR_REVIEW_ONLY','stock_container_sha256':sha(data),
  'candidate_container_sha256':sha(packed),'bytes':len(packed),'payload_changed_bytes':len(changed),
  'candidate_plan':plan,'original_container_round_trip':True,'candidate_container_round_trip':True,
  'all_record_headers_and_setup_preserved':True,'vectors_reset_runtime_and_high_resources_preserved':True,
  'stock_restore':{'path':str(stock_path.resolve()),'sha256':sha(data),
     'usable_only_if_factory_updater_remains_reachable':True,'full_device_backup':False},
  'ready_to_flash':False,'device_acceptance_proven':False,'loader_erase_boundaries_proven':False,
  'usb_recovery_proven':False,'physical_tests_required':['Loader acceptance and independently reachable recovery remain unresolved',
    'After a separately justified installation: marker query, fixed-register reads, audio-block counter, reset/re-entry checks'],
  'stock_dependency':'Exact public V1.5.6: blue setup 20220615, application 20220515. Current device state is recorded separately.',
  'device_access':False,'playback':False,'uploader_included':False}
 out_dir.mkdir(parents=True,exist_ok=True)
 target=out_dir/f"MP3-silent-probe-{plan['standard_version_marker']}-UNVERIFIED.bin"
 need(not target.exists() or target.read_bytes()==packed,'Refusing to overwrite a different staged image')
 target.write_bytes(packed)
 (out_dir/'review.json').write_text(json.dumps(result,indent=2)+'\n')
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('stock_package',type=Path);p.add_argument('probe_elf',type=Path);p.add_argument('output_dir',type=Path);a=p.parse_args()
 result=stage(a.stock_package,a.probe_elf,a.output_dir)
 print(json.dumps({k:result[k] for k in ['status','candidate_container_sha256','payload_changed_bytes','ready_to_flash','device_access','playback']},indent=2))
if __name__=='__main__':main()
