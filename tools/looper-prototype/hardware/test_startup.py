#!/usr/bin/env python3
"""Compiled NAMLNK25 cold/warm startup, diagnostics and negative controls.
Synthetic counter fixtures establish logic only, never M7 execution deadlines.
"""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_MEM_READ,UC_HOOK_CODE
from harness import setup

p=argparse.ArgumentParser(description=__doc__)
for n in ['baseline','payload','output','models']:p.add_argument(n,type=Path)
a=p.parse_args();M,v,s,preset,input_block,model_slot=setup(a.baseline,a.payload,a.output)
m=M(fill=0xa5);m.service();m.initialize_usb()
def fault():return m.diag()[3]
assert m.loop_report()==m.loop_report(1)
assert m.page(24)[1]&255==8
identity=json.loads((a.output/'build/build.json').read_text())['identity']
assert bytes(m.u.mem_read(v.sym['mpp_probe_identity'],8))==identity.encode()
initial=m.diag();print('Cold startup: two complete RAM passes, code copy and inactive loop PASS',flush=True)
models=sorted(a.models.glob('*-lite.nam'));assert len(models)==3
saved=[]
for color,model in enumerate(models):
    slot=model_slot(model);m.upload(slot,100+color)
    data=bytearray(preset([8],{8:4}));data[84]=37;data[70:74]=bytes([20,20,50,0]);m.u.mem_write(m.preset,bytes(data))
    import zlib
    body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(data),1,8)+hashlib.sha256(slot).digest()+f'Loop startup test {color}'.encode().ljust(64,b'\0')
    assert m.bank_request(2,color,body,nonce=200+color)[7]==0;saved.append(body)
assert m.diag()[31]>0 and not fault()
# Warm reboot must reconstruct code/state from flash and forget the RAM loop.
m.u.mem_write(0x20318020,b'\xff'*0x1fc0)
m.restart();m.service();m.initialize_usb();assert m.loop_state(0)==m.loop_state(3)==0
assert m.words()[5]==struct.unpack_from('<I',saved[0])[0] and m.get(v.sym['mpp_listen_enabled'])==1
for expected in [1,2,0]:assert m.button()==expected
for i in range(1450):m.process(i,input_block(i))
assert not fault() and m.diag()[17]>=1450 and m.diag()[25]>0
assert m.loop_report(1)[20]>0
print('Idle saving, warm restart, normal startup playback and preset cycling PASS',flush=True)
# Stale page without a latched snapshot, invalid commands, immutable snapshot.
m.put(s['_ZN12_GLOBAL__N_114snapshot_readyE'],0)
assert m.loop_request(0,1)[0]==2
assert m.loop_request(0,5)[0]==(1 if identity=='NAMLNK25' else 0)
assert m.loop_request(0,7)[0]==1
assert m.loop_request(1,0)[0]==1
first=m.loop_request(0,0)[1]
m.process(1450,input_block(1450));assert m.loop_request(0,1)[0]==0
for channel in [0,1]:
    assert m.loop_request(1,1,channel)[0]==0
    assert m.loop_request(1,1,channel)[0]==2
    # Zero guitar waits at the threshold; pending command is acknowledged in IRQ.
    for i in range(3):m.process(1500+i,[0.]*8)
    assert m.loop_state(3)==1 and m.loop_report()[12]==0 and m.diag()[14]==0
    assert m.loop_request(1,4,channel)[0]==0;m.process(1504,[0.]*8)
    assert m.loop_state(3)==0
print('USB/BLE command mailbox and threshold arming PASS',flush=True)
# Malformed packets must not be acknowledged or queue actions.
good=bytearray([240,67,88,112,4,2,78,79,1,1,1,73,0,247])
for packet in [good[:-1],good[:9]+good[-1:],good[:8]+bytes([2])+good[9:],good[:11]+bytes([0,0,247])]:
    assert m.ingress([bytes(packet)])==[]
assert m.loop_report()[12]==0
print('Malformed diagnostic packets rejected PASS',flush=True)
# Each fault disables only the looper. Guitar remains running and output armed.
negative=[]
def check_disabled(label,flag):
    assert fault()&flag,(label,m.diag())
    assert m.loop_request(1,1)[0]==3
    y=m.process(1700,input_block(1700))
    assert any(y) and m.words()[4]==0 and m.words()[9]==1 and m.get(v.sym['mpp_listen_enabled'])==1
    negative.append(dict(case=label,fault=fault(),guitar_running=True,output_armed=True))
address=0x202a0020
m.arm_loop('mpp_loop_boot')
m.u.mem_write(address,b'\0'*4);m.service();check_disabled('idle ownership overwrite',8)
m.arm_loop('mpp_loop_boot')
m.u.mem_write(address-32,b'\0'*4);m.process(1701,input_block(1701));check_disabled('guard overwrite',4)
m.arm_loop('mpp_loop_boot')
end=s['__loop_code_end'];source=s['__loop_code_load']+end-s['__loop_code_start']-4
original=bytes(m.u.mem_read(source,4));m.u.mem_write(source,b'\0'*4)
m.arm_loop('mpp_loop_boot');m.u.mem_write(source,original);check_disabled('startup code copy mismatch',1)
# Force a bus-read mismatch after each pattern fill. Do not bypass the checker.
def corrupt(u,kind,addr,size,value,user):u.mem_write(addr,b'\0'*4)
hook=m.u.hook_add(UC_HOOK_MEM_READ,corrupt,begin=address,end=address+3)
try:m.arm_loop('mpp_loop_boot')
finally:m.u.hook_del(hook)
check_disabled('RAM readback mismatch',2)
m.arm_loop('mpp_loop_boot');assert not fault()
# Model an IRQ publishing "touched" and recording bytes during an idle sweep.
# The new read must not be mistaken for foreign RAM ownership. The separate
# ownership-overwrite negative control above still has to fail closed.
if identity in ['NAMLNK26','NAMLNK27','NAMLNK28']:
    def arm_during_read(u,kind,addr,size,value,user):
        u.mem_write(s['_ZN12_GLOBAL__N_17touchedE'],b'\1');u.mem_write(addr,b'\0'*4)
    hook=m.u.hook_add(UC_HOOK_MEM_READ,arm_during_read,begin=address,end=address+3)
    try:m.service()
    finally:m.u.hook_del(hook)
    assert not fault(),'Arming during idle audit caused a false ownership fault'
    m.arm_loop('mpp_loop_boot')
# An entire idle sweep verifies both noncontiguous buffers after stock services.
for _ in range(1451):m.service()
assert m.diag()[7]>=1 and not fault()
print('RAM/copy/guard negative controls and full idle sweep PASS',flush=True)
# Isolate the compiled timing wrapper with an explicitly stubbed inner IRQ.
# This checks wrap/reset/disabled-counter logic, not DSP time or ISR overhead.
entry=s['mpp_base_irq']&~1;previous=bytes(m.u.mem_read(entry,2))
m.u.mem_write(entry,bytes.fromhex('7047'));m.u.ctl_flush_tb()
timing=[]
try:
    m.synthetic_cycle=0xfffffc00
    accepted=m.diag()[17];m.arm_loop('mpp_loop_irq')
    assert m.diag()[17]==accepted+1 and m.diag()[19]==1000
    timing.append('32-bit cycle wrap accepted')
    m.put(0xe0001000,0);rejected=m.diag()[18];m.arm_loop('mpp_loop_irq')
    assert m.diag()[18]==rejected+1 and m.diag()[17]==accepted+1
    timing.append('disabled cycle counter rejected');m.put(0xe0001000,1)
    def reset_epoch(*args):m.put(v.sym['mpp_dwt_reset_epoch'],m.get(v.sym['mpp_dwt_reset_epoch'])+1)
    hook=m.u.hook_add(UC_HOOK_CODE,reset_epoch,begin=entry,end=entry)
    try:m.arm_loop('mpp_loop_irq')
    finally:m.u.hook_del(hook)
    assert m.diag()[18]==rejected+2 and m.diag()[26]==1
    timing.append('counter reset during IRQ rejected')
finally:m.u.mem_write(entry,previous);m.u.ctl_flush_tb()
m.process(1800,input_block(1800));assert not m.words()[4]
print('Compiled timing wrap/reset/disabled-counter negative controls PASS',flush=True)
report=dict(status='PASS_OFFLINE_LOOP_STARTUP',elf_sha256=hashlib.sha256((a.output/'build/loop-startup-test.elf').read_bytes()).hexdigest(),
    candidate_payload_sha256=v.plan['candidate_sha256'],startup_bytes_checked=initial[5],startup_pattern_passes=initial[6],
    startup_code_hash=initial[34],loop_state_bytes=initial[15],cold_fill=165,warm_dirty_state_cleared=True,
    boot_events=m.loop_boot_events,normal_output_on_after_restart=True,preset_colors_cycled=[1,2,0],
    idle_preset_save_supported=True,USB_BLE_mailbox=True,malformed_packets_rejected=True,negative_controls=negative,arm_during_idle_sweep_safe=identity in ['NAMLNK26','NAMLNK27','NAMLNK28'],
    idle_full_sweeps=m.diag()[7],startup_cache_operations_recorded=len([x for x in m.stock_writes if x[0] in (0xe000ef68,0xe000ef70,0xe000ef50)]),
    timing_negative_controls=timing,synthetic_timing_only=True,physical_RAM_safe_proven=False,device_access=False,host_audio_access=False,flashed=False)
(a.output/'startup.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'],flush=True)
