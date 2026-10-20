#!/usr/bin/env python3
"""Offline stock effects + compiled ARM NAM, with independent NAM oracle.
No host sound, USB, firmware writer or physical device calls.
"""
import argparse,json,math,hashlib,time
from pathlib import Path
import candidate_vm as v
from stock_chain_vm import StockChainMachine,GROUPS,NAMES,ORDER
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
v.configure(a.payload,True)
result={'status':'RUNNING','candidate_sha256':v.plan['candidate_sha256'],'device_or_audio_access':False,
 'physical_validation':False,'cases':[],'sample_rate_assumed':48000,'samples_per_block':8}
def save():a.output.write_text(json.dumps(result,indent=2)+'\n')
def signal(n):return [.16*math.sin((n*8+i)*.071)+.04*math.sin((n*8+i)*.213) for i in range(8)]
def run(m,n,offset=0,order=ORDER,control=1):
 out=[]
 for b in range(n):out+=m.block(signal(offset+b),order,control)
 return out
start=time.monotonic();save()
try:
 # Establish equivalent results for instruction and block instrumentation.
 slow=StockChainMachine();fast=StockChainMachine(fast=True)
 for m in [slow,fast]:m.set_preset([1,2,4,6,7,8,9])
 y=run(slow,24);z=run(fast,24)
 v.require(y==z,'Instrumentation changes simulated outputs')
 result['instrumentation_crosscheck']={'blocks':24,'bit_identical':True,'instruction_trace':slow.stats(),'block_trace':fast.stats()};save()
 print('Instrumentation crosscheck passed',flush=True)
 # Compare the complete stock chain against an independent NAM substitution.
 # All other effects and their histories execute in both machines.
 oracle=StockChainMachine(reference_amp=True,fast=True);compiled=StockChainMachine(fast=True)
 for m in [oracle,compiled]:m.set_preset([1,2,4,6,7,8,9])
 paired=[];total=0
 for label,order,control,blocks in [('full_chain',ORDER,1,192),('reordered',[0,5,3,1,2,4,9,8,6,7,10],1,160),('amp_bypass',ORDER,0x41,160),('amp_reenable',ORDER,1,160)]:
  maxerr=0.;peak=0.;sq=0.
  for n in range(blocks):
   x=signal(total+n);y=compiled.block(x,order,control);z=oracle.block(x,order,control)
   maxerr=max(maxerr,max(abs(c-r) for c,r in zip(y,z)));peak=max(peak,max(map(abs,y)));sq+=sum(q*q for q in y)
  v.require(maxerr<2e-5,'Complete chain differs from independent NAM substitution')
  v.require(peak>1e-7,'Vacuous silent complete chain')
  paired.append({'case':label,'order':order,'amp_control':control,'blocks':blocks,'final_chain_max_abs_error':maxerr,'peak_output':peak,'rms_output':math.sqrt(sq/(blocks*8))})
  total+=blocks;print(json.dumps(paired[-1]),flush=True)
 result['paired_full_chain']=paired;result['compiled_full_chain']=compiled.stats();result['reference_full_chain']=oracle.stats();save()
 # Each saved V1.5.6 dynamic model. Use real audio-triggered transitions and
 # background loaders; never write the loader's internal current-model fields.
 for stage,(base,count) in GROUPS.items():
  m=StockChainMachine(fast=True);m.set_preset([stage]);run(m,136)
  for model in range(1,count+1):
   m.set_preset([stage],{stage:model})
   before=dict(m.overlay_blocks);output=run(m,48,model*48)
   actual=m.u.mem_read(base+1,1)[0]
   v.require(actual==model,f'Model transition incomplete for {stage}/{model}: {actual}')
   delta={k:m.overlay_blocks[k]-before.get(k,0) for k in m.overlay_blocks if m.overlay_blocks[k]!=before.get(k,0)}
   # Studio compressor is a built-in function; other models run copied overlays.
   pointer_offset={1:0x1c,2:0x34,6:0x34,7:0x24,8:0x1c}[stage]
   processor=m.get(base+pointer_offset)
   v.require(0x39000<=processor<0x3e000 and processor&1,'Invalid stock process pointer')
   overlay=hex(processor&~0xfff)
   v.require(delta.get(overlay,0)>0 or (stage==1 and model==3),'Selected effect did not execute its stock overlay')
   row={'stage':NAMES[stage],'model':model,'blocks':48,'active_model':actual,'output_peak':max(map(abs,output)),
    'overlay_blocks':delta,'process_pointer_observed':hex(processor),'max_nam_error':m.max_nam_error}
   result['cases'].append(row);save();print(json.dumps(row),flush=True)
  result.setdefault('group_stats',{})[NAMES[stage]]=m.stats();save()
 # Exercise second EQ, a different bundled cabinet and enabled gate together.
 m=StockChainMachine(fast=True);m.set_preset([4,5,9],{4:2,9:10});run(m,192)
 result['eq_gate_cab_case']=m.stats();save()
 # Guards must reject a stock memory helper aimed at the NAM arena.
 for reg,value in zip(v.R[:3],[v.state_start,0x30040000,16]):m.u.reg_write(reg,value)
 m.phase='background'
 try:m.run(0x5488)
 except ValueError as e:
  v.require('overlaps NAM RAM' in str(e),'Unexpected negative-control failure')
  result['negative_copy_control']=str(e)
 else:raise ValueError('Bad stock copy was not rejected')
 result['status']='PASS_BOUNDED_ACTUAL_STOCK_AUDIO_CHAIN'
except Exception as e:
 result['status']='INCOMPLETE_WITH_FAILURE';result['failure']={'type':type(e).__name__,'message':str(e)};save();raise
finally:
 result['wall_seconds']=round(time.monotonic()-start,2)
 result['limits']=['Only exact V1.5.6 candidate and embedded H3 NAM correctness fixture',
 'Unicorn A15 Thumb/VFP compatibility model, not Cortex-M7 timing/cache/interrupt/peripheral emulation',
 'Boot peripherals and preset storage remain stubbed; presets are explicit RAM fixtures',
 'Saved payload mapped at inferred 0x30040000; no flash contents or device state read',
 'Real shared initialization and routing fade tables retained; dispatcher supplied synthetic 8-frame inputs',
 'Stock effects execute unchanged instructions but their algorithms are not independently validated against physical hardware',
 'Short windows exercise DSP, transitions and memory; no claim of settled full delay/reverb tails or listening quality',
 'Block instrumentation stack sampling is a lower bound; no target deadline or total RAM safety proof',
 'No firmware/update container emitted; USB recovery remains unproven']
 save()
print(json.dumps({'status':result['status'],'model_cases':len(result['cases']),'seconds':result['wall_seconds']},indent=2))
