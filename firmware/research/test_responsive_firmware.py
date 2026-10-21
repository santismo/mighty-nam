import json,struct,math,zlib,hashlib,argparse
from pathlib import Path
from test_preset_runtime import PresetMachine,v,build,preset_fixture,BANK,BANK_END
from test_link_firmware import unpack
from a2_storage import model_slot
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC
p=argparse.ArgumentParser(description='NAMLNK15 button, idle FX and compact tuner ARM checks; no device/audio access.')
for key in ['payload','elf','model','output_dir']:p.add_argument(key,type=Path)
a=p.parse_args();elf=a.elf;payload=a.payload;a.output_dir.mkdir(parents=True,exist_ok=True)
v.configure(payload,True,candidate_bundle=build(payload.read_bytes(),elf));v.elf_path=elf
m=PresetMachine();m.service();slot=model_slot(a.model);m.upload(slot,551)
effects=bytearray(preset_fixture([]));m.u.mem_write(m.preset,bytes(effects))
body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(effects),1,8)+hashlib.sha256(slot).digest()+b'Only Green'.ljust(64,b'\0')
assert m.bank_request(2,0,body,1)[7]==0
flash=bytes(m.u.mem_read(BANK,BANK_END-BANK));n=PresetMachine(flash);n.service()
for i in range(1300):n.process(i)
# Keep unsaved parameters and model history when the stock button wraps to itself.
n.u.mem_write(n.preset+20,b'\x34');before=bytes(n.u.mem_read(n.preset,128));words=n.words();listen=n.page(23)
assert n.button()==0
assert bytes(n.u.mem_read(n.preset,128))==before and n.words()[5:8]==words[5:8] and n.page(23)==listen
assert n.words()[9]==1 and n.get(v.sym['mpp_listen_warm'])==0
# Repeated button requests before foreground service preserve original listening intent.
n.call(v.sym['mpp_bank_request'],[1]);n.call(v.sym['mpp_bank_request'],[0]);n.service();assert n.page(23)==(0,3)
print('PASS single-color PRESET keeps live audio, model state and unsaved effects',flush=True)
# Idle FX skips dispatch entirely, re-enables, then becomes idle after fade.
entries=[0]
def observe(u,pc,size,unused):entries[0]+=1
hook=n.u.hook_add(UC_HOOK_CODE,observe,begin=v.sym['mpp_fx_before']&~1,end=v.sym['mpp_fx_before']&~1)
for i in range(20):n.process(1400+i)
assert entries[0]==0 and n.get(v.sym['mpp_fx_active'])==0
config=[1,1,2,12,100,30,50,0,50,50,0,0,0,0,0,0,2,0,3,12,100,30,50,0,50,50,0,0,0,0,0,0]
def fx(c):
 q=bytes([240,67,88,112,4,2,78,70,1,1,0,61,0,0]+[(n.words()[5]>>(7*i))&127 for i in range(5)]+c+[247]);assert n.ingress([q])[0][0][13]==0
fx(config)
for i in range(50):n.process(1420+i)
assert entries[0]>0;config[1]=0;fx(config)
for i in range(70):n.process(1470+i)
assert n.get(v.sym['mpp_fx_active'])==0
count=entries[0]
for i in range(20):n.process(1540+i)
assert entries[0]==count;n.u.hook_del(hook)
print('PASS bypassed FX engine dispatch: zero calls, wake and settled sleep',flush=True)
n.arm(False);messages=[]
def query(op,ch=1):
 nonce=401+op;q=bytes([240,67,88,112,4,2,78,85,1,op,0,nonce&127,nonce>>7,247]);replies=n.ingress([q],ch,start=2045);assert len(replies)==1
 wire=replies[0][0];assert len(wire)==42 and wire[:9]==bytes([240,67,88,112,4,2,78,86,2]);raw=unpack(wire[9:-1]);assert len(raw)==28 and zlib.crc32(raw[:24])==struct.unpack_from('<I',raw,24)[0]
 messages.append(dict(request=list(q),wire=list(wire)));return raw
assert query(3)[7]==0 and query(4)[7]==1
rows=[]
for hz in [82.4069,110,329.6276,0]:
 start=query(3)
 for block in range(512):n.process(block,[.25*math.sin(2*math.pi*hz*(block*8+i)/48000) for i in range(8)])
 result=query(4);assert result[7]==0 and result[12:16]==start[12:16]
 actual=struct.unpack_from('<I',result,16)[0]/1000
 if hz:assert abs(1200*math.log2(actual/hz))<1,(hz,actual)
 else:assert actual==0
 assert query(4)==result;rows.append(dict(input=hz,detected=actual));print('PASS ARM compact tuner',hz,actual,flush=True)
assert query(5)[7]==0 and query(4)[7]==1
n.arm();assert query(3)[7]==3;n.arm(False);n.guards()
(a.output_dir/'compact-wire.json').write_text(json.dumps(messages))
report=dict(status='PASS_'+v.plan['identity']+'_RESPONSIVE_ARM',elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),single_preset_no_reload=True,unsaved_settings_preserved=True,idle_fx_zero_dispatch=True,wake_and_fade_sleep=True,compact_tuner=rows,one_42_byte_reply_per_request=True,stale_generation_and_muted_only=True,physical_latency_measured=False,device_access=False,audio_playback=False)
(a.output_dir/'responsive.json').write_text(json.dumps(report,indent=2)+'\n')
