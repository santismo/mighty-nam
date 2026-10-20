#!/usr/bin/env python3
"""Execute final ARM output guard against an independent float32 specification."""
import argparse,hashlib,json,math,random,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_FPSCR
from test_link_stock_chain import ChainMachine,v,build
from output_headroom import protect,CEILING,f32
from link_image import elf_identity

p=argparse.ArgumentParser(description=__doc__)
for k in ['payload','elf','model','output']:p.add_argument(k,type=Path)
a=p.parse_args()
identity=elf_identity(a.elf);assert identity in ['NAMLNK06','NAMLNK07','NAMLNK08','NAMLNK09']
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),a.elf,identity))
m=ChainMachine(a.model);entry=v.sym['mpp_output_protect']
left=v.sym['mpp_link_output'];right=v.sym['_ZL11chain_right']
original_fpscr=m.u.reg_read(UC_ARM_REG_FPSCR)
cases=0;nonfinite=0;max_error=0.;max_peak=0.;rng=random.Random(6006)
vectors=[
 ([0.,-0.,.2,-.5,.875,-.875,1e-30,-1e-30],[.1,-.1]*4),
 ([12.13515853881836,-12.,1.,-1.,.875,-.875,0.,-0.],[.5,-.5]*4),
 ([.01]*8,[100.,-100.,50.,-25.,1.,-1.,0.,-.2]),
 ([f32(3.4028234e38),-f32(3.4028234e38)]+[0.]*6,[1.,-1.]*4),
]
# Dense float neighbours at the exact ceiling and random finite magnitudes.
for bits in range(0x3f600000-64,0x3f600000+65):
 x=struct.unpack('<f',struct.pack('<I',bits))[0]
 vectors.append(([x,-x]*4,[x/2,-x/2]*4))
for _ in range(1200):
 values=[f32(rng.uniform(-1,1)*2**rng.randint(-100,100)) for _ in range(16)]
 vectors.append((values[:8],values[8:]))
for bits in [0x7f7866f7]+[rng.randrange(0x7e000000,0x7f800000) for _ in range(1024)]:
 x=struct.unpack('<f',struct.pack('<I',bits))[0]
 vectors.append(([x,-x]*4,[x/2,-x/2]*4))
for which in range(16):
 for value in [float('nan'),float('inf'),-float('inf')]:
  values=[.1]*16;values[which]=value;vectors.append((values[:8],values[8:]))
for flush in [False,True]:
 m.u.reg_write(UC_ARM_REG_FPSCR,(original_fpscr&~(1<<24))|(int(flush)<<24))
 for l,r in vectors:
  l=list(map(f32,l));r=list(map(f32,r))
  expected_l,expected_r,fault=protect(l,r)
  peak=max(map(abs,l+r))
  # ARM's flush-to-zero mode can flush the gain for extreme finite peaks.
  if flush and math.isfinite(peak) and peak>CEILING and 0<float.fromhex('0x1.bffffcp-1')/peak<2**-126:
   expected_l=[math.copysign(0.,x) for x in l];expected_r=[math.copysign(0.,x) for x in r]
  m.floats(left,l);m.floats(right,r)
  m.put(v.sym['mpp_link']+16,0);m.put(v.sym['mpp_link']+36,1)
  before=bytes(m.u.mem_read(v.sym['_ZL5model'],84024))
  m.call(entry,[left,right])
  yl,yr=m.read(left),m.read(right)
  assert all(math.isfinite(x) and abs(x)<=CEILING for x in yl+yr),(l,r,yl,yr)
  err=max(abs(x-y) for x,y in zip(yl+yr,expected_l+expected_r))
  assert err<=2**-24,(flush,err,l,r,yl,yr)
  if not fault and peak<=CEILING:
   assert struct.pack('<16f',*(yl+yr))==struct.pack('<16f',*(l+r))
  assert all(abs(x)<=abs(y) for x,y in zip(yl+yr,l+r) if math.isfinite(y))
  assert m.words()[4]==int(fault) and m.words()[9]==int(not fault)
  assert before==bytes(m.u.mem_read(v.sym['_ZL5model'],84024))
  max_error=max(max_error,err);max_peak=max(max_peak,max(map(abs,yl+yr)))
  cases+=1;nonfinite+=int(fault)
m.u.reg_write(UC_ARM_REG_FPSCR,original_fpscr)
# Inject at the final boundary of the real callback, not into the NAM model.
def inject(u,pc,size,user):m.floats(right,[float('nan')]+[.1]*7)
h=m.u.hook_add(UC_HOOK_CODE,inject,begin=entry&~1,end=entry&~1)
m.put(v.sym['mpp_link']+16,0);m.put(v.sym['mpp_link']+36,1)
try:m.audio()
finally:m.u.hook_del(h)
assert m.words()[4]==1 and m.words()[9]==0
assert m.read(left)+m.read(right)==[0.]*16
assert m.u.mem_read(0x20016900,128)==bytes(128)
# Subsequent callbacks stay silent with the fault latched.
m.audio();assert m.words()[4]==1 and m.words()[9]==0;m.guards()
report={'status':'PASS_'+identity+'_STEREO_OUTPUT_HEADROOM','identity':identity,
 'elf_sha256':hashlib.sha256(a.elf.read_bytes()).hexdigest(),'cases':cases,
 'nonfinite_cases':nonfinite,'ceiling':CEILING,'maximum_protected_peak':max_peak,
 'maximum_reference_error':max_error,'unchanged_below_ceiling':True,
 'both_channels_checked':True,'model_state_unchanged':True,
 'nonfinite_stops_and_clears_both_channels':True,'DMA_always_zero':True,
 'float_flush_modes_tested':[False,True],'independent_reference':True,
 'physical_device_access':False,'audio_playback':False,
 'limits':['Eight-sample common gain with immediate recovery, not a release-smoothed or listening-validated limiter.',
 'Physical M7 timing and real FPU configuration still require the controlled hardware trial.']}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
