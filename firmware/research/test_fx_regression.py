import json,hashlib,struct,argparse
from pathlib import Path
from test_preset_runtime import PresetMachine,build,v,preset_fixture
p=argparse.ArgumentParser(description='NAMLNK13 memory, bypass PCM, full-chain FX and timing-fault regression; no device access.')
for key in ['payload','baseline_build','rebuilt_baseline','candidate_build','model','output']:p.add_argument(key,type=Path)
a=p.parse_args();base=a.baseline_build;candidate=a.candidate_build;stock=a.payload;model=a.model
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert digest(base/'nam-link-offline.elf')==digest(a.rebuilt_baseline/'nam-link-offline.elf')=='21a9e9a3ddeff174367e6a4ae642855b0ec343aebc82520df5a763ac5c160574'
objects=['a2_lite.o','model_receiver.o','sysex_codec.o','listening.o','irq_timing.o','effect_profiler.o']
for name in objects:assert (base/name).read_bytes()==(candidate/name).read_bytes(),name
reference=[];rows=[]
for revision,folder in [(12,base),(13,candidate)]:
 elf=folder/'nam-link-offline.elf';image,symbols,plan=build(stock.read_bytes(),elf);v.configure(stock,True,candidate_bundle=(image,symbols,plan));v.elf_path=elf
 assert image[:0x400]==stock.read_bytes()[:0x400] and image[0x11d94:0x11dd8]==stock.read_bytes()[0x11d94:0x11dd8]
 m=PresetMachine(path=model);m.arm();counter=0
 for case in ['full-chain','reorder','bypass']:
  data=preset_fixture([] if case=='bypass' else [1,2,4,5,6,7,8,9])
  if case=='reorder':data[90:99]=bytes([5,3,1,2,4,9,8,6,7])
  m.u.mem_write(m.preset,bytes(data));samples=[]
  for i in range(1350):samples.extend(m.process(counter));counter+=1
  assert max(map(abs,samples))>0
  if revision==12:reference.append(samples)
  else:assert samples==reference[len(rows)];rows.append(dict(case=case,blocks=1350,bit_identical=True))
  print(revision,case,'passed',flush=True)
 if revision==13:
  # Exercise the two new engines together with the real NAM and all stock effects.
  data=preset_fixture([1,2,4,5,6,7,8,9]);m.u.mem_write(m.preset,bytes(data))
  for pair in [(1,2),(3,4),(5,6),(7,1),(1,1)]:
   c=[0]*32
   for index,mode in enumerate(pair):
    at=index*16;c[at]=mode;c[at+1]=1;c[at+2]=index+2;c[at+3]=19 if index==0 else 5;c[at+4]=100;c[at+5]=30;c[at+6]=c[at+8]=c[at+9]=50;c[at+7]=90
   request=[240,67,88,112,4,2,78,70,1,1,127,61,0,0]+[(m.words()[5]>>(7*i))&127 for i in range(5)]+c+[247]
   reply=m.ingress([bytes(request)])[0][0];assert reply[13]==0
   for i in range(1350):m.process(counter);counter+=1
   m.guards();print('NAM + all stock effects + FX',pair,'passed',flush=True)
  # Existing time fault guard still silences/stops, independent of synthetic timing cost.
  m.timer_ticks=150;m.process(counter,healthy=False);assert m.words()[4]>0 and m.words()[9]==0 and m.page(23)==(0,2)
report=dict(status='PASS_NAMLNK13_PLACEMENT_PCM_REGRESSION',elf_sha256=digest(candidate/'nam-link-offline.elf'),baseline12_rebuilt_exactly=True,unchanged_objects=objects,stock_vectors_and_IRQ_preserved=True,bypassed_fx_PCM=rows,full_chain_fx_pairs=[[1,2],[3,4],[5,6],[7,1],[1,1]],timing_fault_mutes=True,regions=plan['elf_regions'],real_time_performance_measured=False,device_access=False,audio_access=False)
a.output.write_text(json.dumps(report,indent=2)+'\n')
