#!/usr/bin/env python3
"""Sample-exact inactive-loop regression, synthetic PCM only; no audio device."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from harness import setup
p=argparse.ArgumentParser(description=__doc__)
for n in ['baseline','payload','output','model']:p.add_argument(n,type=Path)
p.add_argument('--reference',action='store_true');a=p.parse_args()
M,v,s,preset,input_block,model_slot=setup(a.baseline,a.payload,a.output,a.reference)
m=M();m.service();m.upload(model_slot(a.model),800);m.initialize_usb();m.arm()
cases=[]
for label,enabled,types in [('NAM',[],{}),('NAM + spring',[8],{8:4}),('full stock chain',[1,2,4,5,6,7,8,9],{4:4,8:4})]:
    data=preset(enabled,types);data[84]=37;data[70:74]=bytes([20,20,50,0]);m.u.mem_write(m.preset,bytes(data))
    samples=[]
    for i in range(1450):
        y=m.process(i,input_block(i))
        if i>=1350:samples+=y
    assert any(samples) and not m.words()[4]
    instructions=[0]
    hook=m.u.hook_add(UC_HOOK_CODE,lambda *args:instructions.__setitem__(0,instructions[0]+1))
    try:m.process(1450,input_block(1450))
    finally:m.u.hook_del(hook)
    cases.append(dict(case=label,samples=samples,instructions=instructions[0],graph=m.stats(),faults=m.words()[4],usb_record=bytes(m.u.mem_read(0x200183a0,64)).hex()))
    print(('reference' if a.reference else 'test'),label,'PASS',flush=True)
# Both stock USB ring paths remain stereo, before and after the replacement hook.
left=[.01*(i+1) for i in range(8)];right=[-.015*(i+1) for i in range(8)]
m.host(left,right);m.floats(0x200183a0,left);m.floats(0x200183c0,right);m.run(0x96b8)
assert max(abs(x-y) for x,y in zip(m.read(0x200184a0)+m.read(0x200184c0),left+right))<1e-7
pcm=struct.unpack('<16i',m.u.mem_read(0x2000e8c8,64))
assert max(abs(pcm[2*i]*2**-31-left[i]) for i in range(8))<1e-7
assert max(abs(pcm[2*i+1]*2**-31-right[i]) for i in range(8))<1e-7
m.u.mem_write(0x20012d84+0x54,b'\0\0\1')
data=preset([]);data[3]=65;m.u.mem_write(m.preset,bytes(data))
for i in range(1350):m.process(i,[0.]*8)
media=[]
for i in range(32):
    half=i%2;rx=0x20019000+128*half;tx=0x20019100+128*half
    m.u.mem_write(rx,struct.pack('<32i',*[q for j in range(8) for q in [int(.12*2**31),int(-.07*2**31),0,0]]))
    m.call(0xe19c,[rx,tx]);media+=list(struct.unpack('<32i',m.u.mem_read(tx,128)))
    assert m.read(0x200183a0)+m.read(0x200183c0)==[0.]*16
assert any(media) and not m.words()[4]
result=dict(cases=cases,media=media,model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),baseline_sha256=v.plan.get('baseline_elf_sha256',v.plan['elf_sha256']))
if a.reference:
    (a.output/'audio-reference.json').write_text(json.dumps(result)+'\n')
else:
    expected=json.loads((a.output/'audio-reference.json').read_text());rows=[]
    assert expected['model_sha256']==result['model_sha256'] and expected['baseline_sha256']==result['baseline_sha256']
    for actual,ref in zip(cases,expected['cases']):
        assert actual['case']==ref['case'] and actual['samples']==ref['samples'] and actual['usb_record']==ref['usb_record']
        assert actual['graph']==ref['graph']
        rows.append(dict(case=actual['case'],compared_samples=len(actual['samples']),output_exact=True,USB_record_exact=True,
            baseline_instructions=ref['instructions'],diagnostic_instructions=actual['instructions'],additional_instructions=actual['instructions']-ref['instructions']))
    assert media==expected['media']
    report=dict(status='PASS_OFFLINE_LOOP_GUITAR_AND_MEDIA',elf_sha256=hashlib.sha256((a.output/'build/loop-startup-test.elf').read_bytes()).hexdigest(),
        candidate_payload_sha256=v.plan['candidate_sha256'],cases=rows,stereo_bluetooth_exact=True,stereo_USB_ring_paths=True,
        loop_idle=True,live_sample_rate=48000,callback_frames=8,additional_guitar_buffer_frames=0,
        synthetic_instruction_counts_not_hardware_timing=True,device_access=False,host_audio_access=False)
    (a.output/'audio.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
