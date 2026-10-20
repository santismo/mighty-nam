#!/usr/bin/env python3
"""Silent saved-code test of stock input + master wrappers surrounding DSP."""
import argparse,json,math
from pathlib import Path
import candidate_vm as v
from stock_chain_vm import StockChainMachine,ORDER
p=argparse.ArgumentParser();p.add_argument('payload',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
v.configure(a.payload,True)
m=StockChainMachine(fast=True);oracle=StockChainMachine(fast=True,reference_amp=True)
for vm in (m,oracle):vm.set_preset([1,2,4,6,7,8,9])
cases=[]
for label,volume in [('master_mid',50),('master_high',80),('master_zero',0)]:
 for vm in (m,oracle):vm.u.mem_write(vm.preset+84,bytes([volume]))
 err=0.;peak=0.;last_peak=0.
 for n in range(192):
  xs=[.2*math.sin((n*8+i)*.061) for i in range(8)]
  out=m.outer_block(xs);expected=oracle.outer_block(xs)
  err=max(err,max(abs(x-y) for x,y in zip(out,expected)))
  peak=max(peak,max(map(abs,out)))
  if n>=160:last_peak=max(last_peak,max(map(abs,out)))
 v.require(err<2e-5,'Outer chain reference mismatch')
 if volume:v.require(last_peak>1e-7,'Silent settled master output')
 # Master zero can be attenuated rather than hard muted; report measured level.
 cases.append({'case':label,'master_parameter':volume,'blocks':192,'max_abs_error':err,'peak':peak,'last_32_blocks_peak':last_peak})
 print(json.dumps(cases[-1]),flush=True)
result={'status':'PASS_BOUNDED_STOCK_INPUT_AND_MASTER_WRAPPERS','candidate_sha256':v.plan['candidate_sha256'],
 'entry':'0xe934','master_wrapper':'0xe8f8','cases':cases,'compiled_stats':m.stats(),
 'device_or_audio_access':False,'limits':['Synthetic mono floats into stock software wrapper; not ADC/DAC or DMA execution',
 'A15 Thumb/VFP emulation, no target timing, caches or interrupts','All earlier stock_chain_vm mapping and startup assumptions apply',
 'H3 correctness fixture only; no playback or tone-quality validation']}
a.output.write_text(json.dumps(result,indent=2)+'\n')
