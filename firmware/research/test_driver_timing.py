"""Compiled one-shot diagnostic protocol: default-off, bounded, observational."""
import argparse,json,hashlib,struct
from pathlib import Path
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from test_preset_runtime import PresetMachine,build,v
from decode_driver_timing import decode
p=argparse.ArgumentParser(description=__doc__)
for k in ['payload','elf','model','report']:p.add_argument(k,type=Path)
a=p.parse_args();v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf));v.elf_path=a.elf
assert v.plan['identity']=='NAMLNK19'
m=PresetMachine(path=a.model);m.arm()
state=lambda:m.get(v.sym['mpp_driver_state'])
def command(action,channel=0):
 return m.ingress([bytes([240,67,88,112,4,2,78,68,action,247])],channel)
reads=[];writes=[]
h=m.u.hook_add(UC_HOOK_MEM_READ,lambda u,a,x,n,val,z:reads.append(x),begin=0x40071000,end=0x404040ff)
w=m.u.hook_add(UC_HOOK_MEM_WRITE,lambda u,a,x,n,val,z:writes.append((x,n,val)),begin=0x40071000,end=0xffffffff)
assert m.page(118)==(0,0xd1000000) and m.page(119)[0]==2 and m.page(127)[0]==1
for i in range(8):m.process(i)
assert state()==0 and not any(x in reads for x in [0x40071200,0x40404040,0x404040c0])
# Invalid/foreground-only controls must not arm or mutate playback.
for action in [6,125]:command(action)
assert state()==0
m.put(0xe000ed04,16);m.call(v.sym['mpp_driver_control'],[127]);m.put(0xe000ed04,0);assert state()==0
# Verify instrumented publication while audio is active, after real settling.
for i in range(1350):m.process(100+i)
for channel in [0,1]:
 command(127,channel);assert state()==1
 gen=m.get(v.sym['mpp_driver_generation']);command(127,channel);assert m.get(v.sym['mpp_driver_generation'])==gen
 previous=m.read(v.sym['mpp_link_output'])+m.read(v.sym['_ZL11chain_right'])
 expected=[int(x*2**28)*2**-31 for x in previous];assert max(map(abs,expected))>1e-6
 writes.clear();actual=m.process(20+channel);assert actual==expected
 assert state()==3 and m.get(v.sym['mpp_listen_enabled'])==1
 # The existing IRQ counter reads/reset accounting are independent. New captures write no MMIO.
 assert not writes,writes
 before=m.page(118);words=[]
 for win in range(6):
  command(win,channel)
  for page in range(119,127):
   error,value=m.page(page);assert error==0;words.append(value)
 assert before==m.page(118)
 decoded=decode(words);assert decoded['counter_span_valid'] and decoded['entry']['published_tx_half']==0
 assert decoded['publication']['published_tx_half']==0x20016900+128*((20+channel)%2)
 for i in range(4):m.process(30+i)
 assert words==list(struct.unpack('<48I',m.u.mem_read(v.sym['mpp_driver_words'],192)))
 assert not m.words()[4]
# Negative decoder vectors reject resets, disabled timer, torn DMA, FIFO errors and wrap.
checks=[]
for label,index,value in [('reset',45,words[45]+1),('disabled',25,0),('ctrl-change',44,3),('irq-mismatch',46,words[46]+2)]:
 copy=words.copy();copy[index]=value;assert not decode(copy)['counter_span_valid'];checks.append(label)
copy=words.copy();copy[15]^=4;assert decode(copy)['entry']['dma_changed_during_reads'];checks.append('DMA advanced')
copy=words.copy();copy[9]=33<<16;copy[11]=(1<<18)|(1<<19);d=decode(copy)['entry'];assert not d['tx_fifo_occupancy_valid'] and d['tx_fifo_error'] and d['tx_sync_error'];checks.append('FIFO flags')
copy=words.copy();copy[2]=0xfffffff0;copy[19]=0xfffffff8;copy[26]=4;copy[43]=16;assert decode(copy)['entry_to_publication_cycles']==32;checks.append('counter wrap')
# No output publication must never look like a complete capture.
command(127);m.put(v.sym['mpp_link']+36,0);m.process(40,healthy=False);assert state()==2 and m.page(119)[0]==2
m.process(41,healthy=False);assert state()==4 and m.page(119)[0]==2
command(126);assert state()==0
for fill in [0,165,255]:
 n=PresetMachine(fill=fill,path=a.model);assert n.get(v.sym['mpp_driver_state'])==0 and n.get(v.sym['mpp_driver_generation'])==0
 n.put(v.sym['mpp_driver_state'],3);n.restart();assert n.get(v.sym['mpp_driver_state'])==0
m.guards()
report=dict(status='PASS_NAMLNK19_DRIVER_TIMING_ARM',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),default_off=True,explicit_one_shot=True,read_only_MMIO=True,active_publication_exact=True,no_listen_commands=True,bounded_6_windows_8_words=True,both_channels=True,no_render_incomplete=True,cold_patterns=[0,165,255],warm_restarts=3,negative_vectors=checks,synthetic_example=decode(words),device_access=False,host_audio_access=False)
a.report.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
