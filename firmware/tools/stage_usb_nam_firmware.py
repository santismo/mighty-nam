#!/usr/bin/env python3
"""Stage NAMLNK21/22 with matching offline evidence. No device/USB/audio operations."""
import argparse,json,sys,struct,zlib
from pathlib import Path
from nux_container_lab import Container,need,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from preset_image import build,BANK,BANK_END,FLASH
p=argparse.ArgumentParser(description=__doc__)
for name in ['stock_package','build_dir','reports','output_dir']:p.add_argument(name,type=Path)
p.add_argument('--seed-bank',type=Path,help='Optional locally owned capture bank, never published in source')
p.add_argument('--mac-preset-review',type=Path,help='NAMLNK22 validated local Mac bank review; preserves its captures/effects instead of factory defaults')
a=p.parse_args();root=Path(__file__).resolve().parents[1];elf=a.build_dir/'nam-link-offline.elf';digest=sha(elf.read_bytes());meta=json.loads((a.build_dir/'build.json').read_text())
identity=meta['identity'];pitch=identity=='NAMLNK22'
need(identity in ('NAMLNK21','NAMLNK22') and meta['elf_sha256']==digest,'Expected NAMLNK21/22 build')
need(('-DMPP_PITCH_QUALITY_RELEASE' in meta['compiler_flags'])==pitch,'Wrong pitch release flags')
need(not pitch or '-DMPP_PITCH_QUALITY_PROTOTYPE' in meta['compiler_flags'],'Missing pitch DSP')
need(meta['linker_sha256']==sha((root/'target/link/usb_nam.ld').read_bytes()),'Linker changed')
need('-DMPP_USB_NAM_CONTROLS' in meta['compiler_flags'] and not any(x.startswith('-DMPP_DMA_') for x in meta['compiler_flags']),'Wrong build flags')
for source,expected in {**meta['sources'],**meta['headers']}.items():need(sha((root/source).read_bytes())==expected,'Changed source '+source)
evidence={}
for name,status in [('arm','PASS_OFFLINE_'+identity),('storage','PASS_NAMLNK10_STOCK_STORAGE_CONTRACT')]:
 file=a.reports/(name+'.json');r=json.loads(file.read_text());need(r['status']==status and r['elf_sha256']==digest,'Mismatched '+name);evidence[name]=sha(file.read_bytes())
 if name=='arm':
  for k in ['stereo_USB_PCM_ring_roundtrip','class_mutes_verified','wet_record_excludes_host_return','NAM_controls_both_transports','seven_presets_cold_warm_button','removed_NAM_no_callback','USB_record_gain_guarded_and_persistent','USB_record_gain_headphone_independent']:need(r[k],k)
  need(r['neutral_NAM_reference_peak_error']<2e-5 and r['compiled_callback_blocks']>=1652,'DSP regression')
if pitch:
 for name,status in [('pitch','PASS_OFFLINE_PITCH_ARM'),('chain','PASS_OFFLINE_NAMLNK22_PITCH_CHAIN')]:
  file=a.reports/(name+'.json');r=json.loads(file.read_text());need(r['status']==status,'Wrong '+name+' status')
  need((r['elf_sha256']['prototype'] if name=='pitch' else r['elf_sha256'])==digest,'Mismatched '+name)
  if name=='pitch':
   need(r.get('pitch_release') is True and len(r['cases'])==6,'Missing release DSP checks')
   need(all(c['host_max_error']<2e-5 and c['blocks']>=1024 for c in r['cases']),'Pitch DSP mismatch')
  else:need(r['blocks']>=2501 and r['bypassed_pitch_callbacks']==0,'Pitch chain checks missing')
  evidence[name]=sha(file.read_bytes())
 file=a.reports/'quality.json';quality=json.loads(file.read_text());need(quality['status']=='PASS_OFFLINE_PITCH_QUALITY','Missing pitch quality evidence')
 for source,expected in quality['source_sha256'].items():need(sha((root/source).read_bytes())==expected,'Changed quality source '+source)
 need(quality['summary']['steady']['prototype_worst']<-30 and quality['summary']['vibrato']['prototype_worst']<12,'Pitch quality regression')
 evidence['quality']=sha(file.read_bytes())
stock=a.stock_package.read_bytes();need(sha(stock)=='95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6','Exact V1.5.6 package required')
original=Container(stock);need(original.rebuild_same_length(original.payload)==stock,'Stock roundtrip')
payload,_,plan=build(original.payload,elf);need(plan['identity']==identity,'Wrong image');payload=bytearray(payload)
seed_summary=[];mac_review=None
if a.mac_preset_review:
 need(pitch and a.seed_bank is not None,'Mac presets require NAMLNK22 and a seed bank')
 mac_review=json.loads(a.mac_preset_review.read_text())
 need(mac_review['status']=='PASS_OFFLINE_MAC_PRESET_BANK' and mac_review['elf_sha256']==digest and mac_review['cold_boot_and_nonadjacent_recalls'],'Mac bank verification missing')
 need(mac_review['bank_sha256']==sha(a.seed_bank.read_bytes()) and len(mac_review['presets'])==7,'Mac bank changed')
if a.seed_bank:
 bank=a.seed_bank.read_bytes();need(len(bank)==BANK_END-BANK,'Wrong bank length');normalized=bytearray(bank)
 word=lambda data,at:struct.unpack_from('<I',data,at)[0]
 for i in range(7):
  records=[bank[(i*2+c)*8192:(i*2+c+1)*8192] for c in [0,1]]
  valid=[r for r in records if word(r,0)==0x3142504e and word(r,4)==1 and word(r,8)==i and word(r,8188)==0x454e4f44 and word(r,8184)==zlib.crc32(r[:8184])]
  need(valid,'No valid factory preset');r=max(valid,key=lambda r:word(r,12))
  model=r[256:7772]+b'\xff'*(8192-7516)
  need(word(r,16)==zlib.crc32(model) and word(model,0)==0x3241504d and word(model,8)==48000 and word(model,12)==1871 and word(model,20)==zlib.crc32(model[32:7516]),'Invalid A2 Lite')
  need(r[32:64].hex()==sha(model),'Factory capture SHA mismatch')
  need(word(r,20)==1 and word(r,24)==8,'Seed output/buffer')
  if mac_review:
   expected=mac_review['presets'][i]
   need(expected['slot']==i and expected['model_sha256']==sha(model) and expected['model_crc']==word(r,16),'Mac capture mismatch')
   need(r[128:256]==bytes(expected['effects']) and word(r,7808)==0x33315846 and r[7812:7844]==bytes(expected['extra_fx']),'Mac effects mismatch')
   need(r[64:128]==expected['name'].encode('utf8').ljust(64,b'\0'),'Mac preset name mismatch')
  else:
   need(r[155:163]==bytes([48,12,12,12,100,48,78,2]) and r[163]==48,'Factory NAM controls')
   need([j for j in range(1,10) if not r[128+j]&64]==[3,8] and r[128+84]==37,'Factory two-block chain')
  for c in [0,1]:normalized[(i*2+c)*8192:(i*2+c+1)*8192]=r
  seed_summary.append(dict(slot=i,model_crc=word(r,16),model_sha256=r[32:64].hex(),play_on_boot=True,buffer=8,active_nodes=[j for j in range(1,10) if not r[128+j]&64],master_volume=r[128+84]))
 payload[BANK-FLASH:BANK_END-FLASH]=normalized
payload=bytes(payload);packed=original.rebuild_same_length(payload);decoded=Container(packed)
need(decoded.payload==payload and decoded.rebuild_same_length(payload)==packed,'Candidate roundtrip')
need(len(packed)==len(stock) and decoded.records[0]==original.records[0] and all(x[:28]==y[:28] for x,y in zip(decoded.records,original.records)),'Update record structure changed')
need(payload[:0x400]==original.payload[:0x400] and payload[0x11d94:0x11dd8]==original.payload[0x11d94:0x11dd8],'Vectors/IRQ changed')
need(payload[0x303a4000-FLASH:0x303a6000-FLASH]==b'\xff'*8192,'Global settings overlap')
out=a.output_dir;out.mkdir(parents=True,exist_ok=True);target=out/('NAMLNK22-pitch-quality-test.bin' if pitch else 'NAMLNK21-usb-audio-nam-controls-test.bin')
need(not target.exists() or target.read_bytes()==packed,'Different staged file already exists');target.write_bytes(packed)
report=dict(status='STAGED_'+identity+'_NOT_INSTALLED',identity=identity,elf_sha256=digest,candidate_sha256=sha(packed),bytes=len(packed),candidate_plan=plan,evidence=evidence,factory_presets=seed_summary,source_bank_sha256=sha(a.seed_bank.read_bytes()) if a.seed_bank else None,firmware_updates_preserve_user_presets=False,physical_Logic_duplex_verified=False,physical_real_time_verified=False,device_access=False,host_audio_access=False,firmware_flashing=False,controllers=dict(mac='0.5.1+20' if pitch else '0.5.0+19',phone='0.8.1' if pitch else '0.8.0'))
if mac_review:
 report['mac_presets']=report.pop('factory_presets');report['mac_preset_review_sha256']=sha(a.mac_preset_review.read_bytes())
(out/(identity+'-review.json')).write_text(json.dumps(report,indent=2)+'\n')
manifest=dict(schema='nam-plug-release-1',target='NUX-MP3',firmware=dict(identity=identity,sha256=sha(packed),bytes=len(packed)),restore=dict(sha256=sha(stock),bytes=len(stock)),loader=dict(vid=0x9527,pid=0xc157,identifier='20220615'),mode='experimental-pitch-quality' if pitch else 'experimental-usb-audio-nam-controls')
(out/(identity+'-release.json')).write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','candidate_sha256','bytes']}))
