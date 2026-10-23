"""Memory-only, eight-frame DSP/reference regressions. No audio device API."""
import argparse,ctypes,json,subprocess,hashlib
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
p=argparse.ArgumentParser();p.add_argument('work',type=Path);a=p.parse_args();a.work=a.work.resolve()
ptr=ctypes.POINTER(ctypes.c_float);bp=ctypes.POINTER(ctypes.c_uint8);libs={}
for name,source in [('baseline',ROOT/'firmware/target/link'),('prototype',a.work/'generated/target/link')]:
 path=a.work/(name+'.dylib')
 subprocess.run(['clang++','-O2' if name=='baseline' else '-Os','-std=c++17','-shared','-fPIC','-ffp-contract=off','-DMPP_PITCH_QUALITY_PROTOTYPE',*(['-DMPP_DAISY_WAH'] if name=='prototype' else []),'-I'+str(source),'-I'+str(HERE/'upstream'),str(source/'fx_blocks.cpp'),str(HERE/'host.cpp'),str(HERE/'upstream/autowah.cpp'),'-o',str(path)],check=True)
 lib=ctypes.CDLL(str(path));lib.run_fx.argtypes=[ptr,ptr,ctypes.c_uint,bp];lib.upstream.argtypes=[ptr,ctypes.c_uint,ctypes.c_float];libs[name]=lib
def cfg(n,mode=2,enabled=1,mix=100,sense=50,res=50):
 c=np.zeros((n//8,32),dtype=np.uint8);c[:,:10]=[mode,enabled,2,24,mix,30,50,0,sense,res];c[:,16:26]=[2,0,3,12,100,30,50,0,50,50];return c
def run(name,x,c,r=None):
 l=np.array(x,dtype=np.float32);r=l.copy() if r is None else np.array(r,dtype=np.float32)
 libs[name].run_fx(l.ctypes.data_as(ptr),r.ctypes.data_as(ptr),len(l),c.ctypes.data_as(bp));assert np.isfinite(l).all() and np.isfinite(r).all();return l,r
n=48000;t=np.arange(n)/48000;rows=[]
for hz in [82.4069,110,196,440,659.255]:
 for amp in [.001,.01,.1,.5]:
  env=np.minimum((t%.25)*400,1)*np.exp(-8*(t%.25));x=amp*env*sum(np.sin(2*np.pi*hz*h*t+.2*h)/h**1.5 for h in range(1,9))
  for sense in [0,50,100]:
   c=cfg(n,sense=sense);y,r=run('prototype',x,c);ref=np.array(x,dtype=np.float32);sensitivity=.25+.006375*sense*sense
   libs['prototype'].upstream(ref.ctypes.data_as(ptr),n,sensitivity)
   # The firmware mix uses a 256-frame enable ramp; apply it to the upstream oracle.
   wet=np.minimum((np.arange(n)+1)/256,1);ref=x.astype('float32')+wet*(ref-x.astype('float32'))
   err=float(np.max(abs(y-ref)));relative=float(np.sqrt(np.mean((y-ref)**2))/max(1e-12,np.sqrt(np.mean(ref**2))))
   assert err<.002 and relative<.015,(hz,amp,sense,err,relative)
   assert np.array_equal(y,r)
   rows.append(dict(hz=hz,amplitude=amp,sensitivity=sense,peak=float(max(abs(y))),peak_error=err,relative_rms_error=relative))
rng=np.random.default_rng(42);x=rng.uniform(-.25,.25,n);r=rng.uniform(-.25,.25,n)
for mode in [1,3,4,5,6,7]:
 c=cfg(n,mode=mode);old=run('baseline',x,c,r);new=run('prototype',x,c,r)
 assert all(np.array_equal(b,q) for b,q in zip(old,new)),('non-wah changed',mode)
for c in [cfg(n,enabled=0),cfg(n,mix=0)]:
 l,y=run('prototype',x,c,r);assert np.array_equal(l,x.astype('float32')) and np.array_equal(y,r.astype('float32'))
extremes=[]
for sense in [0,100]:
 for res in [0,100]:
  c=cfg(n,sense=sense,res=res);l,y=run('prototype',x*8,c,r*8);assert max(abs(l))<8 and max(abs(y))<8
  extremes.append(dict(sensitivity=sense,resonance=res,peak=float(max(max(abs(l)),max(abs(y))))))
c=cfg(n);c[1500:1600,1]=0;c[3000:3300,0]=5;c[4000:4300,0]=1
l,y=run('prototype',x,c,np.zeros(n));assert max(abs(y))==0
z=x.copy();z[800]=np.nan;z[1600]=np.inf;run('prototype',z,cfg(n))
report=dict(status='PASS_OFFLINE_DAISY_WAH_HOST',audio_devices_opened=False,device_access=False,block_samples=8,sample_rate=48000,reference_cases=rows,extremes=extremes,non_wah_modes_sample_exact=True,bypass_and_zero_mix_sample_exact=True,stereo_no_crosstalk=True,mode_switches_and_nonfinite_recovery=True,source_sha256=hashlib.sha256((HERE/'wah.hpp').read_bytes()).hexdigest(),limitation='Synthetic signals and host arithmetic; no subjective quality or MCU deadline claim')
(a.work/'host.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],len(rows),'reference cases; max error',max(r['peak_error'] for r in rows))
