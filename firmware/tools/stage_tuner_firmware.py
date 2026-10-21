#!/usr/bin/env python3
"""Stage a local NAMLNK12 trial only with exact-ELF offline evidence. No device access."""
import argparse,json,sys
from pathlib import Path
from nux_container_lab import Container,need,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from preset_image import build,BANK,BANK_END,FLASH
p=argparse.ArgumentParser(description=__doc__)
for name in ['stock_package','elf','reports','output_dir']:p.add_argument(name,type=Path)
a=p.parse_args();stock=a.stock_package.read_bytes();digest=sha(a.elf.read_bytes());evidence={}
need(sha(stock)=='95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6','Exact V1.5.6 stock package required')
def read(name,status):
 path=a.reports/(name+'.json');r=json.loads(path.read_text())
 need(r.get('status')==status and r.get('elf_sha256')==digest,'Missing/mismatched '+name)
 evidence[name]=sha(path.read_bytes());return r
r=read('prime','PASS_NAMLNK12_PRIME_CACHE_COVERAGE')
need(len(r['cases'])==24 and all(x['coverage'] and x['state_unchanged'] for x in r['cases']),'Cache coverage gate')
need(r['model_read_reduction_min']>.8 and r['instruction_reduction_min']>.6,'Preparation work regression')
r=read('profiler','PASS_NAMLNK12_EFFECT_PROFILER')
need(len(r['cases'])==33 and all(x['bit_identical'] for x in r['cases']),'Stage PCM comparison gate')
need(all(r[k] for k in ['default_disabled','invalid_commands_ignored','IRQ_commands_rejected','disabled_counts_frozen','snapshot_coherent_and_frozen','odd_sequence_rejected','counter_disabled_rejected','warm_restart_clears']),'Profiler protocol gate')
r=read('counter','PASS_NAMLNK12_PROFILER_COUNTER_ABI')
need(r['counter_cases']>=138 and all(r[k] for k in ['callees_and_stack_preserved','no_counter_writes','wrap_reset_disabled_saturation_checked','snapshot_preemption_retry_and_busy_checked']),'Counter gate')
r=read('runtime','PASS_NAMLNK12_ARM_PRESET_RUNTIME')
need(all(r[k] for k in ['seven_slots','exact_model_and_effect_recall','stock_button_branch','button_skips_empty','duplicate_saves_do_not_write','failed_driver_write_preserves_saved_data']),'Preset gate')
need(r['cold_patterns']==[0,165,255] and r['warm_restarts']==3 and len(r['accuracy'])==2,'Restart gate')
need(all(x['blocks']>=1300 and x['max_error']<2e-5 and 0<x['peak']<=.109375 for x in r['accuracy']),'Model reference gate')
r=read('placement','PASS_NAMLNK12_PLACEMENT_REGRESSION')
need(r['baseline10_rebuilt_exactly'] and r['output_and_storage_objects_unchanged'] and r['stock_vectors_and_IRQ_preserved'],'Placement gate')
r=read('controller','PASS_NAMLNK12_MAC_CONTROLLER_OFFLINE')
need(r['app_tests']>=60 and r['native_wire_checks']>=1573 and r['analysis_clean'] and r['release_build_verified'],'Controller gate')
r=read('native-preset-wire','PASS_NAMLNK12_NATIVE_PRESET_WIRE')
need(r['operations']==3 and r['actual_stock_receive_ring'] and r['muted'],'Wire gate')
r=read('tuner-arm','PASS_NAMLNK12_TUNER_ARM')
need(r['captured_samples']==2048 and r['full_chain_blocks_identical']>=1024,'Tuner sample/PCM gate')
need(all(r[k] for k in ['actual_stock_ingress','both_usb_channels','exact_dry_input_decimation','starts_muted_only','auto_stop_and_snapshot_frozen','invalid_and_irq_requests_ignored','warm_restart_clears','works_without_model','no_flash_writes']),'Tuner protocol gate')
r=read('tuner-host','PASS_NAMLNK12_TUNER_HOST')
need(r['sanitizer_capture_cases']>=1039 and r['native_wire_cases']>=921 and r['pitch_cases']>=84 and r['pitch_error_bound_cents']<=2 and r['mute_and_close_lifecycle_checked'],'Host tuner gate')
original=Container(stock);need(original.rebuild_same_length(original.payload)==stock,'Stock roundtrip')
payload,_,plan=build(original.payload,a.elf);need(plan['identity']=='NAMLNK12','Wrong image identity')
packed=original.rebuild_same_length(payload);decoded=Container(packed)
need(decoded.payload==payload and decoded.rebuild_same_length(payload)==packed,'Candidate roundtrip')
need(len(packed)==len(stock) and decoded.records[0]==original.records[0],'Setup record/size changed')
need(len(decoded.records)==len(original.records) and all(x[:28]==y[:28] for x,y in zip(decoded.records,original.records)),'Record headers changed')
need(payload[BANK-FLASH:BANK_END-FLASH]==b'\xff'*(BANK_END-BANK),'First-install bank not empty')
need(payload[:0x400]==original.payload[:0x400] and payload[0x11d94:0x11dd8]==original.payload[0x11d94:0x11dd8],'Vector or IRQ body changed')
a.output_dir.mkdir(parents=True,exist_ok=True);target=a.output_dir/'NAMLNK12-tuner-performance-test.bin'
need(not target.exists() or target.read_bytes()==packed,'Refusing to replace a different staged trial')
target.write_bytes(packed)
report=dict(status='STAGED_NAMLNK12_PERFORMANCE_TRIAL_NOT_INSTALLED',identity='NAMLNK12',elf_sha256=digest,candidate_sha256=sha(packed),bytes=len(packed),stock_sha256=sha(stock),candidate_plan=plan,required_report_hashes=evidence,
 tuner_default_enabled=False,tuner_capture_samples=2048,tuner_sample_rate_hz=12000,host_audio_streams_opened=False,default_profiler_enabled=False,latency_samples_changed=False,sample_rate_hz=48000,processing_frames=8,
 stock_tail_policy_changed=False,physical_performance_gain_verified=False,physical_device_tested=False,
 firmware_update_preserves_bank=False,requires_current_preset_backup_and_restore=True,
 USB_recovery_for_this_image_verified=False,full_bootloader_backup=False,general_use_ready=False,
 output='Empty bank boots muted. Saved presets may play on boot. Existing output protection/scheduling preserved.',host_audio_access=False,firmware_flashing=False)
(a.output_dir/'review.json').write_text(json.dumps(report,indent=2)+'\n')
manifest=dict(schema='nam-plug-release-1',target='NUX-MP3',firmware=dict(identity='NAMLNK12',sha256=sha(packed),bytes=len(packed)),restore=dict(sha256=sha(stock),bytes=len(stock)),loader=dict(vid=0x9527,pid=0xc157,identifier='20220615'),mode='experimental-tuner-performance-empty-at-install')
(a.output_dir/'release.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','candidate_sha256','bytes']}))
