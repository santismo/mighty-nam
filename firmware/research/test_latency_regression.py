"""Compare settled baseline builds against NAMLNK15 PCM/sample age, offline only.

Does not model DMA deadlines, physical converter delay or wall-clock CPU time.
No audio APIs, USB, firmware packaging or device writes.
"""
import argparse
import hashlib
import json
import math
import struct
import time
from pathlib import Path
from unicorn import UC_HOOK_CODE
from test_preset_runtime import PresetMachine, build, preset_fixture, v

p = argparse.ArgumentParser(description=__doc__)
for name in ['payload', 'baseline_build', 'candidate_build', 'model', 'report']:
    p.add_argument(name, type=Path)
p.add_argument('--baseline-identity', choices=['NAMLNK10', 'NAMLNK12', 'NAMLNK15'], default='NAMLNK12')
p.add_argument('--candidate-identity', choices=['NAMLNK15', 'NAMLNK16'], default='NAMLNK15')
a = p.parse_args()
started = time.monotonic()
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
objects = ['listening.o', 'irq_timing.o']
if a.baseline_identity == 'NAMLNK12':
    objects.append('a2_lite.o')
for name in objects:
    assert (a.baseline_build / name).read_bytes() == (a.candidate_build / name).read_bytes(), name
stock = a.payload.read_bytes()
references = {}
rows = []
for role, identity, folder in [('baseline', a.baseline_identity, a.baseline_build), ('candidate', a.candidate_identity, a.candidate_build)]:
    elf = folder / 'nam-link-offline.elf'
    bundle = build(stock, elf)
    assert bundle[2]['identity'] == identity
    assert bundle[0][0x11d94:0x11dd8] == stock[0x11d94:0x11dd8]
    v.configure(a.payload, True, candidate_bundle=bundle)
    v.elf_path = elf
    for label, enabled in [('NAM-only', []), ('NAM-and-spring-reverb', [8])]:
        m = PresetMachine(path=a.model)
        data = preset_fixture(enabled, {8: 4})  # Audited stock Spring type.
        data[70:74] = bytes([20, 20, 50, 0])
        m.u.mem_write(m.preset, bytes(data))
        m.arm()
        # Execute actual settling and fade; no timer/state shortcut.
        for block in range(1350):
            m.process(block, [0.] * 8)
        assert m.page(23) == (0, 5)
        assert m.page(24)[1] & 255 == 8
        if 'mpp_fx_active' in v.sym:
            assert m.get(v.sym['mpp_fx_active']) == 0
        calls = []
        hooks = []
        for name, symbol in [('render', 'mpp_listen_render'), ('NAM', 'mpp_stock_amp_process'), ('protect', 'mpp_output_protect')]:
            address = v.sym[symbol] & ~1
            hooks.append(m.u.hook_add(UC_HOOK_CODE, lambda u, pc, size, label: calls.append(label), name, begin=address, end=address))
        samples = []
        for block in range(384):
            previous = m.read(v.sym['mpp_link_output']) + m.read(v.sym['_ZL11chain_right'])
            inputs = [.08 * math.sin((block * 8 + i) * .071) + .023 * math.sin((block * 8 + i) * .193)
                      if block % 97 < 61 else 0. for i in range(8)]
            calls.clear()
            output = m.process(1350 + block, inputs)
            expected = [int(x * 2**28) * 2**-31 for x in previous]
            assert output == expected, (identity, label, block, 'Unexpected sample age')
            assert calls == ['render', 'NAM', 'protect'], calls
            samples.extend(output)
        for hook in hooks:
            m.u.hook_del(hook)
        assert max(map(abs, samples)) > 1e-6
        m.guards()
        if role == 'baseline':
            references[label] = samples
        else:
            assert samples == references[label], (label, 'PCM changed between builds')
        rows.append(dict(role=role, identity=identity, case=label, stock_preset_sha256=hashlib.sha256(data).hexdigest(),
                         warmup_blocks=1350, comparison_blocks=384, frames=3072,
                         PCM_sha256=hashlib.sha256(struct.pack('<%dd' % len(samples), *samples)).hexdigest(),
                         protected_output_age_samples=8, additional_output_queue_samples=0,
                         order=['render-previous', 'process-current-NAM', 'protect-current'],
                         processing_faults=m.words()[4], context_rejections=m.words()[10]))
        print(identity, label, 'PASS: one-block output age; exact PCM comparison', flush=True)
report = dict(status='PASS_OFFLINE_'+a.baseline_identity+'_TO_'+a.candidate_identity.removeprefix('NAMLNK')+'_SAMPLE_AGE', cases=rows,
              baseline_elf_sha256=digest(a.baseline_build / 'nam-link-offline.elf'),
              candidate_elf_sha256=digest(a.candidate_build / 'nam-link-offline.elf'),
              model_sha256=digest(a.model), identical_objects=objects,
              PCM_bit_identical_for_both_cases=True, unchanged_stock_audio_IRQ=True,
              sample_rate_hz=48000, block_samples=8, source_sample_age_ms=8/48,
              physical_latency_measured=False, physical_deadline_proven=False,
              host_audio_access=False, device_access=False, firmware_created=False,
              limits=['Two identical stock-preset fixtures with the same real model; not every preset/model.',
                      'Logical protected-block age excludes codec, DMA release and analog delay.',
                      'Synthetic timing cannot detect hardware deadline misses or establish CPU speed.',
                      'Bit-identical PCM rules out added software sample delay in these fixtures only.'],
              seconds=time.monotonic()-started)
a.report.write_text(json.dumps(report, indent=2)+'\n')
print(report['status'], flush=True)
