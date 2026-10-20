"""Offline old/new output ordering comparison. No hardware or audio APIs."""
import argparse, hashlib, json, math, struct, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'outputs/mighty-plug-nam/research'))
from test_link_listening import ListeningMachine, v, build, preset_fixture, Engine, library
from unicorn import UC_HOOK_CODE

p = argparse.ArgumentParser()
p.add_argument('elf', type=Path)
p.add_argument('mode', choices=['current', 'previous'])
p.add_argument('report', type=Path)
a = p.parse_args()
started = time.monotonic()
payload = ROOT / 'work/firmware/decoded/MP3_V1.5.6.payload'
v.configure(payload, True, candidate_bundle=build(payload.read_bytes(), a.elf, 'NAMLNK07'))
lib = library(ROOT / 'work/nam-chain/liba2-reference-order.dylib')
rows = []
for model in [ROOT / 'work/a2-models/marshall-lite.nam',
              ROOT / 'work/nam-listening/fender/fender-super-reverb-lite.nam']:
    m = ListeningMachine(model, boundary_oracle=Engine(lib, model))
    m.u.mem_write(m.preset, bytes(preset_fixture()))
    assert m.page(23)[1] & 1 == 0
    for i in range(2):
        assert m.process(i) == [0.] * 16
    names = {v.sym['mpp_listen_render'] & ~1: 'render',
             v.sym['mpp_stock_amp_process'] & ~1: 'NAM',
             v.sym['mpp_output_protect'] & ~1: 'protect'}
    trace = []
    for pc in names:
        m.u.hook_add(UC_HOOK_CODE, lambda u, pc, size, _: trace.append(names[pc]),
                     begin=pc, end=pc)
    left, right = v.sym['mpp_link_output'], v.sym['_ZL11chain_right']
    ramp = v.sym['_ZL4ramp']
    m.arm()
    # Establish preset tracking, then exercise steady-state output without a
    # 200 ms wait. This is explicitly an offline fixture, not a startup test.
    m.process(2)
    m.put(v.sym['mpp_listen_warm'], 0)
    m.put(ramp, 1024)
    peak = 0.
    for i in range(3, 259):
        previous = m.read(left) + m.read(right)
        trace.clear()
        inputs = [.08 * math.sin((i * 8 + j) * .029)
                  + .013 * math.sin((i * 8 + j) * .101) for j in range(8)]
        actual = m.process(i, inputs)
        current = m.read(left) + m.read(right)
        source = previous if a.mode == 'previous' else current
        expected = [int(x * 2**28) * 2**-31 for x in source]
        assert actual == expected, (model.name, i, actual, expected)
        expected_order = ['render', 'NAM', 'protect'] if a.mode == 'previous' else ['NAM', 'protect', 'render']
        assert trace == expected_order, trace
        peak = max(peak, *map(abs, actual))
    assert peak > 1e-8
    # New output must not replay a queued audible block after explicit mute,
    # a preset transition, or a fault. Test both alternating DMA halves.
    m.arm(False)
    for i in [259, 260]: assert m.process(i) == [0.] * 16
    m.arm(); m.put(v.sym['mpp_listen_warm'], 0); m.put(ramp, 1024)
    m.process(261)
    m.u.mem_write(m.preset + 3, b'\x41')
    for i in [262, 263]: assert m.process(i) == [0.] * 16
    m.put(v.sym['mpp_listen_warm'], 0); m.put(ramp, 1024)
    m.process(264)
    m.timer_ticks = 150
    assert m.process(265, healthy=False) == [0.] * 16
    assert m.page(23) == (0, 2) and m.words()[4] == 1
    assert m.process(266, healthy=False) == [0.] * 16
    rows.append(dict(model=model.name, steady_blocks=256, peak=peak,
                     NAM_reference_max_error=m.max_boundary_error,
                     NAM_reference_samples=m.boundary_samples,
                     ordering=expected_order, mute_transition_fault_clear=True))
    print(json.dumps(rows[-1]), flush=True)

report = dict(status='PASS_OFFLINE_OUTPUT_PIPELINE_COMPARISON', mode=a.mode,
              elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(), cases=rows,
              seconds=time.monotonic()-started, physical_device_access=False,
              host_audio_access=False, flashed=False,
              limits=['Steady-state fixture skips startup settling/ramp duration',
                      'Synthetic timer and DMA memory; real output deadline not modeled',
                      'Ordering difference is established, audible fix is not'])
a.report.write_text(json.dumps(report, indent=2)+'\n')
print(report['status'], flush=True)
