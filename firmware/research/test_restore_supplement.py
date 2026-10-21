from pathlib import Path
import argparse,json,hashlib
from test_preset_runtime import PresetMachine,v,build
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR

parser=argparse.ArgumentParser(description='Offline restore of private backup controls through actual NAMLNK12 stock MIDI ingress')
for name in ['payload','elf','plan','initial_effects','output']:parser.add_argument(name,type=Path)
args=parser.parse_args();payload=args.payload;elf=args.elf
v.configure(payload,True,candidate_bundle=build(payload.read_bytes(),elf));v.elf_path=elf
class Machine(PresetMachine):
 def code(self,u,pc,size,unused):
  if self.phase=='probe':
   if pc in {0xbfa4,0xc0b0,0xc034,0xba50}:raise AssertionError('Persistent write reached')
   if pc==0xae80:
    data,n,ch=[u.reg_read(r) for r in v.R[:3]];assert 1<=n<=330
    self.messages.append((bytes(u.mem_read(data,n)),ch));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
   if pc in {0xbbcc,0xbc00}:u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  super().code(u,pc,size,unused)

m=Machine();m.phase='probe';m.run(0xb974);m.service()
plans=json.loads(args.plan.read_text())
initial=json.loads(args.initial_effects.read_text());assert len(initial)==128
m.u.mem_write(m.preset,bytes(initial));rows=[]
def send(message):
 m.ingress([bytes(message)],0)
 if message[0]==176:m.run(0xb954)
 m.guards();assert not m.flash_operations

for plan in plans:
 fx=plan['expectedHeader'][128:];before=bytes(m.u.mem_read(m.preset,128))
 # Supplement the production plan only with the exact backed-up stock amp
 # selection/parameters, per-patch level and BPM. No USB/system/drum controls.
 messages=[[176,3,fx[3]]]+[[176,23+i,fx[27+i]] for i in range(8)]+[[176,73,fx[84]],[240,67,88,112,3,1,fx[86],fx[87],fx[85],247]]
 for msg in messages:send(msg)
 actual=bytes(m.u.mem_read(m.preset,128));allowed={3,84,85,86,87}|set(range(27,35))
 assert all(actual[i]==before[i] for i in range(128) if i not in allowed)
 assert all(actual[i]==fx[i] for i in allowed),[(i,actual[i],fx[i]) for i in allowed if actual[i]!=fx[i]]
 for cc,value in plan['controls']:send([176,cc,value])
 send([240,67,88,112,13,1,9]+plan['order']+[247])
 got=list(m.u.mem_read(m.preset,128))
 assert got==fx,[(i,a,b) for i,(a,b) in enumerate(zip(got,fx)) if a!=b]
 rows.append({'slot':plan['slot'],'all128BytesMatch':True,'supplementalMessages':len(messages)})
report={'status':'PASS_NAMLNK12_RESTORE_SUPPLEMENT_ARM','elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'cases':rows,'stockIngress':True,'noPersistentWrites':True,'noOutputEnable':True,'onlyDocumentedPresetFieldsChanged':True,'device_access':False}
args.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
