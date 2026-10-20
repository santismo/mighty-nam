#!/usr/bin/env python3
"""Real stock byte-ring ingress plus malformed-query checks for NAMA2C01."""
import argparse,hashlib,json
from pathlib import Path
import candidate_vm as v
from a2_continuous_image import build
from test_a2_continuous import ContinuousMachine

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('elf',type=Path);p.add_argument('model',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,a.model));m=ContinuousMachine(0xa5)
 version=bytes.fromhex('f0435800f7');query=bytes.fromhex('f043587004024e5000f7');positive=0
 for channel in [0,1]:
  for request in [version,query]:
   for split in range(len(request)+1):
    rows=m.ingress([request[:split],request[split:]],channel,start=2045)
    assert len(rows)==1 and rows[0][1]==channel and m.ingress_lengths[-1]==len(request)-1
    if request==version:assert rows[0][0][4:12]==b'NAMA2C01'
    else:assert rows[0][0][6:9]==bytes([1,0,0])
    positive+=1
  assert not m.ingress([query[:-1]],channel)
  rows=m.ingress([version+query+version],channel);assert [len(x[0]) for x in rows]==[45,15,45]
 negative=0
 for length in list(range(9))+[10,11,255,0xffffffff]:
  assert not m.query(query,entry=v.sym['mpp_probe_query'],length=length);negative+=1
 for i in range(10):
  if i==8:continue
  for value in range(256):
   if value==query[i]:continue
   b=bytearray(query);b[i]=value;assert not m.query(b,entry=v.sym['mpp_probe_query']);negative+=1
 for value in range(128,256):
  b=bytearray(query);b[8]=value;assert not m.query(b,entry=v.sym['mpp_probe_query']);negative+=1
 for channel in [2,127,0xffffffff]:assert not m.query(query,channel,entry=v.sym['mpp_probe_query']);negative+=1
 write=bytearray(query);write[5]=1;assert m.query(write)[0][0][4:6]==bytes([127,2])
 assert not m.mmio_writes;m.guards()
 report={'status':'PASS_A2_CONTINUOUS_REAL_INGRESS_AND_MALFORMED_QUERIES','elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),'model_sha256':hashlib.sha256(a.model.read_bytes()).hexdigest(),'split_ingress_cases':positive,'malformed_queries_rejected':negative,'write_side_unchanged':True,'physical_device_access':False,'audio_playback':False}
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
