#!/usr/bin/env python3
"""Run Dart transfer traces encoded by the actual Mac Swift codec on saved ARM firmware."""
import argparse,hashlib,json,struct,zlib
from pathlib import Path
from test_link_firmware import LinkMachine,unpack,build,v
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('payload',type=Path);p.add_argument('elf',type=Path)
p.add_argument('traces',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True)
p.add_argument('--identity',choices=['NAMLNK01','NAMLNK02','NAMLNK03','NAMLNK04','NAMLNK05','NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09'],default='NAMLNK01');a=p.parse_args()
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,identity=a.identity))
if a.identity in ('NAMLNK02','NAMLNK03','NAMLNK04','NAMLNK05','NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09'):
 from test_link_stock_chain import ChainMachine
def frames(path):
 data=path.read_bytes();pos=0
 while pos<len(data):
  n=struct.unpack_from('<I',data,pos)[0];pos+=4
  assert 0<n<=330 and pos+n<=len(data)
  yield data[pos:pos+n];pos+=n
rows=[]
for prefix in a.traces:
 m=ChainMachine() if a.identity in ('NAMLNK02','NAMLNK03','NAMLNK04','NAMLNK05','NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09') else LinkMachine()
 wire=Path(str(prefix)+'.swift-sysex');replies=Path(str(prefix)+'.replies');slot=Path(str(prefix)+'.slot')
 requests=list(frames(wire));expected=list(frames(replies));assert len(requests)==len(expected)==35
 for index,(message,reply) in enumerate(zip(requests,expected)):
  result=m.ingress([message],0,start=2047)
  assert len(result)==1 and unpack(result[0][0][9:-1])==reply,index
 assert m.words()[5]==zlib.crc32(slot.read_bytes()) and m.words()[9]==1 and m.words()[4]==0
 m.audio();m.guards();assert not m.mmio_writes
 rows.append({'trace':prefix.name,'frames':35,'reply_bytes_identical':True,'model_running':True,'output_zero':True,'wire_sha256':hashlib.sha256(wire.read_bytes()).hexdigest()})
 print('PASS native wire:',prefix.name,flush=True)
result={'status':'PASS_DART_SWIFT_STOCK_ARM_LINK','identity':a.identity,'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),'traces':rows,'physical_device_tested':False,'audio_playback':False,'USB_hardware_emulated':True}
a.output.write_text(json.dumps(result,indent=2)+'\n')
