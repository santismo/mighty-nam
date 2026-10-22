"""Compile and compare default/prototype DSP in memory. No device or playback.

Requires clang++ and numpy. Writes metrics, never opens an audio output device.
The spill metric is energy outside +/-8 Hz of expected steady harmonics;
it is not THD+N or a listening score. Vibrato is time-aligned within the existing
ring before measuring cents, so its alignment is not hardware latency.
"""
import argparse,ctypes,hashlib,json,subprocess
from pathlib import Path
import numpy as np

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args()
 root=Path(__file__).resolve().parents[1];a.output.mkdir(parents=True,exist_ok=True)
 source=root/'target/link/fx_blocks.cpp';wrapper=Path(__file__).with_name('pitch_quality_host.cpp')
 libs={};ptr=ctypes.POINTER(ctypes.c_float);byteptr=ctypes.POINTER(ctypes.c_uint8)
 for name in ['baseline','prototype']:
  path=(a.output/(name+'.dylib')).resolve()
  subprocess.run(['clang++','-std=c++17','-O2','-ffp-contract=off','-shared','-fPIC',
   *(['-DMPP_PITCH_QUALITY_PROTOTYPE'] if name=='prototype' else []),
   '-I'+str(source.parent),str(source),str(wrapper),'-o',str(path)],check=True)
  lib=ctypes.CDLL(str(path));lib.pitch_quality_run.argtypes=[ptr,ptr,ctypes.c_uint,byteptr];libs[name]=lib
 def config(n,shift=12,mode=1,enabled=1,mix=100):
  c=np.zeros((n//8,32),dtype='uint8')
  c[:,0:10]=[mode,enabled,2,shift,mix,30,50,0,50,50]
  c[:,16:26]=[2,0,3,12,100,30,50,0,50,50]
  return c
 def run(name,l,c,r=None):
  l=np.array(l,dtype='float32',copy=True);r=l.copy() if r is None else np.array(r,dtype='float32',copy=True)
  libs[name].pitch_quality_run(l.ctypes.data_as(ptr),r.ctypes.data_as(ptr),len(l),c.ctypes.data_as(byteptr))
  assert np.isfinite(l).all() and np.isfinite(r).all()
  return l,r
 n=48000;t=np.arange(n)/48000;rows=[]
 for name in libs:
  for hz in [65.4064,82.4069,110,196,329.6276,659.255,880]:
   for shift in [-12,-7,-2,2,7,12]:
    for bright in [False,True]:
     nh=min(int(20000/hz),45) if bright else 3
     x=sum(.14/h**(1.15 if bright else 2)*np.sin(2*np.pi*hz*h*t+.13*h) for h in range(1,nh+1))
     l,r=run(name,x,config(n,shift+12),-x*.5)
     assert max(abs(r+l*.5))<1e-6, 'Stereo scaling changed'
     y=l[12000:];f=np.fft.rfftfreq(len(y),1/48000);power=abs(np.fft.rfft(y*np.hanning(len(y))))**2
     mask=np.zeros_like(f,dtype=bool)
     for h in range(1,nh+1):mask|=abs(f-h*hz*2**(shift/12))<8
     rows.append(dict(variant=name,case='steady',hz=hz,semitones=shift,bright=bright,
      spill_db=float(10*np.log10(max(1e-15,power[~mask].sum()/power.sum())))))
  for hz in [82.4069,196,440]:
   for shift in [-12,-2,2,12]:
    target=hz*2**(.035*np.sin(2*np.pi*4*t));x=.2*np.sin(np.cumsum(2*np.pi*target/48000))
    y,_=run(name,x,config(n,shift+12));s=np.fft.fft(y);h=np.zeros(n);h[0]=h[n//2]=1;h[1:n//2]=2;z=np.fft.ifft(s*h)
    inst=np.convolve(np.angle(z[1:]*z[:-1].conj())*48000/(2*np.pi),np.ones(96)/96,mode='same')
    want=target*2**(shift/12);errors=[]
    for lag in range(0,1537,8):
     err=1200*np.log2(np.maximum(inst[8000:40000],1)/want[8000-lag:40000-lag])
     errors.append((float(np.sqrt(np.mean(err**2))),float(np.percentile(abs(err),95)),lag))
    best=min(errors);rows.append(dict(variant=name,case='vibrato',hz=hz,semitones=shift,rms_cents=best[0],p95_cents=best[1],alignment_samples=best[2]))
  print(name,'spectral/tracking checks complete',flush=True)
 # One second of note attacks, half-step slides and a two-semitone bend.
 hz=np.where(t<.3,110,np.where(t<.6,196,329.6276))*2**(np.maximum(t-.7,0)*2/.3/12)
 envelope=np.minimum((t%.3)*400,1)*np.exp(-4*(t%.3));phase=np.cumsum(hz/48000)*2*np.pi
 x=envelope*(.22*np.sin(phase)+.06*np.sin(phase*2)+.03*np.sin(phase*3))
 transitions=[]
 for shift in [0,5,10,12,14,19,24]:
  c=config(n,shift);c[1600:1700,1]=0;c[3000:3100,4]=0;c[4200:4400,3]=12
  for name in libs:
   l,r=run(name,x,c,np.zeros(n));assert max(abs(r))==0, 'Stereo crosstalk'
   assert max(abs(l))<.5 and max(abs(np.diff(l)))<.5
   transitions.append(dict(variant=name,shift=shift-12,peak=float(max(abs(l))),largest_step=float(max(abs(np.diff(l))))))
 # Rapid type/pitch changes, positive to negative/neutral and back, independent
 # channels, bypass and zero mix. Bound safety only, not click-free perception.
 rng=np.random.default_rng(42);x=rng.uniform(-.25,.25,n);r=rng.uniform(-.25,.25,n)
 c=config(n);c[:,3]=(np.arange(n//8)//29)%25;c[:,0]=(np.arange(n//8)//350)%7+1
 for name in libs:
  l,y=run(name,x,c,r);assert max(abs(l))<2 and max(abs(y))<2
 for mode in range(2,8):
  c=config(n,24,mode);old=run('baseline',x,c,r);new=run('prototype',x,c,r)
  assert all(np.array_equal(b,p) for b,p in zip(old,new)), 'Non-pitch mode changed'
 for c in [config(n,12),config(n,24,enabled=0),config(n,24,mix=0)]:
  l,y=run('prototype',x,c,r)
  assert max(abs(l-x.astype('float32')))<3e-8 and max(abs(y-r.astype('float32')))<3e-8
 # An idle upshift filter must not remember the last note across a long
 # downshift/neutral interval and emit it when upshift is selected again.
 c=config(n,24);c[1800:4500,3]=0
 x=.2*np.sin(2*np.pi*110*t);x[14400:]=0
 l,r=run('prototype',x,c)
 assert max(abs(l[36000:]))==0 and max(abs(r[36000:]))==0
 summaries={}
 for case,key in [('steady','spill_db'),('vibrato','rms_cents')]:
  b=[r[key] for r in rows if r['case']==case and r['variant']=='baseline'];q=[r[key] for r in rows if r['case']==case and r['variant']=='prototype']
  summaries[case]=dict(cases=len(b),baseline_median=float(np.median(b)),prototype_median=float(np.median(q)),baseline_worst=max(b),prototype_worst=max(q),improved=sum(y<x for x,y in zip(b,q)),worst_regression=max(y-x for x,y in zip(b,q)))
 assert summaries['steady']['prototype_worst'] < -30
 assert summaries['vibrato']['prototype_median'] < 1.5 and summaries['vibrato']['prototype_worst'] < 12
 report=dict(status='PASS_OFFLINE_PITCH_QUALITY',summary=summaries,cases=rows,transients=transitions,
  engine_bytes={k:v.pitch_quality_engine_bytes() for k,v in libs.items()},non_pitch_modes_exact=True,
  stereo_isolated=True,rapid_switches_bounded=True,dry_and_zero_shift_preserved=True,
  source_sha256={str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in [source,source.with_suffix('.hpp'),wrapper,Path(__file__)]},
  device_access=False,audio_playback=False,limitations=['Synthetic monophonic quality metrics, not listening scores','Chord quality not established','Transitions checked for finite/bounded output, not perceptual smoothness','Time alignment is not physical latency'])
 (a.output/'quality.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summaries,indent=2),flush=True)
if __name__=='__main__':main()
