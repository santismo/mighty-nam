#!/usr/bin/env python3
"""Real compiled boot, settings, buffer and USB/BLE command paths; no hardware."""
import argparse,hashlib,json,sys,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'hardware'))
from harness import setup
p=argparse.ArgumentParser()
for n in ['baseline','payload','output','bank']:p.add_argument(n,type=Path)
a=p.parse_args();M,v,s,preset,input_block,model_slot=setup(a.baseline,a.payload,a.output)
m=M();bank=a.bank.read_bytes();m.u.mem_write(0x30384000,bank);m.restart();m.service();m.initialize_usb();m.arm()
tick=0
def run():
 global tick
 tick+=1;m.process(tick,[0.]*8)
def state():
 error,w=m.loop_request(0,6);assert not error;return w

def set_(op,arg,channel=0):
 error,sequence=m.loop_request(op,arg,channel);assert not error,(op,arg,error)
 run();w=state();assert w[4]==sequence[0] and not w[3] and not(w[5]&255),w
 return w
assert state()[6]==50|(100<<8)|(30<<16)
set_(2,47);set_(3,63);set_(4,60)
assert not state()[6]>>24
# Live changes do not write; restart returns defaults.
m.restart();m.service();m.initialize_usb();assert state()[6]==50|(100<<8)|(30<<16)
set_(2,47);set_(3,63);set_(4,60)
before=bytes(m.u.mem_read(0x30384000,len(bank)))
set_(5,1,1);assert state()[6]==47|(63<<8)|(60<<16)|(1<<24)
assert m.get(v.sym['mpp_listen_enabled'])==1
m.restart();m.service();m.initialize_usb();assert state()[6]==47|(63<<8)|(60<<16)|(1<<24)
assert m.get(v.sym['mpp_listen_enabled'])==1
# Global audio-buffer writes preserve independently saved looper settings.
for samples in [16,32,8]:
 m.call(v.sym['mpp_global_buffer_set'],[samples]);assert m.page(24)[1]&255==samples
 m.restart();m.service();m.initialize_usb();assert state()[6]==47|(63<<8)|(60<<16)|(1<<24)
 assert m.page(24)[1]&255==samples
set_(3,31);assert not state()[6]>>24
m.call(v.sym['mpp_global_buffer_set'],[16]);m.restart();m.service();m.initialize_usb()
assert state()[6]==47|(63<<8)|(60<<16)|(1<<24),'Buffer write persisted an unsaved loop level'
# Saving is explicitly refused while armed or while an existing take is kept.
set_(1,1);assert m.loop_request(5,1)[0]==2
set_(1,5);set_(5,1)
assert bytes(m.u.mem_read(0x30384000,len(bank)))==before
assert not m.words()[4] and not m.diag()[3]
r=dict(status='PASS_OFFLINE_ARM_LOOP_SETTINGS',elf_sha256=hashlib.sha256((a.output/'build/loop-startup-test.elf').read_bytes()).hexdigest(),live_unsaved_restart=True,saved_threshold_level_duration_restart=True,global_buffer_preserved=True,unsaved_level_not_saved_by_buffer=True,armed_save_rejected=True,presets_unchanged=True,playback_state_preserved=True,USB_BLE_save=True,device_access=False)
(a.output/'settings.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
