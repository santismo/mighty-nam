#!/usr/bin/env python3
"""Compile a RAM-only overlay against an exact NAMLNK24 ELF; never package it."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
import ziglang
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('baseline',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parent;out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
elf=a.baseline/'build/nam-link-offline.elf'
assert hashlib.sha256(elf.read_bytes()).hexdigest()=='13e14ec6a6ad1ad30142cf0ae28f57691e35d4d6435db8cc11208bba7726e65d'
with elf.open('rb') as f:
    e=ELFFile(f);symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols() if s.name}
source=(a.baseline/'generated/target/link/stock_chain_firmware.cpp').read_text()
start=source.index('extern "C" void mpp_probe_audio(');end=source.index('extern "C" BANK_TEXT void mpp_probe_version',start)
body=source[start:end].replace('void mpp_probe_audio(', 'void mpp_loop_probe_audio(')
assert body.count(' ++mpp_link.callbacks;')==1
assert body.count(' if(!mpp_link.ready||!mpp_link.running){')==1
assert body.count(' mpp_usb_finish(mpp_link_output,chain_right);')==1
body=body.replace(' ++mpp_link.callbacks;', ' mpp_loop_tick();\n ++mpp_link.callbacks;')
body=body.replace(' if(!mpp_link.ready||!mpp_link.running){',' if(!mpp_link.ready||!mpp_link.running){\n  mpp_loop_render(tx);')
body=body.replace(' mpp_listen_render(mpp_link_output,chain_right,tx);',' mpp_listen_render(mpp_link_output,chain_right,tx);\n mpp_loop_render(tx);')
body=body.replace(' mpp_usb_finish(mpp_link_output,chain_right);',' mpp_loop_capture(rx,mpp_link_output,chain_right,!mpp_listen_warm);\n mpp_usb_finish(mpp_link_output,chain_right);')
preamble='''#include <stdint.h>
#include "listening.hpp"
#include "driver_timing.hpp"
static unsigned rd(uint32_t a){return *(volatile unsigned*)a;}
static void barrier(){__asm__ volatile("dmb":::"memory");}
extern "C" {
struct LinkStatus { uint32_t magic,schema,ready,callbacks,faults,model_crc,generation,runs,timer_max,running,context_rejections,last_output_bits; };
extern volatile LinkStatus mpp_link;
extern float mpp_link_output[],chain_right[];
void mpp_usb_begin(bool);void mpp_usb_finish(float*,float*);
void mpp_tuner_feed(const int32_t*);void mpp_output_protect(float*,float*);
void mpp_loop_tick();void mpp_loop_render(int32_t*);
void mpp_loop_capture(const int32_t*,const float*,const float*,unsigned);
}
'''
(out/'audio_overlay.cpp').write_text(preamble+body)
flags=['--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=vfpv3-d16','-mfloat-abi=hard','-std=c++17','-O2',
 '-ffreestanding','-fno-builtin','-ffp-contract=off','-fno-exceptions','-fno-rtti','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wall','-Wextra','-Werror']
defines=[x for x in json.loads((a.baseline/'build/build.json').read_text())['compiler_flags'] if x.startswith('-D')]
assert all('-D'+name in defines for name in ['MPP_EARLY_OUTPUT','MPP_USB_NAM_CONTROLS','MPP_LISTENING'])
assert not any(x.startswith('-DMPP_DMA_') for x in defines),'Only the established early-output pipeline is supported'
objects=[]
for src in [root/'continuity.cpp',out/'audio_overlay.cpp']:
    obj=out/(src.stem+'.o');subprocess.run(['clang++',*flags,*defines,'-I'+str(a.baseline.resolve()/'generated/target/link'),'-c',str(src),'-o',str(obj)],check=True);objects.append(obj)
aliases={name:value for name,value in symbols.items() if name.startswith('mpp_')}
aliases['chain_right']=symbols['_ZL11chain_right']
ld=out/'overlay.ld';ld.write_text(root.joinpath('continuity.ld').read_text()+'\n'+'\n'.join(f'PROVIDE({k} = {v:#x});' for k,v in aliases.items())+'\n')
target=out/'loop-continuity-RAM-only.elf'
subprocess.run([str(Path(ziglang.__path__[0])/'zig'),'cc','-target','thumb-freestanding-eabihf','-mcpu=cortex_m7','-nostdlib','-Wl,-e,mpp_loop_init','-Wl,-T,'+str(ld),*[str(o) for o in objects],'-o',str(target)],check=True)
with target.open('rb') as f:
    e=ELFFile(f);assert not [s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF']
    regions=[dict(name=s.name,start=hex(s['sh_addr']),bytes=s['sh_size'],end=hex(s['sh_addr']+s['sh_size'])) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']]
(out/'continuity-build.json').write_text(json.dumps(dict(status='OFFLINE_RAM_OVERLAY_ONLY',baseline_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),audio_source_sha256=hashlib.sha256(source.encode()).hexdigest(),compiler_defines=defines,regions=regions,flash_container_created=False,boot_copy_implemented=False,physical_RAM_safe_proven=False),indent=2)+'\n')
print('Built RAM-only preset continuity overlay')
