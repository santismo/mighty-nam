#!/usr/bin/env python3
import argparse,json,hashlib,zlib
from pathlib import Path
from test_preset_runtime import PresetMachine,v,build,unpack
p=argparse.ArgumentParser();p.add_argument('payload',type=Path);p.add_argument('elf',type=Path);p.add_argument('prefix',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf));v.elf_path=a.elf
prefix=str(a.prefix);m=PresetMachine();m.service();model=Path(prefix+'.slot').read_bytes();m.upload(model,123)
m.u.mem_write(m.preset,Path(prefix+'.effects').read_bytes());replies=[]
for wire in json.loads(Path(prefix+'.swift-wire.json').read_text()):
 messages=m.ingress([bytes(wire)],0,start=2047);assert len(messages)==1
 raw=unpack(messages[0][0][9:-1]);assert raw[7]==0
 replies.append(list(messages[0][0]))
assert m.words()[5]==zlib.crc32(model) and m.words()[9]==1 and m.page(23)==(0,2)
Path(prefix+'.arm-wire.json').write_text(json.dumps(replies))
report=dict(status='PASS_NAMLNK10_NATIVE_PRESET_WIRE',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),operations=3,Dart_requests_Swift_encoded=True,actual_stock_receive_ring=True,model_and_effects_recalled=True,muted=True,device_access=False,audio_access=False)
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
