#!/usr/bin/env python3
"""Build an emulator-only ELF and native parity library; no firmware container."""
import argparse,json,subprocess,hashlib
from pathlib import Path
from elftools.elf.elffile import ELFFile
import ziglang
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parent;out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
flags=['-std=c++17','-O2','-Wall','-Wextra','-Werror','-ffp-contract=off']
subprocess.run(['clang++',*flags,'-dynamiclib',str(root/'arm_bridge.cpp'),'-o',str(out/'loop-native.dylib')],check=True)
subprocess.run(['clang++',*flags,'--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=vfpv3-d16','-mfloat-abi=hard',
 '-ffreestanding','-fno-builtin','-fno-exceptions','-fno-rtti','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
 '-c',str(root/'arm_bridge.cpp'),'-o',str(out/'loop-arm.o')],check=True)
subprocess.run([str(Path(ziglang.__path__[0])/'zig'),'cc','-target','thumb-freestanding-eabihf','-mcpu=cortex_m7','-nostdlib',
 '-Wl,-e,lp_init','-Wl,-T,'+str(root/'loop_emulator.ld'),str(out/'loop-arm.o'),'-o',str(out/'loop-emulator-only.elf')],check=True)
with (out/'loop-emulator-only.elf').open('rb') as f:
 e=ELFFile(f);assert not [s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF']
 sections=[dict(name=s.name,address=hex(s['sh_addr']),bytes=s['sh_size']) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']]
(out/'loop-build.json').write_text(json.dumps(dict(status='OFFLINE_ELF_ONLY',sections=sections,
 sha256=hashlib.sha256((out/'loop-emulator-only.elf').read_bytes()).hexdigest(),
 physical_RAM_address_chosen=False,flash_container_created=False),indent=2)+'\n')
print('Built emulator-only component and native parity library')
