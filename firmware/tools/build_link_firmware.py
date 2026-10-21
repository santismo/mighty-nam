#!/usr/bin/env python3
"""Build original USB model-link code; no device access or flash container."""
import argparse, hashlib, json, subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
import ziglang

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('build_dir',type=Path)
p.add_argument('--stock-chain',action='store_true',help='Build NAMLNK02 stock-chain experiment; not an installable release')
p.add_argument('--fused',action='store_true',help='Experimental M7 FPv5 fused arithmetic; requires separate accuracy and physical timing validation')
p.add_argument('--m7-conv',action='store_true',help='Non-fused packed-load M7 convolution; offline validation required')
p.add_argument('--fast-bypass',action='store_true',help='NAMLNK03 stock bypass suspension after 200 ms; requires stock chain')
p.add_argument('--m7-dense',action='store_true',help='NAMLNK04 packed projection/head; requires M7 convolution and fast bypass')
p.add_argument('--prime-state',action='store_true',help='NAMLNK05 read-only model working-set preparation; requires M7 dense')
p.add_argument('--irq-timing',action='store_true',help='NAMLNK06 offline raw audio-IRQ timing; requires prime-state')
p.add_argument('--listening',action='store_true',help='NAMLNK07 offline listening prototype; starts muted; requires IRQ timing')
p.add_argument('--early-output',action='store_true',help='NAMLNK08 prior-block output before NAM processing; requires listening')
p.add_argument('--output-buffer',action='store_true',help='NAMLNK09 selectable 8/16/32-sample output staging; processing remains eight frames')
p.add_argument('--preset-bank',action='store_true',help='NAMLNK10 seven persistent preset banks; offline experimental build')
p.add_argument('--performance',action='store_true',help='NAMLNK11 opt-in per-effect profiler and cache-line preparation; requires preset bank')
p.add_argument('--tuner',action='store_true',help='NAMLNK12 bounded dry-input captures for the Mac tuner; requires performance')
p.add_argument('--fx-blocks',action='store_true',help='NAMLNK13 two independent FX blocks and bounded BLE replies; requires tuner')
p.add_argument('--cut-eq',action='store_true',help='NAMLNK14 High/Low Cut EQ; requires --fx-blocks')
p.add_argument('--responsive-controls',action='store_true',help='NAMLNK15 compact phone tuner, same-preset no-op and idle FX shortcut; requires --cut-eq')
p.add_argument('--nam-pointer',action='store_true',help='NAMLNK16 non-fused NAM tap-address optimization; requires --responsive-controls and --m7-conv')
p.add_argument('--adc-short-delay',action='store_true',help='NAMLNK17 startup-only ADC short-delay trial; requires --nam-pointer')
p.add_argument('--global-buffer',action='store_true',help='NAMLNK18 global persistent buffer and playback-preserving successful saves; requires --adc-short-delay')
p.add_argument('--driver-timing',action='store_true',help='NAMLNK19 delay/reverb bypass sleep and opt-in read-only DMA/SAI timing; requires --global-buffer')
p.add_argument('--dma-current-prototype',action='store_true',help='OFFLINE ONLY: NAMDMP01 current-block output with experimental TX watermark eight; no release packaging')
a=p.parse_args()
if a.dma_current_prototype and not a.driver_timing:p.error('--dma-current-prototype requires --driver-timing')
if a.driver_timing and not a.global_buffer:p.error('--driver-timing requires --global-buffer')
if a.global_buffer and not a.adc_short_delay:p.error('--global-buffer requires --adc-short-delay')
if a.adc_short_delay and not a.nam_pointer:p.error('--adc-short-delay requires --nam-pointer')
if a.nam_pointer and not (a.responsive_controls and a.m7_conv):p.error('--nam-pointer requires --responsive-controls and --m7-conv')
if a.responsive_controls and not a.cut_eq:p.error('--responsive-controls requires --cut-eq')
if a.cut_eq and not a.fx_blocks:p.error('--cut-eq requires --fx-blocks')
if a.fx_blocks and not a.tuner:p.error('--fx-blocks requires --tuner')
if a.fused and not a.stock_chain:p.error('--fused requires --stock-chain')
if a.m7_conv and (not a.stock_chain or a.fused):p.error('--m7-conv requires --stock-chain without --fused')
if a.fast_bypass and not a.stock_chain:p.error('--fast-bypass requires --stock-chain')
if a.m7_dense and not (a.m7_conv and a.fast_bypass):p.error('--m7-dense requires --m7-conv --fast-bypass')
if a.prime_state and not a.m7_dense:p.error('--prime-state requires --m7-dense')
if a.irq_timing and not a.prime_state:p.error('--irq-timing requires --prime-state')
if a.listening and not a.irq_timing:p.error('--listening requires --irq-timing')
if a.early_output and not a.listening:p.error('--early-output requires --listening')
if a.preset_bank and not a.output_buffer:p.error('--preset-bank requires --output-buffer')
if a.performance and not a.preset_bank:p.error('--performance requires --preset-bank')
if a.tuner and not a.performance:p.error('--tuner requires --performance')
if a.output_buffer and not a.early_output:p.error('--output-buffer requires --early-output')
root=Path(__file__).resolve().parents[1];out=a.build_dir.resolve();out.mkdir(parents=True,exist_ok=True)
flags=['--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=vfpv3-d16','-mfloat-abi=hard',
 '-std=c++17','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-ffp-contract=off',
 '-fno-exceptions','-fno-rtti','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
 '-ffunction-sections','-fdata-sections','-DMPP_COMPACT_INIT']
sources=['target/a2/a2_lite.cpp','target/link/model_receiver.cpp','target/link/sysex_codec.cpp','target/link/link_firmware.cpp']
if a.stock_chain:
 sources[-1]='target/link/stock_chain_firmware.cpp'
 flags+=['-DMPP_REFERENCE_ORDER']
if a.fused:
 flags=[flag for flag in flags if not flag.startswith(('-mfpu=','-ffp-contract='))]
 flags+=['-mfpu=fpv5-sp-d16','-ffp-contract=fast']
if a.m7_conv:flags+=['-DMPP_M7_CONV']
if a.fast_bypass:flags+=['-DMPP_FAST_BYPASS']
if a.m7_dense:flags+=['-DMPP_M7_DENSE']
if a.prime_state:flags+=['-DMPP_PRIME_STATE']
if a.irq_timing:
 # No unwinder/debug frame chain on the target. Freeing r7 shrinks the new
 # guard/telemetry while keeping all code inside the retired stock amp region.
 flags+=['-DMPP_IRQ_TIMING','-fomit-frame-pointer']
 sources+=['target/link/irq_timing.cpp']
if a.listening:
 flags+=['-DMPP_LISTENING']
 sources+=['target/link/listening.cpp']
if a.early_output:flags+=['-DMPP_EARLY_OUTPUT']
if a.output_buffer:flags+=['-DMPP_OUTPUT_BUFFER']
if a.preset_bank:
 flags+=['-DMPP_PRESET_BANK']
 sources+=['target/link/preset_bank.cpp','target/link/preset_runtime.cpp']
if a.performance:
 flags+=['-DMPP_EFFECT_PROFILER','-DMPP_CACHE_LINE_PRIME']
 sources+=['target/link/effect_profiler.cpp']
if a.tuner:
 flags+=['-DMPP_TUNER']
 sources+=['target/link/tuner.cpp']
if a.fx_blocks:
 flags+=['-DMPP_FX_BLOCKS']
 sources+=['target/link/fx_blocks.cpp','target/link/fx_runtime.cpp','target/link/reply_transport.cpp']
if a.cut_eq:
 flags+=['-DMPP_CUT_EQ']
 sources+=['target/link/cut_eq.cpp','target/link/cut_eq_runtime.cpp']
if a.responsive_controls:flags+=['-DMPP_RESPONSIVE_CONTROLS']
if a.nam_pointer:flags+=['-DMPP_M7_POINTER_TAPS']
if a.adc_short_delay:
 flags+=['-DMPP_ADC_SHORT_DELAY']
 sources+=['target/link/codec_startup.cpp']
if a.global_buffer:
 flags+=['-DMPP_GLOBAL_BUFFER']
 sources+=['target/link/global_buffer.cpp']
if a.driver_timing:
 flags+=['-DMPP_DRIVER_TIMING']
 sources+=['target/link/driver_timing.cpp']
if a.dma_current_prototype:flags+=['-DMPP_DMA_CURRENT_PROTOTYPE']
objects=[]
for source in sources:
 obj=out/(Path(source).stem+'.o')
 optimize='-O2' if ('a2_lite' in source or 'fx_blocks.cpp' in source or 'cut_eq.cpp' in source) else '-Oz'
 subprocess.run(['clang++',*flags,optimize,'-c',str(root/source),'-o',str(obj)],check=True)
 objects.append(str(obj))
elf=out/'nam-link-offline.elf';ld=root/('target/link/presets.ld' if a.preset_bank else ('target/link/listening.ld' if a.listening else 'target/link/link_firmware.ld'))
if a.fx_blocks:ld=root/'target/link/fx_blocks.ld'
if a.driver_timing:ld=root/'target/link/driver_timing.ld'
subprocess.run([str(Path(ziglang.__path__[0])/'zig'),'cc','-target','thumb-freestanding-eabihf','-mcpu=cortex_m7',
 '-nostdlib','-Wl,--gc-sections','-Wl,--build-id=none','-Wl,-e,mpp_stock_amp_init','-Wl,-T,'+str(ld),
 *(['-Wl,-u,mpp_fast_dispatch'] if a.fast_bypass else []),
 *(['-Wl,-u,mpp_link_irq','-Wl,-u,mpp_track_dwt_reset'] if a.irq_timing else []),
 *(['-Wl,-u,mpp_codec_startup_write'] if a.adc_short_delay else []),
 *objects,'-o',str(elf)],check=True)
with elf.open('rb') as f:
 e=ELFFile(f)
 assert not [s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF']
 regions=[dict(name=s.name,start=hex(s['sh_addr']),bytes=s['sh_size'],end_exclusive=hex(s['sh_addr']+s['sh_size'])) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']]
report={'identity':'NAMLNK06' if a.irq_timing else ('NAMLNK05' if a.prime_state else ('NAMLNK04' if a.m7_dense else ('NAMLNK03' if a.fast_bypass else ('NAMLNK02' if a.stock_chain else 'NAMLNK01')))),'status':'LINKED_NOT_HARDWARE_VERIFIED','elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),
 'float_mode':'experimental-fused-MAC' if a.fused else 'non-fused',
 'convolution':'packed-load-M7' if a.m7_conv else 'portable-C++',
 'projection_and_head':'packed-load-M7' if a.m7_dense else 'portable-C++',
 'working_set_preparation':a.prime_state,
 'raw_audio_irq_timing':a.irq_timing,
 'output_headroom':{'ceiling':0.875,'mode':'stereo-linked eight-sample block gain; no makeup gain',
                    'nonfinite':'clear both channels and latch fault'} if a.irq_timing else None,
 'bypass':'dry-bypass sleep after 200 ms; used gate/delay/reverb retain stock residuals' if a.fast_bypass else 'stock',
 'compiler_flags':flags,
 'regions':regions,'audio_output':'always zero','model_storage':'volatile RAM; upload again after restart',
 'device_access':False,'flash_container_created':False,
 'sources':{s:hashlib.sha256((root/s).read_bytes()).hexdigest() for s in sources}}
if a.listening:
 report.update(identity='NAMLNK07',audio_output='muted until explicit RAM listen arm; stock L/R/L/R, -18.06 dB pad and 1024-sample fade',
   effect_change_settling_blocks=1200,stock_global_volume=True,
   new_code_region='retired stock audio callback body 0x14c04..0x14f08')
if a.early_output:
 report.update(identity='NAMLNK08',output_pipeline='previous protected block rendered before current NAM processing',
   output_pipeline_latency_samples=8,physical_output_deadline_verified=False)
if a.output_buffer:
 report.update(identity='NAMLNK09',output_buffer_samples=[8,16,32],default_output_buffer_samples=8,
   processing_block_samples=8,sample_rate_hz=48000,
   buffer_scope='Output staging only; larger settings add latency, not CPU capacity; eight matches NAMLNK08',
   runtime_changes='volatile, reset output to mute; reboot restores eight samples')
if a.preset_bank:
 report.update(identity='NAMLNK10',model_storage='Seven dual-copy persistent preset records; physical validation pending',preset_bank=[hex(0x30384000),hex(0x303a0000)],copied_code_source=hex(0x303a0000),copied_code_destination=hex(0x20308000),
   audio_output='Empty bank boots muted; saved presets with play flag resume after startup/settling/fade. Upload/save mutes.',
   runtime_changes='Buffer changes mute; Save to plug persists the buffer with each preset',
   firmware_updates_preserve_bank=False)
if a.performance:
 report.update(identity='NAMLNK11',working_set_preparation='32-byte cache-line coverage; same call sites',
  effect_profiler='Disabled at boot; select one stage using bounded NT command; raw DWT cycles only',
  stock_bypass_tail_policy='Unchanged; gate/delay/reverb residuals remain active after use',
  physical_performance_gain_verified=False)
if a.tuner:
 report.update(identity='NAMLNK12',tuner='Explicit, muted-only 2048-sample dry input capture at 12 kHz; no streaming audio device on Mac',tuner_default='off; each requested capture stops automatically',physical_tuner_verified=False)
if a.fx_blocks:
 report.update(identity='NAMLNK13',custom_fx_slots=2,custom_fx_modes=['Pitch','Auto Wah','Chorus','Flanger','Phaser','Tremolo','Vibrato'],pitch_semitones=list(range(-12,13)),ble_reply_page_bytes=40,physical_fx_verified=False,copied_code_destination=hex(0x20310000))
if a.cut_eq:
 report.update(identity='NAMLNK14',cut_eq_type=4,cut_eq_slope_db_oct=12,cut_eq_low_hz=[20,1000],cut_eq_high_hz=[1000,20000],cut_eq_off_value=0,physical_cut_eq_verified=False)
if a.responsive_controls:
 report.update(identity='NAMLNK15',compact_tuner=True,same_preset_button_no_op=True,idle_fx_shortcut=True,physical_latency_improvement_verified=False)
 report['headers']={str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sorted((root/'target').rglob('*.hpp'))}
if a.nam_pointer:
 report.update(identity='NAMLNK16',nam_pointer_taps=True,codec_filters='Unchanged stock settings',physical_latency_improvement_verified=False)
if a.adc_short_delay:
 report.update(identity='NAMLNK17',codec_filters='Startup-only ADC short-delay sharp, register 0x0a=0x22; other 20 writes unchanged',codec_status_page=117,codec_identification='Inferred AK4619; not a part-ID read',physical_codec_readback_verified=False)
if a.global_buffer:
 report.update(identity='NAMLNK18',global_persistent_buffer=True,global_settings_flash=[hex(0x303a4000),hex(0x303a6000)],runtime_changes='Global 8/16/32 setting survives power-off and preset changes; buffer/save resume prior output intent',physical_global_buffer_verified=False)
if a.driver_timing:
 report.update(identity='NAMLNK19',driver_timing='Explicit one-shot; DMA/SAI/counter reads only; disabled at boot',driver_status_pages=[118,126],stock_bypass_tail_policy='Delay/reverb hard-bypass sleeps after 1198 blocks, resets on wake; gate unchanged',bypass='Used delay/reverb sleep and reset; no spillover',physical_driver_timing_verified=False)
if a.dma_current_prototype:
 report.update(identity='NAMDMP01',status='OFFLINE_DMA_PROTOTYPE_NOT_FOR_INSTALLATION',
  output_pipeline='current protected block after timing guard; DSB then publication snapshot',
  output_pipeline_latency_samples=0,experimental_tx_fifo_watermark=8,
  buffer_scope='Output staging only: adds 0/8/24 frames to current-block publication; DSP stays eight frames',
  requires_offline_image_opt_in=True,physical_output_deadline_verified=False,
  timer_guard_scope='Checks DSP/protection before publication; excludes final render. Whole-IRQ diagnostics still enclose all work.',
  deadline_guard='Existing GPT processing guard only; no proven TX ownership/deadline guard')
 report['linker_sha256']=hashlib.sha256(ld.read_bytes()).hexdigest()
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
