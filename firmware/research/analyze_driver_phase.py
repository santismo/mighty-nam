"""Offline NAMLNK19 phase screen from recorded physical observations.

No MIDI, audio, firmware packaging or device writes. The event model assumes
instantaneous DMA and atomic serial words. Its hypothetical completion time is
the measured whole-IRQ duration, not a measured current-block publication time.
It must not be used to authorize a shorter output handoff on hardware.
"""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

from audit_audio_scheduling import simulate
from decode_driver_timing import decode


def period_pair(a, b):
    """Estimate cycles/IRQ from sparse same-epoch samples; assume < one wrap."""
    if not all(p['counter_valid'] for p in (a, b)):
        raise ValueError('Invalid counter bracket')
    if a['epoch_before'] != b['epoch_before'] or a['ctrl_before'] != b['ctrl_before']:
        raise ValueError('Counter epoch/control changed')
    cycles = (b['cycles_before'] - a['cycles_before']) & 0xffffffff
    seq = (b['irq_sequence'] - a['irq_sequence']) & 0xffffffff
    if not (0 < cycles < 0x80000000 and 0 < seq < 0x80000000 and seq % 2 == 0):
        raise ValueError('Ambiguous interval or IRQ sequence')
    return cycles / (seq // 2)


def phase_states(rx_start, entry_lag=0, publication_lag=1):
    """Integer-word phase fit, with the stock 16/16/16 FIFO/burst settings."""
    tx, rx, tc, rc = 32, 0, 32, 0
    states, irqs = {}, []
    for tick in range(1, 1025):
        tx -= 1
        if tx <= 16:
            tx += 16
            tc = (tc + 16) % 64
        if tick > rx_start:
            rx += 1
        if rx > 16:
            rx -= 16
            rc = (rc + 16) % 64
            if rc % 32 == 0:
                irqs.append((tick, (rc - 32) % 64))
        states[tick] = (tx, rx, tc, rc)
    pairs = []
    for tick, half in irqs:
        entry, publication = tick + entry_lag, tick + entry_lag + publication_lag
        if 128 < tick and publication < 1000:
            pairs.append((half, states[entry], states[publication]))
    return pairs


def fits_recorded_phase(rx_start, lag):
    pairs = phase_states(rx_start, lag)
    return bool(pairs) and all(
        entry[:2] == (30, 1) and publication[:2] == (29, 2)
        and entry[2] == publication[2] == half
        and entry[3] == publication[3] == (half + 32) % 64
        for half, entry, publication in pairs)


def self_test():
    a = dict(counter_valid=True, epoch_before=1, ctrl_before=1,
             cycles_before=0xfffffff0, irq_sequence=0xfffffff1)
    b = dict(a, cycles_before=84, irq_sequence=5)
    assert period_pair(a, b) == 10  # Counter and sequence wrap.
    negatives = [dict(b, epoch_before=2), dict(b, ctrl_before=3),
                 dict(b, counter_valid=False), dict(b, irq_sequence=4),
                 dict(b, irq_sequence=a['irq_sequence']),
                 dict(b, cycles_before=a['cycles_before'])]
    for invalid in negatives:
        try:
            period_pair(a, invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid interval accepted')
    fits = [(p, lag) for p in range(64) for lag in range(4) if fits_recorded_phase(p, lag)]
    assert fits == [(1, 0)]
    # At a coincident TX read, publication is conservatively too late.
    safe = simulate(16, 16, 16, 13, previous_block=False, rx_start_words=1)
    late = simulate(16, 16, 16, 14, previous_block=False, rx_start_words=1)
    assert safe['sequence_discontinuities'] == 0 and late['sequence_discontinuities'] > 0
    return dict(period_wrap=True, invalid_intervals_rejected=len(negatives),
                discrete_phase_candidates_checked=256, deadline_boundary_rejected=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['physical_raw', 'startup_audit', 'report']:
        p.add_argument(name, type=Path)
    a = p.parse_args()
    checks = self_test()
    rows = json.loads(a.physical_raw.read_text())
    setup = json.loads(a.startup_audit.read_text())['actual_setup']
    assert setup['serial_words_per_frame'] == 4 and setup['frames_per_interrupt'] == 8
    assert setup['rx_fifo_watermark'] == setup['tx_fifo_watermark'] == 16
    assert all(d['burst_bytes'] == 64 and d['iterations'] == 2 for d in setup['descriptors'])
    cases, period_estimates, captured = [], [], []
    for row in rows:
        frames = []
        for raw in row['driver_captures']:
            assert raw['status'] == 'DIAGNOSTIC_READ_COMPLETE' and raw['version'] == 'NAMLNK19'
            c = decode(raw['words'])
            assert c['counter_span_valid']
            e, u = c['entry'], c['publication']
            half = u['published_tx_half']
            assert half in (0x20016900, 0x20016980)
            for ph, fifo in [(e, (30, 1)), (u, (29, 2))]:
                assert not ph['dma_changed_during_reads']
                assert (ph['tx_fifo_occupancy'], ph['rx_fifo_occupancy']) == fifo
                assert ph['tx_source_before'] == half
                assert ph['rx_destination_before'] == (half - 0x100) ^ 0x80
                assert ph['rx_doff_citer_before'] >> 16 == 2
                assert ph['tx_doff_citer_before'] >> 16 == 2
                assert all(not ph[side + suffix] for side in ['tx', 'rx']
                           for suffix in ['_fifo_error', '_sync_error'])
            frames.append(c)
        rates = [period_pair(x['entry'], y['entry']) for x, y in zip(frames, frames[1:])]
        period_estimates += rates
        period = statistics.median(rates)
        irq = row['irq_snapshots']
        assert all(t['usable'] and not t['flags'] and not t['rejected'] for t in irq)
        durations = [t['lastCycles'] for t in irq]
        cases.append(dict(case=row['case'], period_pairs=len(rates),
                          estimated_cycles_per_irq_period=period,
                          median_irq_cycles=statistics.median(durations),
                          max_observed_irq_cycles=max(durations),
                          median_irq_fraction_of_period=statistics.median(durations)/period,
                          max_irq_fraction_of_period=max(durations)/period,
                          whole_irq_proxy_in_serial_word_times=max(durations)/period*32,
                          publication_fraction_of_period_max=max(
                              c['entry_to_publication_cycles'] for c in frames)/period))
        captured += frames
    matches = [dict(rx_start_words=phase, entry_lag_words=lag)
               for phase in range(64) for lag in range(4) if fits_recorded_phase(phase, lag)]
    assert matches == [dict(rx_start_words=1, entry_lag_words=0)]
    candidates = []
    for watermark in [16, 12, 8, 4, 0]:
        current = simulate(16, 16, watermark, 1, previous_block=True, rx_start_words=1)
        candidate = dict(tx_watermark=watermark, fifo_reserve_words_at_request=watermark,
                         protected_output_model=current, cases=[])
        for case in cases:
            # Round up to the next serial-word tick and add explicit jitter.
            proxy = math.ceil(case['whole_irq_proxy_in_serial_word_times'])
            for jitter in [0, 2, 4, 8]:
                model = simulate(16, 16, watermark, proxy+jitter,
                                 previous_block=False, rx_start_words=1)
                candidate['cases'].append(dict(case=case['case'],
                    whole_irq_proxy_words=proxy, extra_jitter_words=jitter, model=model))
        candidates.append(candidate)
    result = dict(status='PASS_OFFLINE_RECORDED_PHASE_SCREEN', tests=checks,
        input_sha256={key:hashlib.sha256(getattr(a,key).read_bytes()).hexdigest()
                      for key in ['physical_raw','startup_audit']},
        physical_snapshots=len(captured), same_epoch_period_pairs=len(period_estimates),
        estimated_cycles_per_irq_period=dict(min=min(period_estimates),
            median=statistics.median(period_estimates), max=max(period_estimates)),
        counter_to_wall_clock_calibrated=False, cases=cases,
        discrete_phase_matches=matches, candidate_screens=candidates,
        buffer_settings=[dict(setting_samples=n, extra_samples=n-8,
            extra_ms=(n-8)/48, processing_samples=8) for n in [8,16,32]],
        maximum_protected_stage_saving_ms=8/48,
        device_access=False, host_audio_access=False, firmware_created=False,
        physical_latency_measured=False, hardware_deadline_proven=False,
        limits=[
            'Sparse period estimates assume no unseen whole counter wraps or untracked resets.',
            'One discrete model phase fits the observations; continuous phases, IRQ latency and non-atomic reads remain uncertain.',
            'The startup reference is executed stock setup, not a new live register read.',
            'Whole IRQ cost is a proxy, not a timestamp for hypothetical post-DSP publication.',
            'Instantaneous DMA excludes bus arbitration, synchronization, IRQ preemption and store visibility.',
            'Alternative watermarks change fetch margin, not steady serial label age by themselves.',
            'A smaller watermark reduces FIFO reserve; zero is only a mathematical bound.',
            'Serial labels exclude ADC/DAC filters, channel-slot mapping, NAM response and analog delay.',
            'No model result makes any candidate safe to flash.'])
    a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'])
    print(json.dumps(dict(period=result['estimated_cycles_per_irq_period'],cases=cases,
                          phase_matches=matches),indent=2))


if __name__ == '__main__':
    main()
