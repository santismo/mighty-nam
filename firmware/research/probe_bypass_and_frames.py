"""Offline stock-callback tail/wake and four-frame boundary experiments.

Runs actual initialized stock callbacks at their normal eight-frame ABI. The
last four output samples are tagged to detect why a four-frame DMA change
alone is unsafe. Tail experiments bypass NAM and operate on isolated effects;
they are not CPU benchmarks, listening tests or release changes.
"""
import argparse, hashlib, json, math, struct, time
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R6, UC_ARM_REG_R12
from test_preset_runtime import PresetMachine, build, preset_fixture, v

p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','elf','model','report']: p.add_argument(name,type=Path)
a=p.parse_args(); started=time.monotonic()
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf));v.elf_path=a.elf
L,R,OL,OR=0x20032000,0x20032040,0x20032080,0x200320c0

def machine():
    m=PresetMachine(path=a.model);m.arm();callbacks={}
    data=preset_fixture([1,2,4,5,6,7,8,9],{7:1,8:4});data[3]|=64
    data[61:65]=bytes([50,40,60,0]);data[70:74]=bytes([40,40,50,0])
    m.u.mem_write(m.preset,bytes(data))
    def trace(u,pc,size,unused):
        remaining=u.reg_read(UC_ARM_REG_R6); stage=u.mem_read(m.preset+100-remaining,1)[0]
        callbacks[stage]=u.reg_read(UC_ARM_REG_R12)
    h=m.u.hook_add(UC_HOOK_CODE,trace,begin=0x1230c,end=0x1230c)
    for i in range(2):m.process(i,[0.]*8)
    m.u.hook_del(h)
    assert all(k in callbacks for k in (1,2,4,5,6,7,8,9)), callbacks
    return m,callbacks,data

def run(m,callback,xs):
    m.floats(L,xs);m.floats(R,xs)
    m.floats(OL,[1234.5]*8);m.floats(OR,[-1234.5]*8)
    m.call(callback,[L,R,OL,OR]);ys=m.read(OL)+m.read(OR)
    assert all(math.isfinite(x) for x in ys)
    return ys

def snapshot(m):
    return m.u.context_save(), [(base,bytes(m.u.mem_read(base,size))) for base,size in
           [(0x20000000,0x40000),(0x20200000,0x40000),(0x20240000,0x80000),(0x202c0000,0x80000)]]

def restore(m,saved):
    context,ram=saved
    for base,blob in ram:m.u.mem_write(base,blob)
    m.u.context_restore(context)

m,callbacks,data=machine();frames=[]
for stage in (1,2,4,5,6,7,8,9):
    ys=run(m,callbacks[stage],[.1+.001*i for i in range(8)])
    changed=sum(x!=1234.5 for x in ys[4:8])+sum(x!=-1234.5 for x in ys[12:16])
    assert changed==8,(stage,ys)
    frames.append(dict(stage=stage,callback=hex(callbacks[stage]),writes_past_four_frames=changed))
print('PASS: eight stock stages overwrite samples 5–8; DMA-only four-frame change is unsafe',flush=True)

rows=[]
for stage in (5,7,8):
    m,callbacks,data=machine();callback=callbacks[stage]
    def sine(block):return [.12*math.sin(2*math.pi*110*(block*8+i)/48000) for i in range(8)]
    # Fill actual delay/reverb history for one second at the normal eight-frame cadence.
    active_difference=0.
    for i in range(6000):
        xs=sine(i);ys=run(m,callback,xs)
        quantized=list(struct.unpack('<8f',struct.pack('<8f',*xs)))
        active_difference=max(active_difference,max(abs(y-x) for y,x in zip(ys,quantized*2)))
    if stage in (7,8): assert active_difference>1e-5, ('Effect was not active',stage)
    data[stage]|=64;m.u.mem_write(m.preset,bytes(data))
    windows=[];peak=energy=0.;exact=0
    for i in range(30000):
        xs=sine(i+6000) if i<6000 else [0.]*8
        ys=run(m,callback,xs)
        quantized=list(struct.unpack('<8f',struct.pack('<8f',*xs)))
        difference=[y-x for y,x in zip(ys,quantized*2)]
        peak=max(peak,max(map(abs,difference)));energy+=sum(x*x for x in difference)
        if not any(difference):exact+=1
        if (i+1)%6000==0:
            windows.append(dict(second=(i+1)//6000,input='guitar-like' if i<6000 else 'silence',
                                peak_residual=peak,rms_residual=math.sqrt(energy/(6000*16)),exact_dry_blocks=exact))
            peak=energy=0.;exact=0
        if i==1199:early=snapshot(m)
    # Compare wake with and without keeping the bypassed callback alive during
    # a further one-second guitar burst. Frozen state is a simulation of sleep.
    late=snapshot(m)
    for i in range(6000):run(m,callback,sine(i))
    data[stage]&=63;m.u.mem_write(m.preset,bytes(data));reference=[]
    for i in range(600):reference+=run(m,callback,[0.]*8)
    restore(m,late);m.u.mem_write(m.preset,bytes(data));frozen=[]
    for i in range(600):frozen+=run(m,callback,[0.]*8)
    difference=max(abs(x-y) for x,y in zip(reference,frozen));m.guards()
    restore(m,early);m.u.mem_write(m.preset,bytes(data));early_wake=[]
    for i in range(600):early_wake+=run(m,callback,[0.]*8)
    early_difference=max(abs(x-y) for x,y in zip(reference,early_wake));m.guards()
    rows.append(dict(stage=stage,active_peak_difference=active_difference,bypassed_seconds=5,windows=windows,
                     naive_sleep_wake_max_difference=difference,
                     continuously_processed_wake_peak=max(map(abs,reference)),frozen_wake_peak=max(map(abs,frozen)),
                     sleep_after_200ms_wake_difference=early_difference,sleep_after_200ms_wake_peak=max(map(abs,early_wake))))
    print(json.dumps(rows[-1]),flush=True)

report=dict(status='PASS_OFFLINE_BYPASS_AND_FRAME_BOUNDARIES',identity=v.plan['identity'],
            elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),fixed_eight_frame_callbacks=frames,
            bypass_history=rows,firmware_policy_changed=False,four_frame_firmware_created=False,
            device_access=False,host_audio_access=False,seconds=time.monotonic()-started,
            limits=['Isolated stock gate, digital delay and spring fixtures only; not every type or setting.',
                    'Skipping callbacks freezes delay/envelope state; output similarity on quiet input does not prove safe reactivation.',
                    'Four frames also requires changes to DMA halves, IRQ, conversion, custom DSP, tuner and protection.',
                    'No physical deadlines, true end-to-end latency, clicks or listening quality measured.'])
a.report.write_text(json.dumps(report,indent=2)+'\n')
