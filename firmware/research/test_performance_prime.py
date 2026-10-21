import sys,json,hashlib,struct,random,argparse
from pathlib import Path
from link_image import elf_identity
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_preset_runtime import PresetMachine,build,v
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
p=argparse.ArgumentParser(description='Compare exact ARM priming cache-line coverage and work; no device access.')
for name in ['payload','baseline','candidate','model','output']:p.add_argument(name,type=Path)
a=p.parse_args();payload=a.payload;modelpath=a.model
kernels=[6]*14+[15,15]+[6]*7
dilations=[1,3,7,17,41,101,239,1,3,7,17,41,101,239,1,13,1,3,7,17,41,101,239]
rows=[]
for name,elf in [('baseline10',a.baseline),('candidate',a.candidate)]:
 v.configure(payload,True,candidate_bundle=build(payload.read_bytes(),elf));v.elf_path=elf
 m=PresetMachine(path=modelpath);entry=v.sym['_ZNK3mpp6A2Lite17prime_working_setEv'];model=v.sym['_ZL5model']
 for case in range(12):
  rng=random.Random(case)
  pos=[(0 if case==0 else ((k-1)*d if case==1 else rng.randrange((k-1)*d+1))) for k,d in zip(kernels,dilations)]
  m.u.mem_write(model+83924,struct.pack('<23I',*pos))
  expected=set(range(model,model+7484,4))|set(range(model+83732,model+83924,4));hi=0
  for k,d,p in zip(kernels,dilations,pos):
   length=(k-1)*d+1
   for frame in range(8):
    for tap in range(k):
     col=(p+frame+1+tap*d)%length
     expected.update(model+7484+4*(hi+col*3+c) for c in range(3))
   hi+=3*length
  before=bytes(m.u.mem_read(model,84024));reads=[];writes=[];instructions=[0]
  def read(u,access,addr,size,value,user):reads.extend(range(addr,addr+size,4))
  def write(u,access,addr,size,value,user):writes.append((addr,size))
  def count(u,pc,size,user):instructions[0]+=1
  hs=[m.u.hook_add(UC_HOOK_MEM_READ,read,begin=model,end=model+84023),m.u.hook_add(UC_HOOK_MEM_WRITE,write,begin=v.state_start,end=v.state_end-1),m.u.hook_add(UC_HOOK_CODE,count)]
  try:m.call(entry,[model])
  finally:
   for h in hs:m.u.hook_del(h)
  assert not writes and bytes(m.u.mem_read(model,84024))==before
  assert all(model<=addr<model+84024 for addr in reads)
  assert {a//32 for a in expected}<={a//32 for a in reads},(name,case,'missing cache coverage')
  rows.append(dict(build=name,case=case,model_reads=len(reads),instructions=instructions[0],cache_lines=len({a//32 for a in expected}),coverage=True,state_unchanged=True))
 print(name,rows[-1],flush=True)
old=rows[:12];new=rows[12:]
assert all(n['model_reads']<o['model_reads']*.3 and n['instructions']<o['instructions'] for o,n in zip(old,new))
r=dict(status='PASS_'+elf_identity(a.candidate)+'_PRIME_CACHE_COVERAGE',elf_sha256=hashlib.sha256(a.candidate.read_bytes()).hexdigest(),cases=rows,model_read_reduction_min=1-max(n['model_reads']/o['model_reads'] for o,n in zip(old,new)),instruction_reduction_min=1-max(n['instructions']/o['instructions'] for o,n in zip(old,new)),physical_timing_measured=False,device_access=False,audio_access=False)
a.output.write_text(json.dumps(r,indent=2)+'\n');print(r['status'],r['model_read_reduction_min'],r['instruction_reduction_min'])
