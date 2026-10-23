"""Bounded candidate-RAM ownership audit. Local files + ARM CPU emulator only."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
from collections import Counter
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_PC
p=argparse.ArgumentParser(description=__doc__)
for n in ['baseline','payload','models','output']:p.add_argument(n,type=Path)
a=p.parse_args();sys.path[:0]=[str(a.baseline/'generated/research'),str(a.baseline/'generated/tools')]
from test_usb_nam import UsbMachine,v,preset_fixture,input_block,model_slot
from preset_image import build
from test_dma_current_prototype import fx_pair
elf=a.baseline/'build/nam-link-offline.elf';raw=a.payload.read_bytes()
v.configure(a.payload,True,candidate_bundle=build(raw,elf));v.elf_path=elf
m=UsbMachine();m.service();m.initialize_usb();m.upload(model_slot(sorted(a.models.glob('*-lite.nam'))[0]),901);m.arm()
regions=[('store1',0x202a0000,0x202e2040),('overlay',0x20314000,0x2031a000),('store2',0x2031c000,0x20334ac0)]
phase='startup';accesses=[];helpers=Counter();spans=[]
class OwnershipError(Exception):pass
def watch(u,kind,addr,n,val,user):
    row=dict(phase=phase,pc=hex(u.reg_read(UC_ARM_REG_PC)),address=hex(addr),bytes=n,write=kind==UC_MEM_WRITE)
    accesses.append(row);raise OwnershipError(str(row))
for name,lo,hi in regions:
    m.u.mem_write(lo,b'\xa5'*(hi-lo))
    m.u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,watch,begin=lo,end=hi-1)
def helper(u,pc,size,user):
    destination=u.reg_read(v.R[0]);n=u.reg_read(v.R[1 if pc==0x556c else 2]);helpers[hex(pc)]+=1
    if n and 0x20200000<=destination<0x20400000:
        spans.append((destination,destination+n))
        assert not any(destination<hi and destination+n>lo for _,lo,hi in regions),(phase,hex(pc),hex(destination),n)
for pc in [0x54bc,0x54dc,0x556c]:m.u.hook_add(UC_HOOK_CODE,helper,begin=pc,end=pc)
counter=0;cases=[]
for stage,count in [(1,3),(2,14),(4,4),(5,1),(6,13),(7,5),(8,6),(9,34)]:
    for typ in range(1,count+1):
        phase=f'loader {stage}:{typ}';data=bytearray(preset_fixture([stage],{stage:typ}));data[84]=37
        # Max delay/reverb/modulation lengths exercise allocation and tails.
        data[54:60]=bytes([95,100,90,85,100,90]);data[61:69]=bytes([100,95,85,100,90,95,100,85]);data[70:74]=bytes([85,100,95,90])
        m.u.mem_write(m.preset,bytes(data))
        for _ in range(10):m.process(counter,input_block(counter));counter+=1
        cases.append([stage,typ]);assert m.words()[4]==0
    print('Candidate RAM loader group',stage,count,'PASS',flush=True)
for label,enabled,types,pair in [
    ('long delay reverb',[7,8],{7:3,8:5},None),
    ('full stock',[1,2,4,5,6,7,8,9],{2:14,4:4,8:4,9:34},None),
    ('pitch wah',[8],{8:4},(1,2)),('modulation',[8],{8:6},(5,6))]:
    phase=label;data=bytearray(preset_fixture(enabled,types));data[84]=37
    data[61:69]=bytes([100,95,85,100,90,95,100,85]);data[70:74]=bytes([85,100,95,90])
    m.u.mem_write(m.preset,bytes(data))
    if pair:fx_pair(m,pair)
    for _ in range(1500):m.process(counter,input_block(counter));counter+=1
    assert m.words()[4]==0;m.guards();print('Candidate RAM',label,'PASS',flush=True)
assert not accesses
for _,lo,hi in regions:assert bytes(m.u.mem_read(lo,hi-lo))==b'\xa5'*(hi-lo)
# Negative control: real CPU STR into each reserve must be caught by watcher.
testcode=0x24000;m.u.mem_write(testcode,bytes.fromhex('01607047')) # str r1,[r0]; bx lr
for name,lo,hi in regions:
    phase='intentional guard negative control '+name
    try:m.call(testcode,[lo,0x12345678])
    except OwnershipError:pass
    else:raise AssertionError('Ownership watcher missed deliberate access')
assert len(accesses)==len(regions)
zeroed=[]
for at in range(0x226b4,0x2270c,8):
    n,addr=struct.unpack_from('<II',raw,at);zeroed.append(dict(start=hex(addr),end=hex(addr+n),bytes=n))
report=dict(status='PASS_BOUNDED_DEVICE_ADDRESS_RAM_AUDIT',baseline_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
    stock_sha256=hashlib.sha256(raw).hexdigest(),regions=[dict(name=n,start=hex(lo),end=hex(hi)) for n,lo,hi in regions],
    loader_cases=cases,callbacks=counter,stock_candidate_accesses=0,helper_calls=dict(helpers),
    max_observed_stock_helper_end=hex(max(hi for lo,hi in spans)),unique_stock_helper_spans=[dict(start=hex(lo),end=hex(hi)) for lo,hi in sorted(set(spans))],
    cold_zero_spans=zeroed,negative_controls=accesses,guards_intact_before_negative_controls=True,
    physical_RAM_safe_proven=False,device_access=False,audio_device_opened=False,
    limitations=['Bounded CPU paths only; unobserved RAM is not proof of unowned hardware RAM.',
    'Stock initialization zeroes overlay code/state: a future boot copy must occur AFTER that clear.',
    'Hardware DMA, M4, MPU/cache permissions and bus contention remain unverified.',
    'No updater image or boot-persistent allocation is produced.'])
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
