"""Offline instruction/callback audit of minimal chains and bypass history.
Counts are emulator instruction events, not physical cycles or latency.
No USB, host audio, flash-container creation or firmware installation.
"""
import argparse,collections,hashlib,json,struct,time
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R6
from test_preset_runtime import PresetMachine,build,v,preset_fixture

p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','elf','model','report']:
    p.add_argument(name,type=Path)
a=p.parse_args();started=time.monotonic()
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf));v.elf_path=a.elf

class ProfileMachine(PresetMachine):
    entry=0
    def run(self,pc,*args,**kwargs):
        previous=self.entry;self.entry=pc
        try:return super().run(pc,*args,**kwargs)
        finally:self.entry=previous

m=ProfileMachine(path=a.model);m.arm();counter=0;rows=[]
def set_chain(enabled):
    global counter
    data=preset_fixture(enabled,{8:4});data[70:74]=bytes([20,20,50,0])
    m.u.mem_write(m.preset,bytes(data))
    for _ in range(1350):m.process(counter);counter+=1
    assert m.page(23)==(0,5) and m.page(24)[1]&255==8

def measure(label):
    global counter
    counts=collections.Counter();dispatch=collections.Counter();callbacks=collections.Counter();per=[];pcm=[]
    entries={v.sym[s]&~1:s for s in ['mpp_stock_amp_process','mpp_listen_render','mpp_output_protect','mpp_fast_dispatch']}
    for name in ['mpp_fx_before','mpp_tuner_feed']:
        if name in v.sym:entries[v.sym[name]&~1]=name
    def observe(u,pc,size,unused):
        if m.entry!=0x205a4:return
        counts['IRQ_instruction_events']+=1
        if pc in entries:counts[entries[pc]]+=1
        if pc==(v.sym['mpp_fast_dispatch']&~1) or pc==0x1230c:
            remaining=u.reg_read(UC_ARM_REG_R6)
            assert 1<=remaining<=11
            stage=u.mem_read(m.preset+100-remaining,1)[0]
            assert stage<=10
            (dispatch if pc!=0x1230c else callbacks)[stage]+=1
    hook=m.u.hook_add(UC_HOOK_CODE,observe)
    try:
        for _ in range(8):
            before=counts['IRQ_instruction_events'];pcm.extend(m.process(counter));counter+=1
            per.append(counts['IRQ_instruction_events']-before)
    finally:m.u.hook_del(hook)
    m.guards()
    row=dict(case=label,observed_blocks=8,instruction_events_per_IRQ=per,
        calls=dict(counts),dispatches_by_stage=dict(dispatch),callbacks_by_stage=dict(callbacks),
        bypass_hold=list(struct.unpack('<11H',m.u.mem_read(v.sym['mpp_bypass_hold'],22))),
        controls=list(m.u.mem_read(m.preset,11)),faults=m.words()[4],
        PCM_sha256=hashlib.sha256(struct.pack('<%dd'%len(pcm),*pcm)).hexdigest())
    rows.append(row);print(json.dumps(row),flush=True)

set_chain([]);measure('fresh-NAM-only')
set_chain([8]);measure('NAM-and-spring')
# Gate/delay/reverb become active before returning to the minimal chain.
# Their stock residual policy is stateful even when the UI shows bypass.
set_chain([5,7,8]);measure('gate-delay-spring-active')
set_chain([8]);measure('NAM-and-spring-after-bypassing-gate-delay')
set_chain([]);measure('NAM-only-after-bypassing-used-tails')
result=dict(status='PASS_OFFLINE_MINIMAL_CHAIN_PROFILE',identity=v.plan['identity'],
    elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),
    model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),cases=rows,
    metric='Emulator instruction events, not M7 cycles, CPU percentage or headphone latency',
    physical_timing_measured=False,hardware_deadline_proven=False,host_audio_access=False,
    device_access=False,firmware_created=False,seconds=time.monotonic()-started,
    limits=['Short windows do not establish worst-case execution cost.',
            'Synthetic timer, no target caches, bus contention or interrupt preemption.',
            'Used gate/delay/reverb continue stock residual/tail callbacks; counts alone do not justify truncating them.'])
a.report.write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],flush=True)
