#!/usr/bin/env python3
"""Owned startup/audio/A2 path vs official NAM, no audio devices or USB."""
import argparse,ctypes as c,json,math,random,struct,hashlib,time
from pathlib import Path
from a2_oracle import library,Engine,extract
p=argparse.ArgumentParser();p.add_argument('library');p.add_argument('reference');p.add_argument('models',nargs='+',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
l=c.CDLL(str(Path(a.library).resolve()));F=c.POINTER(c.c_float);I=c.POINTER(c.c_int32)
l.standalone_create.argtypes=[F,c.c_uint,c.c_uint];l.standalone_create.restype=c.c_void_p
l.standalone_step.argtypes=[c.c_void_p,I,F,c.c_uint];l.standalone_step.restype=c.c_int
l.standalone_restart.argtypes=[c.c_void_p,F,c.c_uint,c.c_uint];l.standalone_restart.restype=c.c_int
l.standalone_status.argtypes=[c.c_void_p,c.POINTER(c.c_uint32)];l.standalone_trace.argtypes=[c.c_void_p,c.POINTER(c.c_uint32)];l.standalone_trace.restype=c.c_uint
l.standalone_destroy.argtypes=[c.c_void_p]
ref=library(a.reference);rng=random.Random(6000);results=[];trace_check=False
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
for path in a.models:
 j=extract(json.loads(path.read_text()));w=(c.c_float*1871)(*j['weights']);slot=len(results)%4
 h=l.standalone_create(w,1871,slot);assert h
 try:
  if not trace_check:
   trace=(c.c_uint32*(128*5))();count=l.standalone_trace(h,trace);requests=[list(trace[i*5:i*5+5]) for i in range(count)]
   recovered=json.loads((Path(__file__).resolve().parents[1]/'artifacts/stock-clock-emulation.json').read_text())['cases'][0]['events']
   actual=[]
   for op,x,y,z,v in requests:
    if op==5:actual.append(('pll_ldo_enable_stub',[0x40c84000]))
    elif op==6:actual.append(('analog_write_stub',[2,x,y]))
    elif op==7:actual.append(('analog_modify_stub',[2,x,y,z],v))
    elif op==9 and x in (100,225):actual.append(('delay_stub',[x,1000000000]))
   expected=[(e['kind'],e['args'],e['bit_shift']) if 'bit_shift' in e else (e['kind'],e['args']) for e in recovered]
   assert actual==expected,(actual,expected)
   assert requests[0][0]==1 and requests[1][0]==2 and requests[-1][0]==14
   assert [r[2] for r in requests if r[0]==8 and r[1]==0x40c84300]==[0x2000,0x20002000]
   trace_check=True
  oracle=Engine(ref,path);maxerr=0;first=[];inputs=[];peak=0;start=time.perf_counter()
  for b in range(6000):
   block=[];x=[]
   for f in range(8):
    t=b*8+f;value=(.2*math.sin(2*math.pi*110*t/48000)+rng.uniform(-.02,.02)) if t<24000 else 0
    q=int(value*2**31);x.append(f32(q/2**31))
    block.extend([q if s==slot else (0x70000000 if s&1 else -0x70000000) for s in range(4)])
   inp=(c.c_int32*32)(*block);out=(c.c_float*8)();assert l.standalone_step(h,inp,out,b)
   target=oracle.run(x);maxerr=max(maxerr,max(abs(v-z) for v,z in zip(out,target)));peak=max(peak,max(map(abs,out)))
   if b<64:first.extend(out);inputs.append(block)
  assert maxerr<2e-5 and peak>0
  status=(c.c_uint32*7)();l.standalone_status(h,status);assert list(status)==[2,0,6000,48000,100,6000,0]
  assert l.standalone_restart(h,w,1871,slot)
  reset=[]
  for b,block in enumerate(inputs):
   out=(c.c_float*8)();assert l.standalone_step(h,(c.c_int32*32)(*block),out,b);reset.extend(out)
  assert reset==first
  results.append(dict(model=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),input_slot=slot,samples=48000,blocks=6000,max_reference_error=maxerr,peak_diagnostic=peak,warm_restart_first_512_bit_identical=True,all_tx_words_zero=True,elapsed_seconds=time.perf_counter()-start))
  print(json.dumps(results[-1]),flush=True)
 finally:l.standalone_destroy(h)
report={'status':'PASS_STANDALONE_NATIVE_A2_REFERENCE','models':results,'clock_plan_matches_saved_cold_stock_AI_transactions':trace_check,'stock_code_executed':False,'physical_peripherals_simulated':True,'timing_ticks_synthetic':True,'playback':False,'device_access':False,'tolerance':2e-5}
a.output.write_text(json.dumps(report,indent=2)+'\n')
