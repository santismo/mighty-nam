#!/usr/bin/env python3
"""Link an offline ARM entry diagnostic. No upload or updater-file generation."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
import ziglang

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('build_dir',type=Path)
 p.add_argument('--startup-control',action='store_true',help='Include early watchdog control and read-only clock audit in an offline variant')
 a=p.parse_args()
 root=Path(__file__).resolve().parents[1];build=a.build_dir.resolve();build.mkdir(parents=True,exist_ok=True)
 sources=['target/diagnostic/entry.S','target/diagnostic/image.cpp',
  'target/hardware/direct_mmio.cpp','target/hardware/handoff.cpp','target/hardware/rt1176_backend.cpp',
  'target/standalone/prototype.cpp','target/standalone/clock_plan.cpp',
  'target/board/audio_transport.cpp','target/board/codec_control.cpp',
  'target/link/model_receiver.cpp','target/a2/a2_lite.cpp']
 if a.startup_control:sources+=['target/hardware/startup_watchdogs.S','target/hardware/startup_clock.cpp']
 arm=['--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=fpv5-d16','-mfloat-abi=hard']
 if a.startup_control:arm+=['-DMPP_STARTUP_CONTROL=1']
 flags=['-std=c++20','-O2','-Wall','-Wextra','-Werror','-ffp-contract=off',
  '-ffreestanding','-fno-builtin','-fno-exceptions','-fno-rtti',
  '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-ffunction-sections','-fdata-sections']
 objects=[]
 for src in sources:
  obj=build/(Path(src).stem+'.o')
  subprocess.run(['clang++',*arm,*(flags if src.endswith('.cpp') else []),'-c',str(root/src),'-o',str(obj)],check=True)
  objects.append(str(obj))
 elf=build/('startup-control-offline-only.elf' if a.startup_control else 'entry-diagnostic-offline-only.elf')
 linker=root/'target/diagnostic/offline_candidate.ld'
 # Retain every linked function so unresolved target integration errors cannot
 # hide behind dead stripping. Reset still calls only the diagnostic path.
 subprocess.run([str(Path(ziglang.__path__[0])/'zig'),'cc','-target','thumb-freestanding-eabihf',
  '-mcpu=cortex_m7','-nostdlib','-Wl,--no-gc-sections','-Wl,--build-id=none','-Wl,-e,mpp_diag_reset',
  '-Wl,-T,'+str(linker),*objects,'-o',str(elf)],check=True)
 with elf.open('rb') as f:
  e=ELFFile(f);syms={s.name:s for s in e.get_section_by_name('.symtab').iter_symbols()}
  undef=[s.name for s in syms.values() if s.name and s['st_shndx']=='SHN_UNDEF'];assert not undef,undef
  regions=[dict(name=s.name,start=hex(s['sh_addr']),size=s['sh_size'],stored_in_file=s['sh_type']!='SHT_NOBITS') for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']]
  value=lambda n:syms[n]['st_value']
  assert e.header['e_entry']==value('mpp_diag_reset')
  sizes={n:syms[n]['st_size'] for n in ['mpp_diag_app','mpp_diag_receiver','mpp_diag_status']}
  report={'status':'LINKED_OFFLINE_STARTUP_CONTROL' if a.startup_control else 'LINKED_OFFLINE_ENTRY_DIAGNOSTIC',
   'startup_control_included':a.startup_control,'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),
   'regions':regions,'object_sizes':sizes,'load_bytes_through_data':value('__image_load_end'),
   'dtcm_initialized_or_zeroed_bytes':value('__bss_end')-value('__data_start'),
   'candidate_dtcm_gap_before_stack_bytes':value('__stack_bottom')-value('__bss_end'),
   'stack_reserved_bytes':value('__stack_top')-value('__stack_bottom'),
   'undefined_symbols':undef,'retained_all_functions':True,'physical_memory_ownership_verified':False,
   'loader_acceptance_verified':False,'updater_container_generated':False,
   'audio_driver_called_by_entry':False,'device_access':False,'playback':False,
   'sources':{s:hashlib.sha256((root/s).read_bytes()).hexdigest() for s in sources+['target/diagnostic/offline_candidate.ld',
    'target/hardware/handoff.hpp','target/hardware/rt1176_backend.hpp','target/standalone/prototype.hpp',
    'target/standalone/platform.hpp','target/link/model_receiver.hpp','target/a2/a2_lite.hpp',
    'target/board/audio_transport.hpp','target/board/codec_control.hpp','tools/build_entry_diagnostic.py']+
    (['target/hardware/startup_clock.hpp'] if a.startup_control else [])}}
 (build/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
