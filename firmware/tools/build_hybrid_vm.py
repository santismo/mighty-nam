#!/usr/bin/env python3
"""Build an ARM ELF ONLY for the offline VM. Requires ziglang==0.13.0, clang.
Uses a saved subset of that Zig distribution's unmodified musl math sources.
Standard musl headers come from the same pinned Zig distribution.
No host callbacks substitute for ARM math. No USB or audio dependencies.
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
import ziglang

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('build_dir',type=Path)
profiles=p.add_mutually_exclusive_group()
profiles.add_argument('--candidate-v1',action='store_true',help='Use candidate padding addresses; still emulator-only')
profiles.add_argument('--reclaimed-v1',action='store_true',help='Reuse retired stock AMP code; still emulator-only')
a=p.parse_args(); a.build_dir.mkdir(parents=True,exist_ok=True)
stock_profile=a.candidate_v1 or a.reclaimed_v1
profile='reclaimed-v1' if a.reclaimed_v1 else ('candidate-v1' if a.candidate_v1 else 'hybrid')
root=Path(__file__).resolve().parents[1]
zig=Path(ziglang.__path__[0]); libc=zig/'lib/libc'; musl=libc/'musl'
math_src=root/'third_party/musl-math'
version=subprocess.check_output([str(zig/'zig'),'version'],text=True).strip()
if version!='0.13.0': raise ValueError('Revalidate a different Zig/musl version first')
# Restrict FPU instructions to the VFPv3-D16 subset supported by both the
# target's DP FPU and Unicorn's A15 instruction-compatibility test model.
flags=['--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=vfpv3-d16',
       '-mfloat-abi=hard','-O2','-ffreestanding','-fno-builtin','-ffp-contract=off',
       '-fdata-sections','-ffunction-sections']
objects=[]; sources={}
cpp_sources=[root/'src/engine.cpp',root/'target/hybrid/amp_hook.cpp']
if stock_profile:cpp_sources.append(root/'target/hybrid/stock_v1_wrapper.cpp')
for src in cpp_sources:
    out=a.build_dir/(src.stem+'.o');objects.append(out)
    subprocess.run(['clang++',*flags,'-std=c++20','-fno-exceptions','-fno-rtti',
        '-I',str(root/'include'),'-I',str(root/'target'),'-c',str(src),'-o',str(out)],check=True)
for name in ['expf','tanhf','expm1f','exp2f_data','__math_oflowf','__math_uflowf','__math_xflowf']:
    src=math_src/(name+'.c');out=a.build_dir/(name+'.o');objects.append(out)
    sources[name+'.c']=hashlib.sha256(src.read_bytes()).hexdigest()
    subprocess.run(['clang',*flags,'-Dhidden=',
        '-I',str(math_src),
        '-isystem',str(libc/'include/arm-linux-musl'),
        '-isystem',str(libc/'include/generic-musl'),'-c',str(src),'-o',str(out)],check=True)
elf=root/('artifacts/'+profile+'-lab-only.elf' if stock_profile else 'artifacts/hybrid-vm-only.elf')
entry='mpp_stock_amp_process' if stock_profile else 'mpp_hybrid_amp'
linker='reclaimed_v1.ld' if a.reclaimed_v1 else ('candidate_v1.ld' if a.candidate_v1 else 'vm_only.ld')
subprocess.run([str(zig/'zig'),'cc','-target','thumb-freestanding-eabihf','-mcpu=cortex_m7',
    '-nostdlib','-Wl,--gc-sections','-Wl,-e,'+entry,'-Wl,-T,'+str(root/'target/hybrid'/linker),
    *[str(x) for x in objects],'-o',str(elf)],check=True)
manifest={'status':'LINKED_FOR_SYNTHETIC_VM_ONLY_NOT_DEVICE_FIRMWARE',
    'candidate_stock_addresses':stock_profile,'profile':profile,
    'zig_version':version,'fpu_instruction_subset':'VFPv3-D16, hard float, contraction disabled',
    'math':'Unmodified bundled musl expf/tanhf/expm1f and support routines',
    'math_source_sha256':sources,
    'math_header_sha256':{n:hashlib.sha256((math_src/n).read_bytes()).hexdigest() for n in ['libm.h','fp_arch.h','exp2f_data.h']},
    'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),
    'hardware_loadable':False,'device_or_audio_access':False}
if stock_profile:manifest['status']='CANDIDATE_PLACEMENT_LAB_ONLY_NOT_DEVICE_FIRMWARE'
(root/('artifacts/'+profile+'-build.json')).write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
