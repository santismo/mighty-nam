#!/usr/bin/env python3
"""Reproduce RAM/recall prototype tests; local files only, no updater or device."""
import argparse,hashlib,json,struct,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['baseline','payload','output']:p.add_argument(key,type=Path)
p.add_argument('--signal-python',default='python3.12');a=p.parse_args()
here=Path(__file__).resolve().parent;repo=here.parents[1];out=a.output.resolve()
native=out/'native';overlay=out/'overlay';models=native/'models';models.mkdir(parents=True,exist_ok=True);overlay.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(repo/'firmware/tools'));from a2_model import extract
provenance=json.loads((repo/'firmware/models/riffsmith/provenance.json').read_text());weights=[]
for row in provenance['models']:
    source=repo/'firmware/models/riffsmith'/row['file'];raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==row['sha256']
    lite=extract(json.loads(raw));name=source.stem+'-lite';assert len(lite['weights'])==1871
    (models/(name+'.nam')).write_text(json.dumps(lite)+'\n')
    weight=models/(name+'.weights');weight.write_bytes(struct.pack('<1871f',*lite['weights']));weights.append(weight)
def run(*args):subprocess.run([str(x) for x in args],check=True)
for name in ['test','test_audio','test_segments','test_compressed']:
    sources=[here/(name+'.cpp')]
    if name=='test_compressed':sources.append(repo/'firmware/target/a2/a2_lite.cpp')
    exe=native/name
    run('clang++','-std=c++17','-O2','-ffp-contract=off','-DMPP_REFERENCE_ORDER','-fsanitize=address,undefined','-Wall','-Wextra','-Werror',*sources,'-o',exe)
    run(exe,*([native,*sorted(weights)] if name=='test_compressed' else []))
run(a.signal_python,here/'check_compression.py',native)
run(sys.executable,here/'build_continuity.py',a.baseline,overlay)
run('clang++','-std=c++17','-O2','-ffp-contract=off','-Wall','-Wextra','-Werror','-dynamiclib',here/'arm_bridge.cpp','-o',overlay/'loop-native.dylib')
run(sys.executable,here/'audit_memory_contract.py',a.payload,out/'memory-contract.json')
run(sys.executable,here/'audit_layout.py',a.baseline,a.payload,models,out/'ram-layout-audit.json')
run(sys.executable,here/'test_continuity.py',a.baseline,a.payload,native,overlay)
report=dict(status='PASS_OFFLINE_LOOP_RAM_AND_PRESET_CONTINUITY',
    sources={str(f.relative_to(repo)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(here.iterdir()) if f.suffix in ['.py','.cpp','.hpp','.ld']},
    tests=['ASan/UBSan controls, PCM, full compressed 30s capture/60s playback with A2 Lite at 8 frames',
           'Segmented encode/decode parity and bounds','Independent CPython codec/filter oracle',
           'Exact stock MPU and C-runtime contract','80 stock loader cases and long-chain RAM guards',
           'Actual ARM IRQ interleaved during preset copy/CRC/load, settling, physical-button path and failed save',
           'Actual recording hook, native parity, segment boundary, partial final block and wrap'],
    device_access=False,audio_device_opened=False,flash_container_created=False,physical_RAM_safe_proven=False)
(out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('All offline RAM/continuity checks passed. No device or audio access; no installable firmware.')
