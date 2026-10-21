"""Execute global buffer storage, physical-button branch and output intent on ARM; no device/audio."""
import argparse,hashlib,json,struct,zlib
from pathlib import Path
from test_preset_runtime import PresetMachine,v,build,preset_fixture,model_slot,BANK,BANK_END
p=argparse.ArgumentParser(description=__doc__)
for key in ['payload','elf','model','output']:p.add_argument(key,type=Path)
a=p.parse_args();bundle=build(a.payload.read_bytes(),a.elf);assert bundle[2]['identity']=='NAMLNK18';v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=a.elf
m=PresetMachine(path=a.model);m.service();assert m.page(24)==(0,(48000<<16)|(2<<8)|8)
def command(samples):return bytes([240,67,88,112,4,2,78,66,samples,247])
def status(m):
 error,word=m.page(24);assert error==0 and word>>16==48000 and (word>>8)&15==2
 return word&255,(word>>12)&15
def flash(m):return bytes(m.u.mem_read(BANK,0x303a6000-BANK))
# Persist even before any saved capture; never touch the preset/code ranges.
m.ingress([command(16)]);assert status(m)==(16,0) and not (m.page(23)[1]&1)
n=PresetMachine(flash(m),0xff,path=a.model);n.service();assert status(n)==(16,0)
model=model_slot(a.model);m.upload(model,501);m.ingress([command(8)])
for slot in range(7):
 fx=bytes(preset_fixture([]));m.u.mem_write(m.preset,fx)
 body=struct.pack('<4I',zlib.crc32(model),zlib.crc32(fx),1,8)+hashlib.sha256(model).digest()+f'Global {slot}'.encode().ljust(64,b'\0')
 assert m.bank_request(2,slot,body,channel=slot%2)[7]==0
bank_before=bytes(m.u.mem_read(BANK,BANK_END-BANK));model_before=m.words()[5:7];cycles=0
for enabled in [False,True]:
 m.arm(enabled)
 for size in [16,32,8,16]:
  m.ingress([command(size)],channel=cycles%2);assert status(m)==(size,0) and bool(m.page(23)[1]&1)==enabled
  assert m.words()[5:7]==model_before and bytes(m.u.mem_read(BANK,BANK_END-BANK))==bank_before
  writes=len(m.flash_operations);m.ingress([command(size)]);assert len(m.flash_operations)==writes
  for slot in range(7):
   reply=m.bank_request(3,slot,channel=slot%2);assert reply[7]==0 and struct.unpack_from('<I',reply,40)[0]==size and status(m)==(size,0) and bool(m.page(23)[1]&1)==enabled
   assert m.words()[5]==zlib.crc32(model)
  model_before=m.words()[5:7];cycles+=1
# The same hardware-button branch must keep the global buffer for each color.
for slot in range(7):assert m.button()==slot and status(m)==(16,0)
for fill in [0,0xa5,0xff]:
 n=PresetMachine(flash(m),fill,path=a.model);n.service();assert status(n)==(16,0) and n.page(23)[1]&1
 n.restart();n.service();assert status(n)==(16,0) and n.page(23)[1]&1
# Saving another preset resumes the previous listening intent.
m.arm();fx=bytes(m.u.mem_read(m.preset,128));body=struct.pack('<4I',m.words()[5],zlib.crc32(fx),1,16)+hashlib.sha256(model).digest()+b'Playing save'.ljust(64,b'\0')
assert m.bank_request(2,0,body)[7]==0 and m.page(23)[1]&1
before=flash(m);m.fail_write=True;m.ingress([command(32)]);assert status(m)==(16,3) and m.page(23)[1]&1 and flash(m)==before
m.fail_write=False;m.ingress([command(32)]);assert status(m)==(32,0) and m.page(23)[1]&1
for value in [0,4,9,64,127]:
 before=flash(m);m.ingress([command(value)]);assert status(m)==(32,0) and m.page(23)[1]&1 and before==flash(m)
m.put(0xe000ed04,16);m.query(command(8));m.put(0xe000ed04,0);assert status(m)==(32,0)
# Capture transfers remain transiently muted; the controller restores intent
# only after validating the complete new model and effect chain.
for block in range(1350):m.process(block)
m.guards();m.timer_ticks=150;m.process(1350,healthy=False);assert m.words()[4]>0 and not m.words()[9] and not (m.page(23)[1]&1)
report=dict(status='PASS_NAMLNK18_GLOBAL_BUFFER_ARM',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),empty_bank_persistence=True,seven_color_global_recall=True,physical_button_branch_keeps_global=True,cold_patterns=[0,165,255],warm_restarts=3,settings_changes_do_not_write_presets=True,buffer_and_save_preserve_listening_intent=True,duplicate_setting_no_writes=True,failed_write_visible_and_old_setting_retained=True,fault_still_mutes=True,invalid_commands_ignored=True,settings_flash_bounds=['0x303a4000','0x303a6000'],hardware_access=False,host_audio=False)
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
