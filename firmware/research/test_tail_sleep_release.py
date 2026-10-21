"""NAMLNK19 compiled full-IRQ tail sleep/wake for every stock delay/reverb type.

Drives the real foreground loaders, chain and protected output. Peripherals
are virtual; no physical timing or audible quality claim.
"""
import argparse,hashlib,json,struct,math,time
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R6,UC_ARM_REG_R0,UC_ARM_REG_R1
from test_preset_runtime import PresetMachine,build,preset_fixture,v
p=argparse.ArgumentParser(description=__doc__)
for k in ['payload','elf','model','report']:p.add_argument(k,type=Path)
p.add_argument('--stage',type=int,choices=[7,8]);p.add_argument('--type',type=int,choices=range(1,7));
a=p.parse_args();started=time.monotonic();v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf));v.elf_path=a.elf
assert v.plan['identity']=='NAMLNK19';rows=[]
for stage,base,maximum in [(7,0x20003a08,5),(8,0x200041d8,6)]:
 if a.stage is not None and a.stage!=stage:continue
 for typ in range(1,maximum+1):
  if a.type is not None and a.type!=typ:continue
  for setting in ['ordinary','long']:
   m=PresetMachine(path=a.model);m.arm();data=preset_fixture([stage],{stage:typ});data[3]|=64
   data[61:65]=bytes([50,45,50,40] if setting=='ordinary' else [90,85,90,85]);data[70:74]=bytes([40,35,40,35] if setting=='ordinary' else [85,85,85,85]);m.u.mem_write(m.preset,bytes(data))
   for i in range(1400):m.process(i)
   assert bytes(m.u.mem_read(base,2))==bytes([typ,typ])
   data[stage]|=64;m.u.mem_write(m.preset,bytes(data))
   for i in range(1202):m.process(1400+i)
   assert struct.unpack('<H',m.u.mem_read(v.sym['mpp_bypass_hold']+stage*2,2))[0]==65534
   calls=[0]
   def callback(u,pc,size,_):
    if u.mem_read(m.preset+100-u.reg_read(UC_ARM_REG_R6),1)[0]==stage:calls[0]+=1
   h=m.u.hook_add(UC_HOOK_CODE,callback,begin=0x1230c,end=0x1230c)
   for i in range(16):m.process(2700+i,[0.]*8)
   assert calls[0]==0;m.u.hook_del(h)
   # The actual compiled wake must request the stock clear in foreground,
   # not revive the frozen history. Dry NAM bypass isolates retained tails.
   clears=[]
   def clear(u,pc,size,_):
    if u.reg_read(UC_ARM_REG_R1)==0x40000:clears.append(u.reg_read(UC_ARM_REG_R0))
   h=m.u.hook_add(UC_HOOK_CODE,clear,begin=0x5530,end=0x5530)
   data[stage]&=63;m.u.mem_write(m.preset,bytes(data));peak=0.
   for i in range(1320):
    y=m.process(2800+i,[0.]*8)
    if i>=1200:peak=max(peak,max(map(abs,y)))
   m.u.hook_del(h);assert clears and peak<1e-6,(stage,typ,setting,clears,peak)
   assert bytes(m.u.mem_read(base,2))==bytes([typ,typ])
   response=max(max(map(abs,m.process(4200+i))) for i in range(64));assert response>1e-4
   m.guards();assert not m.words()[4]
   rows.append(dict(stage=stage,type=typ,setting=setting,sleep_callbacks=0,foreground_history_clears=len(clears),silent_wake_peak=peak,new_input_peak=response))
   print(stage,typ,setting,'PASS',flush=True)
report=dict(status='PASS_NAMLNK19_TAIL_SUBSET_ARM' if a.stage or a.type else 'PASS_NAMLNK19_ALL_TAIL_TYPES_ARM',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),cases=rows,compiled_IRQ=True,real_foreground_loaders=True,blocks_per_case=4002,device_access=False,host_audio_access=False,seconds=time.monotonic()-started,physical_timing_verified=False)
a.report.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
