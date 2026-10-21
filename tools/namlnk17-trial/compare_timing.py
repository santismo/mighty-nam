#!/usr/bin/env python3
"""Compare recorded 16/17 silent trials; no device access or audio."""
import argparse
import json
import statistics
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['baseline', 'candidate', 'output']:
    p.add_argument(key, type=Path)
a = p.parse_args()
reports = [json.loads(path.read_text()) for path in [a.baseline, a.candidate]]
cases = ['NAM-only', 'NAM-plus-Spring', 'NAM-after-bypassing-Spring']
selected = []
for identity, report in zip(['NAMLNK16', 'NAMLNK17'], reports):
    assert report['identity'] == identity
    assert report['status'] == 'PASS_' + identity + '_SILENT_MINIMAL_CHAIN_TIMING'
    assert report['originalSettingsRestored']
    assert not any(report[k] for k in ['hostAudioAccess', 'MacTeamsAudioChanged',
                                     'firmwareWrites', 'presetWrites', 'outputEnableCommands'])
    rows = {e['step']: e['result'] for e in report['events'] if e['step'] in cases}
    assert set(rows) == set(cases)
    selected.append(rows)
assert reports[0]['captureCRC'] == reports[1]['captureCRC']
comparison = []
for case in cases:
    base, trial = [rows[case] for rows in selected]
    for key in ['stockEffects', 'fx', 'bufferSamples']:
        assert base[key] == trial[key], (case, key)
    assert base['bufferSamples'] == 8
    summaries = []
    for row in [base, trial]:
        snapshots = row['rawIRQTiming']
        assert len(snapshots) == 24
        assert all(x['usable'] and x['flags'] == 0 and x['rejected'] == 0 for x in snapshots)
        counts = [x['accepted'] for x in snapshots]
        assert all(b > a for a, b in zip(counts, counts[1:]))
        values = [x['lastCycles'] for x in snapshots]
        assert all(v > 0 for v in values)
        summaries.append(dict(min_cycles=min(values), median_cycles=statistics.median(values),
                              max_cycles=max(values), snapshots=len(values)))
    comparison.append(dict(case=case, baseline16=summaries[0], candidate17=summaries[1],
                           median_cycle_change_percent=100 * (summaries[1]['median_cycles'] /
                                                              summaries[0]['median_cycles'] - 1)))
result = dict(status='PASS_MATCHED_NAMLNK16_17_TIMING_REPORTS', cases=comparison,
              capture_crc=reports[0]['captureCRC'], buffer_samples=8,
              physical_latency_measured=False, hardware_deadline_proven=False,
              caveats=['Quiet uncontrolled input; runs are sequential, not interleaved.',
                       'Effect state/history can differ between runs.',
                       'Last-call snapshots, not worst-case deadline coverage.',
                       'The intended ADC filter difference is outside these IRQ measurements.'])
a.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
