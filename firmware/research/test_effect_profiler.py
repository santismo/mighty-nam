import sys,json,hashlib,struct,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_preset_runtime import PresetMachine,build,v,preset_fixture
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_READ
from unicorn.arm_const import *
p=argparse.ArgumentParser(description='Compare real stock-chain PCM with each profiler stage selected; offline only.')
for name in ['payload','elf','model','output']:p.add_argument(name,type=Path)
args=p.parse_args();payload=args.payload;elf=args.elf
v.configure(payload,True,candidate_bundle=build(payload.read_bytes(),elf));v.elf_path=elf
path=args.model
a=PresetMachine(path=path);b=PresetMachine(path=path)
def command(m,mode):m.ingress([bytes([0xf0,0x43,0x58,0x70,4,2,ord('N'),ord('T'),mode,0xf7])])
def snapshot(m):
 assert m.page(26)==(0,0x46585031)
 return [m.page(i)[1] for i in range(27,117)]
assert a.page(27)==(3,0)
assert snapshot(a)==[0]*90
assert a.page(117)==(1,0)
for mode in [11,12,125]:
 command(a,mode);assert snapshot(a)==[0]*90
command(a,3);assert snapshot(a)[:2]==[4,1]
a.put(0xe000ed04,16);command(a,126);a.put(0xe000ed04,0)
assert snapshot(a)[:2]==[4,1],'IRQ command accepted'
command(a,126);assert snapshot(a)[:2]==[0,2]
for m in [a,b]:
 m.u.mem_write(m.preset,bytes(preset_fixture([1,2,4,5,6,7,8,9])));m.arm()
for i in range(1250):assert a.process(i)==b.process(i)
rows=[];block=1250
for label,enabled,blocks in [('enabled',[1,2,4,5,6,7,8,9],32),('bypass',[],16),('resume',[1,2,4,5,6,7,8,9],16)]:
 for m in [a,b]:m.u.mem_write(m.preset,bytes(preset_fixture(enabled)))
 for i in range(1250):assert a.process(block)==b.process(block);block+=1
 for stage in range(11):
  command(a,126);command(a,stage)
  for i in range(blocks):
   assert a.process(block)==b.process(block),(label,stage,block)
   block+=1
  s=snapshot(a);r=s[2+8*stage:10+8*stage]
  assert r[:5]==[blocks,blocks,0,1000,1000],(label,stage,r)
  sleeping=label=='bypass' and stage in {1,2,4,6,9}
  assert r[6]==(blocks if sleeping else 0),(label,stage,r)
  assert all(x==0 for j in range(11) if j!=stage for x in s[2+8*j:10+8*j])
  frozen=s[2:];a.process(block);b.process(block);block+=1
  assert [a.page(i)[1] for i in range(29,117)]==frozen
  rows.append(dict(case=label,stage=stage,samples=blocks,sleeping=sleeping,bit_identical=True))
 print(label,'all 11 stage selections preserved PCM',flush=True)
command(a,127);assert snapshot(a)[0]==0
before=snapshot(a)[2:]
for i in range(16):a.process(block);block+=1
assert snapshot(a)[2:]==before
# Standalone callback: exercise invalid DWT spans without the outer IRQ harness.
stats=v.sym['mpp_profile_stats']+3*32
entry=v.sym['mpp_profile_dispatch'];stub=0x3e000
# Thumb no-op for a counter fault case, not DSP proof.
a.u.mem_write(stub,bytes.fromhex('7047'))
def invoke():
 sp=v.SP
 a.u.mem_write(sp,struct.pack('<2I',0x20025100,0x20025140))
 a.call(entry,[3,stub|1,0x20025000,0x20025040])
command(a,126);a.put(0xe0001000,0);invoke()
r=struct.unpack('<8I',a.u.mem_read(stats,32));assert r[0:3]==(1,0,1) and r[7]&1
# Bounded seqlock refuses a snapshot if publication remains odd.
a.put(v.sym['mpp_profile_sequence'],1);assert a.page(26)==(2,0) and a.page(27)==(3,0)
a.put(v.sym['mpp_profile_sequence'],2)
a.restart();assert snapshot(a)==[0]*90,'Warm restart failed to clear diagnostics'
report=dict(status='PASS_NAMLNK11_EFFECT_PROFILER',elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),cases=rows,default_disabled=True,invalid_commands_ignored=True,IRQ_commands_rejected=True,disabled_counts_frozen=True,snapshot_coherent_and_frozen=True,odd_sequence_rejected=True,counter_disabled_rejected=True,warm_restart_clears=True,physical_cycles_measured=False,device_access=False,audio_access=False)
args.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
