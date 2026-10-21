#!/usr/bin/env python3
"""Analyze synthetic mono pitch outputs from test_fx_blocks/pitch_range. No playback."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser(description=__doc__)
for key in ['semitone_samples','range_samples','source_root','output']:p.add_argument(key,type=Path)
a=p.parse_args();rows=[]
def measure(x,input_hz,shift,harmonics):
 s=np.abs(np.fft.rfft(x*np.hanning(len(x)),n=524288));peak=int(s.argmax())*48000/524288
 target=input_hz*2**(shift/12);error=1200*np.log2(peak/target)
 assert np.isfinite(x).all() and np.max(np.abs(x))<8 and abs(error)<5,(input_hz,shift,harmonics,error)
 return dict(input_hz=input_hz,shift=shift,harmonics=harmonics,expected_hz=target,peak_hz=peak,cents=float(error))
for shift,x in zip(range(-12,13),np.fromfile(a.semitone_samples,'float32').reshape(25,48000)):rows.append(measure(x,220,shift,False))
samples=np.fromfile(a.range_samples,'float32').reshape(112,48000);i=0
for frequency in [82.406889,110,146.832384,196,246.941651,329.627557,659.255114,880]:
 for harmonic in [False,True]:
  for shift in [-12,-7,-1,0,1,7,12]:rows.append(measure(samples[i],frequency,shift,harmonic));i+=1
sources=['target/link/fx_blocks.cpp','target/link/fx_blocks.hpp','research/test_fx_blocks.cpp','research/test_fx_pitch_range.cpp']
report=dict(status='PASS_FX_PITCH_ANALYSIS',cases=rows,max_error_cents=max(abs(r['cents']) for r in rows),source_sha256={s:hashlib.sha256((a.source_root/s).read_bytes()).hexdigest() for s in sources},audio_playback=False,physical_device_access=False,limits=['Steady synthetic monophonic notes; not chord quality, transients or hardware timing'])
a.output.write_text(json.dumps(report,indent=2)+'\n');print(f"PASS {len(rows)} cases; max {report['max_error_cents']:.3f} cents")
