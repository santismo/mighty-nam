#!/usr/bin/env python3
"""Package NAMLNK20 only with exact-build offline evidence. Never accesses a device."""
import argparse,json,sys
from pathlib import Path
from nux_container_lab import Container,need,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from preset_image import build,BANK,BANK_END,FLASH
p=argparse.ArgumentParser(description=__doc__)
for name in ['stock_package','build_dir','reports','output_dir']:p.add_argument(name,type=Path)
p.add_argument('--controller-dir',type=Path,required=True,help='Tested public controller source checkout')
a=p.parse_args();elf=a.build_dir/'nam-link-offline.elf';digest=sha(elf.read_bytes());stock=a.stock_package.read_bytes();evidence={}
need(sha(stock)=='95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6','Exact V1.5.6 stock package required')
meta=json.loads((a.build_dir/'build.json').read_text());need(meta['elf_sha256']==digest and meta['identity']=='NAMLNK20','Wrong build')
need(meta.get('nam_pointer_taps') and '-DMPP_M7_POINTER_TAPS' in meta['compiler_flags'],'NAM pointer optimization missing')
root=Path(__file__).resolve().parents[1]
need(meta.get('headers') and meta.get('compact_tuner') and meta.get('same_preset_button_no_op') and meta.get('idle_fx_shortcut'),'Missing responsive build metadata')
need(meta.get('linker_sha256')==sha((root/'target/link/driver_timing.ld').read_bytes()),'Linker changed since build')
need(meta.get('active_chain') and '-DMPP_ACTIVE_CHAIN_RELEASE' in meta['compiler_flags'], 'Active graph missing')
need(not any(flag.startswith('-DMPP_DMA_') for flag in meta['compiler_flags']), 'DMA experiment excluded')
for source,expected in {**meta['sources'],**meta['headers']}.items():need(sha((root/source).read_bytes())==expected,'Source changed since build: '+source)
def read(name,status,bound=True):
 path=a.reports/(name+'.json');r=json.loads(path.read_text())
 need(r.get('status')==status and (not bound or r.get('elf_sha256')==digest),'Missing/mismatched '+name)
 evidence[name]=sha(path.read_bytes());return r
r=read('runtime','PASS_NAMLNK20_ARM_PRESET_RUNTIME')
need(all(r[k] for k in ['seven_slots','exact_model_and_effect_recall','stock_button_branch','button_skips_empty','duplicate_saves_do_not_write','failed_driver_write_preserves_saved_data']),'Preset regression')
need(r['cold_patterns']==[0,165,255] and r['warm_restarts']==3 and len(r['accuracy'])==2,'Startup regression')
need(all(x['blocks']>=1300 and x['max_error']<2e-5 and 0<x['peak']<=.109375 for x in r['accuracy']),'NAM reference regression')
r=read('fx-arm','PASS_NAMLNK20_ARM_FX_AND_PAGED_BLE')
need(all(r[k] for k in ['seven_independent_fx_presets','legacy_preset_defaults','duplicate_fx_saves_no_write','preset_fx_save_recall_restart','stock_order_unchanged','tuner_long_reply_reassembled','ram_guards']),'FX storage/transport gate')
need(r['cold_patterns']==[0,165,255] and r['dispatch_entries']>=700 and r['largest_paged_frame']<=56,'FX startup/page bounds')
r=read('cut-arm','PASS_NAMLNK20_CUT_EQ_ARM')
need(all(r[k] for k in ['real_CC_ingress','seven_independent_presets','warm_restarts','duplicate_save_no_write','fault_guard','ram_guards']),'Cut EQ control/preset regression')
need(r['dispatch_calls']>=320 and abs(r['combined_1kHz_dB']+6.0206)<.06 and r['cold_patterns']==[0,165,255] and r['stock_EQ_types']==[1,2,3],'Cut EQ response/restart regression')
r=read('cut-host','PASS_CUT_EQ_HOST',False)
need(r['cutoff_checks']==10 and r['sanitizers'] and r['exact_bypass'] and r['independent_filters'] and r['rapid_switching'],'Cut EQ host regression')
for source,expected in r['source_sha256'].items():need(sha((root/source).read_bytes())==expected,'Cut EQ source mismatch')
r=read('pitch','PASS_FX_PITCH_ANALYSIS',False)
need(len(r['cases'])==137 and r['max_error_cents']<5,'Pitch frequency regression')
for source,expected in r['source_sha256'].items():need(sha((root/source).read_bytes())==expected,'Pitch source mismatch')
r=read('responsive','PASS_NAMLNK20_RESPONSIVE_ARM')
need(all(r[k] for k in ['single_preset_no_reload','unsaved_settings_preserved','idle_fx_zero_dispatch','wake_and_fade_sleep','one_42_byte_reply_per_request','stale_generation_and_muted_only']),'Responsive firmware regression')
need(len(r['compact_tuner'])==4,'Tuner ARM vectors missing')
r=read('tuner-host','PASS_COMPACT_TUNER_HOST',False)
need(r['cases']>=117 and r['max_cents']<1 and r['silence_dc_noise_rejected'] and r['sanitizers'],'Tuner pitch regression')
for source,expected in r['source_sha256'].items():need(sha((root/source).read_bytes())==expected,'Tuner source mismatch')
r=read('global-arm','PASS_NAMLNK20_GLOBAL_BUFFER_ARM')
need(meta.get('global_persistent_buffer') and '-DMPP_GLOBAL_BUFFER' in meta['compiler_flags'],'Global buffer missing')
need(all(r[k] for k in ['empty_bank_persistence','seven_color_global_recall','physical_button_branch_keeps_global','settings_changes_do_not_write_presets','buffer_and_save_preserve_listening_intent','duplicate_setting_no_writes','failed_write_visible_and_old_setting_retained','fault_still_mutes','invalid_commands_ignored']),'Global settings regression')
need(r['cold_patterns']==[0,165,255] and r['warm_restarts']==3 and r['settings_flash_bounds']==['0x303a4000','0x303a6000'],'Global settings bounds/restarts')
r=read('global-host','PASS_GLOBAL_BUFFER_STORAGE_HOST',False)
need(r['cases']>=38 and r['sanitizers'] and r['torn_write_boundaries']==3,'Persistent global storage regression')
for source,expected in r['source_sha256'].items():need(sha((root/source).read_bytes())==expected,'Global store source mismatch')
r=read('arm','PASS_OFFLINE_ACTIVE_CHAIN')
need(r['identity']=='NAMLNK20' and all(r[k] for k in ['custom_removal_no_calls','invalid_topology_silent','restart_rebuild','saved_membership_recalled']), 'Graph membership/storage regression')
need([x['case'] for x in r['cases']]==['NAM','NAM-Spring','full','empty'], 'Graph coverage')
need(all(x['steady_output_exact'] and x['max_NAM_reference_error']<2e-5 and x['active_instructions']<x['baseline_instructions'] for x in r['cases']), 'PCM/work regression')
need(r['cases'][1]['actual_callbacks']==[3,8] and r['cases'][3]['actual_callbacks']==[], 'Inactive callbacks')
need(len(r['transitions'])==5 and all(x['blocks']>=1350 and x['NAM_error']<2e-5 for x in r['transitions']), 'Graph switching coverage')
r=read('startup','PASS_OFFLINE_ROUTING_STARTUP',False)
rows=[x for x in r['cases'] if x['identity']=='NAMLNK20']
need([x['fill'] for x in rows]==[0,165,255] and all(x['elf_sha256']==digest and x['cold_and_warm'] and x['reloaded'] and x['descriptor_bytes_unchanged'] and x['changed_register_writes']==[] for x in rows), 'Driver startup changed')
r=read('planner','PASS_ACTIVE_CHAIN_HOST',False)
need(r['cases']==450560 and r['sanitizers'], 'Planner coverage')
need(r['source_sha256']==sha((root/'target/link/active_chain.hpp').read_bytes()), 'Planner source mismatch')
r=read('controller','PASS_NAMLNK20_CONTROLLER_OFFLINE')
need(r['web_tests']>=105 and r['mac_app_tests']>=85 and r['native_fx_checks']>=85 and r['arm_wire_roundtrip'] and r['compact_browser_pass'] and r['analysis_no_errors_or_warnings'] and r['release_signature_verified'], 'Controller checks missing')
for key,base in [('phone_sources',a.controller_dir),('mac_sources',root.parent/'app')]:
 need(r.get(key), 'Controller source hashes missing')
 for source,expected in r[key].items():
  rel=Path(source);need(not rel.is_absolute() and '..' not in rel.parts, 'Invalid controller source path')
  need(sha((base/rel).read_bytes())==expected, 'Controller source changed since test: '+source)
original=Container(stock);need(original.rebuild_same_length(original.payload)==stock,'Stock roundtrip')
payload,_,plan=build(original.payload,elf);need(plan['identity']=='NAMLNK20','Wrong identity')
packed=original.rebuild_same_length(payload);decoded=Container(packed)
need(decoded.payload==payload and decoded.rebuild_same_length(payload)==packed,'Candidate roundtrip')
need(len(packed)==len(stock) and decoded.records[0]==original.records[0],'Setup record/size changed')
need(len(decoded.records)==len(original.records) and all(x[:28]==y[:28] for x,y in zip(decoded.records,original.records)),'Record headers changed')
need(payload[BANK-FLASH:BANK_END-FLASH]==b'\xff'*(BANK_END-BANK),'Bank not empty')
need(payload[0x303a4000-FLASH:0x303a6000-FLASH]==b'\xff'*8192,'Global settings not initialized empty')
need(payload[:0x400]==original.payload[:0x400] and payload[0x11d94:0x11dd8]==original.payload[0x11d94:0x11dd8],'Vectors/IRQ changed')
a.output_dir.mkdir(parents=True,exist_ok=True);target=a.output_dir/'NAMLNK20-active-chain-test.bin'
need(not target.exists() or target.read_bytes()==packed,'Refusing to replace a different staged candidate')
target.write_bytes(packed)
report=dict(status='STAGED_NAMLNK20_EXPERIMENTAL_NOT_INSTALLED', identity='NAMLNK20', elf_sha256=digest, candidate_sha256=sha(packed), bytes=len(packed), stock_sha256=sha(stock), candidate_plan=plan, required_report_hashes=evidence,
 physical_device_tested=False, physical_real_time_verified=False, physical_Bluetooth_verified=False, physical_latency_measured=False, additional_latency_reduction_claimed=False,
 firmware_update_preserves_bank=False, requires_current_preset_backup_and_restore=True, USB_recovery_for_this_image_verified=False, full_bootloader_backup=False, general_use_ready=False,
 active_only_chain=True, available_stock_categories=9, custom_fx_slots=2, removed_nodes_receive_callbacks=False, removed_tail_spillover=False, per_effect_memory_reclaimed=False,
 dma_current_prototype_included=False, driver_and_codec_same_as_NAMLNK19=True, graph_status_pages=[118,123], one_shot_driver_snapshot_available=False, whole_IRQ_timing=True,
 global_buffer_persistent=True, global_buffer_default=8, global_buffer_choices=[8,16,32], normal_edits_preserve_playback=True, sample_rate_hz=48000, processing_frames=8,
 USB_recording_regression_tested=False, host_audio_access=False, firmware_flashing=False,
 output='Empty bank boots muted. Saved presets may resume headphone output. Existing output protection remains.',
 controllers=dict(mac='0.4.0+15',phone='0.7.0'))
(a.output_dir/'NAMLNK20-review.json').write_text(json.dumps(report,indent=2)+'\n')
manifest=dict(schema='nam-plug-release-1',target='NUX-MP3',firmware=dict(identity='NAMLNK20',sha256=sha(packed),bytes=len(packed)),restore=dict(sha256=sha(stock),bytes=len(stock)),loader=dict(vid=0x9527,pid=0xc157,identifier='20220615'),mode='experimental-active-chain-empty-at-install')
(a.output_dir/'NAMLNK20-release.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','candidate_sha256','bytes']}))
