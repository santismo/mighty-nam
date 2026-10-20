#!/usr/bin/env python3
"""Reset/reorder/ownership tests of saved files; all peripherals simulated."""
import argparse, json, math
from pathlib import Path
from unicorn import UcError
import candidate_vm as vm
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('output',type=Path)
p.add_argument('--reclaimed-v1',action='store_true');p.add_argument('--extended-ram',action='store_true');a=p.parse_args()
vm.configure(a.payload,a.reclaimed_v1)
from candidate_vm import Machine, Reference, Collision, require, state_start, state_end, sym, plan, SP, R, default_copy_end

orders=[list(range(11)),[10,8,3,1,0,9,2,4,5,7,6]];results=[];first_outputs=[]
for fill in [0,0xa5,0xff]:
 m=Machine(fill);m.boot();ref=Reference();maxerr=0;first=None
 for block in range(64):
  xs=[.25*math.sin((block*8+i)*.071) for i in range(8)]
  x,out=m.dispatch(orders[(block//16)%2],xs)
  if first is None:first=out
  maxerr=max(maxerr,max(abs(y-z) for y,z in zip(out,ref.run(x))))
  m.background()
 require(maxerr<2e-6,'Candidate numerical error')
 # Stock bypass bit is read directly by the wrapper; no host enable write.
 xs=[i/16 for i in range(8)];x,out=m.dispatch(orders[0],xs,0x41);require(out==x,'Stock AMP bypass bit ignored')
 x,out=m.dispatch(orders[0],xs,1);require(max(abs(y-z) for y,z in zip(out,Reference().run(x)))<2e-6,'Re-enable did not reset NAM state')
 m.guards();first_outputs.append(first)
 results.append({'initial_ram_fill':hex(fill),'startup_order':m.boot_events,'audio_samples':512,
  'max_abs_error':maxerr,'background_calls_without_state_change':64,'forbidden_state_writes':m.violations,
  'observed_stack_bytes_below_test_call_sp':SP-m.minimum_sp,'note':'Observed bounded-call depth only; not an interrupt/whole-system stack requirement'})
 # Retained-memory warm restart, after corrupting NAM state on purpose.
 m.u.mem_write(state_start,b'\x5a'*(state_end-state_start));m.boot()
 _,again=m.dispatch(orders[0],[.25*math.sin(i*.071) for i in range(8)])
 require(again==first,'Fresh/warm restart outputs differ')
require(all(x==first_outputs[0] for x in first_outputs),'Cold restart outputs differ')

# Negative control: restore only the old background entry and supply a tiny
# controlled stock amp descriptor. Real stock memcpy must trip the RAM watcher.
n=Machine(0,missing_patch=0x57c0);n.boot();n.phase='negative-control'
n.u.mem_write(n.preset+3,b'\x01');n.u.mem_write(0x20003774,b'\x01');n.u.mem_write(0x2000cb3f,b'\x00')
descriptor=0x2000cd08+32;n.u.mem_write(descriptor,b'\x00'*32);n.u.mem_write(descriptor,b'\x01')
n.put(descriptor+4,32);n.put(descriptor+12,0x20025000);n.u.mem_write(0x20025000,b'\x6d'*32)
try:n.run(0x57c0)
except Collision:pass
require(bool(n.violations),'Negative ownership control failed to detect old writer')

# The reclaimed profile already uses the short copy for every positive run.
# Its negative control removes the module itself; the old gap profile instead
# checks that a short copy fails when it omits that gap.
short=Machine(0,copy_end=0x2356c,omit_module=a.reclaimed_v1);short.phase='negative-copy'
copy_failed=False
try:short.run(0x5778,limit=5000)
except (UcError,ValueError):copy_failed=True
require(copy_failed,'Truncated loader copy unexpectedly worked')
extended=None
if a.extended_ram:
 # Test every AMP control byte, including unsupported IDs and bypass/reserved
 # bits. This is a fixed one-model adapter, so these never index a model array.
 t=Machine(0);t.boot();cases=0;maximum=0;ref=Reference();last=None
 for control in range(256):
  x,out=t.dispatch(orders[control%2],[.125*math.sin((control*8+i)*.1) for i in range(8)],control)
  if control!=last:ref=Reference()
  expected=x if control&0x40 else ref.run(x)
  maximum=max(maximum,max(abs(v-w) for v,w in zip(out,expected)));last=control
  # Exercise every legacy background state, including pending reload/reset.
  t.u.mem_write(0x20003776,bytes([control&3]));t.background();cases+=1
 require(maximum<2e-6,'Extended control-byte numerical error')
 # Invalid current-preset pointer must mute without dereferencing it.
 original=t.preset;invalid=[0,0x1fffffff,0x2003ff81,0xffffffff]
 for value in invalid:
  t.put(0x20005ad0,value)
  for r,v in zip(R,[0x20025000,0x20025040,0x20025080,0x200250c0]):t.u.reg_write(r,v)
  t.floats(0x20025000,[.1]*8);t.floats(0x20025040,[.2]*8)
  t.run(0x5578);require(t.read(0x20025080)==[0]*8 and t.read(0x200250c0)==[0]*8,'Invalid pointer did not mute')
 t.put(0x20005ad0,original);t.guards()
 extended={'all_amp_control_bytes':cases,'max_abs_error':maximum,'legacy_background_flag_values':[0,1,2,3],
  'invalid_preset_pointer_cases':len(invalid),'foreign_code_data_reads':t.foreign_code_reads,'forbidden_state_writes':t.violations}
result={'status':'PASS_OFFLINE_CANDIDATE_RESET_AND_PLACEMENT_TESTS','candidate_plan':plan,
 'cold_starts':3,'retained_memory_restarts':3,'cold_and_warm_first_outputs_identical':True,
 'runs':results,'negative_control_old_background_writer':n.violations,
 'negative_control':{'kind':'module_removed' if a.reclaimed_v1 else 'padding_not_copied','failed_as_expected':copy_failed},
 'positive_copy_end_exclusive':hex(default_copy_end),'original_padding_not_needed_in_vm':a.reclaimed_v1,
 'padding_non_executable_in_vm':a.reclaimed_v1,'extended_ram_tests':extended,
 'boot_stubs':[hex(x) for x in sorted(m.stubs)],
 'limits':['Missing loader replaced by an explicit memory-copy assumption',
 'Board/USB/clock/other-effect initialization and other effect processing are stubs',
 'Unity fade curve and controlled preset inputs','A15 Thumb/VFP instruction model, not full M7 system emulation',
 'Static/dynamic ownership evidence is bounded; indirect aliases and untested paths remain',
 'No device reboot, flash, USB recovery test or audio playback'],
 'physical_reboot_persistence_proven':False,'physical_placement_safe_proven':False,
 'device_or_audio_access':False,'modified_firmware_file_written':False}
a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','cold_starts','retained_memory_restarts','runs','negative_control_old_background_writer','negative_control','extended_ram_tests']},indent=2))
