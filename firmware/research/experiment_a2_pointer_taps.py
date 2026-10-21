"""Build a local, offline-only A2 tap-address experiment from exact source.

No production source edits, flash container, USB or audio access. The ELF keeps
the baseline identity solely for the existing CPU harness and is NOT a release.
"""
import argparse,hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('output',type=Path)
a=p.parse_args();out=a.output.resolve()
if out.exists():p.error('Output must be a new directory; do not replace a verified build.')
root=Path(__file__).resolve().parents[1]
source=root/'target/a2/a2_lite.cpp'
original=source.read_text()
changed=original
edits=[
 ('   unsigned taps=k;\n   float z0=0,z1=0,z2=0;',
  '   unsigned taps=k;\n   const float* tap_history=ring+3*col;\n   const float* history_end=ring+3*length;\n   const unsigned history_step=d*12,history_span=length*12;\n   float z0=0,z1=0,z2=0;'),
 ('    "add r12, %[col], %[col], lsl #1\\n"\n    "add r12, %[ring], r12, lsl #2\\n"\n    "vldmia r12, {s12-s14}\\n"',
  '    "vldmia %[history], {s12-s14}\\n"'),
 ('    "add %[col], %[col], %[d]\\n"\n    "cmp %[col], %[length]\\n"\n    "it hs\\n"\n    "subhs %[col], %[col], %[length]\\n"',
  '    "add %[history], %[history], %[step]\\n"\n    "cmp %[history], %[end]\\n"\n    "it hs\\n"\n    "subhs %[history], %[history], %[span]\\n"'),
 ('    : [col] "+&r"(col),[weights] "+&r"(w),[taps] "+&r"(taps),',
  '    : [history] "+&r"(tap_history),[weights] "+&r"(w),[taps] "+&r"(taps),'),
 ('    : [ring] "r"(ring),[d] "r"(d),[length] "r"(length)',
  '    : [step] "r"(history_step),[end] "r"(history_end),[span] "r"(history_span)'),
]
for before,after in edits:
    assert changed.count(before)==1,'Baseline kernel changed; review the experiment.'
    changed=changed.replace(before,after)
with tempfile.TemporaryDirectory(prefix='nam-pointer-source-',dir=out.parent) as temp:
    trial=Path(temp)
    shutil.copytree(root/'target',trial/'target')
    (trial/'tools').mkdir()
    shutil.copyfile(root/'tools/build_link_firmware.py',trial/'tools/build_link_firmware.py')
    (trial/'target/a2/a2_lite.cpp').write_text(changed)
    subprocess.run([sys.executable,str(trial/'tools/build_link_firmware.py'),str(out),
        '--stock-chain','--m7-conv','--fast-bypass','--m7-dense','--prime-state','--irq-timing',
        '--listening','--early-output','--output-buffer','--preset-bank','--performance',
        '--tuner','--fx-blocks','--cut-eq','--responsive-controls'],check=True,stdout=subprocess.DEVNULL)
report=json.loads((out/'build.json').read_text())
report.update(status='OFFLINE_EXPERIMENT_NOT_INSTALLABLE',experimental=True,
    experiment='A2 pointer tap addressing; floating-point arithmetic order unchanged',
    release_identity_assigned=False,flash_container_created=False,
    baseline_source_sha256=hashlib.sha256(original.encode()).hexdigest(),
    experimental_source_sha256=hashlib.sha256(changed.encode()).hexdigest())
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'DO-NOT-FLASH.txt').write_text('Offline experiment only. No release identity or flashable firmware. The baseline identity is retained for CPU testing only.\n')
print('Built offline pointer-tap experiment; no firmware image or device access.')
