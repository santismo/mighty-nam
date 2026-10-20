#!/usr/bin/env python3
"""Stage the NAMLNK10 preset trial after bounded storage/controller checks.
Files only. Does not discover a plug, flash, reset, or open any audio device.
"""
import argparse,json,sys
from pathlib import Path
from nux_container_lab import Container,need,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from preset_image import build,BANK,BANK_END,FLASH
p=argparse.ArgumentParser(description=__doc__)
for name in ['stock_package','elf','reports','output_dir']:p.add_argument(name,type=Path)
a=p.parse_args();stock=a.stock_package.read_bytes();digest=sha(a.elf.read_bytes());evidence={}
need(sha(stock)=='95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6','Exact stock restore package required')
def read(name,status,bind=True):
 path=a.reports/(name+'.json');r=json.loads(path.read_text())
 need(r.get('status')==status and (not bind or r.get('elf_sha256')==digest),'Missing/mismatched '+name)
 evidence[name]=sha(path.read_bytes());return r
r=read('runtime','PASS_NAMLNK10_ARM_PRESET_RUNTIME')
need(all(r.get(k) for k in ['seven_slots','exact_model_and_effect_recall','stock_button_branch','button_skips_empty','duplicate_saves_do_not_write','failed_driver_write_preserves_saved_data']),'Runtime/recall gates')
need(r['cold_patterns']==[0,165,255] and r['warm_restarts']==3 and len(r['accuracy'])==2,'Cold/warm/model gates')
need(all(c['blocks']>=1300 and 0<c['peak']<=.109375 and c['max_error']<2e-5 for c in r['accuracy']),'Saved-model chain accuracy gate')
r=read('storage-contract','PASS_NAMLNK10_STOCK_STORAGE_CONTRACT')
need(r['stock_MPU_allows_code_execution'] and r['region']['executable'] and r['region']['full_access'] and len(r['real_stock_wrapper_cases'])>=7 and r['error_propagation_cases']>=4,'Stock storage contract gate')
r=read('bank-core','PASS_NAMLNK10_PRESET_BANK_SANITIZERS')
need(r['cases']>=252 and r['address_sanitizer'] and r['undefined_behavior_sanitizer'],'Storage interruption/memory gate')
r=read('placement','PASS_NAMLNK10_PLACEMENT_AND_NAMLNK09_REGRESSION')
need(r['baseline09_rebuilt_bit_identical'] and r['stock_IRQ_body_preserved'] and r['vector_table_preserved'] and set(r['unchanged_DSP_and_output_objects'])=={'a2_lite.o','sysex_codec.o','listening.o','irq_timing.o'},'DSP and placement regression gate')
for key,status in [('listening','PASS_NAMLNK09_BOUNDED_LISTENING_CPU_TESTS'),('edges','PASS_NAMLNK09_RENDER_PROTOCOL_AND_EFFECT_EDGES'),('headroom','PASS_NAMLNK09_STEREO_OUTPUT_HEADROOM'),('buffer','PASS_NAMLNK09_OUTPUT_BUFFER')]:
 baseline=read('baseline09-'+key,status,False)
 need(baseline['elf_sha256']=='05342d67b9147fdf31fd133ad0ed1fad018d407c45e198cc329957e34e6a1a97','Baseline evidence mismatch')
r=read('native-preset-wire','PASS_NAMLNK10_NATIVE_PRESET_WIRE')
need(r['operations']==3 and r['muted'] and r['actual_stock_receive_ring'],'Native preset wire gate')
r=read('preset-wire.dart-result','PASS_DART_PRESET_ARM_REPLIES',False);need(r['operations']==3,'Dart decoded ARM replies required')
r=read('controller','PASS_NAMLNK10_MAC_CONTROLLER_OFFLINE')
need(r['widget_tests']>=50 and r['native_wire_checks']>=1500 and all(r[k] for k in ['analyzer_passed','release_build_passed','native_smoke_passed','drafts_preserved','independent_save_readback_checked']),'Controller gate')
original=Container(stock);need(original.rebuild_same_length(original.payload)==stock,'Stock round trip failed')
payload,_,plan=build(original.payload,a.elf);packed=original.rebuild_same_length(payload);decoded=Container(packed)
need(decoded.payload==payload and decoded.rebuild_same_length(decoded.payload)==packed,'Candidate round trip failed')
need(len(packed)==len(stock) and decoded.records[0]==original.records[0],'Setup record/length changed')
need(len(decoded.records)==len(original.records) and all(x[:28]==y[:28] for x,y in zip(decoded.records,original.records)),'Record headers changed')
need(payload[BANK-FLASH:BANK_END-FLASH]==b'\xff'*(BANK_END-BANK),'First-install bank must be empty')
need(payload[:0x400]==original.payload[:0x400] and payload[0x11d94:0x11dd8]==original.payload[0x11d94:0x11dd8],'Vector or stock IRQ changed')
a.output_dir.mkdir(parents=True,exist_ok=True);target=a.output_dir/'NAMLNK10-onboard-presets-test.bin'
need(not target.exists() or target.read_bytes()==packed,'Refusing to replace a different staged trial')
target.write_bytes(packed)
report=dict(status='STAGED_NAMLNK10_ONBOARD_PRESET_PROTOTYPE_NOT_INSTALLED',identity='NAMLNK10',elf_sha256=digest,
 candidate_sha256=sha(packed),bytes=len(packed),stock_sha256=sha(stock),candidate_plan=plan,required_report_hashes=evidence,
 preset_slots=7,colors=['Green','Orange','Red','Blue','Cyan','Pink','Lilac'],copies_per_slot=2,record_bytes=8192,
 model_format='A2 Lite, 1871 weights, 48kHz',onboard_content='Capture, name, stock effect types/parameters/bypasses/order, output buffer, boot play flag',
 output='First install/empty bank muted. Saved presets with play flag start after startup, settling and fade; transfer/save mutes.',
 firmware_update_preserves_bank=False,physical_device_tested=False,physical_flash_write_verified=False,physical_preset_button_verified=False,
 USB_recovery_for_this_image_verified=False,full_bootloader_backup=False,full_chain_deadline_proven=False,general_use_ready=False,
 host_audio_access=False,firmware_flashing=False)
(a.output_dir/'review.json').write_text(json.dumps(report,indent=2)+'\n')
manifest=dict(schema='nam-plug-release-1',target='NUX-MP3',firmware=dict(identity='NAMLNK10',sha256=sha(packed),bytes=len(packed)),
 restore=dict(sha256=sha(stock),bytes=len(stock)),loader=dict(vid=0x9527,pid=0xc157,identifier='20220615'),mode='experimental-onboard-presets-empty-at-install')
(a.output_dir/'release.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','candidate_sha256','bytes']}))
