#!/usr/bin/env python3
"""Build/test the exact-V1.5.6 raw IRQ capture overlay. No hardware transport."""
import argparse,hashlib,json,struct,subprocess,random
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
import ziglang
p=argparse.ArgumentParser();p.add_argument('payload');p.add_argument('build_dir');p.add_argument('--output',required=True);a=p.parse_args()
r=Path(__file__).resolve().parents[1];b=Path(a.build_dir).resolve();b.mkdir(parents=True,exist_ok=True)
stock=Path(a.payload).read_bytes();assert hashlib.sha256(stock).hexdigest()=='a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990'
a2=r/'artifacts/a2-reclaimed-v1-lab-only.elf';assert hashlib.sha256(a2.read_bytes()).hexdigest()=='4bfb01ab3032e151299a11b58a611a3ef180022428858a3727f2a0ec52d216c3'
src=r/'target/telemetry/irq_capture.c';ld=src.with_suffix('.ld');obj=b/'capture.o';elf=b/'capture.elf'
subprocess.run(['clang','--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-Oz','-ffreestanding','-fno-builtin','-std=c11','-Wall','-Wextra','-Werror','-c',str(src),'-o',str(obj)],check=True)
z=Path(ziglang.__path__[0])/'zig'
subprocess.run([str(z),'cc','-target','thumb-freestanding-eabi','-mcpu=cortex_m7','-nostdlib','-Wl,-e,mpp_capture_irq','-Wl,-T,'+str(ld),str(obj),'-o',str(elf)],check=True)
regions=[];code=[];symbols={}
with elf.open('rb') as f:
 e=ELFFile(f);symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
 undefined=[s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'];assert not undefined
 for s in e.iter_sections():
  if not s['sh_flags']&2 or not s['sh_size']:continue
  addr,size=s['sh_addr'],s['sh_size'];regions.append({'name':s.name,'start':hex(addr),'bytes':size,'end_exclusive':hex(addr+size)})
  if s['sh_type']=='SHT_NOBITS':assert addr==0x202f88a0 and size==52
  else:assert 0x1b2d0<=addr<addr+size<=0x1b488;code.append((addr,s.data()))
assert struct.unpack_from('<II',stock,0x202fc)==(0x38000,0x202e4000)
assert struct.unpack_from('<I',stock,0x205a8)[0]==0x11d95
STATE=0x202f88a0;STOP=0x3fffc;G=0x400f0000
fields=['armed','count','invalid','flags','begin_ref','end_ref','begin_cycle','end_cycle','previous_entry','last_interval','maximum_interval','maximum_duration','last_dma_pointer']
def state(u):return dict(zip(fields,struct.unpack('<13I',u.mem_read(STATE,52))))
def setstate(u,**kw):
 d={x:0 for x in fields};d.update(kw);u.mem_write(STATE,struct.pack('<13I',*[d[x] for x in fields]))
def put(u,addr,v):u.mem_write(addr,struct.pack('<I',v&0xffffffff))
def setup():
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
 for addr,size in [(0,0x40000),(0x20000000,0x40000),(0x202f8000,0x1000),(0x40070000,0x2000),(G,0x1000),(0xe0001000,0x1000)]:u.mem_map(addr,size)
 u.mem_write(0,stock[:0x2356c])
 for addr,data in code:u.mem_write(addr,data)
 # Only in VM: redirect stock IRQ trampoline to the new wrapper.
 put(u,0x205a8,symbols['mpp_capture_irq']);u.mem_write(0x150fc,bytes.fromhex('04207047'));u.mem_write(0x14bfc,bytes.fromhex('7047'))
 u.mem_write(STATE-16,b'\xc3'*16);u.mem_write(STATE+52,b'\x3c'*16)
 put(u,G,0x741);put(u,0x40071018,0x20016aa0)
 return u
cases=[]
def trial(name,start=100,end=1000,initial=None,cr=0x741,pr=0,ir=0,after_cr=None,expect_count=1,expect_flags=0):
 u=setup();setstate(u,**({'armed':0x54494d45} if initial is None else initial));put(u,G,cr);put(u,G+4,pr);put(u,G+12,ir)
 reads=[];cycles=[];callback=[];writes=[];bad=[]
 def read(uc,access,addr,size,value,user):
  if addr==G+0x24:val=[start,end][len(reads)];reads.append(val);put(uc,addr,val)
  elif addr==0xe0001004:val=[12345,54321][len(cycles)];cycles.append(val);put(uc,addr,val)
 def cb(uc,pc,size,user):
  callback.append([uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)])
  if after_cr is not None:put(uc,G,after_cr)
 def memory(uc,access,addr,size,value,user):
  if 0x202f8800<=addr<0x202f8a00:
   assert STATE<=addr and addr+size<=STATE+52
   writes.append(addr)
  else:bad.append(hex(addr))
 u.hook_add(UC_HOOK_MEM_READ,read,begin=G+0x24,end=G+0x27);u.hook_add(UC_HOOK_MEM_READ,read,begin=0xe0001004,end=0xe0001007)
 u.hook_add(UC_HOOK_CODE,cb,begin=0x14bfc,end=0x14bfc)
 u.hook_add(UC_HOOK_MEM_WRITE,memory,begin=0x202f8800,end=0x202f89ff)
 u.hook_add(UC_HOOK_MEM_WRITE,memory,begin=G,end=G+0xfff);u.hook_add(UC_HOOK_MEM_WRITE,memory,begin=0xe0001000,end=0xe0001fff)
 saved={reg:0x20000000+i*16 for i,reg in enumerate([UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11])}
 for reg,val in saved.items():u.reg_write(reg,val)
 u.reg_write(UC_ARM_REG_SP,0x20035f00);u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(0x205a5,STOP,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==STOP and u.reg_read(UC_ARM_REG_SP)==0x20035f00
 assert all(u.reg_read(k)==v for k,v in saved.items())
 assert callback==[[0x20016800,0x20016900]] and not bad
 assert struct.unpack('<I',u.mem_read(0x200147c8,4))[0]==8
 assert bytes(u.mem_read(STATE-16,16))==b'\xc3'*16 and bytes(u.mem_read(STATE+52,16))==b'\x3c'*16
 d=state(u);assert (d['count'],d['flags'])==(expect_count,expect_flags),(name,d)
 if d['armed']==0:assert not reads and not cycles and not writes
 elif not expect_flags:
  assert d['maximum_duration']==max((end-start)&0xffffffff,(initial or {}).get('maximum_duration',0))
  assert [d[x] for x in ['begin_ref','end_ref','begin_cycle','end_cycle']]==[start&0xffffffff,end&0xffffffff,12345,54321]
 cases.append(name);return d
trial('dormant hook preserves stock IRQ and avoids timer access',initial={},expect_count=0)
trial('ordinary capture');trial('32-bit timer wrap',0xfffffff0,0x100)
for label,args in [('stopped timer',dict(cr=0x740)),('nonzero prescaler',dict(pr=1)),('timer interrupt already enabled',dict(ir=1)),('clock config changed mid-IRQ',dict(after_cr=0x740)),('stalled counter',dict(end=100)),('ambiguous long duration',dict(end=0x80000064))]:trial(label,**args,expect_count=0,expect_flags=1)
trial('saturated capture count',initial={'armed':0x54494d45,'count':0xffffffff},expect_count=0xffffffff,expect_flags=2)
d=trial('cadence includes gap',start=10000,end=11000,initial={'armed':0x54494d45,'count':2,'previous_entry':1000,'maximum_duration':2000},expect_count=3);assert d['last_interval']==d['maximum_interval']==9000
rng=random.Random(144)
for i in range(128):
 start=rng.randrange(2**32);duration=rng.randrange(1,100000);trial('random '+str(i),start,(start+duration)&0xffffffff)
report={'status':'PASS_OFFLINE_IRQ_CAPTURE','device_access':False,'playback':False,'cases':len(cases),'named_cases':cases[:-128],'random_wrap_cases':128,'regions':regions,'undefined_symbols':undefined,'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'canonical_a2_elf_unchanged':True,'loaded_bytes':sum(len(x) for _,x in code),'state_bytes':52,'remaining_code_bytes':0x1b488-max(addr+len(x) for addr,x in code),'sp_and_r4_r11_preserved':True,'state_guards_intact':True,'timer_and_dwt_writes':0,'stock_irq_body_executed':True,'stock_dma_status_helper_and_processing_callback_stubbed':True,'trampoline_pointer_patch_vm_only':{'offset':'0x205a8','original':'0x11d95','new':hex(symbols['mpp_capture_irq'])},'runtime_zero_table_covers_state':True,'dormant_after_runtime_zero':True,'integration_limits':['No GPT2 initialization or hardware ownership proof','No hardware deadline/release sequence validation','DWT samples are raw: resets are not classified by this compact hook','Raw maxima exclude timestamp-reader prologue, post-sample stats update, exception entry/exit and entry latency','No physical output muting or data retrieval path','The test invokes the IRQ as an ARM function; actual NVIC exception entry/return is not emulated']}
Path(a.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','cases','loaded_bytes','state_bytes','remaining_code_bytes','timer_and_dwt_writes']}))
