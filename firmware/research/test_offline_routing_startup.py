"""Dirty-RAM startup for the separate graph/DMA research identities."""
import argparse,json,hashlib
from pathlib import Path
from preset_image import build
from test_codec_startup import Startup,EXPECTED
from test_dma_deadline import GuardMachine
from test_active_chain import ActiveMachine
from test_preset_runtime import v,preset_fixture,model_slot

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['payload','baseline','guard_elf','graph_elf','model','report']:p.add_argument(name,type=Path)
 a=p.parse_args();stock=a.payload.read_bytes();baseline=build(stock,a.baseline)
 assert hashlib.sha256(a.baseline.read_bytes()).hexdigest()=='4c058e7d985897a3ef84f78881a98f0fff0aa9ee3d930347d158a3f0421ebbb0'
 rows=[]
 for elf,kind in [(a.guard_elf,GuardMachine),(a.graph_elf,ActiveMachine)]:
  bundle=build(stock,elf,allow_dma_prototype=True,allow_active_prototype=True);identity=bundle[2]['identity']
  for fill in (0,165,255):
   b,c=Startup(*baseline,fill),Startup(*bundle,fill);assert b.codec()==c.codec()==EXPECTED
   for boot in ('cold','warm'):
    bm,bd=b.audio_setup();cm,cd=c.audio_setup();assert bd==cd and len(bm)==len(cm)
    delta=[(x,y) for x,y in zip(bm,cm) if x!=y]
    assert delta==([((0x4040400c,4,16),(0x4040400c,4,8))] if identity=='NAMDMP02' else [])
   v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=elf
   m=kind(fill=fill,path=a.model);assert not any(m.stats());m.arm();m.u.mem_write(m.preset,bytes(preset_fixture([8],{8:4})))
   m.process(0);m.process(1);assert not m.words()[4]
   if identity in ('NAMACP01','NAMLNK20'):assert m.stats()[0]==2
   else:assert m.stats()[0]==0 and m.stats()[1:3]==[2,2]
   m.restart();assert not any(m.stats());m.upload(model_slot(a.model),444);m.arm();m.process(0)
   rows.append(dict(identity=identity,elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),fill=fill,cold_and_warm=True,reloaded=True,descriptor_bytes_unchanged=True,changed_register_writes=delta))
   print(identity,fill,'PASS',flush=True)
 a.report.write_text(json.dumps(dict(status='PASS_OFFLINE_ROUTING_STARTUP',cases=rows,device_access=False,host_audio_access=False),indent=2)+'\n')
if __name__=='__main__':main()
