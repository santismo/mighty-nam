#!/usr/bin/env python3
"""Build native silent tests and self-contained ARM-VM ELF. No device interfaces."""
from pathlib import Path
import argparse,subprocess,json,hashlib
import ziglang
from elftools.elf.elffile import ELFFile
p=argparse.ArgumentParser(description=__doc__);p.add_argument('build_dir',type=Path);a=p.parse_args()
r=Path(__file__).resolve().parents[1];b=a.build_dir.resolve();b.mkdir(parents=True,exist_ok=True)
common=['target/standalone/prototype.cpp','target/standalone/clock_plan.cpp','target/a2/a2_lite.cpp','target/board/audio_transport.cpp','target/board/codec_control.cpp','target/board/startup_memory.cpp']
flags=['-std=c++20','-O2','-ffp-contract=off','-Wall','-Wextra','-Werror']
sources=[str(r/x) for x in common]
for name,extra in [('native',[]),('sanitizers',['-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
 exe=b/('standalone-'+name)
 subprocess.run(['clang++',*flags,*extra,*sources,str(r/'tests/test_standalone.cpp'),'-o',str(exe)],check=True)
 result=subprocess.check_output([str(exe)],text=True);(b/(name+'.json')).write_text(result);print(result.strip(),flush=True)
subprocess.run(['clang++',*flags,'-dynamiclib',*sources,str(r/'research/standalone_host_bridge.cpp'),'-o',str(b/'libstandalone.dylib')],check=True)
arm=['--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=fpv5-d16','-mfloat-abi=hard','-ffreestanding','-fno-builtin','-fno-exceptions','-fno-rtti','-ffunction-sections','-fdata-sections']
objects=[]
for src in common+['target/standalone/lab_image.cpp','target/standalone/lab_startup.S']:
 obj=b/(Path(src).stem+'.o');args=arm if src.endswith('.S') else flags+arm
 subprocess.run(['clang++',*args,'-c',str(r/src),'-o',str(obj)],check=True);objects.append(str(obj))
elf=b/'standalone-vm-only.elf';z=Path(ziglang.__path__[0])/'zig'
subprocess.run([str(z),'cc','-target','thumb-freestanding-eabihf','-mcpu=cortex_m7','-nostdlib','-Wl,--gc-sections','-Wl,-e,mpp_lab_reset','-Wl,-T,'+str(r/'target/standalone/lab_only.ld'),*objects,'-o',str(elf)],check=True)
with elf.open('rb') as f:
 e=ELFFile(f);regions=[dict(name=s.name,start=hex(s['sh_addr']),size=s['sh_size']) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']]
 undefined=[s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'];assert not undefined
headers=['target/standalone/platform.hpp','target/standalone/prototype.hpp','target/a2/a2_lite.hpp','target/board/audio_transport.hpp','target/board/codec_control.hpp','target/board/startup_memory.hpp']
report={'status':'BUILT_SELF_CONTAINED_ARM_VM_PROTOTYPE','elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'undefined_symbols':undefined,'regions':regions,'nux_application_code_linked':False,'physical_board_port_implemented':False,'hardware_loadable':False,'device_access':False,'playback':False,'sources':{s:hashlib.sha256((r/s).read_bytes()).hexdigest() for s in common+headers+['target/standalone/lab_image.cpp','target/standalone/lab_startup.S','target/standalone/lab_only.ld','tests/standalone_ram_port.hpp']}}
(b/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
