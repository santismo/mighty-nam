"""Stock extension with original N29 looper; no physical devices/audio."""
from integration import *
import hashlib,json,struct,time
started=time.monotonic();M,v,s,preset,input_block,model_slot=setup(True)
m=M(TEST_BANK.read_bytes());m.service();m.initialize_usb();m.arm();rows=[]
def config(model):return bytes([8,1,2,model,100,50,50,50,50,50,0,0,0,0,0,0,2,0,3,12,100,30,50,0,50,50,0,0,0,0,0,0])
def set_fx(c):
 m.u.mem_write(0x20025000,c);m.call(v.sym['mpp_fx_set'],[0x20025000]);assert m.u.reg_read(v.R[0])==1
 m.service()
def loops_hash():return hashlib.sha256(m.u.mem_read(0x202a0020,270336)+m.u.mem_read(0x2031c020,100980)).hexdigest()
print('Candidate boot/foreground PASS',flush=True)
exec(Path(__file__).with_name('test_more.py').read_text())
(HERE/'loop-tests.json').write_text(json.dumps(dict(status='PASS_NAMLNK30_STOCK_LOOP',sha256=sha(HERE/'build/extra.elf'),rows=rows,seconds=time.monotonic()-started,hardware_deadlines_verified=False),indent=2)+'\n')
