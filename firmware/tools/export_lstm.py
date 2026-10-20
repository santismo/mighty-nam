#!/usr/bin/env python3
"""Export the supported NAM subset to a C++ weight header; no device access."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def export(source, destination):
    raw=source.read_bytes(); j=json.loads(raw)
    if j['version'].split('.')[:2] not in (['0','5'],['0','6']):
        raise ValueError('Only NAM v0.5/v0.6 supported')
    c=j['config']
    if j['architecture']!='LSTM' or j.get('sample_rate')!=48000 or c['num_layers']!=1 or c['input_size']!=1 or c.get('in_channels',1)!=1 or c.get('out_channels',1)!=1:
        raise ValueError('Requires 48 kHz mono single-layer LSTM')
    if set(c)-{'num_layers','input_size','hidden_size','in_channels','out_channels'}:
        raise ValueError('Unsupported LSTM config field')
    h=c['hidden_size']; w=j['weights']
    if type(h) is not int or not 1<=h<=16 or len(w)!=4*h*(h+1)+7*h+1:
        raise ValueError('Unsupported hidden size or incorrect weight count')
    if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>3.4028234e38 for v in w):
        raise ValueError('Invalid weights')
    # Scientific notation always yields a valid floating-point C++ literal.
    lines=['#pragma once','// Generated from NAM SHA256 '+hashlib.sha256(raw).hexdigest(),
           '// Correctness fixture by default; replace with a compatible licensed capture.',
           'namespace embedded_model {',f'constexpr unsigned hidden={h};',f'constexpr unsigned count={len(w)};',
           'constexpr float weights[] = {']
    lines += ['  '+', '.join(f'{v:.9e}f' for v in w[i:i+4])+',' for i in range(0,len(w),4)]
    lines+=['};','}']; destination.write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('model',type=Path);p.add_argument('header',type=Path);a=p.parse_args()
    try: export(a.model,a.header)
    except (OSError,ValueError,KeyError,TypeError) as e:p.exit(1,str(e)+'\n')
