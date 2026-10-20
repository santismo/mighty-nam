#!/usr/bin/env python3
"""Build original continuous code only; no device access or firmware container."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
import ziglang

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('build_dir',type=Path);a=p.parse_args()
 root=Path(__file__).resolve().parents[1];b=a.build_dir.resolve();b.mkdir(parents=True,exist_ok=True)
 sources=[root/'target/a2/a2_lite.cpp',root/'target/continuous/a2_continuous.cpp']
 flags=['--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=vfpv3-d16','-mfloat-abi=hard',
  '-std=c++17','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-ffp-contract=off',
  '-fno-exceptions','-fno-rtti','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
  '-ffunction-sections','-fdata-sections']
 objects=[]
 for src,opt in zip(sources,['-O2','-Oz']):
  obj=b/(src.stem+'.o');subprocess.run(['clang++',*flags,opt,'-c',str(src),'-o',str(obj)],check=True);objects.append(str(obj))
 ld=root/'target/continuous/a2_continuous.ld';elf=b/'a2-silent-continuous-offline-only.elf'
 subprocess.run([str(Path(ziglang.__path__[0])/'zig'),'cc','-target','thumb-freestanding-eabihf','-mcpu=cortex_m7',
  '-nostdlib','-Wl,--no-gc-sections','-Wl,--build-id=none','-Wl,-e,mpp_stock_amp_init','-Wl,-T,'+str(ld),*objects,'-o',str(elf)],check=True)
 with elf.open('rb') as f:
  e=ELFFile(f);assert not [s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF']
  regions=[dict(name=s.name,start=hex(s['sh_addr']),bytes=s['sh_size'],end_exclusive=hex(s['sh_addr']+s['sh_size'])) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']]
 report={'status':'BUILT_ORIGINAL_A2_CONTINUOUS_NOT_HARDWARE_TESTED','identity':'NAMA2C01','elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'regions':regions,
  'sources':{str(x.relative_to(root)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources+[root/'target/a2/a2_lite.hpp',ld,Path(__file__)]},
  'physical_device_access':False,'audio_playback':False,'stock_or_model_bytes_included_in_elf':False,'firmware_container_created':False}
 (b/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
