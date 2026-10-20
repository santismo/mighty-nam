#!/usr/bin/env python3
"""Validate the exact dispatcher trampoline against stock bypass transitions.
No USB or host audio. Timing is deliberately not inferred from this emulator.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
from test_link_stock_chain import ChainMachine, build, v, preset_fixture, ORDER
from link_image import elf_identity
from stock_chain_vm import GROUPS

p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','elf','model','output']:p.add_argument(name,type=Path)
a=p.parse_args()
identity=elf_identity(a.elf)
assert identity in ('NAMLNK03','NAMLNK04','NAMLNK05','NAMLNK06')
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,identity))
hold=v.sym['mpp_bypass_hold']
eligible={1,2,4,5,6,7,8,9}
residual={5,7,8}
m=ChainMachine()
abi_cases=0
# Check every stage, enabled/bypassed, before and after the hold period, using
# distinct stereo channels and disjoint/in-place buffers. Verify live registers.
for order in [ORDER,list(reversed(ORDER))]:
 for slot,stage in enumerate(order):
  for bypass in [False,True]:
   for pending in [0,2,65535]:
    for inplace in [False,True]:
     preset=preset_fixture();preset[89:100]=bytes(order)
     preset[stage]=1|(64 if bypass else 0)
     m.u.mem_write(m.preset,bytes(preset))
     m.u.mem_write(hold,struct.pack('<11H',*([pending]*11)))
     left,right=0x20025000,0x20025040
     outl,outr=(left,right) if inplace else (0x20025100,0x20025140)
     xs=[float(i+1) for i in range(8)];ys=[-float(i+11) for i in range(8)]
     m.floats(left,xs);m.floats(right,ys)
     regs={UC_ARM_REG_R4:0x200005d0,UC_ARM_REG_R5:outr,UC_ARM_REG_R6:11-slot,
           UC_ARM_REG_R7:right,UC_ARM_REG_R8:outl,UC_ARM_REG_R9:left,
           UC_ARM_REG_R10:0x12345678,UC_ARM_REG_R11:0x10203040,
           UC_ARM_REG_R12:0x13579,UC_ARM_REG_LR:0x24681,UC_ARM_REG_SP:v.SP}
     for reg,value in regs.items():m.u.reg_write(reg,value)
     floats={UC_ARM_REG_S0+i:0x3f800000+i for i in range(32)}
     for reg,value in floats.items():m.u.reg_write(reg,value)
     stopped=[]
     def stop(u,pc,size,user):
      stopped.append(pc);u.emu_stop()
     h=m.u.hook_add(UC_HOOK_CODE,stop,begin=0x1230c,end=0x1230e)
     try:m.u.emu_start(v.sym['mpp_fast_dispatch']|1,0,count=1000)
     finally:m.u.hook_del(h)
     sleeping=stage in eligible and bypass and pending==0
     assert stopped==[0x1230e if sleeping else 0x1230c],(stage,stopped)
     for reg,value in regs.items():
      assert m.u.reg_read(reg)==value+(28 if reg==UC_ARM_REG_R4 else 0),(stage,reg)
     assert all(m.u.reg_read(reg)==value for reg,value in floats.items())
     holds=struct.unpack('<11H',m.u.mem_read(hold,22))
     expected=pending if stage not in eligible else (
      (pending if pending==65535 else max(pending-1,0)) if bypass else
      (65535 if stage in residual else 1200))
     assert holds[stage]==expected
     assert all(x==pending for i,x in enumerate(holds) if i!=stage)
     if sleeping:assert m.read(outl)==xs and m.read(outr)==ys
     else:assert [m.u.reg_read(r) for r in v.R]==[left,right,outl,outr]
     abi_cases+=1
print('PASS trampoline ABI/stereo/in-place:',abi_cases,flush=True)

# Independent comparison: same NAM bytes, but restore the exact original stock
# dispatcher in the reference machine. This does not compare two copies of the
# new bypass policy. NAM is bypassed so the stock switch-off behavior is isolated.
actual=ChainMachine(a.model);reference=ChainMachine(a.model)
reference.u.mem_write(0x12302,a.payload.read_bytes()[0x12302:0x1230c])
reference.u.ctl_remove_cache(0x12302,0x1230c)
counts={}
def observe(u,pc,size,user):counts[pc]=counts.get(pc,0)+1
callbacks={1:0x123be,2:0x1262a,4:0x1307e,5:0x1f5ec,6:0x128ba,
           7:0x12c48,8:0x12eb2,9:0x13394}
for pc in callbacks.values():actual.u.hook_add(UC_HOOK_CODE,observe,begin=pc,end=pc)
rows=[];offset=0
def config(enabled,types=None):
 data=preset_fixture(enabled,types);data[3]=65
 for machine in [actual,reference]:machine.u.mem_write(machine.preset,bytes(data))
def compare(label,blocks,identical=True):
 global offset
 error=peak=0.
 for i in range(blocks):
  x=actual.process(offset+i);y=reference.process(offset+i)
  error=max(error,max(abs(xx-yy) for xx,yy in zip(x,y)))
  peak=max(peak,max(map(abs,x)))
 assert not identical or error==0,(label,error,globals().get('stage_differences'))
 assert peak>1e-7,(label,'vacuous')
 rows.append(dict(case=label,blocks=blocks,peak=peak,stock_difference=error,
                  bit_identical_to_original_dispatch=error==0))
 offset+=blocks
 print(json.dumps(rows[-1]),flush=True)
config(eligible);compare('Enabled effects use original callbacks',320)
config([]);counts.clear();compare('200 ms stock switch-off transition',1200)
assert all(counts.get(pc)==1200 for pc in callbacks.values()),counts
stage_differences={};pending=[]
def stock_boundary(u,pc,size,user):
 if pc in callbacks.values():
  il,ir,ol,orr=[u.reg_read(reg) for reg in v.R]
  pending[:]=[pc,reference.read(il)+reference.read(ir),ol,orr]
 elif pending:
  entry,x,ol,orr=pending;pending.clear()
  error=max(abs(xx-yy) for xx,yy in zip(x,reference.read(ol)+reference.read(orr)))
  stage_differences[hex(entry)]=max(error,stage_differences.get(hex(entry),0))
for pc in set(callbacks.values())|{0x1230e}:
 reference.u.hook_add(UC_HOOK_CODE,stock_boundary,begin=pc,end=pc)
counts.clear();compare('Settled dry bypass sleeps; stock residuals continue',256)
assert counts=={callbacks[s]:256 for s in residual},counts
assert struct.unpack('<11H',actual.u.mem_read(hold,22))==tuple(
  65535 if s in residual else 0 for s in range(11))
# A queued selection while asleep loads through the original callback/foreground
# path on re-enable. Retired DSP histories are frozen, not claimed tail spillover.
newtypes={1:3,2:13,4:2,6:13,7:5,8:6,9:34}
config([],newtypes);counts.clear()
compare('Selection while asleep stays bounded',32,identical=False)
assert counts=={callbacks[s]:32 for s in residual}
config(eligible,newtypes);compare('Re-enable and load selected effects',320,identical=False)
for stage in GROUPS:
 assert actual.u.mem_read(GROUPS[stage][0]+1,1)[0]==newtypes[stage],stage
actual.restart()
assert bytes(actual.u.mem_read(hold,22))==bytes(22),'Warm restart did not clear holds'
result={'status':'PASS_'+identity+'_BYPASS_ABI_AND_TRANSITIONS',
 'identity':identity,'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),
 'trampoline_cases':abi_cases,'stock_comparison_cases':rows,
 'sleeping_effect_callback_calls':0,'stock_transition_blocks':1200,
 'stock_residual_stages_preserved':sorted(residual),
 'warm_restart_clears_holds':True,'selected_types_loaded_after_reenable':True,
 'DMA_always_zero':True,'physical_device_access':False,
 'limits':['Representative stock settings, not all effect types/parameters',
           'Dry-bypass effects freeze history after 200 ms; used gate/delay/reverb retain stock processing',
           'Sleeping bypass preserves both channels; some stock callbacks collapse stereo',
           'Emulator does not establish Cortex-M7 timing or interrupt behavior']}
a.output.write_text(json.dumps(result,indent=2)+'\n')
