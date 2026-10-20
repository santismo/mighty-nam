#!/usr/bin/env python3
"""Build register-backend tests and ARM compile-only objects. No device access."""
from pathlib import Path
import argparse,subprocess,json,hashlib
from elftools.elf.elffile import ELFFile
p=argparse.ArgumentParser(description=__doc__);p.add_argument('build_dir',type=Path);a=p.parse_args()
r=Path(__file__).resolve().parents[1];b=a.build_dir.resolve();b.mkdir(parents=True,exist_ok=True)
common=['target/hardware/rt1176_backend.cpp','target/hardware/handoff.cpp','target/standalone/prototype.cpp','target/standalone/clock_plan.cpp','target/board/audio_transport.cpp','target/board/codec_control.cpp','target/a2/a2_lite.cpp']
flags=['-std=c++20','-O2','-ffp-contract=off','-Wall','-Wextra','-Werror']
for name,extra in [('native',[]),('sanitizers',['-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
 exe=b/name
 subprocess.run(['clang++',*flags,*extra,*[str(r/x) for x in common],str(r/'tests/test_hardware_backend.cpp'),'-o',str(exe)],check=True)
 result=subprocess.check_output([str(exe)],text=True);(b/(name+'.json')).write_text(result);print(result.strip(),flush=True)
subprocess.run(['clang++',*flags,'-dynamiclib',*[str(r/x) for x in common],str(r/'research/hardware_host_bridge.cpp'),'-o',str(b/'libhardware.dylib')],check=True)
arm=['--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=fpv5-d16','-mfloat-abi=hard','-ffreestanding','-fno-builtin','-fno-exceptions','-fno-rtti','-ffunction-sections','-fdata-sections']
objects=[]
for src in common+['target/hardware/direct_mmio.cpp']:
 obj=b/(Path(src).stem+'.o');subprocess.run(['clang++',*flags,*arm,'-c',str(r/src),'-o',str(obj)],check=True)
 with obj.open('rb') as f:
  e=ELFFile(f);objects.append({'file':obj.name,'sha256':hashlib.sha256(obj.read_bytes()).hexdigest(),'code_bytes':sum(s['sh_size'] for s in e.iter_sections() if s['sh_flags']&4)})
sourcepaths=common+['target/hardware/direct_mmio.cpp','target/hardware/rt1176_backend.hpp','target/hardware/handoff.hpp','target/board/codec_control.hpp','tests/rt1176_register_model.hpp','tests/test_hardware_backend.cpp','research/hardware_host_bridge.cpp']
sourcepaths+=['target/standalone/prototype.hpp','target/standalone/platform.hpp','target/board/audio_transport.hpp','target/a2/a2_lite.hpp','tools/build_hardware_backend.py','research/test_hardware_host.py','research/audit_stock_handoff.py']
report={'status':'PASS_NATIVE_AND_ARM_COMPILE_ONLY','objects':objects,'sources':{s:hashlib.sha256((r/s).read_bytes()).hexdigest() for s in sourcepaths},'hardware_entry_linked':False,'hardware_loadable_image':False,'device_access':False,'playback':False}
(b/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
