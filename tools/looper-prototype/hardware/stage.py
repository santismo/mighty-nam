#!/usr/bin/env python3
"""Stage a PRIVATE local NAMLNK25 RAM/timing trial after exact offline gates.
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
    if manifest['sha256']!=sha(elf.read_bytes()):raise ValueError('ELF does not match build manifest')
    for name,digest in manifest['source_hashes'].items():
        if sha((ROOT.parent/name).read_bytes())!=digest:raise ValueError('Source changed: '+name)
    payload,symbols,plan=build(stock.payload,baseline/'build/nam-link-offline.elf',elf)
    expected={'startup.json':'PASS_OFFLINE_LOOP_STARTUP','audio.json':'PASS_OFFLINE_LOOP_GUITAR_AND_MEDIA','continuity-test.json':'PASS_OFFLINE_STARTUP_PRESET_LOOP'}
    reports={}
    for file,status in expected.items():
        r=json.loads((work/file).read_text());reports[file]=r
        if r['status']!=status or r.get('elf_sha256',r.get('overlay_sha256'))!=manifest['sha256'] or r['candidate_payload_sha256']!=sha(payload):raise ValueError('Missing/stale offline gate: '+file)
    boot=reports['startup.json'];audio=reports['audio.json'];loop=reports['continuity-test.json']
    if not(boot['startup_bytes_checked']==371316 and boot['startup_pattern_passes']==2 and boot['warm_dirty_state_cleared'] and boot['normal_output_on_after_restart'] and len(boot['negative_controls'])==4 and len(boot['timing_negative_controls'])==3):raise ValueError('Startup/fault coverage incomplete')
    if not(all(c['output_exact'] and c['USB_record_exact'] for c in audio['cases']) and len(audio['cases'])==3 and audio['stereo_bluetooth_exact'] and audio['stereo_USB_ring_paths']):raise ValueError('Guitar/media regression')
    if not(loop['startup_copy_used'] and loop['callbacks']>8000 and loop['interleaved_IRQs']>1000 and loop['recall_masked_instructions']==0 and loop['masked_foreground_instructions']==loop['rejected_save_masked_instructions']<=32 and loop['max_native_loop_sample_error']<2e-6 and loop['max_paused_guitar_PCM_error']<=2 and loop['guards_intact'] and loop['recording_unchanged'] and loop['actual_recording_hook']['encoded_bytes_match_native'] and loop['stop_resume_clear_controls']):raise ValueError('Loop continuity gate failed')
    bank=bank_file.read_bytes();before=json.loads(bank_report.read_text())
    if len(bank)!=0x1c000 or sha(bank)!=before['bank_sha256'] or len(before['presets'])!=3:raise ValueError('Local three-preset bank mismatch')
    data=bytearray(payload);data[0x344000:0x360000]=bank
    encoded=stock.rebuild_same_length(bytes(data));final=Container(encoded)
    assert final.payload==bytes(data) and len(encoded)==len(stock.data)
    assert final.records[0]==stock.records[0] and all(x[:28]==y[:28] for x,y in zip(final.records,stock.records))
    assert final.payload[:0x400]==stock.payload[:0x400] and final.payload[0x22618:0x229ac]==stock.payload[0x22618:0x229ac]
    assert final.payload[0x344000:0x360000]==bank
    name='NAMLNK25-looper-ram-timing-test.bin'
    report=dict(status='PASS_LOCAL_NAMLNK25_DIAGNOSTIC_STAGING',identity='NAMLNK25',file=name,sha256=sha(encoded),bytes=len(encoded),
        elf_sha256=manifest['sha256'],payload_sha256=sha(data),bank_sha256=sha(bank),local_three_presets_unchanged=True,
        presets=[{k:r[k] for k in ['color','color_name','name','model_crc','model_sha256']} for r in before['presets']],
        play_on_boot=True,looper_active_on_boot=False,live_sample_rate=48000,callback_frames=8,
        storage_bytes=371316,recording_seconds=30,recording_sample_rate=24000,recording_format='mono IMA ADPCM',
        private_diagnostic_build=True,public_release=False,physical_RAM_safe_proven=False,physical_timing_verified=False,
        boot_copy_implemented=True,physical_looper_buttons_implemented=False,looper_UI_implemented=False,
        current_app_identity_allowlist_update_needed=True,standard_protocol_unchanged=True,
        flash_and_vectors_preserved=True,preset_writes_blocked_while_loop_exists=True,
        sources=manifest['source_hashes'],evidence={n:sha((work/n).read_bytes()) for n in expected},
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
