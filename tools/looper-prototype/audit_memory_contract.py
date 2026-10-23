"""Execute exact stock MPU/C-runtime setup, model registers only; no device I/O."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE,UC_HOOK_MEM_READ
from unicorn.arm_const import UC_CPU_ARM_CORTEX_M7,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
b=a.payload.read_bytes();assert hashlib.sha256(b).hexdigest()=='e971240a1e333003804cfd154e5ee053026254bbf09b11499e8b4968d3600752'
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
for lo,n in [(0,0x40000),(0x20000000,0x400000),(0xe0000000,0x100000)]:u.mem_map(lo,n)
u.mem_write(0,b[:0x40000]);regions={};selected=0
def observe(u,kind,address,n,value,user):
    global selected
    if address==0xe000ed9c:
        assert value&16;selected=value&15;regions[selected]=dict(base=value&~31)
    if address==0xe000eda0:regions[selected]['attributes']=value
h=u.hook_add(UC_HOOK_MEM_WRITE,observe,begin=0xe000ed94,end=0xe000ef80)
def run(pc,sp=0x20035000):
    u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x3fff1)
    u.emu_start(pc|1,0x3fff0,count=5000000);assert u.reg_read(UC_ARM_REG_PC)==0x3fff0
run(0x73e0);u.hook_del(h)
assert struct.unpack('<I',u.mem_read(0xe000ed94,4))[0]==5
for r in regions.values():
    attr=r['attributes'];r.update(bytes=1<<(((attr>>1)&31)+1),enabled=bool(attr&1),subregions_disabled=(attr>>8)&255,
        executable=not bool(attr&(1<<28)),AP=(attr>>24)&7,TEX=(attr>>19)&7,shareable=bool(attr&(1<<18)),cacheable=bool(attr&(1<<17)),bufferable=bool(attr&(1<<16)))
def owner(address):
    matches=[]
    for index,r in regions.items():
        off=address-r['base'];size=r['bytes']
        if r['enabled'] and 0<=off<size and not (size>=256 and r['subregions_disabled']&(1<<(off//(size//8)))):matches.append(index)
    assert matches,hex(address);return max(matches)
checks=[]
for name,lo,hi,execute,write in [('store1',0x202a0020,0x202e2020,False,True),('store2',0x2031c020,0x20334a94,False,True),
    ('code',0x20314020,0x20317fe0,True,True),('state',0x20318020,0x20319fe0,False,True),('preset AHB read',0x30384000,0x303a0000,False,False)]:
    winners=sorted(set(owner(x) for x in range(lo,hi,32)))
    for index in winners:
        r=regions[index];assert r['AP'] in ([3] if write else [1,2,3,5,6]);assert not execute or r['executable']
    checks.append(dict(name=name,start=hex(lo),end=hex(hi),highest_priority_regions=winners,required_access_allowed=True))
# Classify the apparent RAM-pointer words in executable code as actual STRB
# instructions. The one initializer lead is consumed by the real decompressor.
cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB);instruction_words=[]
for at in [0xf828,0xf858,0x13db4,0x13e80]:
    i=next(cs.disasm(b[at:at+4],at));assert i.mnemonic=='strb.w'
    instruction_words.append(dict(at=hex(at),word=hex(struct.unpack_from('<I',b,at)[0]),instruction=i.mnemonic+' '+i.op_str))
initializer_reads=[]
u.hook_add(UC_HOOK_MEM_READ,lambda u,k,at,n,v,x:initializer_reads.append(dict(pc=hex(u.reg_read(UC_ARM_REG_PC)),address=hex(at),bytes=n)),begin=0x23a7c,end=0x23a7f)
u.mem_write(0x20000000,b'\xa5'*0x400000);run(0x22640,0x20080000);assert initializer_reads
ram=bytes(u.mem_read(0x20000000,0x40000));digest=hashlib.sha256(ram).hexdigest()
assert digest=='ef63d9923157937962ff44d67f94e59c047a6078abd0972c8ebd7014c9b0e921'
# Runtime zero table must be respected: cold init owns/clears the overlay region.
assert u.mem_read(0x20314000,0x6000)==bytes(0x6000)
assert u.mem_read(0x202a0020,270336)==b'\xa5'*270336
assert u.mem_read(0x2031c020,100980)==b'\xa5'*100980
report=dict(status='PASS_STOCK_MPU_AND_C_RUNTIME_CONTRACT',stock_sha256=hashlib.sha256(b).hexdigest(),
    MPU_routine='0x73e0',regions=regions,checks=checks,instruction_words_not_pointers=instruction_words,
    compressed_initializer_lead=dict(address='0x23a7c',reads=initializer_reads,initialized_DTCM_sha256=digest),
    stock_startup_clears_overlay=True,stock_startup_preserves_recording_buffers=True,physical_RAM_safe_proven=False,
    device_access=False,audio_device_opened=False,limitations=['Registers are modeled; actual MPU state/cache coherency and instruction fetch remain untested.',
    'Fixed OCRAM ranges avoid FlexRAM/ECC aliases; this does not prove no DMA or other core owns them.',
    'Boot must initialize transport and copy loop code after the stock clear; RAM is not persistent loop storage.',
    'No exhaustive computed-pointer or whole-program ownership proof.'])
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
