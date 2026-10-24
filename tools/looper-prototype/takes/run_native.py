#!/usr/bin/env python3
"""ASan/UBSan numeric-only NAMLNK29 gates. No audio or device access."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('models',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parent;out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);repo=root.parents[2]
inputs=list(root.glob('*.hpp'))+list(root.glob('*.cpp'))+[Path(__file__)]+list(root.parent.glob('*.hpp'))+list((root.parent/'layers').glob('*.hpp'))+list((root.parent/'settings').glob('*.hpp'))+list((root.parent/'settings').glob('test_*.cpp'))+list((repo/'firmware/target/a2').glob('*.hpp'))+[repo/'firmware/target/a2/a2_lite.cpp']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={str(p.relative_to(root.parent)) if p.is_relative_to(root.parent) else '../../'+str(p.relative_to(repo)):sha(p) for p in inputs}
for name,report,folder in [('test_store','settings-store','settings'),('test_gestures','gestures','settings'),('test_quality','quality','settings'),('test_takes','takes','takes'),('test_long','full-duration','takes')]:
 target=out/name;sources=[root.parent/folder/(name+'.cpp')];args=[]
 if name=='test_long':
  sources+=[repo/'firmware/target/a2/a2_lite.cpp'];args=[str((a.models/(n+'.weights')).resolve()) for n in ['riffsmith-clean-lite','riffsmith-distorted-lite','riffsmith-bass-clean-lite']]
 subprocess.run(['clang++','-std=c++17','-O2','-ffp-contract=off','-DREQUIRE_QUALITY','-fsanitize=address,undefined',*map(str,sources),'-o',str(target)],check=True)
 result=subprocess.run([str(target),*args],capture_output=True,text=True,check=True)
 value=json.loads(result.stdout.splitlines()[-1]);assert value['status'].startswith('PASS_')
 (out/(report+'.json')).write_text(json.dumps(value,indent=2)+'\n');print(value['status'],flush=True)
for name,digest in hashes.items():assert sha(root.parent/name)==digest,'Source changed during testing'
(out/'source-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
