"""Build an isolated delay/reverb hard-bypass sleep experiment. Never flash.

Retains the baseline identity only for the ARM harness. Production sources and
verified update containers remain unchanged. Re-enable intentionally discards
old history through the stock foreground loader, with existing switch settling.
"""
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args()
out=a.output.resolve();root=Path(__file__).resolve().parents[1]
if out.exists():p.error('Use a new output directory; never overwrite a verified build.')
original=(root/'target/link/stock_chain_firmware.cpp').read_text();changed=original
def replace(before,after):
    global changed
    assert changed.count(before)==1, 'Baseline changed; review the patch'
    changed=changed.replace(before,after)

replace('uint16_t mpp_bypass_hold[11];', '''uint16_t mpp_bypass_hold[11];
// OFFLINE EXPERIMENT ONLY. Reuse the stock type-change handoff in foreground.
// 65534 denotes a used tail effect put to sleep, distinct from fresh bypass.
extern "C" BANK_TEXT void mpp_tail_resume(unsigned stage){
 const auto* preset=*(const volatile uint8_t**)0x20005ad0;
 unsigned type=preset[stage]&63;
 const unsigned maximum=stage==7?5:6;
 if(type<1||type>maximum)type=1;
 auto* base=(volatile uint8_t*)(stage==7?0x20003a08u:0x200041d8u);
 base[0]=type;base[1]=0;
 *(volatile uint32_t*)(base+12)=127;
 *(volatile uint32_t*)(base+(stage==7?44:40))=0;
}
''')
replace('  "ldrb r1, [r1, r0]\\n"','  "mov r3, r0\\n"\n  "ldrb r1, [r1, r0]\\n"')
replace('''  // Gate/delay/reverb retain small bypass residuals in stock V1.5.6.
  // Once used, keep their stock path alive; do not truncate those signals.
  "cmp r0, #5\\n"
  "beq 5f\\n"
  "cmp r0, #7\\n"
  "beq 5f\\n"
  "cmp r0, #8\\n"
  "beq 5f\\n"
''','''  "cmp r0, #7\\n"
  "beq 10f\\n"
  "cmp r0, #8\\n"
  "bne 11f\\n"
  "10: ldrh r1, [r2]\\n"
  "movw r3, #65534\\n"
  "cmp r1, r3\\n"
  "bne 12f\\n"
  "push {r0-r3,r12,lr}\\n"
  "bl mpp_tail_resume\\n"
  "pop {r0-r3,r12,lr}\\n"
  // Finish sleeping two blocks before the existing 1200-block mute settles.
  "12: movw r0, #1198\\n"
  "b 6f\\n"
  "11: cmp r0, #5\\n"
  "beq 5f\\n"
''')
replace('''  "cbz r0, 2f\\n"
  "movw r1, #65535\\n"''','''  "cbz r0, 2f\\n"
  "movw r1, #65534\\n"
  "cmp r0, r1\\n"
  "beq 2f\\n"
  "movw r1, #65535\\n"''')
replace('''  "subs r0, #1\\n"
  "strh r0, [r2]\\n"''','''  "subs r0, #1\\n"
  "bne 13f\\n"
  "cmp r3, #7\\n"
  "beq 14f\\n"
  "cmp r3, #8\\n"
  "bne 13f\\n"
  "14: movw r0, #65534\\n"
  "13: strh r0, [r2]\\n"''')
with tempfile.TemporaryDirectory(prefix='tail-sleep-source-',dir=out.parent) as temp:
    trial=Path(temp);shutil.copytree(root/'target',trial/'target');(trial/'tools').mkdir()
    shutil.copyfile(root/'tools/build_link_firmware.py',trial/'tools/build_link_firmware.py')
    (trial/'target/link/stock_chain_firmware.cpp').write_text(changed)
    subprocess.run([sys.executable,str(trial/'tools/build_link_firmware.py'),str(out),
        '--stock-chain','--m7-conv','--fast-bypass','--m7-dense','--prime-state','--irq-timing',
        '--listening','--early-output','--output-buffer','--preset-bank','--performance',
        '--tuner','--fx-blocks','--cut-eq','--responsive-controls','--nam-pointer',
        '--adc-short-delay','--global-buffer'],check=True,stdout=subprocess.DEVNULL)
report=json.loads((out/'build.json').read_text())
report.update(status='OFFLINE_EXPERIMENT_NOT_INSTALLABLE',experimental=True,
    experiment='Delay/reverb hard-bypass sleep with stock foreground reset on wake',
    bypass='Delay/reverb sleep after 1198 bypass blocks and reset on wake; used gate retains keepalive',
    release_identity_assigned=False,flash_container_created=False,
    baseline_source_sha256=hashlib.sha256(original.encode()).hexdigest(),
    experimental_source_sha256=hashlib.sha256(changed.encode()).hexdigest())
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'stock_chain_firmware.experimental.cpp').write_text(changed)
(out/'DO-NOT-FLASH.txt').write_text('Offline experiment only. No release identity or flashable firmware. Baseline identity retained for CPU harness only.\n')
print('Built offline tail-sleep experiment; no update container or device access.')
