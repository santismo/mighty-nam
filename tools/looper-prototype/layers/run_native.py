#!/usr/bin/env python3
"""Run numeric-only layer tests and bind their evidence to source hashes."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('models',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parent;out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
inputs=list(root.glob('*.hpp'))+[root/'test_layers.cpp',root/'test_long.cpp']+list(root.parent.glob('*.hpp'))
inputs+=list((root.parents[2]/'firmware/target/a2').glob('*.hpp'))
inputs+=[root.parents[2]/'firmware/target/a2/a2_lite.cpp']
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
before={str(f.relative_to(root.parent)) if f.is_relative_to(root.parent) else '../../'+str(f.relative_to(root.parents[2])):sha(f) for f in inputs}
for name,report,args in [('test_layers','layers.json',[]),('test_long','full-duration.json',[
    str((a.models/(n+'.weights')).resolve()) for n in ['riffsmith-clean-lite','riffsmith-distorted-lite','riffsmith-bass-clean-lite']])]:
    target=out/name
    sources=[root/(name+'.cpp')]
    if name=='test_long':sources += [root.parents[2]/'firmware/target/a2/a2_lite.cpp']
    subprocess.run(['clang++','-std=c++17','-O2','-ffp-contract=off','-fsanitize=address,undefined',*map(str,sources),'-o',str(target)],check=True)
    result=subprocess.run([str(target),*args],capture_output=True,text=True)
    (out/(name+'.log')).write_text(result.stdout+result.stderr)
    result.check_returncode()
    value=json.loads(result.stdout.splitlines()[-1]);assert value['status'].startswith('PASS_')
    (out/report).write_text(json.dumps(value,indent=2)+'\n')
    print(value['status'],flush=True)
for name,digest in before.items():assert sha(root.parent/name)==digest,'Source changed during test: '+name
(out/'source-hashes.json').write_text(json.dumps(before,indent=2)+'\n')
