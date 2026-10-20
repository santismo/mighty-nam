#!/usr/bin/env python3
"""Stage exact NAMLNK07/08 listening prototype after CPU/controller checks.
Files only. No device, updater, playback, reset or flash API.
"""
import argparse,json,sys
from pathlib import Path
from nux_container_lab import Container,need,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from link_image import build,elf_identity
p=argparse.ArgumentParser(description=__doc__)
for name in ['stock_package','elf','reports','output_dir']:p.add_argument(name,type=Path)
a=p.parse_args();stock=a.stock_package.read_bytes();digest=sha(a.elf.read_bytes())
need(sha(stock)=='95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6',
     'Exact stock restore package required')
identity=elf_identity(a.elf)
need(identity in ('NAMLNK07','NAMLNK08','NAMLNK09'),'Only NAMLNK07/08/09 can use this staging path')
reports={}
def read(name,status):
 path=a.reports/(name+'.json');data=json.loads(path.read_text())
 need(data.get('status')==status and data.get('elf_sha256')==digest,'Missing/mismatched '+name)
 reports[name]=sha(path.read_bytes());return data
listen=read('listening','PASS_'+identity+'_BOUNDED_LISTENING_CPU_TESTS')
need(len(listen['cases'])==12 and len({x['model'] for x in listen['cases']})==2,'Two-model chain coverage required')
need(all(x['blocks']>=1500 and x['silent_blocks']>=1199 and
         0<x['peak_Q31_normalized']<=0.109375 and
         x['peak_reference_error']<.001 and x['relative_RMS_error']<.001 and
         x['max_NAM_boundary_error']<2e-5 for x in listen['cases']),'Listening/accuracy gate')
edges=read('edges','PASS_'+identity+'_RENDER_PROTOCOL_AND_EFFECT_EDGES')
need(edges['algorithm_combinations']==13 and edges['wet_tail_samples']>=192000 and
     edges['cold_starts']==3 and edges['warm_restarts']==3 and
     edges['renderer_samples']>=1056 and edges['max_NAM_boundary_error']<2e-5,'Renderer/lifecycle/effect gate')
head=read('headroom','PASS_'+identity+'_STEREO_OUTPUT_HEADROOM')
need(head['cases']>=4812 and head['nonfinite_cases']>=96 and
     head['maximum_protected_peak']<=.875 and head['maximum_reference_error']<=2**-24 and
     head['nonfinite_stops_and_clears_both_channels'] and head['model_state_unchanged'],'Output guard gate')
irq=read('irq-timing','PASS_'+identity+'_IRQ_TIMING_OFFLINE')
need(irq['cases']>=145 and irq['timer_writes_by_capture']==0 and
     irq['snapshot_coherent_and_bounded'] and irq['known_reset_behavior_preserved'],'IRQ hook gate')
wire=read('native-wire','PASS_DART_SWIFT_STOCK_ARM_LINK')
need(wire['identity']==identity and len(wire['traces'])==2 and
     all(x['frames']==35 and x['reply_bytes_identical'] and x['output_zero'] for x in wire['traces']),'Model protocol gate')
baseline={'NAMLNK07':'06','NAMLNK08':'07','NAMLNK09':'08'}[identity]
placement=read('placement','PASS_'+identity+'_PLACEMENT_AND_NAMLNK'+baseline+'_REGRESSION')
need(all(placement[k] for k in ['baseline'+baseline+'_rebuilt_bit_identical','NAM_object_bit_identical',
 'stock_IRQ_body_preserved','vector_table_preserved','high_resources_preserved_except_IRQ_pointer',
 'exact_changed_span_allowlist_passed']),'Placement gate')
app=read('controller','PASS_'+identity+'_MAC_CONTROLLER_OFFLINE')
need(app['native_wire_checks']>=784 and app['widget_tests']>=31 and app['analyzer_passed'] and
     app['release_build_passed'] and app['explicit_listening_widget_test_passed'] and
     app['full_capture_auto_cabinet_bypass'] and app['selected_vs_loaded_model_identity_checked'],'Mac controller gate')
if identity in ('NAMLNK08','NAMLNK09'):
 pipeline=read('pipeline','PASS_OFFLINE_OUTPUT_PIPELINE_COMPARISON')
 need(pipeline['mode']=='previous' and len(pipeline['cases'])==2 and
      all(c['steady_blocks']>=256 and c['NAM_reference_max_error']<2e-5 and
          c['ordering']==['render','NAM','protect'] and c['mute_transition_fault_clear']
          for c in pipeline['cases']),'Early-output pipeline gate')
 need(app.get(identity+'_explicit_listening_test_passed') is True,'Current listening controller gate')
if identity=='NAMLNK09':
 buffer=read('buffer','PASS_NAMLNK09_OUTPUT_BUFFER')
 need({c['samples'] for c in buffer['cases']}=={8,16,32} and buffer['renderer_samples']>=5600
      and buffer['negative_commands']>=130,'Output buffer sample/command coverage')
 need(all(buffer[k] for k in ['model_identity_unchanged','model_transfer_preserves_buffer_and_mutes',
      'restart_restores_eight_and_mutes','fault_discards_queued_audio','lowest_matches_NAMLNK08']),
      'Output buffer lifecycle gate')
 need(buffer['sample_rate_hz']==48000 and buffer['processing_frames']==8 and
      app.get('output_buffer_readback_and_mute_test_passed') is True,'Buffer controller gate')
original=Container(stock)
need(original.rebuild_same_length(original.payload)==stock,'Stock round trip failed')
payload,_,plan=build(original.payload,a.elf,identity)
packed=original.rebuild_same_length(payload);decoded=Container(packed)
need(decoded.payload==payload and decoded.rebuild_same_length(decoded.payload)==packed,'Candidate round trip failed')
need(len(packed)==len(stock) and decoded.records[0]==original.records[0],'Setup record/length changed')
need(len(decoded.records)==len(original.records) and all(x[:28]==y[:28] for x,y in zip(decoded.records,original.records)),
     'Record headers changed')
spans=[(int(s['start'],16),int(s['end_exclusive'],16)) for s in plan['elf_regions'] if s['name']!='.bss']
spans += [(int(s['offset'],16),int(s['offset'],16)+len(bytes.fromhex(s['replacement']))) for s in plan['patches']]
changed=[i for i,(x,y) in enumerate(zip(original.payload,payload)) if x!=y]
need(all(any(lo<=i<hi for lo,hi in spans) for i in changed),'Unexpected payload change')
need(payload[:0x400]==original.payload[:0x400] and payload[0x11d94:0x11dd8]==original.payload[0x11d94:0x11dd8],
     'Vector or stock IRQ body changed')
need(payload[0x202a8:0x205a8]==original.payload[0x202a8:0x205a8] and payload[0x205ac:]==original.payload[0x205ac:],
     'High resource changed outside IRQ pointer')
need(plan['retired_audio_audit']['status']=='PASS_BOUNDED_RETIRED_AUDIO_BODY_AUDIT','Audio body retirement not audited')
a.output_dir.mkdir(parents=True,exist_ok=True)
image=a.output_dir/(identity+'-listening-test.bin')
need(not image.exists() or image.read_bytes()==packed,'Refusing to replace a different trial')
image.write_bytes(packed)
report=dict(status='STAGED_'+identity+'_LISTENING_PROTOTYPE_NOT_INSTALLED',identity=identity,
 elf_sha256=digest,candidate_sha256=sha(packed),bytes=len(packed),stock_sha256=sha(stock),
 payload_changed_bytes=len(changed),required_report_hashes=reports,candidate_plan=plan,
 output='Muted until explicit Listen on plug; restart/model transfer/fault disarms',
 output_lane_order=['L','R','L','R'],starting_pad_dB=-18.0618,fade_in_samples=1024,
 settling_blocks_after_preset_change=1200,headroom_ceiling_before_pad=.875,maximum_PCM_after_pad=.109375,
 output_pipeline=('previous protected block before NAM' if identity in ('NAMLNK08','NAMLNK09') else 'current block after NAM'),
 output_pipeline_latency_samples=8 if identity in ('NAMLNK08','NAMLNK09') else 0,
 output_buffer_samples=[8,16,32] if identity=='NAMLNK09' else None,
 sample_rate_hz=48000,
 model_storage='volatile RAM',timer_guard_ticks=150,physical_device_tested=False,
 full_chain_deadline_proven=False,listening_quality_verified=False,USB_recovery_for_this_image_verified=False,
 full_bootloader_backup=False,general_use_ready=False,host_audio_access=False,firmware_flashing=False)
(a.output_dir/'review.json').write_text(json.dumps(report,indent=2)+'\n')
manifest={'schema':'nam-plug-release-1','target':'NUX-MP3',
 'firmware':{'identity':identity,'sha256':sha(packed),'bytes':len(packed)},
 'restore':{'sha256':sha(stock),'bytes':len(stock)},
 'loader':{'vid':0x9527,'pid':0xc157,'identifier':'20220615'},
 'mode':'experimental-listening-prototype-muted-at-startup'}
(a.output_dir/'release.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','candidate_sha256','bytes','payload_changed_bytes']},indent=2))
