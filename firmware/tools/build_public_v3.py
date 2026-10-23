#!/usr/bin/env python3
"""Compile original NAMLNK23 sources for public V3.0.5 Original. No device I/O."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ports/v3'))
from prepare import prepare
FEATURES='stock-chain m7-conv fast-bypass m7-dense prime-state irq-timing listening early-output output-buffer preset-bank performance tuner fx-blocks cut-eq responsive-controls nam-pointer adc-short-delay global-buffer driver-timing active-chain usb-nam-controls pitch-quality'.split()
p=argparse.ArgumentParser();p.add_argument('output',type=Path)
p.add_argument('--bluetooth-audio',action='store_true',help='Opt-in NAMLNK23-r2 stereo playback trial; requires separate Bluetooth-path evidence before staging')
a=p.parse_args();out=a.output.resolve();generated=prepare(out/'generated')
subprocess.run([sys.executable,str(generated/'tools/build_link_firmware.py'),str(out/'build'),*['--'+f for f in FEATURES],*(['--bluetooth-audio'] if a.bluetooth_audio else [])],check=True)
meta_path=out/'build/build.json';meta=json.loads(meta_path.read_text())
meta.update(stock_base='V3.0.5 Original',status='OFFLINE_PUBLIC_V3_PORT',port_sources={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (ROOT/'ports/v3').iterdir() if f.name in ('prepare.py','relocations.json','image.py')},generated_provenance_sha256=hashlib.sha256((generated/'port-provenance.json').read_bytes()).hexdigest(),new_code_region='Retired AMP model 16 initializer, 0x1c0e8..0x1c270',physical_validation='pending')
meta_path.write_text(json.dumps(meta,indent=2)+'\n')
