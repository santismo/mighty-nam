#!/usr/bin/env python3
"""Cold/warm A2 restarts and storage failures, offline and silent."""
import argparse,json,math,hashlib,struct,zlib,time
from pathlib import Path
from unicorn import UC_HOOK_CODE,UcError
from unicorn.arm_const import UC_ARM_REG_PC
import candidate_vm as v
from a2_reclaimed_vm import configure,A2ReclaimedMachine
from a2_oracle import library
from a2_storage import SLOT_OFFSET,SLOT_SIZE,SLOT_ADDRESS,HEADER_SIZE,BYTES
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('library');p.add_argument('models',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();lib=library(a.library)
result={'status':'RUNNING','silent':True,'device_access':False,'models':[],'limits':['Starts at recovered stock C runtime then main; earlier physical bootloader/system registers are not modeled','Peripherals/preset storage stubbed; all stock DSP initialization and audio effects execute','Mapped resource flash at inferred address, not a measured loader mapping','A15 instruction compatibility, not M7 timing/cache/interrupt simulation','Exact public V1.5.6; installed 20220720 differs','Only one fixed model per candidate; no on-device model writing or phone upload']}
def save():a.output.write_text(json.dumps(result,indent=2)+'\n')
def preset(m):m.set_preset([1,2,4,5,6,7,8,9],{1:3,2:2,4:2,6:1,7:2,8:2,9:10})
def signal(b):return [.15*math.sin(2*math.pi*110*(b*8+i)/48000)+.03*math.sin(2*math.pi*333*(b*8+i)/48000) for i in range(8)]
start=time.perf_counter();save()
try:
 for path in a.models:
  plan=configure(a.payload,path);rows=[];prefix=None
  for fill in [0,0xa5,0xff]:
   m=A2ReclaimedMachine(lib,path,fill=fill);preset(m);ys=[]
   for b in range(1088 if fill==0 else 256):
    control=0x41 if 1024<=b<1056 else 1
    order=[0,5,1,2,3,9,4,6,7,8,10] if b<1024 else [0,5,1,3,2,9,4,6,7,8,10]
    ys+=m.block(signal(b),order,control)
   assert max(map(abs,ys))>1e-5,'Vacuous output'
   if prefix is None:prefix=ys[:2048]
   else:assert prefix==ys[:2048],'Cold fills changed output'
   cold_reads=m.model_reads;warm_reads=m.warm_restart(poison=True);preset(m);warm=[]
   for b in range(256):warm+=m.block(signal(b))
   assert warm==prefix,'Warm restart differs from cold start'
   assert bytes(m.u.mem_read(SLOT_ADDRESS,SLOT_SIZE))==v.candidate[SLOT_OFFSET:SLOT_OFFSET+SLOT_SIZE]
   assert m.get(v.sym['mpp_a2_load_status'])==0
   assert not m.violations and not m.model_access_violations
   rows.append(dict(fill=hex(fill),cold_blocks=len(ys)//8,warm_blocks=256,cold_warm_prefix_bit_identical=True,cold_model_read_operations=cold_reads,warm_model_read_operations=warm_reads,boot_order=m.boot_events,load_status=0,output_peak=max(map(abs,ys)),stats=m.stats(),model_access_violations=m.model_access_violations))
   print(path.name,hex(fill),'cold+warm PASS',m.max_nam_error,flush=True);del m
  result['models'].append(dict(model=path.name,candidate_plan=plan,runs=rows));save()
 # Fail closed for damaged/incompatible records, including CRC-valid NaN.
 path=a.models[0];configure(a.payload,path);clean=v.candidate;negative=[]
 for label,expected_status in [('blank_slot',1),('wrong_version',1),('wrong_rate',1),('wrong_count',1),('reserved_flags',1),('bit_flip',2),('truncated_weights',2),('crc_valid_nan',3)]:
  b=bytearray(clean)
  if label=='blank_slot':b[SLOT_OFFSET:SLOT_OFFSET+SLOT_SIZE]=b'\xff'*SLOT_SIZE
  if label in ['wrong_version','wrong_rate','wrong_count','reserved_flags']:
   idx={'wrong_version':1,'wrong_rate':2,'wrong_count':3,'reserved_flags':7}[label];struct.pack_into('<I',b,SLOT_OFFSET+idx*4,123)
  if label=='bit_flip':b[SLOT_OFFSET+HEADER_SIZE+200]^=1
  if label=='truncated_weights':b[SLOT_OFFSET+HEADER_SIZE+BYTES//2:SLOT_OFFSET+HEADER_SIZE+BYTES]=b'\x00'*(BYTES-BYTES//2)
  if label=='crc_valid_nan':
   struct.pack_into('<I',b,SLOT_OFFSET+HEADER_SIZE+16,0x7fc00000);struct.pack_into('<I',b,SLOT_OFFSET+20,zlib.crc32(b[SLOT_OFFSET+HEADER_SIZE:SLOT_OFFSET+HEADER_SIZE+BYTES]))
  v.candidate=bytes(b);m=A2ReclaimedMachine(lib,path,fill=0xa5,expected_ready=0);m.phase='negative-validation'
  assert m.get(v.sym['mpp_hybrid_ready'])==0 and m.get(v.sym['mpp_a2_load_status'])==expected_status
  m.u.mem_write(m.preset+3,b'\x01');m.floats(0x20025000,[.1]*8);m.floats(0x20025040,[-.1]*8)
  for reg,val in zip(v.R,[0x20025000,0x20025040,0x20025080,0x200250c0]):m.u.reg_write(reg,val)
  m.run(0x5578);assert m.read(0x20025080)+m.read(0x200250c0)==[0.]*16
  negative.append(dict(case=label,load_status=expected_status,boot_completed=True,amp_output_zero=True));print(label,'PASS',flush=True);del m
 v.candidate=clean;result['storage_rejection_tests']=negative;save()
 # No model read dependency on a synthetic region; missing code must fail.
 saved=v.candidate;b=bytearray(saved);b[v.code_start:v.code_end]=b'\0'*(v.code_end-v.code_start);v.candidate=bytes(b)
 try:A2ReclaimedMachine(lib,path)
 except (UcError,ValueError):result['missing_code_negative_control']=True
 else:raise AssertionError('Missing module boot succeeded')
 v.candidate=saved
 # Restoring original AMP background must hit the protected expanded state.
 m=A2ReclaimedMachine(lib,path);m.u.mem_write(0x57c0,v.stock[0x57c0:0x57c2]);m.u.ctl_remove_cache(0x57c0,0x57c4);m.phase='negative-ownership'
 m.u.mem_write(m.preset+3,b'\x01');m.u.mem_write(0x20003774,b'\x01');m.u.mem_write(0x2000cb3f,b'\x00')
 d=0x2000cd08+32;m.u.mem_write(d,bytes(32));m.u.mem_write(d,b'\x01');m.put(d+4,32);m.put(d+12,0x20025000);m.u.mem_write(0x20025000,b'\x6d'*32)
 try:m.run(0x57c0)
 except (v.Collision,ValueError):pass
 else:raise AssertionError('Old background not rejected')
 result['old_background_negative_control']=True;result['old_background_observed_writes']=m.violations
 result['status']='PASS_OFFLINE_A2_COLD_WARM_AND_MODEL_STORAGE'
except Exception as e:result['status']='FAILED';result['error']=repr(e);raise
finally:result['wall_seconds']=time.perf_counter()-start;save()
print(json.dumps({'status':result['status'],'models':len(result['models']),'cold_starts':3*len(result['models']),'warm_restarts':3*len(result['models']),'storage_rejections':len(negative),'wall_seconds':result['wall_seconds']}))
