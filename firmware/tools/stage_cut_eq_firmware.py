#!/usr/bin/env python3
"""Package NAMLNK14 only with exact-build offline evidence. Never accesses a device."""
import argparse,json,sys
from pathlib import Path
from nux_container_lab import Container,need,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from preset_image import build,BANK,BANK_END,FLASH
p=argparse.ArgumentParser(description=__doc__)
for name in ['stock_package','build_dir','reports','output_dir']:p.add_argument(name,type=Path)
a=p.parse_args();elf=a.build_dir/'nam-link-offline.elf';digest=sha(elf.read_bytes());stock=a.stock_package.read_bytes();evidence={}
need(sha(stock)=='95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6','Exact V1.5.6 stock package required')
meta=json.loads((a.build_dir/'build.json').read_text());need(meta['elf_sha256']==digest and meta['identity']=='NAMLNK14','Wrong build')
root=Path(__file__).resolve().parents[1]
for source,expected in meta['sources'].items():need(sha((root/source).read_bytes())==expected,'Source changed since build: '+source)
def read(name,status,bound=True):
 path=a.reports/(name+'.json');r=json.loads(path.read_text())
 need(r.get('status')==status and (not bound or r.get('elf_sha256')==digest),'Missing/mismatched '+name)
 evidence[name]=sha(path.read_bytes());return r
r=read('runtime','PASS_NAMLNK14_ARM_PRESET_RUNTIME')
need(all(r[k] for k in ['seven_slots','exact_model_and_effect_recall','stock_button_branch','button_skips_empty','duplicate_saves_do_not_write','failed_driver_write_preserves_saved_data']),'Preset regression')
need(r['cold_patterns']==[0,165,255] and r['warm_restarts']==3 and len(r['accuracy'])==2,'Startup regression')
need(all(x['blocks']>=1300 and x['max_error']<2e-5 and 0<x['peak']<=.109375 for x in r['accuracy']),'NAM reference regression')
r=read('arm','PASS_NAMLNK14_ARM_FX_AND_PAGED_BLE')
need(all(r[k] for k in ['seven_independent_fx_presets','legacy_preset_defaults','duplicate_fx_saves_no_write','preset_fx_save_recall_restart','stock_order_unchanged','tuner_long_reply_reassembled','ram_guards']),'FX storage/transport gate')
need(r['cold_patterns']==[0,165,255] and r['dispatch_entries']>=700 and r['largest_paged_frame']<=56,'FX startup/page bounds')
r=read('regression','PASS_NAMLNK14_PLACEMENT_PCM_REGRESSION')
need(r['baseline13_rebuilt_exactly'] and r['stock_vectors_and_IRQ_preserved'] and r['timing_fault_mutes'],'Placement/fault regression')
need(len(r['bypassed_fx_PCM'])==3 and all(x['bit_identical'] and x['blocks']>=1350 for x in r['bypassed_fx_PCM']),'Bypass PCM regression')
need(r['full_chain_fx_pairs']==[[1,2],[3,4],[5,6],[7,1],[1,1]],'Full-chain FX regression')
need(r['full_chain_cut_eq_blocks']>=1350,'Cut EQ full chain regression')
r=read('cut-arm','PASS_NAMLNK14_CUT_EQ_ARM')
need(all(r[k] for k in ['real_CC_ingress','seven_independent_presets','warm_restarts','duplicate_save_no_write','fault_guard','ram_guards']),'Cut EQ control/preset regression')
need(r['dispatch_calls']>=320 and abs(r['combined_1kHz_dB']+6.0206)<.06 and r['cold_patterns']==[0,165,255] and r['stock_EQ_types']==[1,2,3],'Cut EQ response/restart regression')
r=read('cut-host','PASS_CUT_EQ_HOST',False)
need(r['cutoff_checks']==10 and r['sanitizers'] and r['exact_bypass'] and r['independent_filters'] and r['rapid_switching'],'Cut EQ host regression')
for source,expected in r['source_sha256'].items():need(sha((root/source).read_bytes())==expected,'Cut EQ source mismatch')
r=read('pitch','PASS_FX_PITCH_ANALYSIS',False)
need(len(r['cases'])==137 and r['max_error_cents']<5,'Pitch frequency regression')
for source,expected in r['source_sha256'].items():need(sha((root/source).read_bytes())==expected,'Pitch source mismatch')
r=read('controller','PASS_NAMLNK14_CONTROLLER_OFFLINE')
need(r['web_tests']>=49 and r['legacy_browser_pass'] and r['fx_browser_pass'] and r['mac_app_tests']>=63 and r['native_wire_checks']>=1586 and r['analysis_clean'] and r['release_signature_verified'],'Controller regression')
original=Container(stock);need(original.rebuild_same_length(original.payload)==stock,'Stock roundtrip')
payload,_,plan=build(original.payload,elf);need(plan['identity']=='NAMLNK14','Wrong identity')
packed=original.rebuild_same_length(payload);decoded=Container(packed)
need(decoded.payload==payload and decoded.rebuild_same_length(payload)==packed,'Candidate roundtrip')
need(len(packed)==len(stock) and decoded.records[0]==original.records[0],'Setup record/size changed')
need(len(decoded.records)==len(original.records) and all(x[:28]==y[:28] for x,y in zip(decoded.records,original.records)),'Record headers changed')
need(payload[BANK-FLASH:BANK_END-FLASH]==b'\xff'*(BANK_END-BANK),'Bank not empty')
need(payload[:0x400]==original.payload[:0x400] and payload[0x11d94:0x11dd8]==original.payload[0x11d94:0x11dd8],'Vectors/IRQ changed')
a.output_dir.mkdir(parents=True,exist_ok=True);target=a.output_dir/'NAMLNK14-high-low-cut-test.bin'
need(not target.exists() or target.read_bytes()==packed,'Refusing to replace a different staged candidate')
target.write_bytes(packed)
report=dict(status='STAGED_NAMLNK14_EXPERIMENTAL_NOT_INSTALLED',identity='NAMLNK14',elf_sha256=digest,candidate_sha256=sha(packed),bytes=len(packed),stock_sha256=sha(stock),candidate_plan=plan,required_report_hashes=evidence,
 physical_device_tested=False,physical_real_time_verified=False,physical_Bluetooth_verified=False,firmware_update_preserves_bank=False,requires_current_preset_backup_and_restore=True,USB_recovery_for_this_image_verified=False,full_bootloader_backup=False,general_use_ready=False,
 cut_eq=dict(type=4,slope_db_oct=12,low_cut_hz=[20,1000],high_cut_hz=[1000,20000],off_value=0),custom_fx_slots=2,pitch='Experimental monophonic; algorithm delay additional to output buffer',default_fx_enabled=False,sample_rate_hz=48000,processing_frames=8,host_audio_access=False,firmware_flashing=False,
 output='Empty bank boots muted. Saved presets may resume headphone output. Existing protection/scheduling preserved.')
(a.output_dir/'NAMLNK14-review.json').write_text(json.dumps(report,indent=2)+'\n')
manifest=dict(schema='nam-plug-release-1',target='NUX-MP3',firmware=dict(identity='NAMLNK14',sha256=sha(packed),bytes=len(packed)),restore=dict(sha256=sha(stock),bytes=len(stock)),loader=dict(vid=0x9527,pid=0xc157,identifier='20220615'),mode='experimental-high-low-cut-empty-at-install')
(a.output_dir/'NAMLNK14-release.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','candidate_sha256','bytes']}))
