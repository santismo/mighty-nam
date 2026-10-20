#!/usr/bin/env python3
"""Heavy valid settings, stock algorithm changes and RAM model swaps; no devices/audio."""
import argparse,hashlib,json,math,time
from pathlib import Path
from link_irq_vm import IrqChainMachine
from test_link_stock_chain import Engine,library,v,preset_fixture,ORDER,build,model_slot
from stock_chain_vm import GROUPS
from link_image import elf_identity

p=argparse.ArgumentParser(description=__doc__)
for key in ['payload','elf','library','model','second_model','output']:p.add_argument(key,type=Path)
a=p.parse_args();started=time.monotonic()
assert elf_identity(a.elf)=='NAMLNK06'
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,'NAMLNK06'))
lib=library(str(a.library))
actual=IrqChainMachine(a.model,boundary_oracle=Engine(lib,a.model))
reference=IrqChainMachine(a.model,oracle=Engine(lib,a.model))
rows=[];offset=0;loaded={str(k):set() for k in GROUPS}
def set_preset(types,order=ORDER,bypass=(),high=True):
 data=preset_fixture([1,2,4,5,6,7,8,9],types)
 data[89:100]=bytes(order)
 if high:
  # Documented 0..100 parameter ranges. High drive, long repeats and wet reverb.
  data[20:26]=bytes([95,85,100,90,85,100])
  data[54:60]=bytes([95,100,90,85,100,90])
  data[61:69]=bytes([100,95,85,100,90,95,100,85])
  data[70:74]=bytes([85,100,95,90])
 for stage in bypass:data[stage]|=64
 for m in [actual,reference]:m.u.mem_write(m.preset,bytes(data))
 return data
def run(name,blocks,zero=False):
 global offset
 peak=energy=ref_energy=err=0.;exact=True;max_step=0.;last=None
 before=actual.irq_calls
 for i in range(blocks):
  n=offset+i
  x=[0.]*8 if zero else [
   .35*math.sin(2*math.pi*82.4*(n*8+j)/48000)+.12*math.sin(2*math.pi*329.6*(n*8+j)/48000)
   for j in range(8)]
  ys=actual.process(n,x);expected=reference.process(n,x)
  exact &= ys==expected
  err=max(err,max(abs(y-z) for y,z in zip(ys,expected)))
  energy+=sum((y-z)**2 for y,z in zip(ys,expected));ref_energy+=sum(z*z for z in expected)
  peak=max(peak,max(map(abs,ys)))
  for y in ys:
   if last is not None:max_step=max(max_step,abs(y-last))
   last=y
 rms=math.sqrt(energy/max(ref_energy,1e-30))
 assert err<.001 and rms<.001,(name,err,rms)
 assert actual.irq_calls-before==blocks
 for stage,(base,_) in GROUPS.items():
  value=actual.u.mem_read(base+1,1)[0]
  assert value==reference.u.mem_read(base+1,1)[0]
  loaded[str(stage)].add(value)
 row={'case':name,'blocks':blocks,'seconds':blocks/6000,'peak_internal_output':peak,
      'max_adjacent_sample_step':max_step,'peak_error':err,'relative_RMS_error':rms,
      'bit_identical':exact,'DMA_always_zero':True,'whole_software_IRQ_executed':True}
 rows.append(row);offset+=blocks;print(json.dumps(row),flush=True)

types={1:3,2:13,4:2,6:5,7:3,8:5,9:10}
set_preset(types)
run('High drive + detune + long modulation delay + shimmer',6000)
# Change algorithms while active: cover all stock comp/drive/mod/delay/reverb IDs.
for i in range(13):
 types={1:1+i%3,2:1+i,4:1+i%2,6:1+i,7:1+i%5,8:1+i%6,9:[1,10,19][i%3]}
 order=ORDER if i%2==0 else [0,5,3,1,2,4,9,8,6,7,10]
 set_preset(types,order)
 run('Active algorithm switch '+str(i+1),384)
 for stage in GROUPS:
  assert actual.u.mem_read(GROUPS[stage][0]+1,1)[0]==types[stage],('Selected type not loaded',stage)
# Repeated bypass/resume: the 200ms dry-effect suspension is actually reached.
set_preset(types,bypass=[1,2,4,6,9])
run('Dry effects bypass through 200ms suspension',1300)
types.update({1:3,2:2,6:5,7:5,8:5,9:10})
set_preset(types,bypass=[1,2,4,6,9])
run('Change dry types while asleep; delay and shimmer stay active',128)
set_preset(types)
run('Re-enable selected dry types',512)
for i in range(6):
 set_preset(types,bypass=[3] if i%2==0 else [])
 run('Rapid NAM toggle '+str(i+1),64)
# Model replacement while effects retain histories, on the same native protocol.
slot=model_slot(a.second_model)
actual.upload(slot,202);reference.upload(slot,202)
actual.boundary_oracle=Engine(lib,a.second_model);reference.oracle=Engine(lib,a.second_model)
run('Second model with existing effect histories',2048)
# Long wet decay: avoid NAM zero-input bias by bypassing NAM but retaining wet FX.
set_preset(types,bypass=[1,2,3,4,6,9])
for i in range(4):run('High-feedback delay and shimmer zero-input tail '+str(i+1),6000,zero=True)
for m in [actual,reference]:m.guards();assert not m.violations
for stage,(_,count) in GROUPS.items():
 assert set(range(1,count+1))<=loaded[str(stage)],(stage,loaded[str(stage)])
report={'status':'PASS_NAMLNK06_HEAVY_EFFECTS_AND_SWITCHING_OFFLINE','identity':'NAMLNK06',
 'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),
 'first_model':a.model.name,'second_model':a.second_model.name,
 'cases':rows,'total_samples':offset*8,'whole_IRQ_invocations':actual.irq_calls,
 'stock_algorithm_ids_loaded':{k:sorted(v) for k,v in loaded.items()},
 'maximum_NAM_boundary_error':actual.max_boundary_error,
 'maximum_internal_output':max(r['peak_internal_output'] for r in rows),
 'unprotected_stereo_peak':actual.unprotected_peak,'protected_stereo_peak':actual.protected_peak,
 'independent_host_output_guard':True,'output_guard_blocks':actual.headroom_blocks,
 'protected_state_writes':actual.violations,'physical_device_access':False,'audio_playback':False,
 'wall_seconds':time.monotonic()-started,
 'limits':['A15-compatible CPU simulation; actual IRQ entry/return, peripheral timing and preemption are not emulated.',
 'DWT and DSP timing values are synthetic fixtures, not real-time performance results.',
 'High valid settings and all available algorithms in five groups, not every parameter combination or fully settled long-tail behavior.',
 'Peak and sample-step measurements are protected internal values; no listening assessment or smooth-release claim.',
 'The comparison uses the same bypass policy with an independent NAM Core engine; it does not promise stock-equivalent sleeping-effect histories.']}
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(report['status'],flush=True)
