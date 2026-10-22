"""NAMLNK22 actual ARM chain with two pitch slots, NAM and stock Spring. Offline.
The VM models peripherals/timing: this is not a physical deadline measurement.
"""
import argparse,hashlib,json,math
from pathlib import Path
from test_usb_nam import UsbMachine,v,preset_fixture,input_block,Engine,library,model_slot
from preset_image import build

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['payload','elf','model','library','output']:p.add_argument(n,type=Path)
 a=p.parse_args();bundle=build(a.payload.read_bytes(),a.elf);assert bundle[2]['identity']=='NAMLNK22'
 v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=a.elf
 m=UsbMachine(boundary_oracle=Engine(library(str(a.library)),a.model));m.service();m.upload(model_slot(a.model),101)
 settings=bytearray(preset_fixture([8],{8:4}));settings[84]=37;settings[70:74]=bytes([20,20,50,0]);m.u.mem_write(m.preset,bytes(settings));m.arm()
 config=bytearray(32);config[:10]=bytes([1,1,2,24,100,30,50,0,50,50]);config[16:26]=bytes([1,1,10,0,100,30,50,0,50,50])
 def publish():
  at=v.SP-512;m.u.mem_write(at,bytes(config));m.call(v.sym['mpp_fx_set'],[at])
 publish();peak=0;blocks=0;rows=[]
 for label,shifts in [('octaves',(24,0)),('opposite',(0,24)),('neutral',(12,12))]:
  config[3],config[19]=shifts;publish()
  for i in range(1500 if blocks==0 else 500):
   y=m.process(blocks,input_block(blocks));blocks+=1
   assert all(math.isfinite(x) and abs(x)<=.8751 for x in y)
   peak=max(peak,max(map(abs,y)))
  assert m.stats()[0]==4 and m.stats()[2:]==[2,2,0],m.stats()
  assert m.words()[4]==0 and m.max_boundary_error<2e-5
  rows.append(dict(case=label,graph=list(m.stats()),max_NAM_reference_error=m.max_boundary_error))
  print(label,'PASS',flush=True)
 config[1]=config[17]=0;publish();m.process(blocks,input_block(blocks));blocks+=1
 assert m.stats()[0]==2 and m.stats()[3]==0 and m.words()[4]==0
 assert peak>1e-6
 report=dict(status='PASS_OFFLINE_NAMLNK22_PITCH_CHAIN',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),blocks=blocks,cases=rows,peak=peak,bypassed_pitch_callbacks=0,physical_deadlines_verified=False,device_access=False,host_audio_access=False)
 a.output.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
