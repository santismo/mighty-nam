#!/usr/bin/env python3
"""Check NAMLNK11 placement and byte-identical NAMLNK10 output/storage objects."""
import argparse,hashlib,json
from pathlib import Path
from preset_image import build
p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','baseline_build','candidate_build','rebuilt_baseline','output']:p.add_argument(name,type=Path)
a=p.parse_args();digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=a.baseline_build/'nam-link-offline.elf';new=a.candidate_build/'nam-link-offline.elf'
assert digest(old)==digest(a.rebuilt_baseline/'nam-link-offline.elf')=='7b92cb19fd515067c65034e27cf8c7b4364e4a5100a05b8fde0f36946e7151c9'
objects=['sysex_codec.o','model_receiver.o','listening.o','irq_timing.o','preset_bank.o','preset_runtime.o']
for obj in objects:assert (a.baseline_build/obj).read_bytes()==(a.candidate_build/obj).read_bytes(),obj
stock=a.payload.read_bytes();image,symbols,plan=build(stock,new)
assert plan['identity'] in ('NAMLNK11','NAMLNK12') and image[:0x400]==stock[:0x400] and image[0x11d94:0x11dd8]==stock[0x11d94:0x11dd8]
assert symbols['mpp_profile_selected']<0x20308000 and symbols['mpp_profile_dispatch']>=0x20308000
report=dict(status='PASS_'+plan['identity']+'_PLACEMENT_REGRESSION',elf_sha256=digest(new),baseline10_rebuilt_exactly=True,output_and_storage_objects_unchanged=True,unchanged_objects=objects,stock_vectors_and_IRQ_preserved=True,regions=plan['elf_regions'],copied_code=plan['copied_code'],preset_storage=plan['preset_ownership'],physical_placement_tested=False,device_access=False,audio_access=False)
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
