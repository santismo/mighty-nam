#!/usr/bin/env python3
"""Four-second stock delay/hall tail test, excited by offline A2 output.
The ARM AMP is bypassed in this test: long wet tails are separated from the
model's DC response. The companion chain test executes ARM A2 concurrently.
No playback, audio device, USB or firmware writes.
"""
import argparse,math,json,time
from pathlib import Path
import candidate_vm as v
from stock_chain_vm import StockChainMachine,ORDER,GROUPS
from a2_oracle import Engine,library
p=argparse.ArgumentParser();p.add_argument('payload');p.add_argument('library');p.add_argument('model',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();v.configure(a.payload,True);lib=library(a.library)
nam=Engine(lib,a.model,'small');base=Engine(lib,a.model,'small')
for _ in range(1024):nam.run([0.]*8);base.run([0.]*8)
burst=[]
for b in range(300):
 x=[.15*math.sin(2*math.pi*110*(b*8+i)/48000)*math.sin(math.pi*(b*8+i)/2400)**2 for i in range(8)]
 y=nam.run(x);z=base.run([0.]*8);burst += [(v-w)*math.sin(math.pi*(b*8+i)/2400)**2 for i,(v,w) in enumerate(zip(y,z))]
assert max(map(abs,burst))>1e-5
m=StockChainMachine(fast=True,observe_blocks=False);m.set_preset([7,8],{7:2,8:2})
# Saved V1.5.6 parameter positions. Delay: level, feedback, time.
# Hall: decay, pre-delay, tone, level. No tempo synchronization.
m.u.mem_write(m.preset+61,bytes([70,55,40]));m.u.mem_write(m.preset+70,bytes([65,10,50,60]))
for _ in range(256):m.block([0.]*8,control=0x41)
assert m.u.mem_read(GROUPS[7][0]+1,1)[0]==2 and m.u.mem_read(GROUPS[8][0]+1,1)[0]==2
zero=max(abs(x) for x in m.block([0.]*8,control=0x41));assert zero<1e-8
bins=[dict(peak=0.,sum_sq=0.,samples=0) for _ in range(8)]
stage_bins={s:[dict(peak=0.,sum_sq=0.,samples=0) for _ in range(8)] for s in [7,8]}
start=time.perf_counter()
for b in range(24000):
 xs=burst[b*8:b*8+8] if b<300 else [0.]*8
 ys=m.block(xs,control=0x41)
 idx=b//3000
 for series,data in [(bins,ys)]+[(stage_bins[s],m.last_outputs[s]) for s in [7,8]]:
  q=series[idx];q['peak']=max(q['peak'],max(map(abs,data)));q['sum_sq']+=sum(x*x for x in data);q['samples']+=len(data)
 if b%3000==0:print('Tail simulated seconds',b/6000,flush=True)
for series in [bins,*stage_bins.values()]:
 for q in series:q['rms']=math.sqrt(q.pop('sum_sq')/q['samples'])
assert bins[2]['peak']>1e-6,'No measurable tail after one second'
assert bins[-1]['rms']<bins[1]['rms'],'Tail did not decay over measured window'
assert stage_bins[7][1]['peak']>1e-6 and stage_bins[8][1]['peak']>1e-6
r=dict(status='PASS',silent=True,device_access=False,seconds=4,excitation_seconds=.05,excitation_model=a.model.name,excitation='Compact A2 render minus its zero-input response, tapered to zero; no audio output',amp_bypassed=True,concurrent_arm_a2=False,delay_model=2,reverb_model=2,delay_parameter_bytes=[70,55,40],hall_parameter_bytes=[65,10,50,60],zero_input_baseline_peak=zero,half_second_output_bins=bins,stage_bins=stage_bins,wall_seconds=time.perf_counter()-start,stock_stats=m.stats(),limits=['No cycle timing or physical DSP validation','Bounded four-second tail; not a proof for all settings or complete decay','Scoped old NAM memory guard and boundary checks; no basic-block stack coverage'])
a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS',r['wall_seconds'],flush=True)
