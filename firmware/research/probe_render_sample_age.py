"""Check exact NAMLNK19 output-staging sample age in ARM emulation only.

This isolates the renderer after settling; it does not measure ADC/DAC, DMA,
NAM/effect response, or physical latency. No device or host audio access.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from test_preset_runtime import PresetMachine, build, v


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['payload', 'elf', 'model', 'report']:
        p.add_argument(name, type=Path)
    a = p.parse_args()
    bundle = build(a.payload.read_bytes(), a.elf)
    assert bundle[2]['identity'] == 'NAMLNK19'
    v.configure(a.payload, True, candidate_bundle=bundle)
    v.elf_path = a.elf
    m = PresetMachine(path=a.model)
    left, right, tx = v.sym['mpp_link_output'], v.sym['_ZL11chain_right'], 0x20016900
    rows = []
    for size in [8, 16, 32]:
        m.call(v.sym['mpp_buffer_set'], [size])
        m.arm()
        # Isolate settled rendering; real settling is covered by full-IRQ tests.
        m.put(v.sym['mpp_listen_warm'], 0)
        out_l, out_r = [], []
        for block in range(140):
            l, r = [0.] * 8, [0.] * 8
            if block == 132:
                l[0], r[0] = .25, -.125
            m.floats(left, l)
            m.floats(right, r)
            m.u.mem_write(tx, bytes(128))
            m.call(v.sym['mpp_listen_render'], [left, right, tx])
            words = struct.unpack('<32i', m.u.mem_read(tx, 128))
            assert words[0::4] == words[2::4] and words[1::4] == words[3::4]
            out_l.extend(words[0::4])
            out_r.extend(words[1::4])
        expected_at = 132 * 8 + size - 8
        assert [(i, x) for i, x in enumerate(out_l) if x] == [(expected_at, 1 << 26)]
        assert [(i, x) for i, x in enumerate(out_r) if x] == [(expected_at, -(1 << 25))]
        m.guards()
        rows.append(dict(setting_samples=size, input_impulse_frame=132*8,
                         output_impulse_frame=expected_at, extra_frames=size-8,
                         extra_ms_at_48k=(size-8)/48, stereo_pcm_exact=True))
    result = dict(status='PASS_NAMLNK19_EXACT_RENDER_QUEUE_AGE', cases=rows,
                  elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),
                  rendered_frames=3*140*8, guard_checks_passed=True,
                  device_access=False, host_audio_access=False, firmware_created=False,
                  physical_latency_measured=False,
                  limits=['Renderer isolated after settling, with synthetic impulse input.',
                          'Excludes the existing protected prior block and all analog/DMA latency.'])
    a.report.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
