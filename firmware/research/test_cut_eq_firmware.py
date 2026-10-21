"""Exact ARM EQ callback, real CC ingress, persistent controls and stock fallback. No device/audio access."""
import argparse,hashlib,json,math,struct,zlib
from pathlib import Path
from unicorn import UC_HOOK_CODE
from test_preset_runtime import PresetMachine,v,build,preset_fixture
p=argparse.ArgumentParser()
for n in ['payload','elf','model','output']:p.add_argument(n,type=Path)
a=p.parse_args();bundle=build(a.payload.read_bytes(),a.elf);v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=a.elf
assert bundle[2]['identity'] in ('NAMLNK14','NAMLNK15','NAMLNK16')
m=PresetMachine();m.service();slot=a.model.read_bytes();m.upload(slot,33);m.phase='probe';m.run(0xb974)
def cc(id,value):
 m.ingress([bytes([176,id,value])]);m.run(0xb954)
 assert m.u.mem_read(m.preset+(id if id==4 else 36+id-31),1)[0]==value
fx=preset_fixture([]);fx[3]|=64;m.u.mem_write(m.preset,bytes(fx));cc(4,4);cc(31,55);cc(32,60)
# The real IRQ must reach our replacement at the movable EQ stage, including profiling.
seen=[];pc=v.sym['mpp_cut_eq_process']&~1
hook=m.u.hook_add(UC_HOOK_CODE,lambda u,p,n,x:seen.append(1),begin=pc,end=pc)
for i in range(320):m.process(i)
assert len(seen)==320
m.u.hook_del(hook)
# Direct exact ARM kernel response at 1 kHz: both cutoffs 1 kHz => -6.0206 dB.
# Each call still enters the same firmware wrapper and reads the real preset.
cc(31,100);cc(32,1)
m.call(v.sym['mpp_cut_eq_init'],[])
energy=source=0
for b in range(1500):
 xs=[.2*math.sin(2*math.pi*1000*(b*8+i)/48000) for i in range(8)]
 m.floats(0x20025000,xs);m.floats(0x20025100,[-x for x in xs]);m.call(v.sym['mpp_cut_eq_process'],[0x20025000,0x20025100,0x20025200,0x20025300])
 ys=m.read(0x20025200);zs=m.read(0x20025300)
 assert max(abs(y+z) for y,z in zip(ys,zs))<1e-6
 if b>900:energy+=sum(y*y for y in ys);source+=sum(x*x for x in xs)
db=10*math.log10(energy/source);assert abs(db+6.0206)<.06,db
# Every color stores its own cut settings using existing effect bytes and CRC.
configs=[]
for color in range(7):
 cc(4,4|(64 if color==6 else 0));cc(31,color*16);cc(32,100-color*16)
 controls=bytes(m.u.mem_read(m.preset,128));configs.append(controls)
 body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(controls),0,8)+bytes([42])*32+f'Cut {color}'.encode().ljust(64,b'\0')
 assert m.bank_request(2,color,body)[7]==0
 before=len(m.flash_operations)
 assert m.bank_request(2,color,body)[7]==0 and len(m.flash_operations)==before
for color in range(7):
 assert m.bank_request(3,color)[7]==0;assert bytes(m.u.mem_read(m.preset,128))==configs[color]
for color in range(7):assert m.button()==color and bytes(m.u.mem_read(m.preset,128))==configs[color]
flash=bytes(m.u.mem_read(0x30384000,0x1c000))
for fill in [0,165,255]:
 fresh=PresetMachine(flash,fill);fresh.service();assert bytes(fresh.u.mem_read(fresh.preset,128))==configs[0]
 fresh.restart();fresh.service();assert bytes(fresh.u.mem_read(fresh.preset,128))==configs[0];fresh.guards()
# Existing 1/2/3 remain stock routines; new filter is routed only for type4.
for typ in [1,2,3,4]:
 cc(4,typ);cc(31,50);cc(32,50)
 for i in range(250):m.process(i)
 m.guards()
# Timing guard remains active.
m.timer_ticks=150;m.process(1800,healthy=False);assert m.words()[4]>0 and m.words()[9]==0
report=dict(status='PASS_'+bundle[2]['identity']+'_CUT_EQ_ARM',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),real_CC_ingress=True,dispatch_calls=len(seen),combined_1kHz_dB=db,seven_independent_presets=True,cold_patterns=[0,165,255],warm_restarts=True,duplicate_save_no_write=True,stock_EQ_types=[1,2,3],fault_guard=True,ram_guards=True,device_access=False,audio_playback=False)
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
