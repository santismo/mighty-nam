#!/usr/bin/env python3
"""Bounded compiled ARM mailbox/DSP test. No device or audio access."""
import argparse,json,sys,struct,hashlib
from pathlib import Path
from unicorn import UC_HOOK_CODE
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'hardware'))
from harness import setup
p=argparse.ArgumentParser(description=__doc__)
for n in ['baseline','payload','output','model']:p.add_argument(n,type=Path)
a=p.parse_args();M,v,s,preset,input_block,model_slot=setup(a.baseline,a.payload,a.output)
m=M();m.service();m.upload(model_slot(a.model),800);m.initialize_usb();m.arm()
data=preset([8],{8:4});data[84]=37;data[70:74]=bytes([20,20,50,0]);m.u.mem_write(m.preset,bytes(data))
tick=0;costs={}
def process(count,signal=None,label=None):
    global tick
    maximum=0
    for _ in range(count):
        tick+=1;n=[0]
        hook=m.u.hook_add(UC_HOOK_CODE,lambda *args:n.__setitem__(0,n[0]+1)) if label else None
        try:m.process(tick,input_block(tick) if signal is None else signal)
        finally:
            if hook:m.u.hook_del(hook)
        maximum=max(maximum,n[0]);assert not m.words()[4] and not m.diag()[3]
    if label:costs[label]=maximum
def status():
    error,words=m.loop_request(0,5);assert not error;return words
def command(op,arg,expected=0):
    error,words=m.loop_request(op,arg);assert not error
    process(2,[0.]*8)
    state=status();assert state[3]==0 and state[4]==words[0] and state[5]==expected,state
    return state
process(1350);process(8,label='idle_NAM_spring')
assert bytes(m.u.mem_read(v.sym['mpp_probe_identity'],8))==b'NAMLNK26'
assert status()[6]==40|(50<<8)|(30<<16)
command(2,60);command(3,35);command(4,60)
assert status()[6]==60|(35<<8)|(60<<16)
assert m.loop_request(2,11)[0]==1 and m.loop_request(3,101)[0]==1 and m.loop_request(4,45)[0]==1
command(1,9);command(1,1);process(20,[0.]*8)
assert status()[0]&255==1
command(4,30,2) # Existing recording/rate cannot be overwritten.
process(160,label='record_60s_mode');assert status()[0]&255==2
command(1,2);assert status()[0]&255==3
process(180,label='play_60s_mode')
original_length=status()[1];assert original_length>100
command(1,6);assert status()[0]&(2<<8)
process(240,label='overdub_60s_mode')
assert status()[1]==original_length and m.loop_state(11)>0
command(1,10);assert not status()[0]&(1<<8) and status()[0]&(2<<8)
command(1,8);cursor=status()[2];process(80,[0.]*8,label='paused_partial_commit')
assert status()[2]==cursor and not status()[0]&(4<<8)
command(1,7);process(80,label='resume')
command(1,4);process(80,[0.]*8);assert status()[0]&255==5 and status()[2]==0
command(1,7);process(20);command(1,6);process(17)
command(1,5);assert status()[0]&255==0 and status()[1]==0
assert status()[6]==60|(35<<8)|(60<<16) # Clear retains settings.
command(4,30);command(1,1);process(160);command(1,2);command(1,6)
process(120,label='overdub_30s_mode');command(1,5)
assert status()[1]==0 and m.get(v.sym['mpp_listen_enabled'])==1 and m.diag()[31]==0
# Corrupt a buffer guard: loop is disabled without changing live guitar output.
m.u.mem_write(0x202a0000,b'\0'*4)
for i in range(65):tick+=1;m.process(tick,input_block(tick))
assert m.diag()[3]&4 and m.get(v.sym['mpp_listen_enabled'])==1 and not m.words()[4]
assert m.loop_request(1,1)[0]==3
report=dict(status='PASS_OFFLINE_ARM_LAYERS',elf_sha256=hashlib.sha256((a.output/'build/loop-startup-test.elf').read_bytes()).hexdigest(),
    max_executed_instructions_per_case=costs,callback_frames=8,live_sample_rate=48000,stored_rates=[24000,12000],
    settings_readback=True,clear_while_overdubbing=True,guard_fault_guitar_unchanged=True,
    physical_deadlines_proven=False,device_access=False,host_audio_access=False,flashed=False)
(a.output/'layers-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
