#!/usr/bin/env python3
"""Stage a PRIVATE local NAMLNK25–29 trial after exact offline gates.
Requires the user's stock firmware and an already validated local preset bank.
Does not enumerate USB, invoke an updater, mute, reset or access host audio.
"""
import argparse,hashlib,json,sys
from pathlib import Path
from image import build

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
sha=lambda b:hashlib.sha256(b).hexdigest()

def stage(baseline,work,stock_file,bank_file,bank_report,output):
    sys.path[:0]=[str(baseline/'generated/research'),str(baseline/'generated/tools'),str(REPO/'firmware/tools')]
    from nux_container_lab import Container
    stock=Container(stock_file.read_bytes())
    if sha(stock_file.read_bytes())!='39fa7057865f95e4c52c48544cd8284f4da606d3ac29e985e9b8938a3237467e':raise ValueError('Exact MP3_OR_V3.0.5.bin required')
    elf=work/'build/loop-startup-test.elf';manifest=json.loads((work/'build/build.json').read_text())
    identity=manifest['identity']
    if identity not in ['NAMLNK25','NAMLNK26','NAMLNK27','NAMLNK28','NAMLNK29']:raise ValueError('Unsupported diagnostic identity')
    extended=identity in ['NAMLNK26','NAMLNK27','NAMLNK28','NAMLNK29']
    if manifest['sha256']!=sha(elf.read_bytes()):raise ValueError('ELF does not match build manifest')
    for name,digest in manifest['source_hashes'].items():
        if sha((ROOT.parent/name).read_bytes())!=digest:raise ValueError('Source changed: '+name)
    payload,symbols,plan=build(stock.payload,baseline/'build/nam-link-offline.elf',elf,identity)
    expected={'startup.json':'PASS_OFFLINE_LOOP_STARTUP','audio.json':'PASS_OFFLINE_LOOP_GUITAR_AND_MEDIA','continuity-test.json':'PASS_OFFLINE_STARTUP_PRESET_LOOP'}
    reports={}
    for file,status in expected.items():
        r=json.loads((work/file).read_text());reports[file]=r
        if r['status']!=status or r.get('elf_sha256',r.get('overlay_sha256'))!=manifest['sha256'] or r['candidate_payload_sha256']!=sha(payload):raise ValueError('Missing/stale offline gate: '+file)
    boot=reports['startup.json'];audio=reports['audio.json'];loop=reports['continuity-test.json']
    if not(boot['startup_bytes_checked']==371316 and boot['startup_pattern_passes']==2 and boot['warm_dirty_state_cleared'] and boot['normal_output_on_after_restart'] and len(boot['negative_controls'])==4 and len(boot['timing_negative_controls'])==3):raise ValueError('Startup/fault coverage incomplete')
    if not(all(c['output_exact'] and c['USB_record_exact'] for c in audio['cases']) and len(audio['cases'])==3 and audio['stereo_bluetooth_exact'] and audio['stereo_USB_ring_paths']):raise ValueError('Guitar/media regression')
    masks_ok=(0<loop['rejected_save_masked_instructions']<=32 and
        loop['masked_foreground_instructions']==loop['rejected_save_masked_instructions']+(loop.get('button_mailbox_masked_instructions',0) if extended else 0))
    if not(loop['startup_copy_used'] and loop['callbacks']>8000 and loop['interleaved_IRQs']>1000 and loop['recall_masked_instructions']==0 and masks_ok and loop['max_native_loop_sample_error']<2e-6 and loop['max_paused_guitar_PCM_error']<=2 and loop['guards_intact'] and loop['recording_unchanged'] and loop['actual_recording_hook']['encoded_bytes_match_native'] and loop['stop_resume_clear_controls']):raise ValueError('Loop continuity gate failed')
    extra_evidence={}
    if extended:
        if not boot.get('arm_during_idle_sweep_safe'):raise ValueError('Idle-sweep arming coverage missing')
        if not(loop.get('overdub_encoded_bytes_match_native') and len(loop.get('overdub_preset_recalls',[]))==3 and loop.get('layer_commits',0)>0 and 0<loop.get('max_masked_instruction_run',999)<=64):raise ValueError('Overdub continuity gate failed')
        for name,status in [('layers-arm.json','PASS_OFFLINE_ARM_LAYERS'),('buttons.json','PASS_OFFLINE_STOCK_BUTTON_LED_ADAPTER')]:
            r=json.loads((work/name).read_text());extra_evidence[name]=sha((work/name).read_bytes())
            if r['status']!=status or r['elf_sha256']!=manifest['sha256']:raise ValueError('Missing/stale extended gate: '+name)
            if name=='layers-arm.json' and not(r['settings_readback'] and r['clear_while_overdubbing'] and r['guard_fault_guitar_unchanged']):raise ValueError('Layer control gate failed')
            if identity in ['NAMLNK27','NAMLNK28','NAMLNK29'] and name=='layers-arm.json' and not r.get('live_meter_in_compact_status'):raise ValueError('Live meter coverage missing')
            if identity in ['NAMLNK27','NAMLNK28','NAMLNK29'] and name=='buttons.json' and not r.get('phone_arm_physical_short_tap_finish'):raise ValueError('Short tap coverage missing')
            if name=='buttons.json' and not(r['power_double_enter'] and r['threshold_arm'] and (r.get('tap_hold_clear') and r.get('hold_overdub') and r.get('hold_previous_once') if identity in ['NAMLNK28','NAMLNK29'] else r['hold_preset_clear']) and r['stock_volume_preserved'] and r['stock_power_hold_shutdown']):raise ValueError('Button gate failed')
        native_gates=[('offline/takes.json','PASS_INDEPENDENT_TAKES')] if identity=='NAMLNK29' else [('offline/layers.json','PASS_OFFLINE_LAYERS')]
        for name,status in native_gates+[('offline/full-duration.json','PASS_FULL_DURATION_NAM_LAYERS')]:
            r=json.loads((work/name).read_text());extra_evidence[name]=sha((work/name).read_bytes())
            if r['status']!=status or r['loop_storage_bytes' if name.endswith('full-duration.json') else 'storage_bytes']!=371316:raise ValueError('Native layer gate failed')
            if name.endswith('layers.json') and r.get('partial_layer_cases')!=3484:raise ValueError('Partial layer coverage missing')
            if name.endswith('takes.json') and not(r.get('boundary_cases')==49 and all(r.get(k) for k in ['multi_pass_undo','base_unchanged','cross_window','full_capacity_rejected'])):raise ValueError('Independent lane coverage missing')
            if name.endswith('full-duration.json') and not((r['callbacks'],r['nam_model_changes'])==((2700000,86) if identity=='NAMLNK29' else (1620000,52))):raise ValueError('Full duration coverage missing')
        if identity in ['NAMLNK27','NAMLNK28','NAMLNK29']:
            quality=json.loads((work/'offline/quality.json').read_text())
            if quality.get('status')!='PASS_OFFLINE_OVERDUB_QUALITY' or quality['snr_db']<=25 or quality['block_start_error_rms']>=250:raise ValueError('Overdub quality gate failed')
            extra_evidence['offline/quality.json']=sha((work/'offline/quality.json').read_bytes())
        native_sources=json.loads((work/'offline/source-hashes.json').read_text())
        for name,digest in native_sources.items():
            if sha((ROOT.parent/name).read_bytes())!=digest:raise ValueError('Native source changed: '+name)
        extra_evidence['offline/source-hashes.json']=sha((work/'offline/source-hashes.json').read_bytes())
    if identity in ['NAMLNK28','NAMLNK29']:
        r=json.loads((work/'settings.json').read_text())
        if r['status']!='PASS_OFFLINE_ARM_LOOP_SETTINGS' or r['elf_sha256']!=manifest['sha256'] or not all(r[k] for k in ['live_unsaved_restart','saved_threshold_level_duration_restart','global_buffer_preserved','unsaved_level_not_saved_by_buffer','armed_save_rejected','presets_unchanged','playback_state_preserved','USB_BLE_save']):raise ValueError('Settings persistence gate failed')
        native=json.loads((work/'offline/settings-store.json').read_text())
        if native['status']!='PASS_LOOP_SETTINGS_STORE' or native['interrupted_write_cases']!=261:raise ValueError('Interrupted settings coverage missing')
        for name in ['settings.json','offline/settings-store.json','offline/gestures.json']:extra_evidence[name]=sha((work/name).read_bytes())
    if identity=='NAMLNK29':
        lanes=json.loads((work/'layers-arm.json').read_text())
        if lanes.get('independent_lanes')!=3 or not all(lanes.get(k) for k in ['existing_lane_multi_pass','undo_redo','individual_level_mute_delete']):raise ValueError('Compiled lane controls missing')
        r=json.loads((work/'seven-presets.json').read_text())
        if r.get('status')!='PASS_SEVEN_PRESETS_STALE_AHB' or r.get('elf_sha256')!=manifest['sha256'] or not all(r.get(k) for k in ['seven_slots','USB_BLE','random_recall','restart_and_button_cycle','failed_write_preserves_previous']):raise ValueError('Seven-preset gate failed')
        extra_evidence['seven-presets.json']=sha((work/'seven-presets.json').read_bytes())
        cache=json.loads((work/'seven-presets-cpu.json').read_text())
        if cache.get('status')!='PASS_NAMLNK29_SEVEN_CPU_CACHE' or cache.get('elf_sha256')!=manifest['sha256'] or cache.get('saves',0)<21 or not all(cache.get(k) for k in ['USB_BLE','overwrite_and_random_recall','restart','button_cycle','failed_write_preserves_previous','original_failure_reproduced']):raise ValueError('CPU cache seven-preset coverage missing')
        extra_evidence['seven-presets-cpu.json']=sha((work/'seven-presets-cpu.json').read_bytes())
        vm=json.loads((work/'vm-observer.json').read_text())
        if vm.get('status')!='PASS_VM_OBSERVER_REGRESSION' or not vm.get('unobserved_programs_pass'):raise ValueError('Emulator observer regression missing')
        extra_evidence['vm-observer.json']=sha((work/'vm-observer.json').read_bytes())
    bank=bank_file.read_bytes();before=json.loads(bank_report.read_text())
    if len(bank)!=0x1c000 or sha(bank)!=before['bank_sha256'] or len(before['presets']) not in (3,7):raise ValueError('Local preset bank mismatch')
    data=bytearray(payload);data[0x344000:0x360000]=bank
    encoded=stock.rebuild_same_length(bytes(data));final=Container(encoded)
    assert final.payload==bytes(data) and len(encoded)==len(stock.data)
    assert final.records[0]==stock.records[0] and all(x[:28]==y[:28] for x,y in zip(final.records,stock.records))
    assert final.payload[:0x400]==stock.payload[:0x400] and final.payload[0x22618:0x229ac]==stock.payload[0x22618:0x229ac]
    assert final.payload[0x344000:0x360000]==bank
    name=identity+'-looper-lanes-test.bin' if identity=='NAMLNK29' else identity+'-looper-layers-test.bin' if extended else 'NAMLNK25-looper-ram-timing-test.bin'
    report=dict(status='PASS_LOCAL_'+identity+'_DIAGNOSTIC_STAGING',identity=identity,file=name,sha256=sha(encoded),bytes=len(encoded),
        elf_sha256=manifest['sha256'],payload_sha256=sha(data),bank_sha256=sha(bank),local_presets_unchanged=True,preset_count=len(before['presets']),
        presets=[{k:r[k] for k in ['color','color_name','name','model_crc','model_sha256']} for r in before['presets']],
        play_on_boot=True,looper_active_on_boot=False,live_sample_rate=48000,callback_frames=8,
        storage_bytes=371316,recording_seconds=30,recording_sample_rate=24000,recording_format='mono IMA ADPCM',optional_60_seconds_at_12000_Hz=extended,merged_overdubs=extended and identity!='NAMLNK29',independent_lanes=3 if identity=='NAMLNK29' else 0,undo_levels=1 if identity=='NAMLNK29' else 0,
        private_diagnostic_build=True,public_release=False,physical_RAM_safe_proven=False,physical_timing_verified=False,
        boot_copy_implemented=True,physical_looper_buttons_implemented=extended,looper_phone_UI_implemented=extended,
        required_controller_versions={'phone':'0.10.0','mac':'0.6.1'} if identity=='NAMLNK29' else {'phone':'0.9.0','mac':'0.6.0'} if identity in ['NAMLNK28','NAMLNK29'] else {'phone':'0.8.7','mac':'0.5.8'} if identity=='NAMLNK27' else {'phone':'0.8.6','mac':'0.5.7'} if extended else {'phone':'0.8.5','mac':'0.5.6'},standard_protocol_unchanged=True,
        flash_and_vectors_preserved=True,preset_writes_blocked_while_loop_exists=True,
        sources=manifest['source_hashes'],evidence={**{n:sha((work/n).read_bytes()) for n in expected},**extra_evidence},
        device_access=False,host_audio_access=False,flashed=False,auto_mute_sent=False)
    # Do not create any output until every gate above has passed.
    output.mkdir(parents=True,exist_ok=True);file=output/name
    if file.exists() and file.read_bytes()!=encoded:raise ValueError('Refusing to replace a different staged image')
    file.write_bytes(encoded);(output/'SHA256SUMS.txt').write_text(f'{sha(encoded)}  {name}\n')
    (output/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','work','stock','bank','bank_report','output']:p.add_argument(name,type=Path)
    a=p.parse_args();r=stage(a.baseline,a.work,a.stock,a.bank,a.bank_report,a.output);print(json.dumps({k:r[k] for k in ['status','file','sha256','flashed']},indent=2))
