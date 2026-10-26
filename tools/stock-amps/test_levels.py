"""Private compiled-ARM regression. Synthetic samples stay in memory."""
import sys,json,struct,math,zlib,hashlib,time
import numpy as np
from integration import *
from audit_stock import Stock

start=time.monotonic();bank=TEST_BANK.read_bytes()
M0,v,s0,preset,input_block,model_slot=setup(False)
base=M0(bank);base.service();base.initialize_usb();base.arm()
M,v,s,preset,input_block,model_slot=setup(True)
m=M(bank);m.service();m.initialize_usb();m.arm()
assert m.page(126)==(0,0x5354011d)
data=preset([]);data[84]=37
for q in [base,m]:q.u.mem_write(q.preset,bytes(data))
counter=0;rows=[]
def pair_run(n,equal=True):
 global counter
 a=b=[]
 for _ in range(n):
  x=input_block(counter);a=base.process(counter,x);b=m.process(counter,x)
  if equal:assert a==b,(counter,a,b)
  counter+=1
 return a,b
pair_run(1450);assert m.words()[4]==0
for value in [1,50,100,37]:
 for q in [base,m]:q.u.mem_write(q.preset+84,bytes([value]))
 pair_run(64)
rows.append(dict(case='normal_N29_NAM_audio',exact=True,callbacks=counter))
for q in [base,m]:q.u.mem_write(q.preset+84,b'\0')
calls=m.amp_calls;a,b=pair_run(1500,False)
assert max(map(abs,a))>1e-7 and b==[0.]*16,(a,b)
assert m.amp_calls>calls and m.words()[4]==0
assert m.u.mem_read(0x2000e8c8,0x600)==bytes(0x600),'USB ring not zero after settling'
rows.append(dict(case='chain_master_zero',old_peak=max(map(abs,a)),new_headphone_PCM_zero=True,new_USB_PCM_zero=True,NAM_keeps_running=True))
print('Original N29 unchanged levels; true master zero PASS',flush=True)

(HERE/'nam-regression.json').write_text(json.dumps(dict(status='PASS_NAMLNK30_NAM_LEVEL_REGRESSION',rows=rows,sha256=sha(HERE/'build/extra.elf'),hardware_tested=False),indent=2)+'\n')
