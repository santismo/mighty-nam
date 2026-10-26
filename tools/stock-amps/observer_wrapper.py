"""Isolated real ARM amp DSP parity; only unrelated foreground looper service is stubbed."""
from integration import *
from audit_stock import Stock,STOCK
sys.path[:0]=[str(BASE/"generated/research"),str(BASE/"generated/tools")]
from unicorn import *
from unicorn.arm_const import *
import numpy as np,math,json
blob,s,plan=extension(STOCK,BASE/'build/nam-link-offline.elf',LOOP/'build/loop-startup-test.elf')
def new_candidate():
 m=Stock();m.u.mem_map(0xe000e000,0x2000);m.u.mem_write(0,blob[:0x40000]);m.u.mem_write(0x30040000,blob)
 for r in plan['elf_regions']:
  if 'load_address' in r:m.u.mem_write(int(r['start'],16),blob[int(r['load_address'],16)-0x30040000:int(r['load_address'],16)-0x30040000+r['bytes']])
 m.u.mem_protect(0x30040000,(len(blob)+4095)&~4095,UC_PROT_READ)
 old=symbols(LOOP/'build/loop-startup-test.elf')['mpp_loop_service']&~1
 m.u.hook_add(UC_HOOK_CODE,lambda u,*_:u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR)),begin=old,end=old)
 m.u.hook_add(UC_HOOK_MEM_READ,lambda *args:None,begin=0x2031a800,end=0x2031afe0)
 m.call(s['mpp_fx_init']);m.call(s['mpp_extra_init']);return m
rows=[]
for amp,knobs in [(a,k) for a in [1] for k in [(50,50,50,50,50,0)]]:
 m=new_candidate()
 c=bytes([8,1,2,amp,100,*knobs,0,0,0,0,0,2,0,3,12,100,30,50,0,50,50,0,0,0,0,0,0]);m.u.mem_write(0x20025000,c)
 m.call(s['mpp_fx_set'],[0x20025000]);assert m.u.reg_read(UC_ARM_REG_R0)==1;m.call(s['mpp_extra_service'])
 ref=Stock()
 # Independent stock startup with the same initial knobs, not a mid-position
 # setup followed by a second update (which changes stock tone smoothing).
 ref.u.mem_write(0x200039b0,bytes([amp,*knobs])+bytes(5)+bytes([amp,amp,0]))
 if amp in [1,5,18,21]:ref.u.mem_write(0x200039b6,bytes([int(c[10]>=50)]))
 ref.call(0x533c);ref.call(0x5374);ref.call(0x5148,[0x2000d44c,0x2000d4fc,0x20000374]);ref.call(0x5910,[amp,0x202e4000,0x2031b000,0x2000d44c],[1])
 err=peak=0
 for n in range(128):
  x=np.array([.016*math.sin((n*8+j)*.031) for j in range(8)],dtype=np.float32)
  ref.u.mem_write(0x20025000,(x*np.float32(.2)).tobytes());ref.call(0x58f4,[amp,0x20025000,0x20025100,0x202e4000],[0x2031b000,8])
  y=np.frombuffer(ref.u.mem_read(0x20025100,32),dtype=np.float32)*np.float32(8)
  wet=np.array([min(1,(n*8+j+1)/256) for j in range(8)],dtype=np.float32);expected=x+wet*(y-x)
  m.u.mem_write(0x20025000,x.tobytes());m.u.mem_write(0x20025020,x.tobytes());m.call(s['mpp_extra_process'],[0,0x20025000,0x20025020])
  actual=np.frombuffer(m.u.mem_read(0x20025000,32),dtype=np.float32);err=max(err,float(np.max(abs(actual-expected))));peak=max(peak,float(np.max(abs(actual))))
 assert err<2e-6 and math.isfinite(peak),(amp,knobs,err,peak)
 rows.append(dict(amp=amp,knobs=knobs,max_error=err,peak=peak));print(rows[-1],flush=True)
(HERE/'observer-wrapper.json').write_text(json.dumps(dict(status='PASS_REAL_ARM_STOCK_DSP_REFERENCE',rows=rows),indent=2)+'\n')
