#!/usr/bin/env python3
"""Verify only the licensed public bank on the exact NAMLNK27 image, offline."""
import argparse, hashlib, json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
for name in ['baseline','payload','work','bank','report','reference','output']:p.add_argument(name,type=Path)
a=p.parse_args()
sys.path[:0]=[str(ROOT/'tools/looper-prototype/hardware'),str(ROOT/'scripts'),str(a.baseline/'generated/research'),str(a.baseline/'generated/tools')]
from starter_bank import validate_bank
bank=a.bank.read_bytes();report=json.loads(a.report.read_text());validate_bank(bank,report)
from harness import setup
M,v,s,preset,input_block,model_slot=setup(a.baseline,a.payload,a.work)
from a2_model import extract
from a2_oracle import Engine,library
m=M(bank,fill=0xa5);m.service()
assert m.words()[5]==report['presets'][0]['model_crc'] and m.get(v.sym['mpp_listen_enabled'])==1
assert m.loop_state(0)==m.loop_state(3)==0 and not m.diag()[3]
for color in [1,2,0]:assert m.button()==color
m.restart();m.service();assert m.words()[5]==report['presets'][0]['model_crc']
a.output.mkdir(parents=True,exist_ok=True)
provenance=json.loads((ROOT/'firmware/models/riffsmith/provenance.json').read_text())
checks=[]
for color,entry in enumerate(provenance['models']):
 assert m.bank_request(3,color,nonce=1000+color)[7]==0;m.service()
 lite=a.output/(Path(entry['file']).stem+'-lite.nam')
 lite.write_text(json.dumps(extract(json.loads((ROOT/'firmware/models/riffsmith'/entry['file']).read_text()))))
 m.boundary_oracle=Engine(library(str(a.reference)),lite);m.max_boundary_error=0.;peak=0
 for i in range(1600):
  y=m.process(i,input_block(i));assert all(math.isfinite(x) for x in y);peak=max(peak,max(map(abs,y)))
 assert 1e-7<peak<1 and not m.words()[4] and not m.diag()[3]
 assert m.max_boundary_error<2e-5
 checks.append(dict(color=color,callbacks=1600,peak=peak,reference_error=m.max_boundary_error,faults=0))
 m.boundary_oracle=None
 print('PASS looper public starter',color+1,flush=True)
report.update(elf_sha256=hashlib.sha256((a.work/'build/loop-startup-test.elf').read_bytes()).hexdigest(),callbacks=checks,
 identity=json.loads((a.work/'build/build.json').read_text())['identity'],warm_restart=True,play_on_boot=True,looper_empty_on_boot=True,
 candidate_payload_sha256=v.plan['candidate_sha256'])
for row in report['presets']:row['color_name']=['Green','Orange','Red'][row['color']]
validate_bank(bank,report)
(a.output/'starter-bank.json').write_text(json.dumps(report,indent=2)+'\n')
(a.output/'starter-bank.bin').write_bytes(bank)
print('PASS_OFFLINE_PUBLIC_STARTERS',flush=True)
