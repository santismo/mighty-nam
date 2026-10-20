#!/usr/bin/env python3
"""Build reclaimed-stock A2 ELF for offline tests. No firmware image or device APIs."""
from pathlib import Path
import subprocess,json,hashlib,sys
import ziglang
from elftools.elf.elffile import ELFFile
r=Path(__file__).resolve().parents[1];b=Path(sys.argv[1]);b.mkdir(parents=True,exist_ok=True)
flags=['--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=vfpv3-d16','-mfloat-abi=hard','-O2','-ffreestanding','-fno-builtin','-ffp-contract=off','-ffunction-sections','-fdata-sections','-fno-exceptions','-fno-rtti','-std=c++20']
obj=[]
for name in ['a2_lite','stock_adapter']:
 o=b/(name+'.o');subprocess.run(['clang++',*flags,'-c',str(r/'target/a2'/f'{name}.cpp'),'-o',str(o)],check=True);obj.append(str(o))
z=Path(ziglang.__path__[0])/'zig';assert subprocess.check_output([str(z),'version'],text=True).strip()=='0.13.0';elf=r/'artifacts/a2-reclaimed-v1-lab-only.elf'
subprocess.run([str(z),'cc','-target','thumb-freestanding-eabihf','-mcpu=cortex_m7','-nostdlib','-Wl,--gc-sections','-Wl,-e,mpp_stock_amp_process','-Wl,-T,'+str(r/'target/a2/reclaimed_v1.ld'),*obj,'-o',str(elf)],check=True)
with elf.open('rb') as f:
 e=ELFFile(f);regions=[dict(name=s.name,start=hex(s['sh_addr']),size=s['sh_size'],end=hex(s['sh_addr']+s['sh_size'])) for s in e.iter_sections() if s['sh_flags']&2]
 undefined=[s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'];assert not undefined
m=dict(status='RECLAIMED_STOCK_CANDIDATE_OFFLINE_ONLY',hardware_loadable=False,device_or_audio_access=False,regions=regions,elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),undefined_symbols=undefined,weight_storage='CRC-checked fixed model slot at 0x30384000 in the in-memory candidate payload')
(r/'artifacts/a2-reclaimed-build.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(m,indent=2))
