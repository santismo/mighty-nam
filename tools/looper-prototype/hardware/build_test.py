#!/usr/bin/env python3
"""Build the NAMLNK25 startup/RAM diagnostic ELF offline. No device access."""
import argparse, hashlib, json, subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
import ziglang

BASELINE_SHA = '13e14ec6a6ad1ad30142cf0ae28f57691e35d4d6435db8cc11208bba7726e65d'
ROOT = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def build(baseline, output, variant=None):
    baseline=baseline.resolve(); output=output.resolve(); output.mkdir(parents=True,exist_ok=True)
    elf=baseline/'build/nam-link-offline.elf'
    if sha(elf)!=BASELINE_SHA: raise ValueError('Exact NAMLNK24 baseline required')
    with elf.open('rb') as f:
        e=ELFFile(f); symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols() if s.name}
    source=(baseline/'generated/target/link/stock_chain_firmware.cpp').read_text()
    start=source.index('extern "C" void mpp_probe_audio('); end=source.index('extern "C" BANK_TEXT void mpp_probe_version',start)
    body=source[start:end].replace('void mpp_probe_audio(', 'void mpp_loop_probe_audio(')
    for old,new in [
        (' ++mpp_link.callbacks;', ' mpp_loop_tick();\n ++mpp_link.callbacks;'),
        (' if(!mpp_link.ready||!mpp_link.running){', ' if(!mpp_link.ready||!mpp_link.running){\n  mpp_loop_render(tx);'),
        ('\n mpp_listen_render(mpp_link_output,chain_right,tx);', '\n mpp_listen_render(mpp_link_output,chain_right,tx);\n mpp_loop_render(tx);'),
        (' mpp_usb_finish(mpp_link_output,chain_right);', ' mpp_loop_capture(rx,mpp_link_output,chain_right,!mpp_listen_warm);\n mpp_usb_finish(mpp_link_output,chain_right);')]:
        assert body.count(old)==1,old; body=body.replace(old,new)
    # Reuse the exact declaration preamble from the existing tested overlay.
    script=(ROOT.parent/'build_continuity.py').read_text()
    preamble=script.split("preamble='''",1)[1].split("'''",1)[0]
    (output/'audio.cpp').write_text(preamble+body)
    core=(ROOT.parent/'continuity.cpp').read_text()
    core=core.replace('#include "layout.hpp"','#include "layout.hpp"\n#include "hardware/diagnostics.hpp"')
    core=core.replace('Controls control;','alignas(Controls) uint8_t controls_object[sizeof(Controls)];\nControls* controls;\n#define control (*controls)')
    core=core.replace('control=Controls{};','controls=new(controls_object) Controls{};')
    lo=core.index('void mpp_loop_command('); hi=core.index('void mpp_loop_capture(',lo)
    core=core[:lo]+'''// Commands are applied only in the audio IRQ, never concurrently with DSP.
unsigned mpp_loop_apply(unsigned cmd) {
    if(cmd==1) {
        if(control.loop!=Loop::empty || audio->store.length)return 2;
        control.mode=Mode::looper;control.preset_tap();audio->sync(control);return 0;
    }
    if(cmd==2) {
        if(control.loop==Loop::empty)return 2;
        control.mode=Mode::looper;control.preset_tap();audio->sync(control);return 0;
    }
    if(cmd==3){control.power_single();audio->sync(control);return 0;}
    if(cmd==4){control.power_double();audio->sync(control);return 0;}
    if(cmd==5) {
        if(control.loop==Loop::recording || control.loop==Loop::playing)return 2;
        mpp_loop_init();audio->sync(control);return 0;
    }
    return 1;
}
''' +core[hi:]
    core=core.replace('    for(unsigned i=0;i<8;++i) {\n        recorded_raw',
        '    if(!mpp_loop_allowed() || (control.loop!=Loop::armed && control.loop!=Loop::recording))return;\n    for(unsigned i=0;i<8;++i) {\n        recorded_raw')
    core=core.replace('    if(!audio)return;', '''    mpp_loop_before_tick();
    if(!audio || !mpp_loop_allowed())return;
    if(audio->store.failed){mpp_loop_fail(16,0);return;}
    if(control.loop!=Loop::armed && control.loop!=Loop::recording && control.loop!=Loop::playing) {
        for(float& sample:bus)sample=0;
        guitar_ready=false;return;
    }''')
    core=core.replace('    if(!audio || audio->store.failed || mpp_link.faults)return;',
        '    if(!audio || !mpp_loop_allowed() || control.loop!=Loop::playing || audio->store.failed || mpp_link.faults)return;')
    if variant: core=variant.transform_core(core)
    (output/'core.cpp').write_text(core)
    flags=['--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=vfpv3-d16','-mfloat-abi=hard','-std=c++17','-O2',
        '-ffreestanding','-fno-builtin','-ffp-contract=off','-fno-exceptions','-fno-rtti','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wall','-Wextra','-Werror']
    defines=[x for x in json.loads((baseline/'build/build.json').read_text())['compiler_flags'] if x.startswith('-D')]
    assert '-DMPP_EARLY_OUTPUT' in defines and not any(x.startswith('-DMPP_DMA_') for x in defines)
    objects=[]
    for src in [output/'core.cpp',output/'audio.cpp',variant.diagnostics if variant else ROOT/'diagnostics.cpp',ROOT/'startup.cpp',*(variant.extra_sources if variant else [])]:
        obj=output/(src.stem+'.o')
        extra=variant.file_flags(src) if variant else []
        subprocess.run(['clang++',*flags,*extra,*defines,'-I'+str(ROOT.parent),'-I'+str(baseline/'generated/target/link'),'-c',str(src),'-o',str(obj)],check=True);objects.append(obj)
    aliases={k:v for k,v in symbols.items() if k.startswith('mpp_')}
    aliases['chain_right']=symbols['_ZL11chain_right']
    for name,base in [('init','stock_amp_init'),('service','bank_service'),('irq','link_irq'),('query','probe_query')]:aliases['mpp_base_'+name]=symbols['mpp_'+base]
    ld=output/'test.ld';ld.write_text((ROOT/'test.ld').read_text()+'\n'+'\n'.join(f'PROVIDE({k} = {v:#x});' for k,v in aliases.items())+'\n')
    target=output/'loop-startup-test.elf'
    subprocess.run([str(Path(ziglang.__path__[0])/'zig'),'cc','-target','thumb-freestanding-eabihf','-mcpu=cortex_m7','-nostdlib','-Wl,-e,mpp_loop_startup','-Wl,-T,'+str(ld),*[str(o) for o in objects],'-o',str(target)],check=True)
    with target.open('rb') as f:
        e=ELFFile(f);assert not [s.name for s in e.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF']
        regions=[dict(name=s.name,start=hex(s['sh_addr']),bytes=s['sh_size'],end=hex(s['sh_addr']+s['sh_size'])) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']]
    sources=list(ROOT.glob('*.cpp'))+list(ROOT.glob('*.hpp'))+[ROOT/'test.ld',Path(__file__)]+list(ROOT.parent.glob('*.hpp'))+[ROOT.parent/'continuity.cpp',ROOT.parent/'build_continuity.py']
    if variant: sources+=list(variant.sources)
    report=dict(status='BUILT_OFFLINE_STARTUP_TEST',identity=variant.identity if variant else 'NAMLNK25',baseline_sha256=sha(elf),sha256=sha(target),regions=regions,
        source_hashes={str(p.relative_to(ROOT.parent)):sha(p) for p in sorted(sources)},compiler_flags=flags+defines,
        per_file_flags={src:variant.file_flags(Path(src)) for src in ['core.cpp','audio.cpp','diagnostics.cpp','startup.cpp']} if variant else {},
        flash_container_created=False,physical_RAM_safe_proven=False,device_access=False)
    (output/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(regions,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('baseline',type=Path);p.add_argument('output',type=Path);a=p.parse_args();build(a.baseline,a.output)
