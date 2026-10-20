#!/usr/bin/env python3
"""Offline reproductions of the first physical diagnostic's two defects.

Uses original stock ring assembly, software timer service and power-button
decision code. ADC/LED and USB transmission are intercepted by ProbeMachine.
No physical device access, updater or audio playback.
"""
import argparse, hashlib, json
from pathlib import Path
import candidate_vm as v
from stock_probe_image import build
from test_stock_probe import ProbeMachine

def run(payload, elf, fixed):
    v.configure(payload, True, candidate_bundle=build(payload.read_bytes(), elf))
    m = ProbeMachine(0)
    version = m.ingress([bytes.fromhex('f0435800f7')])
    page = m.ingress([bytes.fromhex('f043587004024e5000f7')])
    assert m.ingress_lengths[-2:] == [4, 9]
    if fixed:
        assert len(version) == len(page) == 1
        assert version[0][0][4:12] == b'NAMPB002'
    else:
        assert not version and not page

    # The real foreground button decision reads these stock-owned fields.
    buttons = 0x2000597c
    info = m.get(0x20005ad8)
    assert 0x20000000 <= info < 0x20040000
    m.u.mem_write(buttons, bytes(0x5c))
    for i in range(5):
        m.put(buttons + 0x44 + i * 4, 0xf)
    m.u.mem_write(buttons + 3, b'\x01')  # POWER is already debounced as held.
    m.put(buttons + 0x50, 0)             # POWER's active-low history.
    m.put(buttons + 0x58, 1)             # A fresh long press is armed.
    m.put(0x200147cc, 0)                 # Start the six-block timer divider.
    m.u.mem_write(info + 0x1e, b'\x00')  # No pending power-off request.
    m.put(0x200147cc + 0x2c, 48000)
    m.call(0x11f7c, [])
    assert m.u.mem_read(info + 0x1e, 1) == b'\x00'

    milestones = []
    # 8 frames/block, 48 frames per stock button-timer tick. This is synthetic
    # callback advancement, not measured hardware time or interrupt scheduling.
    for block in range(9006):
        half = block % 2
        tx = 0x20016900 + 128 * half
        m.u.mem_write(tx, b'\xa5' * 128)
        m.call(v.sym['mpp_probe_audio'], [0x20016800 + 128 * half, tx])
        assert m.u.mem_read(tx, 128) == bytes(128)
        if block + 1 in [6, 9000, 9006]:
            m.call(0x11f7c, [])
            milestones.append({
                'callbacks': block + 1,
                'power_hold_ticks': m.get(buttons + 0x28),
                'power_off_request': m.u.mem_read(info + 0x1e, 1)[0],
                'service_countdown': m.get(0x200147cc + 0x2c),
            })
    assert m.words()[3] == 9006 and m.words()[4] == 0
    if fixed:
        assert [x['power_hold_ticks'] for x in milestones] == [1, 1500, 1501]
        assert [x['power_off_request'] for x in milestones] == [0, 0, 1]
        assert milestones[-1]['service_countdown'] == 0
    else:
        assert all(x['power_hold_ticks'] == x['power_off_request'] == 0 for x in milestones)
        assert milestones[-1]['service_countdown'] == 48000
    m.guards()
    return {
        'elf_sha256': hashlib.sha256(elf.read_bytes()).hexdigest(),
        'version_replies': len(version), 'extension_replies': len(page),
        'ingress_length_arguments': m.ingress_lengths[-2:],
        'power_hold_milestones': milestones,
        'zeroed_blocks': m.words()[3], 'rejected_buffers': m.words()[4],
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('payload', type=Path)
    p.add_argument('failed_elf', type=Path)
    p.add_argument('repaired_elf', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert hashlib.sha256(a.failed_elf.read_bytes()).hexdigest() == '089a56a88a7409a0f8e486ff078c5d023d36fbe7516993e1ae318a0b7f335bdb'
    rows = {}
    for name, elf, fixed in [('failed_NAMPB001', a.failed_elf, False), ('repaired_NAMPB002', a.repaired_elf, True)]:
        rows[name] = run(a.payload, elf, fixed)
        print(json.dumps({'completed': name, **rows[name]}), flush=True)
    report = {
        'status': 'PASS_REPRODUCED_TWO_DEFECTS_AND_OFFLINE_REPAIRS',
        'cases': rows, 'physical_device_access': False, 'audio_playback': False,
        'findings': [
            'The old handlers reject real ingress length arguments 4/9; the repaired handlers reply.',
            'The old silent callback omits stock service 0x15638. POWER hold time and service countdowns do not advance.',
            'The repaired callback preserves that stock service. The original POWER decision sets its shutdown-request flag at 1501 timer ticks.',
        ],
        'limits': [
            'No physical installation or execution of NAMPB002. This is a causal CPU-level reproduction, not a measured trace of the failed unit.',
            'ADC, LED and USB transmitter hardware helpers are intercepted. No real button electrical state, audio DMA, cache, clock or bus timing is modeled.',
            'The test stops at the original power-off request flag; it does not execute power-rail shutdown.',
            'Other consequences of replacing the complete stock audio callback still require review.',
        ],
    }
    a.output.write_text(json.dumps(report, indent=2) + '\n')

if __name__ == '__main__':
    main()
