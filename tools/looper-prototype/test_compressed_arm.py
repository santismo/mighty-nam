#!/usr/bin/env python3
"""Bounded ARM component parity + actual NAM/stock preset paths, offline only.

Loop memory is deliberately outside the device map. This cannot validate RAM
ownership, interrupts running during flash I/O, or a physical audio deadline.
"""
import argparse,ctypes,hashlib,json,struct,sys,zlib
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE

p=argparse.ArgumentParser(description=__doc__)
for name in ['firmware_work','payload','models','work']:p.add_argument(name,type=Path)
a=p.parse_args();sys.path[:0]=[str(a.firmware_work/'generated/research'),str(a.firmware_work/'generated/tools')]
from test_usb_nam import UsbMachine,v,preset_fixture,input_block,model_slot
from preset_image import build
elf=a.firmware_work/'build/nam-link-offline.elf';v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),elf));v.elf_path=elf
m=UsbMachine();m.service();m.initialize_usb()
models=sorted(a.models.glob('*-lite.nam'));assert len(models)==3
for color,model in enumerate(models):
    slot=model_slot(model);m.upload(slot,900+color)
    data=bytearray(preset_fixture([8] if color else [],{8:4}));data[84]=37;data[70:74]=bytes([20,20,50,0]);m.u.mem_write(m.preset,bytes(data))
    body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(data),1,8)+hashlib.sha256(slot).digest()+f'Loop test {color}'.encode().ljust(64,b'\0')
    assert m.bank_request(2,color,body,nonce=950+color)[7]==0
m.arm();counter=0
for _ in range(1320):m.process(counter,input_block(counter));counter+=1
for start,size in [(0x10000000,65536),(0x21000000,65536),(0x21100000,4096),(0x21200000,0x100000)]:m.u.mem_map(start,size)
with (a.work/'loop-emulator-only.elf').open('rb') as f:
    e=ELFFile(f);symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols() if s.name}
    for s in e.iter_sections():
        if s['sh_flags']&2 and s['sh_size'] and s['sh_type']!='SHT_NOBITS':m.u.mem_write(s['sh_addr'],s.data())
native=ctypes.CDLL(str((a.work/'loop-native.dylib').resolve()))
U=ctypes.c_uint;P=ctypes.c_void_p;F=ctypes.c_float
for name,args in [('lp_init',[P,U,U,U]),('lp_command',[U]),('lp_fixture_play',[U]),('lp_fixture_block',[U]),('lp_state',[U]),('lp_process8',[P,P,P,U])]:
    f=getattr(native,name);f.argtypes=args;f.restype=U if name=='lp_state' else None
def arm(name,*args):m.call(symbols[name],list(args));return m.u.reg_read(v.R[0])
def command(value):arm('lp_command',value);native.lp_command(value)
def states():
    x=[arm('lp_state',i) for i in range(8)];assert x==[native.lp_state(i) for i in range(8)];return x
storage=0x21200010;bytes_needed=371316
host=(ctypes.c_uint8*bytes_needed)()
m.u.mem_write(storage-16,b'\xa5'*16);m.u.mem_write(storage+bytes_needed,b'\x5a'*16)
def initialize(rate=24000,frames=720000):
    native.lp_init(host,bytes_needed,rate,frames);arm('lp_init',storage,bytes_needed,rate,frames)
max_error=0.;counts={};total_blocks=0
def loop_block(raw,guitar,ready,label=None):
    global max_error,total_blocks
    raw=(F*8)(*raw);guitar=(F*8)(*guitar);expected=(F*16)()
    native.lp_process8(raw,guitar,expected,ready)
    m.u.mem_write(0x21100000,bytes(raw));m.u.mem_write(0x21100020,bytes(guitar))
    count=[0];hook=None
    if label:hook=m.u.hook_add(UC_HOOK_CODE,lambda *args:count.__setitem__(0,count[0]+1))
    arm('lp_process8',0x21100000,0x21100020,0x21100040,int(ready))
    if hook:m.u.hook_del(hook);counts[label]=max(counts.get(label,0),count[0])
    actual=struct.unpack('<16f',m.u.mem_read(0x21100040,64));error=max(abs(x-y) for x,y in zip(actual,expected));max_error=max(max_error,error)
    assert error<2e-6,(error,actual,list(expected));assert not arm('lp_state',6);total_blocks+=1
def guards():
    assert m.u.mem_read(storage-16,16)==b'\xa5'*16 and m.u.mem_read(storage+bytes_needed,16)==b'\x5a'*16
    m.guards()
# Real ARM NAM + stock spring output feeds the recorder; both sides receive the
# same mono fold-down, so parity tests loop math independently of NAM roundoff.
initialize();command(0)
for i in range(160):
    xs=input_block(counter);ys=m.process(counter,xs);counter+=1
    mono=[(ys[j]+ys[j+8])*.5 for j in range(8)]
    loop_block([0.]*8 if i<16 else [.1]*8,mono,True,'record_arm' if i==15 else 'record_trigger_64_preroll' if i==16 else 'record_steady' if i>16 and i%16==0 else None)
command(1);states();assert bytes(m.u.mem_read(storage,bytes_needed))==bytes(host)
command(2);frozen=bytes(m.u.mem_read(storage,bytes_needed));recalls=[]
for color in [0,1,2,0]:
    before=states();assert m.bank_request(3,color,nonce=1000+color)[7]==0;m.service();assert states()==before
    # The callback is NOT run inside the masked flash driver. That unresolved
    # scheduling gap must not be misrepresented as glitch-free hardware recall.
    for i in range(1320):
        xs=input_block(counter);ys=m.process(counter,xs);counter+=1
        ready=not bool(m.get(v.sym['mpp_listen_warm']))
        loop_block(xs,[(ys[j]+ys[j+8])*.5 for j in range(8)],ready,'play_after_recall' if i in (0,1201,1319) else None)
    assert bytes(m.u.mem_read(storage,bytes_needed))==frozen and m.words()[4]==0
    assert states()[5]-before[5]==1320*8
    recalls.append(dict(color=color,callbacks=1320,store_unchanged=True,playback_frames=1320*8))
    print('Actual ARM preset recall',color,'and independent loop state PASS',flush=True)
# Full 30-second storage fixture: exercise first/last block and wrap on ARM.
initialize();full=(a.work/'record24.blocks').read_bytes();assert len(full)==bytes_needed
m.u.mem_write(storage,full);ctypes.memmove(host,full,len(full));arm('lp_fixture_play',720000);native.lp_fixture_play(720000)
for position in [0,719872]:
    arm('lp_fixture_block',position);native.lp_fixture_block(position)
    for i in range(80):loop_block([0.]*8,[.03125]*8,True,'play_wrap' if i in (0,31,32,33,79) else None)
    states()
assert bytes(m.u.mem_read(storage,bytes_needed))==full
command(1);before=states()
for _ in range(20):loop_block([0.]*8,[.1]*8,True,'paused')
assert states()==before;command(1);loop_block([0.]*8,[.1]*8,True,'resume');command(3);loop_block([0.]*8,[.1]*8,True,'stopped')
guards()
result=dict(status='PASS_BOUNDED_ARM_COMPRESSED_LOOP',firmware_elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
    loop_elf_sha256=hashlib.sha256((a.work/'loop-emulator-only.elf').read_bytes()).hexdigest(),
    loop_ARM_state_bytes=arm('lp_state',8),control_ARM_state_bytes=arm('lp_state',9),
    callback_frames=8,live_rate=48000,recorded_loop_rate=24000,loop_callbacks=total_blocks,
    actual_preset_recalls=recalls,full_duration_fixture_samples=720000,
    max_native_ARM_sample_error=max_error,modeled_instructions_per_loop_callback=counts,
    storage_guards_intact=True,device_access=False,audio_device_opened=False,
    limitations=['Artificial emulator RAM, not device placement.',
        'Loop mixer is called separately after the stock IRQ, not patched into firmware.',
        'Actual stock flash reads remain IRQ-masked; no loop callback occurs during them.',
        'Instruction counts are NOT Cortex-M7 cycles or deadline verification.',
        'Full 30s duration runs natively; ARM tests bounded windows and wrap plus actual NAM/preset paths.'])
(a.work/'compressed-arm.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],flush=True)
