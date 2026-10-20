#!/usr/bin/env python3
"""Run selected real stock effect loaders and background paths in RAM only.
Flash is a read-only mapping of a saved public payload. GPIO/UART registers are
virtual storage; there is no host USB/audio/device access or updater output.
"""
import argparse,json,math
from pathlib import Path
from unicorn import UC_HOOK_CODE,UC_PROT_READ,UC_PROT_ALL
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2
import candidate_vm as v
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
v.configure(a.payload,True)
m=v.Machine(0)
# Stock effects intentionally load executable overlays in the upper ITCM.
# These are separate from reclaimed NAM code below 0x1b488.
m.u.mem_protect(0x24000,0x1c000,UC_PROT_ALL)
m.u.mem_map(0x20240000,0x80000)
m.u.mem_map(0x30040000,(len(v.stock)+4095)&~4095,UC_PROT_READ)
m.u.mem_write(0x30040000,v.stock)
virtual_mmio=[0x40c60000,0x40c5c000,0x40c68000,0x40071000]
for addr in virtual_mmio:m.u.mem_map(addr,0x1000)
# An empty simulated UART DMA receive ring: remaining transfer count = 0x800.
m.put(0x40071074,0x08000000)
# Include the real non-AMP effect initialization in the stock boot order.
m.stubs.remove(0xe98c);m.boot();m.phase='background'
activity=[]
def trace(u,pc,size,user):
 if pc not in [0x5488,0x54a8,0x5530]:return
 dest=u.reg_read(UC_ARM_REG_R0);r1=u.reg_read(UC_ARM_REG_R1);r2=u.reg_read(UC_ARM_REG_R2)
 length=r1 if pc==0x5530 else r2
 v.require(length<=0x100000,'Unexpected memory operation size')
 v.require(not (dest<v.code_end and dest+length>v.code_start),'Stock copy/clear overlaps NAM code')
 v.require(not (dest<0x202e6000 and dest+length>0x202e4000),'Stock copy/clear overlaps NAM reserved RAM')
 activity.append({'entry':hex(pc),'destination':hex(dest),'bytes':length,'source':None if pc==0x5530 else hex(r1)})
m.u.hook_add(UC_HOOK_CODE,trace);m.u.ctl_remove_cache(0,0x24000)
def unchanged_call(entry):
 before=bytes(m.u.mem_read(v.state_start,v.state_end-v.state_start))
 m.phase='background';m.run(entry,limit=3000000);m.guards()
 v.require(before==bytes(m.u.mem_read(v.state_start,v.state_end-v.state_start)),'Stock background changed NAM state')
# Previously stubbed non-AMP DSP initializers now execute with saved resources.
unchanged_call(0xe98c)
groups=[(0x200037e8,0x2c,0x1253c,5),(0x20003a7c,0x44,0x12792,15),
        (0x20004110,0x44,0x12a54,15),(0x20003a08,0x2c,0x12d6a,7),
        (0x200041d8,0x28,0x12fd8,8),(0x20000900,2,0x13344,55)]
results=[];reference=v.Reference();maxerr=0;index=0
for base,flag,entry,count in groups:
 for model in range(count):
  m.u.mem_write(base,bytes([model]))
  if flag==2:m.u.mem_write(base+flag,b'\x01')
  else:m.put(base+flag,1)
  unchanged_call(entry)
  newflag=bytes(m.u.mem_read(base+flag,1))[0] if flag==2 else m.get(base+flag)
  v.require(newflag==2,'Pending stock reload did not complete')
  m.phase='audio';xs=[.2*math.sin((index*8+i)*.063) for i in range(8)]
  x,out=m.dispatch(list(range(11)),xs,1)
  maxerr=max(maxerr,max(abs(y-z) for y,z in zip(out,reference.run(x))));index+=1
 results.append({'entry':hex(entry),'model_values_tested':list(range(count)),'completed':count})
 print(json.dumps({'completed_loader':hex(entry),'cases':count}),flush=True)
v.require(maxerr<2e-6,'NAM output changed across other-effect reloads')
# A bounded idle main-loop pass with real background routines and neutral
# simulated inputs. USB stack polling is excluded (no initialized USB handle).
background_entries=[0x117ec,0x12188,0xbd04,0xe9ae,0x57c0,0xb552,0x1089e]
for _ in range(8):
 for entry in background_entries:unchanged_call(entry)
# Seven synthetic preset buffers exercise active-preset pointer replacement.
# They are fixtures, not the stock flash preset-save/load mechanism.
original=m.preset;template=bytes(m.u.mem_read(original,128));preset_cases=0
for slot in range(7):
 m.preset=0x20026000+slot*128;m.u.mem_write(m.preset,template);m.put(0x20005ad0,m.preset)
 m.phase='audio';xs=[.1*math.cos((slot*8+i)*.09) for i in range(8)]
 x,out=m.dispatch(list(reversed(range(11))),xs,slot+2)
 v.require(max(abs(y-z) for y,z in zip(out,v.Reference().run(x)))<2e-6,'Preset pointer/control transition error')
 m.background();m.guards();preset_cases+=1
m.preset=original;m.put(0x20005ad0,original)
# Boundary audit is also required to reject a deliberately corrupted copy
# descriptor targeting either NAM region. No bad copy is allowed to execute.
negative=[]
for dest in [v.code_start,v.state_start]:
 for reg,value in [(UC_ARM_REG_R0,dest),(UC_ARM_REG_R1,0x30040000),(UC_ARM_REG_R2,16)]:m.u.reg_write(reg,value)
 try:m.run(0x5488)
 except ValueError as e:
  v.require('overlaps NAM' in str(e),'Wrong negative-control failure');negative.append({'destination':hex(dest),'caught':str(e)})
 else:raise ValueError('Overlap negative control not rejected')
overlays=sorted({(int(x['destination'],16),x['bytes']) for x in activity if 0x24000<=int(x['destination'],16)<0x40000})
result={'status':'PASS_BOUNDED_STOCK_BACKGROUND_RAM_TESTS','candidate_sha256':v.plan['candidate_sha256'],
 'non_amp_initializer_executed':'0xe98c during stock startup and again after NAM initialization',
 'startup_order':m.boot_events,'reload_cases':sum(x['completed'] for x in results),'groups':results,
 'nam_samples_interleaved':index*8,'max_abs_error':maxerr,'synthetic_preset_pointer_cases':preset_cases,
 'background_entries':[hex(x) for x in background_entries],'background_passes':8,
 'memory_helper_entry_observations':len(activity),'stock_executable_overlay_ranges':[{'start':hex(x),'bytes':n,'end_exclusive':hex(x+n)} for x,n in overlays],
 'memory_activity':activity,'foreign_code_data_reads':m.foreign_code_reads,'unexpected_code_entries':m.foreign_code_entries,
 'forbidden_state_writes':m.violations,'negative_overlap_checks':negative,
 'virtual_mmio_pages':[hex(x) for x in virtual_mmio],
 'limits':['Flash base 0x30040000 is an offline mapping assumption; only saved payload bytes are supplied',
  'Main boot peripherals and ten other DSP audio callbacks remain stubs; tested non-AMP loader routines are real',
  'Selected neutral-input background paths only; USB stack polling, flash saves, interrupt timing and full UI behavior excluded',
  'Synthetic preset pointer switches are not full stock preset storage transactions',
  'Actual stock overlays are copied but their DSP processing is not executed here',
  'Arena-scoped write watcher avoids the reproduced Unicorn global-hook artifact; not whole-device emulation'],
 'device_or_audio_access':False,'physical_placement_safe_proven':False}
a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','reload_cases','max_abs_error','stock_executable_overlay_ranges','foreign_code_data_reads','unexpected_code_entries','forbidden_state_writes']},indent=2))
