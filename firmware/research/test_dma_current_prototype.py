"""Execute NAMDMP01 startup and DSP offline, against the exact installed19 ELF.

Peripheral/timer models are synthetic. No USB, MIDI, audio API or update file.
The instruction/store trace is ordering evidence, NEVER a CPU-cycle measurement.
"""
import argparse
import hashlib
import json
import math
import struct
import time
from pathlib import Path
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC
from preset_image import build
from test_codec_startup import Startup, EXPECTED
from test_preset_runtime import PresetMachine, preset_fixture, v, model_slot


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fx_pair(m, pair):
    c = [0] * 32
    for index, mode in enumerate(pair):
        at = index * 16
        c[at:at+10] = [mode, 1, index+2, 19 if index == 0 else 5,
                      100, 30, 50, 90, 50, 50]
    request = [240,67,88,112,4,2,78,70,1,1,127,61,0,0]
    request += [(m.words()[5] >> (7*i)) & 127 for i in range(5)] + c + [247]
    assert m.ingress([bytes(request)])[0][0][13] == 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['payload', 'baseline_build', 'candidate_build', 'report']:
        p.add_argument(name, type=Path)
    p.add_argument('--models', nargs=2, type=Path, required=True)
    a = p.parse_args(); start = time.monotonic(); stock = a.payload.read_bytes()
    base_elf = a.baseline_build/'nam-link-offline.elf'
    elf = a.candidate_build/'nam-link-offline.elf'
    assert sha(base_elf.read_bytes()) == '4c058e7d985897a3ef84f78881a98f0fff0aa9ee3d930347d158a3f0421ebbb0'
    baseline = build(stock, base_elf)
    try:
        build(stock, elf)
    except ValueError as e:
        assert 'offline-only' in str(e)
    else:
        raise AssertionError('Default image builder accepted the prototype')
    candidate = build(stock, elf, allow_dma_prototype=True)
    assert candidate[2]['identity'] == 'NAMDMP01'
    unchanged = [x.name for x in a.baseline_build.glob('*.o') if x.name != 'stock_chain_firmware.o']
    for name in unchanged:
        assert (a.baseline_build/name).read_bytes() == (a.candidate_build/name).read_bytes(), name
    # Exact setup on dirty RAM: only TX TCR1 changes. Descriptor storage and
    # every other register transaction, including clocks and RX, stay identical.
    startup = []
    for fill in (0, 165, 255):
        b, c = Startup(*baseline, fill), Startup(*candidate, fill)
        assert b.codec() == c.codec() == EXPECTED
        for boot in ('cold', 'warm'):
            bm, bd = b.audio_setup(); cm, cd = c.audio_setup()
            assert bd == cd and len(bm) == len(cm)
            differences = [(x, y) for x, y in zip(bm, cm) if x != y]
            assert differences == [((0x4040400c, 4, 16), (0x4040400c, 4, 8))], differences
            startup.append(dict(fill=fill, boot=boot, tx_watermark=8,
                                rx_watermark=16, descriptors_identical=True))
    print('startup: six executions; only TX watermark changed', flush=True)
    reference = {}; rows = []; trace = None; total_blocks = 0
    for role, bundle, current_elf in [('baseline', baseline, base_elf), ('prototype', candidate, elf)]:
        v.configure(a.payload, True, candidate_bundle=bundle); v.elf_path = current_elf
        for model_index, model in enumerate(a.models):
            for size in (8, 16, 32):
                m = PresetMachine(path=model)
                m.call(v.sym['mpp_buffer_set'], [size]); m.arm()
                phases = [('NAM', [], {}, None), ('NAM-Spring', [8], {8:4}, None),
                          ('NAM-Delay-Spring', [7,8], {7:1,8:4}, None)]
                if model_index == 0 and size == 8:
                    phases += [('tails-bypassed', [], {7:1,8:4}, None),
                               ('tails-resumed', [7,8], {7:1,8:4}, None),
                               ('full-chain-cut-dualFX', [1,2,4,5,6,7,8,9], {4:4,8:4}, (1,2)),
                               ('reordered-full-chain', [1,2,4,5,6,7,8,9], {4:4,8:4}, (5,6))]
                counter = 0
                for label, enabled, types, pair in phases:
                    data = preset_fixture(enabled, types)
                    data[70:74] = bytes([20,20,50,0])
                    if types.get(4) == 4: data[36:38] = bytes([55,60])
                    if label.startswith('reordered'): data[90:99] = bytes([5,3,1,2,4,9,8,6,7])
                    m.u.mem_write(m.preset, bytes(data))
                    if pair: fx_pair(m, pair)
                    protected = []; pcm = []; order = []; hooks = []
                    for tag, symbol in [('render','mpp_listen_render'), ('NAM','mpp_stock_amp_process'),
                                        ('protect','mpp_output_protect')]:
                        at = v.sym[symbol] & ~1
                        hooks.append(m.u.hook_add(UC_HOOK_CODE, lambda u,pc,n,t: order.append(t), tag, begin=at,end=at))
                    for block in range(1504):
                        inputs = [.08*math.sin((counter*8+i)*.071)+.023*math.sin((counter*8+i)*.193)
                                  if block % 97 < 61 else 0. for i in range(8)]
                        order.clear(); output = m.process(counter, inputs); counter += 1; total_blocks += 1
                        assert order == (['render','NAM','protect'] if role=='baseline' else ['NAM','protect','render']), order
                        protected.append(m.read(v.sym['mpp_link_output']) + m.read(v.sym['_ZL11chain_right']))
                        pcm.append(output)
                        # After real settling/fade, account for queue age in whole blocks.
                        if block >= 1350:
                            age = size//8-1 + int(role=='baseline')
                            expected = [int(x*2**28)*2**-31 for x in protected[block-age]]
                            assert output == expected, (role,model.name,size,label,block,'sample age')
                    for hook in hooks: m.u.hook_del(hook)
                    key = (model_index, size, label)
                    protected_sha = sha(b''.join(struct.pack('<16f',*x) for x in protected))
                    assert max(abs(x) for block in pcm[1350:] for x in block)>1e-8
                    if role == 'baseline': reference[key] = (protected_sha, pcm[1351:])
                    else:
                        prev_hash, shifted = reference[key]
                        assert protected_sha == prev_hash, key
                        assert pcm[1350:-1] == shifted, (key,'PCM not exactly one block earlier')
                        rows.append(dict(model_sha256=sha(model.read_bytes()), buffer=size, case=label,
                                         executed_blocks_per_build=1504, exact_protected_PCM=True,
                                         shifted_comparison_frames=153*8, output_advanced_samples=8,
                                         stock_preset_sha256=sha(data), protected_PCM_sha256=protected_sha))
                    assert m.words()[4] == 0 and m.words()[9] == 1
                    print(role, model.name, size, label, 'PASS', flush=True)
                if role == 'prototype' and model_index == 0 and size == 8:
                    # One actual full-IRQ instruction/store trace; per-instruction
                    # indices give order only. A separate bus model supplies time.
                    events=[]; ins=[0]; calls=[]; hooks=[]
                    def count(u,pc,n,unused): ins[0]+=1
                    def write(u,access,address,n,value,unused):
                        events.append(dict(instruction=ins[0], offset=address-(0x20016900+128*(counter%2)),
                                           bytes=n, value=value, pc=hex(u.reg_read(UC_ARM_REG_PC))))
                    h=m.u.hook_add(UC_HOOK_CODE,count)
                    w=m.u.hook_add(UC_HOOK_MEM_WRITE,write,begin=0x20016900,end=0x200169ff)
                    for name in ['mpp_probe_audio','mpp_listen_render','mpp_output_protect','mpp_driver_capture']:
                        at=v.sym[name]&~1
                        hooks.append(m.u.hook_add(UC_HOOK_CODE,lambda u,pc,n,name:calls.append(dict(name=name,instruction=ins[0],arg0=u.reg_read(UC_ARM_REG_R0))),name,begin=at,end=at))
                    m.process(counter); total_blocks+=1
                    for hook in [h,w,*hooks]: m.u.hook_del(hook)
                    assert len(events)==64 and all(e['value']==0 for e in events[:32])
                    assert sorted(e['offset'] for e in events[32:])==list(range(0,128,4))
                    trace=dict(instructions=ins[0], calls=calls, stores=events,
                               note='Instruction order only; not hardware cycles or store visibility')
    # All guard injection below is inside the CPU model, not the physical plug.
    v.configure(a.payload, True, candidate_bundle=candidate); v.elf_path=elf
    failures=[]
    for kind in ('timer-zero','timer-limit','clock-invalid','nonfinite'):
        m=PresetMachine(path=a.models[0]); m.u.mem_write(m.preset,bytes(preset_fixture([]))); m.arm()
        for i in range(1350): m.process(i,[0.]*8); total_blocks+=1
        calls=[]; at=v.sym['mpp_listen_render']&~1
        m.u.hook_add(UC_HOOK_CODE,lambda *args:calls.append('render'),begin=at,end=at)
        if kind.startswith('timer'): m.timer_ticks=0 if kind=='timer-zero' else 150
        elif kind=='clock-invalid': m.put(0x400ec000,0)
        else:
            at=v.sym['mpp_output_protect']&~1
            m.u.hook_add(UC_HOOK_CODE,lambda u,*args:u.mem_write(v.sym['mpp_link_output'],struct.pack('<f',float('inf'))),begin=at,end=at)
        assert m.process(1400,healthy=False)==[0.]*16 and not calls
        assert m.words()[4]>0 and not m.words()[9]
        failures.append(dict(case=kind, output_zero=True, renderer_not_called=True))
    boots=[]
    for fill in (0,165,255):
        m=PresetMachine(fill=fill,path=a.models[0]); m.arm(); m.process(0)
        assert m.get(v.sym['mpp_driver_state'])==0
        m.restart(); assert m.words()[5:7]==[0,0] and m.page(23)==(0,2)
        m.upload(model_slot(a.models[0]),202); m.arm(); m.process(1); m.guards()
        boots.append(dict(fill=fill,warm_restart=True,reload=True))
    result=dict(status='PASS_OFFLINE_DMA_CURRENT_PROTOTYPE', identity='NAMDMP01',
                elf_sha256=sha(elf.read_bytes()), baseline_elf_sha256=sha(base_elf.read_bytes()),
                unchanged_objects=unchanged, startup=startup, cases=rows, fault_injections=failures,
                cold_and_warm=boots, instruction_store_trace=trace, executed_audio_blocks=total_blocks,
                regions=candidate[2]['elf_regions'], default_image_builder_rejects_prototype=True,
                sample_rate_hz=48000, processing_frames=8, modeled_saving_ms=8/48,
                physical_deadline_proven=False, physical_latency_measured=False,
                device_access=False, host_audio_access=False, flash_container_created=False,
                seconds=time.monotonic()-start)
    a.report.write_text(json.dumps(result,indent=2)+'\n'); print(result['status'],flush=True)


if __name__=='__main__': main()
