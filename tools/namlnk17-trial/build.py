#!/usr/bin/env python3
"""Compile the recorded NAMLNK17 trials on macOS; never run them or access USB."""
import argparse
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
args = parser.parse_args()
here = Path(__file__).resolve().parent
root = here.parents[1]
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
native = root / 'app/plugins/nam_device/macos/Classes'
s = (native / 'NamMidi.swift').read_text()
anchor = '    public func tuner('
assert s.count(anchor) == 1, 'Production tuner API changed; review the adapter.'
pos = s.index(anchor)
s = s[:pos] + '''    public func compactTuner(_ id:Int, operation:Int, nonce:Int, completion:@escaping(Result<[String:Any],Error>)->Void) {
        guard let q=CompactPitch.request(operation,nonce) else {completion(.failure(Failure.message("Invalid compact tuner request")));return}
        start(id,model:nil,tuner:q,completion:completion)
    }
''' + s[pos:]
for old, new in [
    ('if let tuner = pendingTuner {\n                guard',
     'if let tuner = pendingTuner {\n                if tuner[9]>=3 {guard version=="NAMLNK17" else{finish(.failure(Failure.message("Exact NAMLNK17 required")));return};page = -10;request(tuner);return}\n                guard'),
    ('guard let pending = pendingTuner, let raw = NamTunerWire.reply(message,to:pending) else { return }',
     'guard let pending = pendingTuner, let raw = pending[9]>=3 ? CompactPitch.reply(message,to:pending):NamTunerWire.reply(message,to:pending) else { return }'),
]:
    assert s.count(old) == 1, 'Production transport changed; review the adapter.'
    s = s.replace(old, new)
adapter = out / 'NamMidiTrial.swift'
adapter.write_text(s)
wire = native / 'NamLinkWire.swift'
helpers = here / 'physical_helpers.swift'
builds = {
    'restore': [wire, adapter, root / 'tools/namlnk15-trial/CompactPitch.swift', helpers,
        root / 'tools/namlnk12-trial/restore_supplement.swift', here / 'restore.swift'],
    'verify-restart': [wire, native / 'NamMidi.swift', helpers, here / 'verify_restart.swift'],
    'timing': [wire, native / 'NamMidi.swift', helpers, here / 'timing.swift'],
    'compact-wire-test': [wire, root / 'tools/namlnk15-trial/CompactPitch.swift', root / 'tools/namlnk15-trial/compact_wire_test.swift'],
}
for name, sources in builds.items():
    subprocess.run(['swiftc', '-O', *map(str, sources), '-o', str(out / name)], check=True)
print('Compiled four trial tools. No USB or audio operations performed.')
