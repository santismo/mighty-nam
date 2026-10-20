#!/usr/bin/env python3
"""Tests require two original stock binaries, supplied as paths; no USB access."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nux_container_lab import Container

def reject(data):
    try:
        Container(data)
    except ValueError:
        return
    raise AssertionError('Malformed package was accepted')

for filename in sys.argv[1:]:
    data=Path(filename).read_bytes()
    c=Container(data)
    assert c.rebuild_same_length(c.payload)==data
    c.audit()
    reject(data[:-1])
    bad=bytearray(data);bad[20]^=1;reject(bad)
    bad=bytearray(data);bad[c.sections['BINA']['offset']+540+12]^=1;reject(bad)
    bad=bytearray(data);bad[c.sections['BINA']['offset']+52]^=1;reject(bad)
    # Demonstrates a limitation, not success at signing: structural validity
    # can survive a changed application byte. Device acceptance is unknown.
    changed=bytearray(c.payload);changed[1024]^=1
    modified=c.rebuild_same_length(changed)
    assert modified!=data
    assert Container(modified).payload==changed
    print(Path(filename).name+': PASS roundtrip, framing, rejection tests; mutation is structural-only')
assert len(sys.argv)>1, 'Supply stock firmware files'
