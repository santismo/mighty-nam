#!/usr/bin/env python3
"""Negative packaging gates against a completed offline NAMLNK20 build. No devices."""
import argparse, json, shutil, subprocess, sys, tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for arg in ['stock_package','build_dir','reports','controller_dir','result']: p.add_argument(arg,type=Path)
a=p.parse_args();root=Path(__file__).resolve().parents[1]
script=root/'tools/stage_active_chain_firmware.py';cases=[]
with tempfile.TemporaryDirectory(prefix='nam20-package-gates-') as tmp:
 base=Path(tmp)
 def run(name,mutate,expected):
  d=base/name;d.mkdir();build=d/'build';reports=d/'reports';controller=d/'controller'
  build.mkdir();reports.mkdir();controller.mkdir()
  for source in a.build_dir.iterdir():
   if source.name=='build.json': shutil.copyfile(source,build/source.name)
   else: (build/source.name).symlink_to(source.resolve())
  for source in a.reports.glob('*.json'): shutil.copyfile(source,reports/source.name)
  for source in a.controller_dir.iterdir():
   if source.name=='index.html': shutil.copyfile(source,controller/source.name)
   else: (controller/source.name).symlink_to(source.resolve(),target_is_directory=source.is_dir())
  stock=a.stock_package.resolve();changed=mutate(build,reports,controller,d)
  if changed: stock=changed
  result=subprocess.run([sys.executable,str(script),str(stock),str(build),str(reports),str(d/'out'),'--controller-dir',str(controller)],capture_output=True,text=True)
  assert result.returncode and expected in result.stderr,(name,result.stderr)
  assert not (d/'out').exists(),name
  cases.append(name)
 def modify(path,action):
  data=json.loads(path.read_text());action(data);path.write_text(json.dumps(data))
 run('identity',lambda b,r,c,d:modify(b/'build.json',lambda x:x.update(identity='NAMLNK19')),'Wrong build')
 run('runtime-hash',lambda b,r,c,d:modify(r/'runtime.json',lambda x:x.update(elf_sha256='0'*64)),'Missing/mismatched runtime')
 run('planner-source',lambda b,r,c,d:modify(r/'planner.json',lambda x:x.update(source_sha256='0'*64)),'Planner source mismatch')
 run('linker-hash',lambda b,r,c,d:modify(b/'build.json',lambda x:x.update(linker_sha256='0'*64)),'Linker changed')
 run('dma-prototype',lambda b,r,c,d:modify(b/'build.json',lambda x:x['compiler_flags'].append('-DMPP_DMA_CURRENT_PROTOTYPE')),'DMA experiment excluded')
 run('missing-evidence',lambda b,r,c,d:(r/'responsive.json').unlink(),'responsive.json')
 def phone_change(b,r,c,d): (c/'index.html').write_text('changed controller')
 run('controller-changed',phone_change,'Controller source changed')
 def stock_change(b,r,c,d):
  f=d/'bad-stock.bin';f.write_bytes(b'not approved stock');return f
 run('stock-package',stock_change,'Exact V1.5.6 stock package required')
a.result.write_text(json.dumps(dict(status='PASS_NAMLNK20_PACKAGE_REJECTION',cases=cases,device_access=False),indent=2)+'\n')
print('PASS',len(cases),'package rejection gates')
