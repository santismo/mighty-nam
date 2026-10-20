#!/usr/bin/env python3
"""Silent before/after engine comparison, independent official oracle elsewhere."""
import argparse,json,random,math,hashlib,struct
from pathlib import Path
from a2_oracle import library,Engine
p=argparse.ArgumentParser();p.add_argument('baseline');p.add_argument('optimized');p.add_argument('models',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
old,new=library(a.baseline),library(a.optimized);results=[]
for path in a.models:
 rng=random.Random(7381);x=[rng.uniform(-.5,.5) if i<32000 else 0. for i in range(48000)]
 e,f=Engine(old,path,'small'),Engine(new,path,'small');ys=[];zs=[];i=0;partitions=[]
 while i<len(x):
  n=min(rng.choice([1,7,8,17,127,256,1024]),len(x)-i);partitions.append(n)
  y,z=e.run(x[i:i+n]),f.run(x[i:i+n]);assert y==z,(path,i)
  assert all(math.isfinite(q) for q in z);ys+=y;zs+=z;i+=n
 for lib,eng in [(old,e),(new,f)]:lib.a2_small_reset(eng.p)
 assert e.run(x[:1024])==f.run(x[:1024])==ys[:1024]
 results.append(dict(model=path.name,samples=len(x),bit_identical=True,reset_bit_identical=True,partition_sizes=sorted(set(partitions)),output_sha256=hashlib.sha256(struct.pack('<'+'f'*len(ys),*ys)).hexdigest()))
 print(path.name,'48000 samples bit-identical',flush=True)
a.output.write_text(json.dumps(dict(status='PASS',silent=True,device_access=False,models=results,library_sha256={name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in [('baseline',a.baseline),('optimized',a.optimized)]}),indent=2)+'\n')
