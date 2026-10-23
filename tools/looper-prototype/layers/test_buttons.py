#!/usr/bin/env python3
"""Execute the exact stock scanner, patched dispatcher and RGB tails offline."""
import argparse,sys,json,struct,hashlib,zlib
from pathlib import Path
from unicorn import UC_HOOK_MEM_WRITE
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'hardware'))
from harness import setup
p=argparse.ArgumentParser(description=__doc__)
for n in ['baseline','payload','output','model']:p.add_argument(n,type=Path)
a=p.parse_args();M,v,s,preset,input_block,model_slot=setup(a.baseline,a.payload,a.output)
m=M();m.service();m.initialize_usb();slot=model_slot(a.model);m.upload(slot,110)
data=bytearray(preset([8],{8:4}));m.u.mem_write(m.preset,bytes(data))
for color in range(3):
 body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(data),1,8)+hashlib.sha256(slot).digest()+f'Loop buttons {color}'.encode().ljust(64,b'\0')
 assert m.bank_request(2,color,body,nonce=200+color)[7]==0
m.restart();m.service();m.initialize_usb();m.arm()
settings=m.get(0x20014970);keys=0x20005c80;callbacks=v.sym['mpp_link']+12
ms=0;pre=False;power=False
def wait(n):
 global ms
 for _ in range(n):
  ms+=1
  # Exact stock scan uses DR readback. Only PRESET bit7 and POWER bit13
  # are varied; GPIO setup and electrical pin behavior are not modeled here.
  gpio=0xffffffff&~((128 if pre else 0)|(8192 if power else 0))
  m.put(0x40c60000,gpio);m.put(0x40c5c000,0xffffffff);m.put(0x40c68000,0xffffffff)
  before_color=m.u.mem_read(settings+2,1)[0]
  m.run(0x9dd4);m.run(0xa05e)
  if m.u.mem_read(settings+2,1)[0]!=before_color:m.service()
  m.put(callbacks,(ms*6)&0xffffffff);m.arm_loop('mpp_loop_buttons_tick');m.arm_loop('mpp_loop_before_tick')
  assert m.u.mem_read(settings+0x10,1)==b'\0','Tap changed stock mute'
  assert not m.diag()[3]
def tap(is_power,duration=80):
 global pre,power
 if is_power:power=True
 else:pre=True
 wait(duration)
 if is_power:power=False
 else:pre=False
 wait(80)
def double():tap(True);tap(True);wait(310)
def mode():return m.loop_state(9)&1
def color():return m.u.mem_read(settings+2,1)[0]
wait(100)
tap(False);assert color()==1
tap(False);assert color()==2
tap(False);assert color()==0
pre=True;wait(900);pre=False;wait(100);assert color()==0 and m.loop_state(9)&8
tap(False);assert color()==2
double();assert mode()==1 and m.loop_state(3)==0
tap(False);assert m.loop_state(3)==1
# Both LED phases execute the patched entry with real stock RGB-tail writes.
writes=[]
hook=m.u.hook_add(UC_HOOK_MEM_WRITE,lambda u,k,addr,size,value,data:writes.append((addr,value)),begin=0x40c60084,end=0x40c6008b)
try:
 while ms%500>=200:wait(1)
 writes.clear();m.call(0x60ec,[color()]);on=list(writes)
 while ms%500<300:wait(1)
 writes.clear();m.call(0x60ec,[color()]);off=list(writes)
finally:m.u.hook_del(hook)
assert off==[(0x40c60088,0x02404000)] and on!=off and len(on)==3,(on,off)
# A single hold clears instead of firing a tap when released.
pre=True;wait(900);pre=False;wait(150);assert m.loop_state(3)==0 and m.loop_state(0)==0 and mode()==1
tap(False);assert m.loop_state(3)==1
double();assert mode()==0 and m.loop_state(3)==0
# Phone arm, real capture hook, then a short physical PRESET tap. The stock
# scanner already debounces; a second 25 ms window used to discard this tap.
assert m.loop_request(1,1)[0]==0;wait(5);assert mode()==1 and m.loop_state(3)==1
raw=0x20019000;processed=0x20019200
m.u.mem_write(raw,struct.pack('<32i',*([0,0,0,214748364]*8)))
m.u.mem_write(processed,struct.pack('<8f',*([.1]*8)))
for _ in range(70):
 m.arm_loop('mpp_loop_capture',raw,processed,processed,1);m.arm_loop('mpp_loop_tick')
assert m.loop_state(3)==2 and m.loop_state(0)>100
before_color=color();tap(False,12)
assert m.loop_state(3)==3 and color()==before_color
# Long hold after recording still clears; release does not start another loop.
pre=True;wait(900);pre=False;wait(100);assert m.loop_state(3)==0
# Original volume button event and long-POWER shutdown request are preserved.
m.u.mem_write(keys+10,b'\1');before=m.u.mem_read(settings+0x16,1)[0]
m.run(0xa05e);assert m.u.mem_read(settings+0x16,1)[0]==min(before+10,100)
m.u.mem_write(keys+3,b'\1');m.put(keys+0x50,0);m.put(keys+0x28,1501);m.put(keys+0x58,1)
m.run(0xa05e);assert m.u.mem_read(settings+0x1e,1)==b'\1'
m.u.mem_write(settings+0x1e,b'\0')
assert m.get(v.sym['mpp_listen_enabled'])==1
report=dict(status='PASS_OFFLINE_STOCK_BUTTON_LED_ADAPTER',elf_sha256=hashlib.sha256((a.output/'build/loop-startup-test.elf').read_bytes()).hexdigest(),
    forward_colors=[0,1,2,0],reverse_color=2,power_double_enter=True,threshold_arm=True,hold_preset_clear=True,phone_arm_physical_short_tap_finish=True,
    armed_rgb_on_writes=on,armed_rgb_off_writes=off,stock_volume_preserved=True,stock_power_hold_shutdown=True,
    automatic_mute=False,physical_buttons_verified=False,device_access=False,host_audio_access=False)
(a.output/'buttons.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
