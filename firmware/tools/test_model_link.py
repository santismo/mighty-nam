#!/usr/bin/env python3
"""Reproduce silent app/firmware model-link checks. Files and local processes only.

Requires clang++ and a Dart 3.6+ SDK. Run `dart pub get` in the adjacent app's
packages/nam_link first. Does not install, flash, play audio or contact a plug.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--dart', type=Path, required=True)
p.add_argument('--app', type=Path, default=Path(__file__).resolve().parents[2]/'mighty-plug-app')
p.add_argument('--build', type=Path, required=True)
p.add_argument('--models', type=Path, nargs='*', default=[])
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
build = a.build.resolve(); build.mkdir(parents=True, exist_ok=True)
dart = a.dart.resolve(); package = a.app.resolve()/'packages/nam_link'
sources = [root/'target/link/model_receiver.cpp', root/'target/a2/a2_lite.cpp']
flags = ['-std=c++20','-O2','-ffp-contract=off','-Wall','-Wextra','-Werror']
def run(args, cwd=None):
    return subprocess.check_output([str(x) for x in args], cwd=cwd, text=True)

report = {'mode':'OFFLINE_FILES_ONLY','device_access':False,'playback':False,'firmware_loadable':False,'checks':{},'wire_codec':{}}
for name, extra in [('native',[]),('sanitizers',['-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
    run(['clang++',*flags,*extra,*sources,root/'tests/test_model_receiver.cpp','-o',build/name])
    report['checks'][name] = json.loads(run([build/name]))
    run(['clang++',*flags,*extra,root/'target/link/sysex_codec.cpp',root/'tests/test_sysex_codec.cpp','-o',build/(name+'-codec')])
    report['wire_codec'][name] = run([build/(name+'-codec')]).strip()
run(['clang++',*flags,*sources,root/'research/model_transfer_interop.cpp','-o',build/'interop'])
run(['clang++',*flags,'--target=arm-none-eabi','-mcpu=cortex-m7','-mthumb','-mfpu=fpv5-d16',
    '-mfloat-abi=hard','-ffreestanding','-fno-builtin','-fno-exceptions','-fno-rtti','-c',sources[0],'-o',build/'model_receiver.o'])
report['arm_receiver_object_sha256'] = hashlib.sha256((build/'model_receiver.o').read_bytes()).hexdigest()
(build/'dart-tests.log').write_text(run([dart,'test','-r','expanded'], cwd=package))
traces = [('--fixture','fixture')] + [(str(m.resolve()),m.stem) for m in a.models]
report['interop'] = []
for model, name in traces + [(None,'faults')]:
    prefix = build/name
    if model is None:
        run([dart,'run','bin/export_fault_trace.dart',prefix],cwd=package)
    else:
        run([dart,'run','bin/export_trace.dart',model,prefix],cwd=package)
    result = json.loads(run([build/'interop',str(prefix)+'.requests',str(prefix)+'.cpp-replies',str(prefix)+'.slot']))
    assert Path(str(prefix)+'.cpp-replies').read_bytes() == Path(str(prefix)+'.replies').read_bytes()
    result.update(name=name,replies_bit_identical=True,slot_sha256=hashlib.sha256(Path(str(prefix)+'.slot').read_bytes()).hexdigest())
    report['interop'].append(result)
report['sources_sha256'] = {str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources + [root/'target/link/model_receiver.hpp',root/'tests/test_model_receiver.cpp',root/'research/model_transfer_interop.cpp']}
report['status'] = 'PASS_HOST_AND_ARM_COMPILE_ONLY'
(build/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
