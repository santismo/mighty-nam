from audit_stock import *
from capstone import *
from collections import defaultdict
cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB);cs.detail=True
rows=[]
for amp in range(1,30):
 m=Stock();m.u.mem_write(0x200039b0,bytes([amp,50,50,50,50,50,0])+bytes(5)+bytes([amp,amp,0]))
 m.call(0x533c);m.call(0x5374);m.call(0x5148,[0x2000d44c,0x2000d4fc,0x20000374])
 writes=defaultdict(set)
 def write(u,access,at,n,value,ud):
  pc=u.reg_read(UC_ARM_REG_PC);lr=u.reg_read(UC_ARM_REG_LR)
  writes[(pc,lr)].update(range(at-0x202e4000,at-0x202e4000+n))
 h=m.u.hook_add(UC_HOOK_MEM_WRITE,write,begin=0x202e4000,end=0x2031afff)
 m.call(0x5910,[amp,0x202e4000,0x2031b000,0x2000d44c],[1])
 for j in range(8):m.block(amp,j)
 desc=struct.unpack_from('<8I',STOCK,0x1ab60+32*amp)
 row=dict(amp=amp,descriptor=[hex(x) for x in desc],writes=[dict(pc=hex(pc),lr=hex(lr),lo=hex(min(a)),hi=hex(max(a)+1),count=len(a)) for (pc,lr),a in writes.items()])
 print(row,flush=True);rows.append(row)
(HERE/'audit_writes.json').write_text(json.dumps(rows,indent=2)+'\n')
