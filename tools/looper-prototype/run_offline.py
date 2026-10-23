#!/usr/bin/env python3
"""Reproduce the compressed looper prototype. Local files only; no USB or audio.

Run with the research environment (Unicorn, pyelftools, Capstone, ziglang).
--signal-python must be Python 3.12 with numpy and stdlib audioop.
"""
import argparse,hashlib,json,struct,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ['firmware_work','payload','output']:p.add_argument(name,type=Path)
p.add_argument('--signal-python',default='python3')
a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
here=Path(__file__).resolve().parent;root=here.parents[1]
sys.path.insert(0,str(root/'firmware/tools'))
from a2_model import extract
provenance=json.loads((root/'firmware/models/riffsmith/provenance.json').read_text())
models=a.output/'models';models.mkdir(exist_ok=True);weights=[]
for entry in provenance['models']:
    source=root/'firmware/models/riffsmith'/entry['file'];raw=source.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==entry['sha256']
    lite=extract(json.loads(raw));name=source.stem+'-lite'
    (models/(name+'.nam')).write_text(json.dumps(lite)+'\n')
    assert len(lite['weights'])==1871
    dest=models/(name+'.weights');dest.write_bytes(struct.pack('<1871f',*lite['weights']));weights.append(dest)
def run(*args):subprocess.run([str(x) for x in args],check=True)
for test in ['test','test_audio','test_compressed']:
    exe=a.output/test
    sources=[here/(test+'.cpp')]
    if test=='test_compressed':sources.append(root/'firmware/target/a2/a2_lite.cpp')
    run('clang++','-std=c++17','-O2','-ffp-contract=off','-DMPP_REFERENCE_ORDER','-fsanitize=address,undefined',
        '-Wall','-Wextra','-Werror',*sources,'-o',exe)
    if test=='test_compressed':run(exe,a.output,*sorted(weights))
    else:run(exe)
run(a.signal_python,here/'check_compression.py',a.output)
run(sys.executable,here/'build_arm.py',a.output)
run(sys.executable,here/'test_compressed_arm.py',a.firmware_work,a.payload,models,a.output)
run(sys.executable,here/'ram_audit.py',a.firmware_work,a.payload,models,a.output/'ram-audit.json')
print('All offline checks passed. No firmware container created; no device or audio access.')
