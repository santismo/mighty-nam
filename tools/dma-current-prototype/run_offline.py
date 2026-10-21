#!/usr/bin/env python3
"""Build and test the isolated DMA experiment. No packaging or device tools.

Use the existing lab Python with Unicorn, capstone, pyelftools and ziglang.
Stock payload and two licensed A2 Lite models remain private inputs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

FEATURES = ['stock-chain','m7-conv','fast-bypass','m7-dense','prime-state',
            'irq-timing','listening','early-output','output-buffer','preset-bank',
            'performance','tuner','fx-blocks','cut-eq','responsive-controls',
            'nam-pointer','adc-short-delay','global-buffer','driver-timing']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['payload','first_model','second_model','output']: p.add_argument(name,type=Path)
    a=p.parse_args(); repo=Path(__file__).resolve().parents[2]
    out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    payload=a.payload.resolve(); models=[a.first_model.resolve(),a.second_model.resolve()]
    builder=repo/'firmware/tools/build_link_firmware.py'
    research=repo/'firmware/research'
    flags=['--'+s for s in FEATURES]
    steps=[('build19',[builder,out/'rebuilt19',*flags]),
           ('build-prototype',[builder,out/'build',*flags,'--dma-current-prototype']),
           ('arm',[research/'test_dma_current_prototype.py',payload,out/'rebuilt19',out/'build',
                   out/'arm.json','--models',*models]),
           ('driver',[research/'test_driver_timing.py',payload,out/'build/nam-link-offline.elf',
                      models[0],out/'driver.json','--dma-prototype']),
           ('bus-model',[research/'simulate_dma_current_prototype.py',out/'arm.json',
                         repo/'evidence/driver-phase19/phase-screen.json',out/'bus-model.json'])]
    for name,command in steps:
        print(name,flush=True)
        with (out/(name+'.log')).open('w') as log:
            subprocess.run([sys.executable,*map(str,command)],stdout=log,stderr=subprocess.STDOUT,check=True)
    reports=['arm.json','driver.json','bus-model.json']
    manifest=dict(status='OFFLINE_ONLY_NOT_READY_TO_FLASH',
                  reports={s:hashlib.sha256((out/s).read_bytes()).hexdigest() for s in reports},
                  device_access=False,host_audio_access=False,flash_container_created=False)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(manifest['status'])


if __name__=='__main__': main()
