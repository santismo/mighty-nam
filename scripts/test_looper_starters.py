#!/usr/bin/env python3
"""Verify only the licensed public bank on the exact NAMLNK27 image, offline."""
import argparse, hashlib, json, math, sys, struct, zlib, copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
for name in ['baseline','payload','work','bank','report','reference','output']:p.add_argument(name,type=Path)
p.add_argument('--seven',action='store_true')
a=p.parse_args()
sys.path[:0]=[str(ROOT/'tools/looper-prototype/hardware'),str(ROOT/'scripts'),str(a.baseline/'generated/research'),str(a.baseline/'generated/tools')]
from starter_bank import validate_bank
bank=a.bank.read_bytes();report=json.loads(a.report.read_text());validate_bank(bank,report)
if a.seven:
 assert len(report['presets'])==3, 'Expand a verified three-capture starter bank'
 original=bank;bank=bytearray(original);rows=copy.deepcopy(report['presets'])
 for color in range(3,7):
  source=color%3;record=bytearray(original[source*16384:source*16384+8192])
  struct.pack_into('<I',record,8,color);struct.pack_into('<I',record,8184,zlib.crc32(record[:8184]))
  bank[color*16384:color*16384+8192]=record
  row=copy.deepcopy(rows[source]);row['color']=color;rows.append(row)
 bank=bytes(bank);report['presets']=rows;report['bank_sha256']=hashlib.sha256(bank).hexdigest()
 report['button_cycles_three']=False;report['remaining_four_empty']=False
from harness import setup
M,v,s,preset,input_block,model_slot=setup(a.baseline,a.payload,a.work)
from a2_model import extract
from a2_oracle import Engine,library
m=M(bank,fill=0xa5);m.service()
assert m.words()[5]==report['presets'][0]['model_crc'] and m.get(v.sym['mpp_listen_enabled'])==1
assert m.loop_state(0)==m.loop_state(3)==0 and not m.diag()[3]
count=len(report['presets'])
for color in list(range(1,count))+[0]:assert m.button()==color
m.restart();m.service();assert m.words()[5]==report['presets'][0]['model_crc']
a.output.mkdir(parents=True,exist_ok=True)
provenance=json.loads((ROOT/'firmware/models/riffsmith/provenance.json').read_text())
checks=[]
for color in range(count):
 entry=provenance['models'][color%3]
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
report['button_cycles_all']=True
for row in report['presets']:row['color_name']=['Green','Orange','Red','Blue','Cyan','Pink','Lilac'][row['color']]
validate_bank(bank,report)
(a.output/'starter-bank.json').write_text(json.dumps(report,indent=2)+'\n')
(a.output/'starter-bank.bin').write_bytes(bank)
print('PASS_OFFLINE_PUBLIC_STARTERS',flush=True)
