#!/usr/bin/env python3
"""Gate and assemble NAMLNK23 from the exact public Original file. No device I/O."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from nux_container_lab import Container
INPUT_SHA='39fa7057865f95e4c52c48544cd8284f4da606d3ac29e985e9b8938a3237467e'
def sha(b):return hashlib.sha256(b).hexdigest()
def need(ok,message):
 if not ok:raise ValueError(message)
def stage(stock_file,build_dir,reports,out):
 generated=build_dir.parent/'generated';meta=json.loads((build_dir/'build.json').read_text());elf=build_dir/'nam-link-offline.elf'
 need(meta['identity']=='NAMLNK23' and meta['stock_base']=='V3.0.5 Original','Public V3 build required')
 need(sha(elf.read_bytes())==meta['elf_sha256'],'ELF mismatch')
 need(set(meta['port_sources'])=={'prepare.py','relocations.json','image.py'},'Incomplete port provenance')
 for name,digest in meta['port_sources'].items():need(sha((ROOT/'ports/v3'/name).read_bytes())==digest,'Stale port source '+name)
 provenance=json.loads((generated/'port-provenance.json').read_text())
 need(sha((generated/'port-provenance.json').read_bytes())==meta['generated_provenance_sha256'],'Port provenance changed')
 for rel,row in provenance['files'].items():
  need(sha((ROOT/rel).read_bytes())==row['source_sha256'],'Original source changed '+rel)
  need(sha((generated/rel).read_bytes())==row['generated_sha256'],'Generated source changed '+rel)
 for rel,digest in {**meta['sources'],**meta['headers']}.items():need(sha((generated/rel).read_bytes())==digest,'Compiled source mismatch '+rel)
 need(sha((generated/'target/link/usb_nam.ld').read_bytes())==meta['linker_sha256'],'Linker mismatch')
 need('-DMPP_STOCK_V3' in meta['compiler_flags'] and '-DMPP_PITCH_QUALITY_RELEASE' in meta['compiler_flags'],'Required build flags')
 evidence={}
 for name,status in [('arm','PASS_OFFLINE_NAMLNK23'),('storage','PASS_NAMLNK10_STOCK_STORAGE_CONTRACT'),('runtime','PASS_OFFLINE_NAMLNK23_RUNTIME'),('chain','PASS_OFFLINE_NAMLNK23_PITCH_CHAIN')]:
  path=reports/(name+'.json');r=json.loads(path.read_text());need(r['status']==status and r['elf_sha256']==meta['elf_sha256'],'Missing/stale/failed '+name+' evidence');need(r.get('device_access') is False,'Offline evidence required');evidence[name]=sha(path.read_bytes())
  if name=='arm':need(all(r[k] for k in ['stereo_USB_PCM_ring_roundtrip','NAM_controls_both_transports','seven_presets_cold_warm_button','removed_NAM_no_callback']) and r['neutral_NAM_reference_peak_error']<2e-5,'ARM acceptance')
  if name=='runtime':need(len(r['cases'])==6 and r['guard_failures']==0 and r['global_buffers_restarted']==[32,16,8] and r['V3_SysEx_F7_inclusive_and_fragmentation'],'Runtime acceptance')
  if name=='chain':need(r['bypassed_pitch_callbacks']==0 and len(r['cases'])==3,'Pitch chain acceptance')
 stock=stock_file.read_bytes();need(sha(stock)==INPUT_SHA,'Exact public MP3_OR_V3.0.5.bin required; CT and other versions rejected')
 container=Container(stock);need(container.data[7]==2 and container.version=='20240812','Public container format')
 sys.path.insert(0,str(generated/'research'))
 from preset_image import build
 payload,symbols,plan=build(container.payload,elf)
 candidate=container.rebuild_same_length(payload);roundtrip=Container(candidate)
 need(roundtrip.payload==payload and len(candidate)==len(stock),'Container reconstruction')
 need(roundtrip.records[0]==container.records[0] and all(a[:28]==b[:28] for a,b in zip(roundtrip.records,container.records)),'Opaque update headers changed')
 need(payload[:0x400]==container.payload[:0x400] and payload[0x22618:0x229ac]==container.payload[0x22618:0x229ac],'Vectors/startup changed')
 need(payload[0x344000:0x360000]==b'\xff'*0x1c000,'Seeded bank forbidden')
 review=dict(identity='NAMLNK23',stock_base='V3.0.5 Original',input_sha256=sha(stock),output_sha256=sha(candidate),output_payload_sha256=sha(payload),elf_sha256=meta['elf_sha256'],evidence=evidence,candidate_plan=plan,factory_presets=False,source_bank_sha256=None,container_headers_preserved=True,device_access=False,flashed=False,physical_validation='pending',limitations=['Offline CPU and modeled peripherals only','Factory bootloader acceptance and recovery are not proven','Physical audio timing and Logic duplex need a later controlled hardware test'])
 out.mkdir(parents=True,exist_ok=True);(out/'NAMLNK23-public-v3-test.bin').write_bytes(candidate);(out/'NAMLNK23-review.json').write_text(json.dumps(review,indent=2)+'\n')
 return review
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for name in ['stock_file','build_dir','reports','output']:p.add_argument(name,type=Path)
 a=p.parse_args();r=stage(a.stock_file,a.build_dir,a.reports,a.output);print(json.dumps({k:r[k] for k in ['identity','stock_base','output_sha256','flashed','physical_validation']},indent=2))
