"""Compiled active-node dispatcher; no device, playback or installable image."""
import argparse,hashlib,json,math,struct,zlib
from pathlib import Path
from unicorn import UC_HOOK_CODE
from test_preset_runtime import PresetMachine,v,preset_fixture,Engine,library,model_slot
from preset_image import build
from test_dma_current_prototype import fx_pair

class ActiveMachine(PresetMachine):
 def write(self,u,access,addr,n,val,user):
  # Stock callbacks may write ONLY the new ping-pong audio scratch, not model
  # state or graph metadata. All remaining reclaimed-RAM guards stay enabled.
  audio=v.sym.get('_ZN12_GLOBAL__N_15audioE',0)
  if self.phase=='probe' and audio<=addr and addr+n<=audio+128:return
  super().write(u,access,addr,n,val,user)
 def stats(self):return [self.get(v.sym['mpp_graph_stats']+i*4) for i in range(5)]

def input_block(i):return [.08*math.sin((i*8+j)*.071)+.023*math.sin((i*8+j)*.193) for j in range(8)]
def storage_check(model):
 m=ActiveMachine();m.service() # Complete deferred foreground boot before app commands.
 m.upload(model_slot(model),333);m.arm();m.u.mem_write(m.preset,bytes(preset_fixture([8],{8:4})));m.process(0)
 assert m.stats()[0]==2
 settings=bytes(m.u.mem_read(m.preset,128));slot=model_slot(model)
 body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(settings),1,8)+hashlib.sha256(slot).digest()+b'Two blocks'.ljust(64,b'\0')
 assert m.bank_request(2,0,body)[7]==0
 m.restart();m.service();m.process(0);assert m.stats()[0]==2 and m.stats()[2]==2
 assert bytes(m.u.mem_read(m.preset,128))==settings
 return dict(saved_membership_recalled=True,saved_nodes=2,capture_CRC=m.words()[5])
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['payload','baseline','elf','model','library','report']:p.add_argument(name,type=Path)
 p.add_argument('--baseline-cache',type=Path)
 p.add_argument('--storage-only',action='store_true')
 a=p.parse_args();stock=a.payload.read_bytes();base=build(stock,a.baseline);bundle=build(stock,a.elf,allow_active_prototype=True)
 assert bundle[2]['identity']=='NAMACP01'
 try:build(stock,a.elf)
 except ValueError as e:assert 'offline-only' in str(e)
 else:raise AssertionError('Prototype accepted for normal packaging')
 if a.storage_only:
  v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=a.elf
  a.report.write_text(json.dumps(dict(status='PASS_OFFLINE_ACTIVE_CHAIN_STORAGE',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),**storage_check(a.model),device_access=False,host_audio_access=False),indent=2)+'\n')
  print('saved two-block preset and restart PASS',flush=True);return
 lib=library(str(a.library));baseline={};rows=[]
 cache_key=[hashlib.sha256(x.read_bytes()).hexdigest() for x in [a.payload,a.baseline,a.model,a.library,Path(__file__)]]
 if a.baseline_cache and a.baseline_cache.exists():
  cached=json.loads(a.baseline_cache.read_text())
  if cached['key']==cache_key:baseline=cached['cases']
 cases=[('NAM',[],{},False),('NAM-Spring',[8],{8:4},False),('full',[1,2,4,5,6,7,8,9],{4:4,8:4},False),('empty',[],{},True)]
 for role,b,elf in [('baseline',base,a.baseline),('active',bundle,a.elf)]:
  if role=='baseline' and len(baseline)==4:continue
  v.configure(a.payload,True,candidate_bundle=b);v.elf_path=elf
  for label,enabled,types,dry in cases:
   m=ActiveMachine(path=a.model,boundary_oracle=Engine(lib,a.model))
   data=preset_fixture(enabled,types);data[70:74]=bytes([20,20,50,0]);data[36:38]=bytes([55,60]);
   if dry:data[3]|=64
   m.u.mem_write(m.preset,bytes(data));m.arm();samples=[]
   # Same synthetic guitar and full control settling. No audio device is used.
   for i in range(1600):
    y=m.process(i,input_block(i))
    if i>=1500:samples+=y
   assert any(samples) and m.words()[4]==0
   # Trace real callback entries and count instructions on a settled IRQ.
   calls=[];instructions=[0];hooks=[]
   known={m.get(0x20000530+id*12)&~1:id for id in range(11)}
   known[v.sym['mpp_stock_amp_process']&~1]=3;known.pop(0x5578,None)
   known[v.sym['mpp_cut_eq_process']&~1]=4
   if types.get(4)==4:known.pop(0x1307e,None)
   for addr,id in known.items():hooks.append(m.u.hook_add(UC_HOOK_CODE,lambda u,pc,n,id:calls.append(id),id,begin=addr,end=addr))
   hooks.append(m.u.hook_add(UC_HOOK_CODE,lambda *args:instructions.__setitem__(0,instructions[0]+1)))
   m.process(1600,input_block(1600))
   for h in hooks:m.u.hook_del(h)
   if role=='baseline':baseline[label]=(samples,instructions[0],calls)
   else:
    expected=[id for id in data[90:99] if not data[id]&64]
    assert calls==expected,(label,calls,expected)
    assert m.stats()==[len(expected),1,len(expected),0,0],m.stats()
    ref,ins,refcalls=baseline[label];peak=max(abs(x-y) for x,y in zip(samples,ref))
    relative=(sum((x-y)**2 for x,y in zip(samples,ref))/max(sum(x*x for x in ref),1e-30))**.5
    assert samples==ref,(label,peak,relative)
    rows.append(dict(case=label,actual_callbacks=calls,baseline_callbacks=refcalls,active_instructions=instructions[0],baseline_instructions=ins,
     steady_output_exact=samples==ref,peak_difference=peak,relative_RMS_difference=relative,max_NAM_reference_error=m.max_boundary_error))
   print(role,label,calls,instructions[0],'PASS',flush=True)
  if role=='baseline' and a.baseline_cache:a.baseline_cache.write_text(json.dumps(dict(key=cache_key,cases=baseline)))
 # Transitions and all FX choices: a removed block has zero calls immediately;
 # re-add initializes it through its existing foreground type/load handoff.
 v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=a.elf
 m=ActiveMachine(path=a.model,boundary_oracle=Engine(lib,a.model));m.arm();counter=0;transitions=[]
 for label,enabled,order,pair in [
  ('two-block',[8],[5,1,2,3,9,4,6,7,8],None),
  ('add-full-and-FX',[1,2,4,5,6,7,8,9],[5,1,2,3,9,4,6,7,8],(1,2)),
  ('reorder',[1,2,4,5,6,7,8,9],[5,8,3,1,2,4,9,6,7],(5,6)),
  ('remove-stock',[],[5,8,3,1,2,4,9,6,7],(3,4)),
  ('restore-reverb',[8],[5,1,2,3,9,4,6,7,8],(7,2)),
 ]:
  data=preset_fixture(enabled,{4:4,8:4});data[90:99]=bytes(order);m.u.mem_write(m.preset,bytes(data))
  if pair:fx_pair(m,pair)
  for i in range(1350):m.process(counter,input_block(counter));counter+=1
  s=m.stats();assert s[2]==len(enabled)+1 and s[3]==(2 if pair else 0) and not s[4],s
  assert not m.pending_boundary and m.words()[4]==0
  transitions.append(dict(case=label,blocks=1350,stock_calls_per_block=s[2],FX_calls_per_block=s[3],NAM_error=m.max_boundary_error))
  print('transition',label,'PASS',flush=True)
 # Remove both custom nodes without changing their configured modes/order.
 config=v.SP-512;m.call(v.sym['mpp_fx_get'],[config]);fx=bytearray(m.u.mem_read(config,32));fx[1]=fx[17]=0;m.u.mem_write(config,bytes(fx));m.call(v.sym['mpp_fx_set'],[config]);m.process(counter)
 assert m.stats()[3]==0
 # Invalid topology is bounded, silent and not a stale previous plan.
 m.u.mem_write(m.preset+90,b'\x03\x03');m.process(counter+1);assert m.stats()[0]==0 and m.stats()[4]>0
 assert m.read(v.sym['mpp_link_output'])==[0.]*8
 m.restart();assert m.stats()==[0]*5
 m.upload(model_slot(a.model),333);m.arm();m.u.mem_write(m.preset,bytes(preset_fixture([8],{8:4})));m.process(0);assert m.stats()[0]==2
 storage_check(a.model)
 a.report.write_text(json.dumps(dict(status='PASS_OFFLINE_ACTIVE_CHAIN',identity='NAMACP01',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),
  cases=rows,transitions=transitions,custom_removal_no_calls=True,invalid_topology_silent=True,restart_rebuild=True,saved_membership_recalled=True,
  device_access=False,host_audio_access=False,flash_container_created=False,physical_latency_measured=False,
  limits=['Instruction counts are not M7 cycle measurements','One Fender capture, bounded effect settings',
  'Existing routing gain sequence retained during transitions; no gain loops at unity',
  'Effects remain compiled as an available library; only active nodes execute','No app or controller capability is published before hardware validation']),indent=2)+'\n')
if __name__=='__main__':main()
