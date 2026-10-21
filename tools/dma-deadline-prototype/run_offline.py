#!/usr/bin/env python3
"""Build/test the DMA guard; no device or packaging APIs."""
import argparse,subprocess,sys
from pathlib import Path
FEATURES=['stock-chain','m7-conv','fast-bypass','m7-dense','prime-state','irq-timing','listening','early-output','output-buffer','preset-bank','performance','tuner','fx-blocks','cut-eq','responsive-controls','nam-pointer','adc-short-delay','global-buffer','driver-timing','dma-current-prototype','dma-deadline-prototype']
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['payload','model','output']:p.add_argument(name,type=Path)
 a=p.parse_args();repo=Path(__file__).resolve().parents[2];out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 commands=[('build',[repo/'firmware/tools/build_link_firmware.py',out/'build',*['--'+x for x in FEATURES]]),
 ('arm',[repo/'firmware/research/test_dma_deadline.py',a.payload.resolve(),out/'build/nam-link-offline.elf',a.model.resolve(),out/'arm.json']),
 ('model',[repo/'firmware/research/simulate_dma_guard.py',out/'model.json'])]
 for label,cmd in commands:
  print(label,flush=True)
  with (out/(label+'.log')).open('w') as log:subprocess.run([sys.executable,*map(str,cmd)],stdout=log,stderr=subprocess.STDOUT,check=True)
 print('OFFLINE_ONLY_NOT_FOR_INSTALLATION')
if __name__=='__main__':main()
