#!/usr/bin/env python3
"""Build and test active-only routing, without device or packaging tools."""
import argparse,subprocess,sys,json,hashlib
from pathlib import Path
FEATURES=['stock-chain','m7-conv','fast-bypass','m7-dense','prime-state','irq-timing','listening','early-output','output-buffer','preset-bank','performance','tuner','fx-blocks','cut-eq','responsive-controls','nam-pointer','adc-short-delay','global-buffer','driver-timing']
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['payload','model','reference_library','output']:p.add_argument(name,type=Path)
 a=p.parse_args();repo=Path(__file__).resolve().parents[2];out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 flags=['--'+x for x in FEATURES];builder=repo/'firmware/tools/build_link_firmware.py'
 commands=[('build19',[sys.executable,builder,out/'baseline',*flags]),('build',[sys.executable,builder,out/'build',*flags,'--active-chain-prototype']),
 ('planner-build',['clang++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',repo/'firmware/tests/active_chain_test.cpp','-o',out/'planner']),
 ('planner',[out/'planner']),('arm',[sys.executable,repo/'firmware/research/test_active_chain.py',a.payload.resolve(),out/'baseline/nam-link-offline.elf',out/'build/nam-link-offline.elf',a.model.resolve(),a.reference_library.resolve(),out/'arm.json','--baseline-cache',out/'baseline-cache.json'])]
 for label,cmd in commands:
  print(label,flush=True)
  with (out/(label+'.log')).open('w') as log:subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,check=True)
 assert hashlib.sha256((out/'baseline/nam-link-offline.elf').read_bytes()).hexdigest()=='4c058e7d985897a3ef84f78881a98f0fff0aa9ee3d930347d158a3f0421ebbb0'
 print('OFFLINE_ONLY_NOT_FOR_INSTALLATION')
if __name__=='__main__':main()
