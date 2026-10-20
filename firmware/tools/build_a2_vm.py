#!/usr/bin/env python3
"""Build synthetic offline A2 ELF only. No firmware file and no device APIs."""
from pathlib import Path
import subprocess,json,hashlib,sys
import ziglang
from elftools.elf.elffile import ELFFile
r=Path(__file__).resolve().parents[1];b=Path(sys.argv[1]);b.mkdir(parents=True,exist_ok=True)
flags=['--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=vfpv3-d16','-mfloat-abi=hard','-O2','-ffreestanding','-fno-builtin','-ffp-contract=off','-ffunction-sections','-fdata-sections','-fno-exceptions','-fno-rtti','-std=c++20']
obj=[]
for name in ['a2_lite','vm_adapter']:
 o=b/(name+'.o');subprocess.run(['clang++',*flags,'-c',str(r/'target/a2'/f'{name}.cpp'),'-o',str(o)],check=True);obj.append(str(o))
z=Path(ziglang.__path__[0])/'zig';elf=r/'artifacts/a2-lite-vm-only.elf'
subprocess.run([str(z),'cc','-target','thumb-freestanding-eabihf','-mcpu=cortex_m7','-nostdlib','-Wl,--gc-sections','-Wl,-e,mpp_a2_process','-Wl,-T,'+str(r/'target/a2/vm_only.ld'),*obj,'-o',str(elf)],check=True)
with elf.open('rb') as f:
 e=ELFFile(f);regions=[dict(name=s.name,start=hex(s['sh_addr']),size=s['sh_size'],end=hex(s['sh_addr']+s['sh_size'])) for s in e.iter_sections() if s['sh_flags']&2]
 undefined=[s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'];assert not undefined
m=dict(status='SYNTHETIC_VM_ONLY',hardware_loadable=False,device_or_audio_access=False,regions=regions,elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),undefined_symbols=undefined,weight_storage='Copied into fixed RAM; persistent model storage unresolved')
(r/'artifacts/a2-lite-build.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(m,indent=2))
