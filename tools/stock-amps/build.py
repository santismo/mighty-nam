"""Stock amp extension of frozen original NAMLNK29. No device or publishing APIs."""
from pathlib import Path
import sys,hashlib,json,subprocess,struct
import ziglang
from elftools.elf.elffile import ELFFile
from config import HERE,ROOT,BASE,LOOP,PAYLOAD,STOCK_FILE,TEST_BANK
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def symbols(p):
 with p.open('rb') as f:return {s.name:s['st_value'] for s in ELFFile(f).get_section_by_name('.symtab').iter_symbols() if s.name}
def build():
 assert sha(BASE/'build/nam-link-offline.elf')=='13e14ec6a6ad1ad30142cf0ae28f57691e35d4d6435db8cc11208bba7726e65d'
 assert sha(LOOP/'build/loop-startup-test.elf')=='001356fa53c2cd1d2e66ba9e1d8d5c6e37c8d1f64a05898bfd465d3ab45aa496'
 a=symbols(BASE/'build/nam-link-offline.elf');b=symbols(LOOP/'build/loop-startup-test.elf')
 engine=next(k for k in a if k.startswith('_ZN3mpp2fx6Engine7process'))
 aliases={'__aeabi_memcpy':0x54bd,'__aeabi_memcpy4':0x54bd,'__aeabi_memclr4':0x556d,'mpp_fx_get':a['mpp_fx_get'],'mpp_reply_send':a['mpp_reply_send'],'old_loop_startup':b['mpp_loop_startup'],'old_loop_service':b['mpp_loop_service'],'old_loop_query':b['mpp_loop_query'],'stock_engine_process':a[engine],'stock_engines':a['_ZN12_GLOBAL__N_17enginesE']}
 out=HERE/'build';out.mkdir(exist_ok=True)
 ld='''ENTRY(mpp_extra_startup)
MEMORY { BOOT(rx): ORIGIN=0x1d7c4,LENGTH=0x6c
 ZERO(rx): ORIGIN=0x1c238,LENGTH=0x38
 CODE(rx): ORIGIN=0x2031a020,LENGTH=0x7e0
 STATE(rw): ORIGIN=0x20319c00,LENGTH=0xe0
 TONE(rw): ORIGIN=0x20319d00,LENGTH=0x80 }
SECTIONS {
 .extra_boot : { *(.extra_boot*) } > BOOT
 .master_zero : { *(.master_zero*) } > ZERO
 .text : AT(0x303ab000) { __extra_code_start=.; *(.text*) *(.rodata*) . = ALIGN(4); __extra_code_end=.; } > CODE
 __extra_code_load = LOADADDR(.text);
 .data : { *(.data*) } > STATE
 .tone (NOLOAD) : { *(.tone*) } > TONE
 .bss (NOLOAD) : { *(.bss*) *(COMMON) } > STATE
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
ASSERT(SIZEOF(.data)==0,"No initialized globals")
ASSERT(SIZEOF(.text)<=0x1000,"Flash extent")
'''
 # LLD requires spaces around assignment in these linker expressions.
 ld=ld.replace('ORIGIN=','ORIGIN = ').replace('LENGTH=','LENGTH = ').replace('start=.;','start = .;').replace('end=.;','end = .;')
 ld+='\n'+'\n'.join(f'PROVIDE({k} = {v:#x});' for k,v in aliases.items())+'\n'
 (out/'extra.ld').write_text(ld)
 flags=['--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=vfpv3-d16','-mfloat-abi=hard','-std=c++17','-Oz','-ffreestanding','-fno-builtin','-ffp-contract=off','-fno-exceptions','-fno-rtti','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wall','-Wextra','-Werror']
 subprocess.run(['clang++',*flags,'-c',str(Path(__file__).with_name('stock_block.cpp')),'-o',str(out/'extra.o')],check=True)
 subprocess.run([str(Path(ziglang.__path__[0])/'zig'),'cc','-target','thumb-freestanding-eabihf','-mcpu=cortex_m7','-nostdlib','-Wl,-e,mpp_extra_startup','-Wl,-T,'+str(out/'extra.ld'),str(out/'extra.o'),'-o',str(out/'extra.elf')],check=True)
 with (out/'extra.elf').open('rb') as f:
  e=ELFFile(f);assert not [s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF']
  regions=[dict(name=s.name,start=hex(s['sh_addr']),end=hex(s['sh_addr']+s['sh_size']),bytes=s['sh_size']) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']]
 (out/'build.json').write_text(json.dumps(dict(status='BUILT_NAMLNK30_OFFLINE_EXTENSION',sha256=sha(out/'extra.elf'),sources={p.name:sha(p) for p in [Path(__file__).with_name('stock_block.cpp'),Path(__file__)]},regions=regions,flags=flags),indent=2)+'\n')
 print(regions)
if __name__=='__main__':build()
