#!/usr/bin/env python3
"""Independent CPython IMA codec oracle and offline signal measurements.

Requires Python 3.12 (audioop) and numpy. Reads test files, never audio devices.
"""
import argparse, audioop, json, math, struct
from pathlib import Path
import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('work',type=Path);a=p.parse_args()
rows=[]
for name,pcm_name,frames in [('codec','codec-pcm.raw',131071),('record48','reference48.raw',1440000),('record24','reference24.raw',720000)]:
    pcm=(a.work/pcm_name).read_bytes();blocks=(a.work/(name+'.blocks')).read_bytes()
    assert len(pcm)==frames*2 and len(blocks)==math.ceil(frames/256)*132
    state=(0,0);decoded=bytearray()
    for start in range(0,frames,256):
        base=start//256*132;count=min(256,frames-start)
        predictor,index,reserved=struct.unpack_from('<hBB',blocks,base)
        assert (predictor,index)==state and reserved==0
        part=pcm[2*start:2*(start+count)]
        # audioop omits the last half byte for odd sample counts. Pad only its
        # comparison input; ignore the unused low nibble in our final byte.
        packed,next_state=audioop.lin2adpcm(part+(b'\0\0' if count&1 else b''),2,state)
        actual=blocks[base+4:base+4+(count+1)//2]
        if count&1:assert packed[:-1]==actual[:-1] and packed[-1]&240==actual[-1]&240
        else:assert packed==actual
        decoded_part,decoded_state=audioop.adpcm2lin(actual,2,state)
        decoded+=decoded_part[:count*2]
        if not count&1:assert next_state==decoded_state;state=next_state
    if name=='codec':assert decoded==(a.work/'codec-decoded.raw').read_bytes()
    ref=np.frombuffer(pcm,dtype='<i2').astype(np.float64)
    got=np.frombuffer(decoded,dtype='<i2').astype(np.float64)
    # Synthetic guitar-like input through three actual NAM captures; this does
    # not establish perceptual quality for arbitrary guitar playing.
    snr=float(10*np.log10(np.sum(ref*ref)/np.sum((ref-got)**2)))
    if name!='codec':assert snr>20
    rows.append(dict(case=name,samples=frames,independent_encoded_bytes_match=True,
        SNR_dB=snr,peak_error_PCM16=int(np.max(abs(ref-got))),
        wrap_step_PCM16=int(abs(got[-1]-got[0]))))
# Verify the specified FIR independently of its generated C++ constants.
n=np.arange(63);x=n-31
h=2*.1875*np.sinc(2*.1875*x)*(.42-.5*np.cos(2*np.pi*n/62)+.08*np.cos(4*np.pi*n/62));h/=sum(h)
freq=np.linspace(0,24000,24001)
response=np.abs(np.exp(-2j*np.pi*freq[:,None]*n/48000)@h)
pass_min=float(20*np.log10(min(response[freq<=6000])))
stop_max=float(20*np.log10(max(response[freq>=12000])))
assert pass_min>-.02 and stop_max<-60
result=dict(status='PASS_INDEPENDENT_CODEC_AND_FILTER_CHECKS',cases=rows,
    mono=True,format='internal IMA4, 256 samples + 4 byte state per block',
    filter=dict(taps=63,cutoff_Hz=9000,passband_through_6000_Hz_min_dB=pass_min,
        stopband_from_12000_Hz_max_dB=stop_max,recorded_loop_path_group_delay_frames_48k=62,
        live_guitar_added_buffer_frames=0),
    limitations=['No listening or arbitrary-capture perceptual validation.',
        'IMA is lossy; wrap seam is not automatically crossfaded.',
        'Mono recording folds stereo effects down at the proposed integration point.',
        'Filter delay affects recorded loop only, not live guitar.'],audio_device_opened=False)
(a.work/'compression-quality.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
