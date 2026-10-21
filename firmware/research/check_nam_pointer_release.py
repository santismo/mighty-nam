"""Check NAMLNK16 against the tested pointer kernel and exact NAMLNK15 modules.
No device access, audio or firmware-file creation.
"""
import argparse, hashlib, json
from pathlib import Path
from elftools.elf.elffile import ELFFile
from preset_image import build

p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','baseline_build','candidate_build','report']:p.add_argument(name,type=Path)
a=p.parse_args()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(a.baseline_build/'nam-link-offline.elf')=='53d00afbf6773638671c4e99d1af592ba9d7b0d4be8ea79f2dcff572e42d3e75'
meta=json.loads((a.candidate_build/'build.json').read_text())
assert meta['identity']=='NAMLNK16' and meta['nam_pointer_taps']
assert meta['elf_sha256']==sha(a.candidate_build/'nam-link-offline.elf')
with (a.candidate_build/'a2_lite.o').open('rb') as f:
    e=ELFFile(f);code=e.get_section_by_name('.text._ZN3mpp6A2Lite7processEPKfPfj').data()
assert len(code)==820 and hashlib.sha256(code).hexdigest()=='f76f5a955408a6f5dbcef9e0591a82e0b40fce0efdae15f1177edf1dcfe4cc8b'
unchanged=[]
for path in sorted(a.baseline_build.glob('*.o')):
    if path.name in ['a2_lite.o','stock_chain_firmware.o']:continue
    assert path.read_bytes()==(a.candidate_build/path.name).read_bytes(),path.name
    unchanged.append(path.name)
assert len(unchanged)==13
stock=a.payload.read_bytes();base,_,bp=build(stock,a.baseline_build/'nam-link-offline.elf')
candidate,_,cp=build(stock,a.candidate_build/'nam-link-offline.elf')
# Startup and codec setup are outside the permitted hook/resource regions.
assert base[0x116c0:0x11984]==candidate[0x116c0:0x11984]==stock[0x116c0:0x11984]
assert base[:0x400]==candidate[:0x400]==stock[:0x400]
assert [(r['offset'],r['reason']) for r in bp['patches'] if 'identity' not in r['reason']]==[(r['offset'],r['reason']) for r in cp['patches'] if 'identity' not in r['reason']]
r=dict(status='PASS_NAMLNK16_KERNEL_AND_UNCHANGED_MODULES',elf_sha256=meta['elf_sha256'],
    matches_tested_pointer_kernel=True,active_kernel_sha256=hashlib.sha256(code).hexdigest(),active_kernel_bytes=len(code),
    unchanged_objects=unchanged,unchanged_output_pipeline=True,codec_startup_unchanged=True,
    device_access=False,host_audio_access=False,physical_latency_measured=False)
a.report.write_text(json.dumps(r,indent=2)+'\n');print(r['status'])
