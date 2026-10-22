"""NAMPIT01 compiled DSP/host agreement, bounded work and placement. Offline.

Instruction events are NOT Cortex-M7 cycles; this cannot establish a physical
audio deadline. Peripheral behavior comes from the existing limited VM.
"""
import argparse,ctypes,hashlib,json,math,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from test_usb_nam import UsbMachine,v
from preset_image import build

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['payload','baseline','prototype','host_libraries','output']:p.add_argument(name,type=Path)
 a=p.parse_args();stock=a.payload.read_bytes();rows=[];plans={}
 try:build(stock,a.prototype)
 except ValueError as e:assert 'offline-only' in str(e)
 else:raise AssertionError('Research image accepted without explicit opt-in')
 for role,path in [('baseline',a.baseline),('prototype',a.prototype)]:
  bundle=build(stock,path,allow_pitch_prototype=role=='prototype');plans[role]=bundle[2]
  assert bundle[2]['identity']==('NAMLNK21' if role=='baseline' else 'NAMPIT01')
  v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=path
  lib=ctypes.CDLL(str((a.host_libraries/(role+'.dylib')).resolve()))
  ptr=ctypes.POINTER(ctypes.c_float);lib.pitch_quality_run.argtypes=[ptr,ptr,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint8)]
  for hz,shift in [(110,-12),(110,12),(880,12)]:
   m=UsbMachine();m.service();config=bytearray(32);config[:10]=bytes([1,1,2,shift+12,100,30,50,0,50,50]);config[16:26]=bytes([2,0,3,12,100,30,50,0,50,50])
   cfg=v.SP-512;m.u.mem_write(cfg,bytes(config));m.call(v.sym['mpp_fx_set'],[cfg])
   n=8192;left=(ctypes.c_float*n)(*[.14*sum(math.sin(2*math.pi*hz*h*i/48000+.13*h)/h**1.15 for h in range(1,min(int(20000/hz),45)+1)) for i in range(n)])
   original=list(left);right=(ctypes.c_float*n)(*[-x*.5 for x in left]);controls=(ctypes.c_uint8*(32*n//8)).from_buffer_copy(bytes(config)*(n//8))
   lib.pitch_quality_run(left,right,n,controls);error=0;cost=[];steps=[0];hook=None
   for i in range(n//8):
    m.floats(0x20016000,original[i*8:i*8+8]);m.floats(0x20016020,[-x*.5 for x in original[i*8:i*8+8]])
    if i==768:hook=m.u.hook_add(UC_HOOK_CODE,lambda *args:steps.__setitem__(0,steps[0]+1))
    steps[0]=0;m.call(v.sym['mpp_fx_graph_process'],[0,0x20016000,0x20016020])
    if hook is not None:cost.append(steps[0])
    actual=m.read(0x20016000)+m.read(0x20016020);expected=list(left[i*8:i*8+8])+list(right[i*8:i*8+8])
    error=max(error,max(abs(x-y) for x,y in zip(actual,expected)))
   m.u.hook_del(hook);assert error<2e-5,(role,hz,shift,error)
   rows.append(dict(variant=role,hz=hz,semitones=shift,blocks=n//8,profiled_blocks=len(cost),host_max_error=error,instruction_events_min=min(cost),instruction_events_max=max(cost),instruction_events_mean=sum(cost)/len(cost)))
   print(role,hz,shift,'host error',error,'instruction max',max(cost),flush=True)
 # Extra state/code must remain inside precisely the previous audited regions.
 layout={}
 for role,plan in plans.items():
  regions={r['name']:r for r in plan['elf_regions']}
  layout[role]=dict(code_bytes=regions['.banktext']['bytes'],state_bytes=regions['.bss']['bytes'],code_free_bytes=0x20314000-int(regions['.banktext']['end_exclusive'],16),state_free_bytes=0x2030f000-int(regions['.bss']['end_exclusive'],16))
  assert layout[role]['code_free_bytes']>=0 and layout[role]['state_free_bytes']>=0
 assert plans['baseline']['copied_code']['destination']==plans['prototype']['copied_code']['destination']=='0x2030f000'
 report=dict(status='PASS_OFFLINE_PITCH_ARM',cases=rows,layout=layout,ordinary_packaging_rejects_prototype=True,
  elf_sha256={r:hashlib.sha256(p.read_bytes()).hexdigest() for r,p in [('baseline',a.baseline),('prototype',a.prototype)]},
  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),device_access=False,host_audio_access=False,flash_container_created=False,
  limitations=['Instruction events are not M7 cycles or a hardware deadline measurement','Three bounded monophonic traces','Host comparison uses the same algorithm; independent spectral checks are separate'])
 a.output.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
