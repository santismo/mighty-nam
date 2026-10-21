"""Test the compiled, non-installable tail-sleep prototype in the ARM harness.

Full IRQ, NAM, dispatcher, stock loaders and output protection execute. The
DMA/timer peripherals remain virtual. No physical writes or host audio APIs.
"""
import argparse, hashlib, json, struct, time
from pathlib import Path
from collections import Counter
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R6
from test_preset_runtime import PresetMachine, build, preset_fixture, v


class ProfileMachine(PresetMachine):
    audio_scope=False
    def run(self,pc,*args,**kwargs):
        old=self.audio_scope;self.audio_scope=pc==0x205a4
        try:return super().run(pc,*args,**kwargs)
        finally:self.audio_scope=old


def exercise(payload,elf,model,experiment):
    v.configure(payload,True,candidate_bundle=build(payload.read_bytes(),elf));v.elf_path=elf
    m=ProfileMachine(path=model);m.arm();data=preset_fixture([7,8],{7:2,8:4})
    data[61:65]=bytes([30,30,10,0]);data[70:74]=bytes([25,25,40,0])
    count=0;rows=[];active=[]
    def segment(name,blocks,check_counts=False):
        nonlocal count
        m.u.mem_write(m.preset,bytes(data));peak=0.
        for i in range(blocks):
            y=m.process(count);count+=1;peak=max(peak,max(map(abs,y)))
            if name=='initial-active' and i>=1200:active.extend(y)
        holds=list(struct.unpack('<11H',m.u.mem_read(v.sym['mpp_bypass_hold'],22)))
        row=dict(case=name,blocks=blocks,peak=peak,holds=holds)
        if check_counts:
            calls=Counter();events=[0]
            def callback(u,pc,size,_):
                stage=u.mem_read(m.preset+100-u.reg_read(UC_ARM_REG_R6),1)[0];calls[stage]+=1
            h=m.u.hook_add(UC_HOOK_CODE,callback,begin=0x1230c,end=0x1230c)
            def event(u,pc,size,_):
                if m.audio_scope:events[0]+=1
            e=m.u.hook_add(UC_HOOK_CODE,event)
            for i in range(8):m.process(count);count+=1
            m.u.hook_del(e);m.u.hook_del(h)
            row.update(callback_counts=dict(calls),irq_instruction_events=events[0],observed_blocks=8)
            for stage in (7,8):
                if data[stage]&64:assert calls[stage]==(0 if experiment else 8),(name,calls)
                else:assert calls[stage]==8
        assert not m.words()[4];m.guards();rows.append(row)
        print(('experiment' if experiment else 'baseline'),name,flush=True)
    segment('initial-active',1500)
    data[7]|=64;segment('NAM-plus-spring-after-delay',1400,True)
    data[8]|=64;segment('NAM-only-after-both',1400,True)
    data[7]=64|5;data[8]=64|6;segment('type-changes-while-asleep',32,True)
    data[7]&=63;data[8]&=63;segment('wake-new-types',1500,True)
    assert bytes(m.u.mem_read(0x20003a08,2))==bytes([5,5])
    assert bytes(m.u.mem_read(0x200041d8,2))==bytes([6,6])
    # Repeated transitions never confuse fresh/sleep/keepalive sentinel states.
    for i in range(16):
        for stage in (7,8):data[stage]^=64
        m.u.mem_write(m.preset,bytes(data))
        for j in range(4):m.process(count);count+=1
    data[7]|=64;data[8]|=64;segment('after-rapid-switches',1400,True)
    return rows,active


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['payload','baseline','experiment','model','report']:p.add_argument(name,type=Path)
    a=p.parse_args();started=time.monotonic()
    assert json.loads((a.experiment.parent/'build.json').read_text())['status']=='OFFLINE_EXPERIMENT_NOT_INSTALLABLE'
    before,old=exercise(a.payload,a.baseline,a.model,False)
    after,new=exercise(a.payload,a.experiment,a.model,True)
    assert old==new and max(map(abs,new))>1e-6,'Active PCM changed or comparison vacuous'
    rows=[]
    for x,y in zip(before,after):
        row=dict(case=x['case'],baseline=x,experiment=y)
        if 'irq_instruction_events' in x:
            row['instruction_event_reduction_percent']=100*(x['irq_instruction_events']-y['irq_instruction_events'])/x['irq_instruction_events']
        rows.append(row)
    report=dict(status='PASS_OFFLINE_COMPILED_TAIL_SLEEP',cases=rows,
        active_pcm_bit_identical=True,active_compared_frames=len(new)//2,
        baseline_elf_sha256=hashlib.sha256(a.baseline.read_bytes()).hexdigest(),
        experimental_elf_sha256=hashlib.sha256(a.experiment.read_bytes()).hexdigest(),
        stock_sha256=hashlib.sha256(a.payload.read_bytes()).hexdigest(),
        model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),
        seconds=time.monotonic()-started,device_access=False,host_audio_access=False,
        limits=['Instruction events are not CPU cycles or latency measurements.',
            'This compiled chain fixture covers digital delay/spring and waking pan delay/damp only.',
            'Intentional hard-bypass/reset behavior removes stock residuals; no preserved spillover claim.',
            'No electrical FIFO deadline, real foreground loading cost, listening or restart validation.',
            'Research ELF retains baseline identity only for harness compatibility; never install.'])
    a.report.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])


if __name__=='__main__':main()
