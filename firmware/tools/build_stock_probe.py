#!/usr/bin/env python3
"""Build the original diagnostic code only. No stock bytes or device access."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
import ziglang

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('build_dir',type=Path);a=p.parse_args()
 root=Path(__file__).resolve().parents[1];b=a.build_dir.resolve();b.mkdir(parents=True,exist_ok=True)
 src=root/'target/probe/stock_probe.c';ld=root/'target/probe/stock_probe.ld'
 obj=b/'stock_probe.o';elf=b/'stock-probe-offline-only.elf'
 subprocess.run(['clang','--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfloat-abi=soft',
  '-Oz','-std=c11','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin',
  '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-ffunction-sections','-fdata-sections',
  '-c',str(src),'-o',str(obj)],check=True)
 subprocess.run([str(Path(ziglang.__path__[0])/'zig'),'cc','-target','thumb-freestanding-eabi',
  '-mcpu=cortex_m7','-nostdlib','-Wl,--no-gc-sections','-Wl,--build-id=none','-Wl,-e,mpp_stock_amp_init',
  '-Wl,-T,'+str(ld),str(obj),'-o',str(elf)],check=True)
 with elf.open('rb') as f:
  e=ELFFile(f);symbols=list(e.get_section_by_name('.symtab').iter_symbols())
  assert not [s.name for s in symbols if s.name and s['st_shndx']=='SHN_UNDEF']
  regions=[{'name':s.name,'start':hex(s['sh_addr']),'bytes':s['sh_size']} for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']]
 result={'status':'BUILT_ORIGINAL_STOCK_BRIDGE_CODE','elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),
  'regions':regions,'sources':{str(x.relative_to(root)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [src,ld,Path(__file__)]},
  'stock_payload_included':False,'standalone':False,'physical_loadability_verified':False,'device_access':False,'playback':False}
 (b/'build.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
