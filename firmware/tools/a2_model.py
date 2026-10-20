#!/usr/bin/env python3
"""Strict, offline fixed A2 Lite validator/extractor. No device or audio APIs."""
import copy,json,math,struct
from pathlib import Path
K=[6]*14+[15]*2+[6]*7
D=[1,3,7,17,41,101,239]*2+[1,13]+[1,3,7,17,41,101,239]
def signature():
 l=dict(input_size=1,condition_size=1,head=dict(out_channels=1,kernel_size=16,bias=True),channels=3,kernel_sizes=K,dilations=D,
  activation=[dict(type='LeakyReLU',negative_slope=.01)]*23,bottleneck=3,
  head1x1=dict(active=False,out_channels=1,groups=1),layer1x1=dict(active=True,groups=1),groups_input=1,groups_input_mixin=1,
  gating_mode=['none']*23,secondary_activation=[None]*23,slimmable=None)
 for name in ['conv_pre','conv_post','input_mixin_pre','input_mixin_post','activation_pre','activation_post','layer1x1_post','head1x1_post']:
  l[name+'_film']=dict(active=False,shift=True,groups=1)
 return dict(layers=[l],head=None)
def extract(j):
 rate=j.get('sample_rate')
 if j.get('architecture')=='SlimmableContainer':
  if j.get('version')!='0.7.0':raise ValueError('Unsupported container version')
  matches=[]
  for s in j['config']['submodels']:
   m=copy.deepcopy(s['model']);m.setdefault('sample_rate',rate)
   try:matches.append(validate(m))
   except (ValueError,KeyError,TypeError):pass
  if len(matches)!=1:raise ValueError('Need exactly one supported Lite submodel')
  return matches[0]
 return validate(copy.deepcopy(j))
def validate(j):
 if j.get('version')!='0.7.0' or j.get('architecture')!='WaveNet' or j.get('sample_rate')!=48000:raise ValueError('Need file 0.7.0 WaveNet at 48 kHz')
 c=copy.deepcopy(j['config']);scale=c.pop('head_scale',None)
 if c!=signature():raise ValueError('Unsupported topology (this is a strict A2 Lite subset)')
 w=j['weights']
 if len(w)!=1871 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>3.402823466e38 for x in w):raise ValueError('Need 1871 finite float32 weights')
 if type(scale) not in (int,float) or not math.isfinite(scale):raise ValueError('Invalid head scale metadata')
 # Official WaveNet::set_weights_ replaces config head_scale with weights[-1].
 # Some real captures have different JSON metadata; preserve the actual weight.
 return j
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 j=extract(json.loads(a.input.read_text()));a.output.write_text(json.dumps(j)+'\n');print('Validated A2 Lite; extracted 1871 unchanged weights at 48 kHz')
