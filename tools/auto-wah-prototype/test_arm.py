"""Run prototype ARM DSP + A2 Lite + retained effects in eight-frame callbacks.

No hardware/audio access. Instruction counts are workload, not MCU cycles.
"""
import argparse,hashlib,json,math,sys
from pathlib import Path
p=argparse.ArgumentParser()
for n in ['work','payload','baseline_elf','models','library','output']:p.add_argument(n,type=Path)
a=p.parse_args();sys.path[:0]=[str(a.work/'generated/research'),str(a.work/'generated/tools')]
from test_usb_nam import UsbMachine,v,preset_fixture,input_block,Engine,library,model_slot
from preset_image import build
from unicorn import UC_HOOK_CODE
elf=a.work/'build/nam-link-offline.elf';results=[];bypass={};source=a.payload.read_bytes()
def count_block(m,index):
 count=[0];h=m.u.hook_add(UC_HOOK_CODE,lambda *args:count.__setitem__(0,count[0]+1))
 m.process(index,input_block(index));m.u.hook_del(h);return count[0]
models=sorted(a.models.glob('*-lite.nam'));assert len(models)==3
for role,path in [('baseline',a.baseline_elf),('prototype',elf)]:
 bundle=build(source,path);v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=path
 for model in models:
  m=UsbMachine();m.service();m.upload(model_slot(model),101);m.arm();m.initialize_usb()
  m.boundary_oracle=Engine(library(str(a.library)),model)
  assert m.page(24)[1]&255==8
  cases=[('bypassed',False,False),('pre wah',True,False),('post wah spring',True,True),('dual wah spring',True,True)]
  if role=='baseline':cases=cases[:1]
  blocks=0
  for label,enabled,spring in cases:
   m.max_boundary_error=0
   settings=bytearray(preset_fixture([8] if spring else [],{8:4}));settings[84]=37;settings[70:74]=bytes([20,20,50,0]);m.u.mem_write(m.preset,bytes(settings))
   config=bytearray([2,int(enabled),2,12,100,30,50,0,50,50,0,0,0,0,0,0,2,0,3,12,100,30,50,0,50,50,0,0,0,0,0,0])
   if label=='post wah spring':config[2]=9
   if label=='dual wah spring':config[17]=1;config[18]=9;config[24]=100;config[25]=100
   at=v.SP-512;m.u.mem_write(at,bytes(config));m.call(v.sym['mpp_fx_set'],[at]);m.arm();samples=[]
   # Keep reference history across graph changes, just as the loaded model does.
   for i in range(1450):
    y=m.process(blocks,input_block(blocks));blocks+=1
    assert all(math.isfinite(x) and abs(x)<=.8751 for x in y)
    if i>=1400:samples+=y
   assert m.words()[4]==0 and max(map(abs,samples))>1e-9 and m.max_boundary_error<2e-5
   expected_fx=2 if label=='dual wah spring' else int(enabled)
   assert m.stats()[3]==expected_fx and m.stats()[2]==1+int(spring)
   measured=[count_block(m,blocks+i) for i in range(4)];blocks+=4
   if label=='bypassed':
    if role=='baseline':bypass[model.name]=samples
    else:assert bypass[model.name]==samples,'Bypassed wah changed the guitar samples'
   results.append(dict(variant=role,model=model.name,case=label,callbacks=1454,buffer_samples=8,active_fx=expected_fx,stock_callbacks=1+int(spring),NAM_reference_peak_error=m.max_boundary_error,peak=max(map(abs,samples)),whole_callback_instruction_counts=measured,faults=0))
   print(role,model.name,label,'PASS',max(measured),flush=True)
  m.boundary_oracle=None
report=dict(status='PASS_OFFLINE_DAISY_WAH_ARM',elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),cases=results,block_samples=8,sample_rate=48000,bypassed_guitar_sample_exact=True,memory_guards_passed=True,device_access=False,host_audio_access=False,physical_deadlines_verified=False,limitations=['Unicorn executes the actual ARM NAM/effect instructions; peripherals and timers are modeled.','Instruction counts do not measure Cortex-M7 execution time or end-to-end latency.','Listening and worst-case on-device timing are pending.'])
a.output.write_text(json.dumps(report,indent=2)+'\n')
