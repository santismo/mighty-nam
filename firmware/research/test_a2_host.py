#!/usr/bin/env python3
"""Silent offline numerical, ring-wrap, partition/reset and strict-loader checks."""
import argparse,json,math,random,time,hashlib,copy,ctypes as c
from pathlib import Path
from a2_oracle import library,Engine,extract
p=argparse.ArgumentParser();p.add_argument('library');p.add_argument('models',nargs='+',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();lib=library(a.library)
rng=random.Random(3000);n=48000
xs=[(.25*math.sin(2*math.pi*110*t/48000)+.07*math.sin(2*math.pi*277*t/48000)+rng.uniform(-.015,.015))*(.5+.5*math.sin(t/1300)) if 256<t<24000 else (1. if t==0 else 0.) for t in range(n)]
results=[]
for path in a.models:
 j=extract(json.loads(path.read_text()));ref,small=Engine(lib,path),Engine(lib,path,'small');y=[];z=[];start=time.perf_counter()
 for i in range(0,n,8):
  y+=ref.run(xs[i:i+8]);z+=small.run(xs[i:i+8])
 elapsed=time.perf_counter()-start;assert all(math.isfinite(x) for x in z)
 err=max(abs(v-w) for v,w in zip(y,z));rms=math.sqrt(sum((v-w)**2 for v,w in zip(y,z))/n)
 assert err<2e-5,(path,err)
 whole=Engine(lib,path,'small');zz=[]
 for i in range(0,n,1024):zz+=whole.run(xs[i:i+1024])
 assert zz==z,'Block partition changes compact output'
 lib.a2_small_reset(small.p);assert small.run(xs[:512])==z[:512],'Reset fails'
 cases=[]
 for label,change in [('full_channels',lambda q:q['config']['layers'][0].update(channels=8)),('dilation',lambda q:q['config']['layers'][0]['dilations'].__setitem__(0,2)),('activation',lambda q:q['config']['layers'][0]['activation'][0].update(negative_slope=.02)),('wrong_rate',lambda q:q.update(sample_rate=44100)),('weight_nan',lambda q:q['weights'].__setitem__(0,float('nan'))),('missing_weight',lambda q:q['weights'].pop()),('unknown_option',lambda q:q['config'].update(condition_dsp={}))]:
  q=copy.deepcopy(j);change(q)
  try:extract(q)
  except ValueError:cases.append(label)
  else:raise AssertionError(label)
 results.append(dict(model=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),samples=n,seconds=n/48000,max_abs_error=err,rms_error=rms,peak=max(map(abs,z)),last_half_peak=max(map(abs,z[24000:])),block_sizes=[8,1024],block_invariance=True,reset=True,rejected_variants=cases,combined_host_test_seconds=elapsed))
 print(json.dumps(results[-1]),flush=True)
# Runtime loader must reject invalid input even without host validation.
bad=(c.c_float*1871)();bad[17]=float('inf');assert not lib.a2_small_create(bad,1871);assert not lib.a2_small_create(bad,1870)
r=dict(status='PASS',silent=True,device_access=False,reference='Official unmodified NAM Core v0.5.2 generic Eigen WaveNet, subclass exposes buffer sizing to start with zero history',compact_bytes=lib.a2_small_size(),tolerance=2e-5,models=results,nonfinite_and_count_runtime_rejection=True)
a.output.write_text(json.dumps(r,indent=2)+'\n')
