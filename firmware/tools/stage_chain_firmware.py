#!/usr/bin/env python3
"""Package a silent stock-chain trial only after exact-ELF offline reports."""
import argparse,json,sys
from pathlib import Path
from nux_container_lab import Container,need,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from link_image import build,elf_identity
p=argparse.ArgumentParser(description=__doc__)
for name in ['stock_package','elf','reports','output_dir']:p.add_argument(name,type=Path)
a=p.parse_args();stock=a.stock_package.read_bytes();elf_sha=sha(a.elf.read_bytes())
need(sha(stock)=='95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6','Exact stock restore package required')
identity=elf_identity(a.elf)
need(identity in ('NAMLNK02','NAMLNK03','NAMLNK04','NAMLNK05','NAMLNK06'),'Stock-chain image required')
reports={}
def read(name,status):
 path=a.reports/(name+'.json');data=json.loads(path.read_text())
 need(data.get('status')==status and data.get('elf_sha256')==elf_sha,'Missing/mismatched '+name)
 reports[name]=sha(path.read_bytes());return data
for name in ['accuracy-be100-fast','accuracy-marshall-fast']:
 result=read(name,'PASS_BOUNDED_'+identity+'_STOCK_CHAIN_CPU_TEST')
 need(len(result['cases'])==5 and result['max_NAM_boundary_error']<2e-5,'Incomplete accuracy coverage')
 need(all(c['DMA_always_zero'] and c['max_error']<.001 and c['relative_RMS_error']<.001 for c in result['cases']),'Accuracy/silence gate')
life=read('lifecycle','PASS_'+identity+'_LIFECYCLE')
need(life['cold_starts']==3 and life['warm_restarts']==3 and len(life['model_runs'])>=6
     and life['warm_cold_output_bit_identical'] and life['timer_fault_latches'],'Lifecycle gate')
need(all(r['output_peak']>1e-6 for r in life['model_runs']),'Vacuous lifecycle output')
extended=read('extended','PASS_EXTENDED_'+identity+'_CHAIN_AND_TAIL')
need(extended['DMA_always_zero'] and not extended['protected_state_writes'],'Extended silence/state gate')
need(len(extended['cases'])==12 and extended['total_samples']>=225000,'Extended coverage gate')
need(all(c['peak_error']<.001 and c['relative_RMS_error']<.001 for c in extended['cases']),'Extended accuracy gate')
native=read('native-wire','PASS_DART_SWIFT_STOCK_ARM_LINK')
need(native['identity']==identity and len(native['traces'])>=2
     and all(t['frames']==35 and t['reply_bytes_identical'] and t['output_zero'] for t in native['traces']),'Native wire gate')
read('profile-fast','PASS_BOUNDED_INSTRUCTION_PROFILE')
if identity in ('NAMLNK03','NAMLNK04','NAMLNK05','NAMLNK06'):
 bypass=read('bypass','PASS_'+identity+'_BYPASS_ABI_AND_TRANSITIONS')
 need(bypass['trampoline_cases']>=264 and bypass['sleeping_effect_callback_calls']==0
      and bypass['warm_restart_clears_holds'] and bypass['selected_types_loaded_after_reenable']
      and bypass['DMA_always_zero'] and bypass['stock_residual_stages_preserved']==[5,7,8],'Bypass coverage gate')
 need(all(c['bit_identical_to_original_dispatch'] for c in bypass['stock_comparison_cases'][:3]),'Stock transition preservation gate')
original=Container(stock)
if identity in ('NAMLNK05','NAMLNK06'):
 prime=read('prime','PASS_'+identity+'_READ_ONLY_WORKING_SET')
 need(len(prime['cases'])==4 and prime['model_state_unchanged'] and prime['future_frames_covered']==8
      and prime['preparation_after_receiver_scan_before_resume']
      and all(c['entire_NAM_arena_unchanged'] and c['writes_to_NAM_arena']==0 for c in prime['cases']),'Working-set preparation gate')
if identity=='NAMLNK06':
 head=read('headroom','PASS_NAMLNK06_STEREO_OUTPUT_HEADROOM')
 need(head['cases']>=4812 and head['nonfinite_cases']>=96 and head['ceiling']==0.875
      and head['maximum_protected_peak']<=0.875 and head['maximum_reference_error']<=2**-24
      and all(head[k] for k in ['unchanged_below_ceiling','both_channels_checked','model_state_unchanged',
                               'nonfinite_stops_and_clears_both_channels','DMA_always_zero','independent_reference'])
      and head['float_flush_modes_tested']==[False,True],'Stereo headroom gate')
 irq=read('irq-timing','PASS_NAMLNK06_IRQ_TIMING_OFFLINE')
 need(irq['cases']>=145 and irq['timer_writes_by_capture']==0 and irq['raw_counter_synthetic']
      and all(irq[k] for k in ['stock_IRQ_body_and_status_helper_executed','stock_DMA_ack_preserved',
                              'known_reset_behavior_preserved','snapshot_coherent_and_bounded']),'IRQ timing gate')
 heavy=read('heavy-switching','PASS_NAMLNK06_HEAVY_EFFECTS_AND_SWITCHING_OFFLINE')
 need(len(heavy['cases'])==28 and heavy['total_samples']>=314912
      and heavy['whole_IRQ_invocations']>=39364 and heavy['unprotected_stereo_peak']>1
      and heavy['protected_stereo_peak']<=0.875 and heavy['independent_host_output_guard']
      and heavy['maximum_NAM_boundary_error']<2e-5 and not heavy['protected_state_writes']
      and all(c['DMA_always_zero'] and c['peak_error']<.001 and c['relative_RMS_error']<.001
              for c in heavy['cases']),'Heavy chain/headroom gate')
 read('irq-profile','PASS_BOUNDED_NAMLNK06_IRQ_PROFILE')
 placement=read('placement','PASS_NAMLNK06_PLACEMENT_AND_NAMLNK05_REGRESSION')
 need(all(placement[k] for k in ['NAMLNK05_rebuilt_bit_identical','stock_IRQ_body_preserved',
                                'vector_table_preserved','all_other_high_resources_preserved',
                                'exact_changed_span_allowlist_passed'])
      and placement['code_free_bytes']>=0,'Placement gate')
 controller=read('controller','PASS_NAMLNK06_MAC_CONTROLLER_OFFLINE')
 need(controller['native_wire_checks']>=485 and controller['widget_tests']>=25
      and controller['analyzer_passed'] and controller['release_build_passed'],'Mac controller gate')
need(original.rebuild_same_length(original.payload)==stock,'Stock round trip failed')
payload,_,plan=build(original.payload,a.elf,identity=identity)
packed=original.rebuild_same_length(payload);decoded=Container(packed)
need(decoded.payload==payload and decoded.rebuild_same_length(decoded.payload)==packed,'Candidate round trip failed')
need(len(packed)==len(stock) and decoded.records[0]==original.records[0],'Setup record/length changed')
need(len(decoded.records)==len(original.records) and all(x[:28]==y[:28] for x,y in zip(decoded.records,original.records)),'Record headers changed')
spans=[(int(s['start'],16),int(s['end_exclusive'],16)) for s in plan['elf_regions'] if s['name']!='.bss']
spans += [(int(s['offset'],16),int(s['offset'],16)+len(bytes.fromhex(s['replacement']))) for s in plan['patches']]
changed=[i for i,(x,y) in enumerate(zip(original.payload,payload)) if x!=y]
need(all(any(lo<=i<hi for lo,hi in spans) for i in changed),'Unexpected payload change')
need(payload[:0x400]==original.payload[:0x400],'Vectors changed')
if identity=='NAMLNK06':
 need(payload[0x202a8:0x205a8]==original.payload[0x202a8:0x205a8]
      and payload[0x205ac:]==original.payload[0x205ac:]
      and payload[0x11d94:0x11dd8]==original.payload[0x11d94:0x11dd8]
      and plan['audio_irq_trampoline_redirected'],'Unexpected IRQ/startup/resource change')
else:
 need(payload[0x202a8:]==original.payload[0x202a8:],'Startup/resources changed')
a.output_dir.mkdir(parents=True,exist_ok=True)
image=a.output_dir/(identity+'-silent-chain-test.bin')
need(not image.exists() or image.read_bytes()==packed,'Refusing to replace a different trial')
image.write_bytes(packed)
report={'status':'STAGED_SILENT_CHAIN_TIMING_TRIAL_NOT_INSTALLED','identity':identity,
 'elf_sha256':elf_sha,'candidate_sha256':sha(packed),'bytes':len(packed),'stock_sha256':sha(stock),
 'payload_changed_bytes':len(changed),'candidate_plan':plan,'required_report_hashes':reports,
 'vectors_startup_resources_record_headers_preserved':identity!='NAMLNK06',
 'vectors_record_headers_and_original_IRQ_body_preserved':True,
 'only_high_resource_exception':'four-byte IRQ trampoline target at 0x205a8' if identity=='NAMLNK06' else None,
 'physical_device_tested':False,
 'full_chain_deadline_proven':False,'output':'always zero','model_storage':'volatile RAM',
 'general_use_ready':False,'timer_guard_ticks':150,'USB_recovery_for_this_image_verified':False,
 'full_bootloader_backup':False,'audio_playback':False,
 'output_headroom_ceiling':0.875 if identity=='NAMLNK06' else None,
 'timing_unit':'raw uncalibrated counter cycles' if identity=='NAMLNK06' else None}
(a.output_dir/'review.json').write_text(json.dumps(report,indent=2)+'\n')
manifest={'schema':'nam-plug-release-1','target':'NUX-MP3',
 'firmware':{'identity':identity,'sha256':sha(packed),'bytes':len(packed)},
 'restore':{'sha256':sha(stock),'bytes':len(stock)},
 'loader':{'vid':0x9527,'pid':0xc157,'identifier':'20220615'},
 'mode':'experimental-silent-stock-chain-timing-trial'}
(a.output_dir/'release.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','candidate_sha256','bytes','payload_changed_bytes']},indent=2))
