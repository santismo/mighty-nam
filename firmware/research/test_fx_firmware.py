import json,struct,zlib,hashlib,math,argparse
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR
from test_preset_runtime import PresetMachine,v,build
from test_link_firmware import pack,unpack
p=argparse.ArgumentParser(description='CPU-only dual FX, presets and paged Bluetooth protocol checks.')
for key in ['payload','elf','packed_model','output']:p.add_argument(key,type=Path)
a=p.parse_args();elf=a.elf;payload=a.payload
v.configure(payload,True,candidate_bundle=build(payload.read_bytes(),elf));v.elf_path=elf
class Machine(PresetMachine):
 def code(self,u,pc,size,unused):
  if self.phase=='probe' and pc==0xae80:
   data,n,ch=[u.reg_read(r) for r in v.R[:3]];assert 1<=n<=330
   if ch==1:assert n<=65,('Large Bluetooth frame',n)
   self.messages.append((bytes(u.mem_read(data,n)),ch));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  super().code(u,pc,size,unused)
 def wire(self,command,ch=1):
  replies=self.ingress([bytes(command)],channel=ch,start=2045);assert len(replies)==1,(command,replies)
  wire=replies[0][0]
  if wire[6:9]==b'NR\x01':
   generation=wire[9:11];pages=wire[12];total=wire[13]+128*wire[14];body=wire[15:-1]
   assert wire[11]==0
   for page in range(1,pages):
    request=bytes([240,67,88,112,4,2,78,82,1])+generation+bytes([page,247])
    result=self.ingress([request],channel=ch);assert len(result)==1
    part=result[0][0];assert part[9:11]==generation and part[11]==page and part[12]==pages and len(part)<=56
    body+=part[15:-1]
   assert len(body)==total;wire=b'\xf0'+body+b'\xf7'
  return wire
 def fx_command(self,op=0,slot=0,cfg=None):
  request=[240,67,88,112,4,2,78,70,1,op,slot,57,1]
  if op==1:request += [0]+[(self.words()[5]>>(7*i))&127 for i in range(5)]+list(cfg)
  response=self.wire(request+[247]);assert len(response)==48 and response[13]==0,(request,response)
  return list(response[15:47])
 def bank(self,op,slot,body=b'',ch=1):
  raw=struct.pack('<IBBBB I HBB',0x3031504e,1,op,slot,0,123,len(body),0,0)+body;raw+=struct.pack('<I',zlib.crc32(raw))
  response=self.wire(b'\xf0\x43\x58\x70\x04\x02NS\x01'+pack(raw)+b'\xf7',ch)
  raw=unpack(response[9:-1]);assert len(raw)==276 and raw[7]==0 and zlib.crc32(raw[:272])==struct.unpack_from('<I',raw,272)[0]
  return raw
m=Machine();m.service();defaults=m.fx_command(slot=127);assert defaults[1]==defaults[17]==0
slot=a.packed_model.read_bytes();m.upload(slot,123)
fx=list(m.u.mem_read(m.preset,128));fx[3]|=64 # isolate custom effects from NAM for exact dry bypass checks
for i in [1,2,4,5,6,7,8,9]:fx[i]|=64
m.u.mem_write(m.preset,bytes(fx))
# Populate a known color using the existing exact model/effects checksum guards.
body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(bytes(fx)),0,8)+bytes([42])*32+b'FX trial\0'.ljust(64,b'\0')
m.bank(2,0,body);assert m.fx_command(2,0)==defaults
# Move and enable both engines, then save and recall their exact configurations.
c=list(defaults);c[1]=c[17]=1;c[3]=19;c[16]=2;c[2]=10;c[18]=0
assert m.fx_command(1,0,c)==c
m.bank(2,0,body);assert m.fx_command(2,0)==c
m.fx_command(1,0,defaults);m.bank(3,0);assert m.fx_command(0,0)==c
# Observe both actual dispatch entries; MIDI settings never modify stock order.
process=v.sym['_ZN3mpp2fx6Engine7processEPKhPfS4_j'] if '_ZN3mpp2fx6Engine7processEPKhPfS4_j' in v.sym else next(a for n,a in v.sym.items() if 'Engine7process' in n)
seen=[]
def trace(u,pc,size,unused):
 p=u.reg_read(v.R[1]);seen.append(tuple(u.mem_read(p,3)))
hook=m.u.hook_add(UC_HOOK_CODE,trace,begin=process&~1,end=process&~1)
for block in range(350):
 m.process(block,[.1*math.sin(2*math.pi*110*(block*8+i)/48000) for i in range(8)])
 assert not m.words()[4] and m.words()[9]==1
assert len(seen)==700 and seen[0]==(2,1,0) and seen[1]==(1,1,10)
m.u.hook_del(hook);m.guards()
# Tuner's 330-byte reply survives all nine bounded Bluetooth pulls, without audio output.
start=m.wire([240,67,88,112,4,2,78,85,1,1,0,2,1,247]);assert len(start)==330 and unpack(start[9:-1])[7]==0
for i in range(1024):m.process(i,healthy=True)
reply=m.wire([240,67,88,112,4,2,78,85,1,2,15,3,1,247]);assert len(reply)==330 and unpack(reply[9:-1])[7]==0
# Warm restart restores both custom slots and retained capture.
m.restart();m.service();assert m.fx_command(0,0)==c and m.words()[5]==zlib.crc32(slot)
assert not m.get(v.sym['mpp_listen_enabled'])

# Every colored preset retains its own pair through cold and warm starts.
configs=[]
for i in range(7):
 config=list(defaults);config[0]=i+1;config[16]=(i+3)%7+1
 config[1]=config[17]=1;config[3]=i*3;config[2]=i;config[18]=10-i if i!=5 else 0
 m.fx_command(1,m.page(25)[1]&255,config);m.bank(2,i,body);configs.append(config)
 writes=len(m.flash_operations);m.bank(2,i,body);assert len(m.flash_operations)==writes
for i in range(7):
 m.bank(3,i);assert m.fx_command(0,i)==configs[i]
for i in [0,1,2,3,4,5,6]:
 assert m.button()==i;assert m.fx_command(0,i)==configs[i]
flash=bytes(m.u.mem_read(0x30384000,0x1c000))
for fill in [0,165,255]:
 fresh=Machine(flash,fill);fresh.service();assert fresh.fx_command(0,0)==configs[0]
 fresh.restart();fresh.service();assert fresh.fx_command(0,0)==configs[0];fresh.guards()
# Old saved records have FF padding and should load with both new blocks off.
legacy=bytearray(flash)
for offset in range(0,len(legacy),8192):
 if struct.unpack_from('<I',legacy,offset+8188)[0]!=0xffffffff:
  legacy[offset+7808:offset+7844]=bytes([255])*36
  struct.pack_into('<I',legacy,offset+8184,zlib.crc32(legacy[offset:offset+8184]))
fresh=Machine(bytes(legacy));fresh.service();assert fresh.fx_command(0,0)==defaults
report={'status':'PASS_'+v.plan['identity']+'_ARM_FX_AND_PAGED_BLE','elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'dispatch_entries':len(seen),'seven_independent_fx_presets':True,'cold_patterns':[0,165,255],'legacy_preset_defaults':True,'duplicate_fx_saves_no_write':True,'preset_fx_save_recall_restart':True,'stock_order_unchanged':list(m.u.mem_read(m.preset+90,9))==fx[90:99],'tuner_long_reply_reassembled':True,'largest_paged_frame':56,'ram_guards':True,'physical_device_access':False,'audio_playback':False}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report)
