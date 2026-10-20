#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
root=Path(__file__).resolve().parents[1]
exe=Path(sys.argv[1]).resolve()
def run(args,success=True):
    p=subprocess.run([str(exe)]+[str(a) for a in args],capture_output=True,text=True)
    assert (p.returncode==0)==success,(args,p.stdout,p.stderr)
    return p
with tempfile.TemporaryDirectory() as temp:
    d=Path(temp); model=root/'models/lstm.nam'; chain=root/'examples/chain.json'
    f=d/'input.wav'
    with wave.open(str(f),'wb') as w:
        w.setparams((1,2,48000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*480)
    result=run([model,chain,d/'out.wav',f]);report=json.loads(result.stdout);assert report['samples']==480
    # Read our own float32 output with an irregular final processing block.
    run([model,chain,d/'roundtrip.wav',d/'out.wav'])
    with wave.open(str(f),'wb') as w:
        w.setparams((1,2,44100,0,'NONE','not compressed'));w.writeframes(b'\0\0'*100)
    run([model,chain,d/'bad.wav',f],False)
    with wave.open(str(f),'wb') as w:
        w.setparams((1,2,48000,0,'NONE','not compressed'));w.writeframes(b'')
    run([model,chain,d/'bad.wav',f],False)
    j=json.loads(model.read_text());j['weights'].pop();(d/'bad.nam').write_text(json.dumps(j));run([d/'bad.nam',chain,d/'bad.wav'],False)
    j=json.loads(chain.read_text());j['stages'][0]['a']=999;(d/'bad.json').write_text(json.dumps(j));run([model,d/'bad.json',d/'bad.wav'],False)
print('PASS: PCM16/float32 file processing, 44.1kHz/empty WAV rejection, malformed model/config rejection; no playback')
