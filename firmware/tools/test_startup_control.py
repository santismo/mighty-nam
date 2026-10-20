#!/usr/bin/env python3
"""Rebuild and check the offline watchdog/clock milestone. No device access."""
import argparse,json,subprocess,sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('build_dir',type=Path);a=p.parse_args()
 r=Path(__file__).resolve().parents[1];b=a.build_dir.resolve();b.mkdir(parents=True,exist_ok=True)
 with (b/'build.log').open('w') as f:
  subprocess.run([sys.executable,str(r/'tools/build_entry_diagnostic.py'),str(b/'arm'),'--startup-control'],check=True,stdout=f)
 with (b/'vm-tests.log').open('w') as f:
  subprocess.run([sys.executable,str(r/'research/test_startup_control.py'),str(b/'arm/startup-control-offline-only.elf'),
   '--output',str(b/'vm-tests.json')],check=True,stdout=f)
 for mode,extra in [('native',[]),('sanitizers',['-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
  exe=b/('clock-'+mode)
  subprocess.run(['clang++','-std=c++20','-O2','-Wall','-Wextra','-Werror',*extra,
   str(r/'target/hardware/startup_clock.cpp'),str(r/'tests/test_startup_clock.cpp'),'-o',str(exe)],check=True)
  output=subprocess.check_output([str(exe)],text=True);json.loads(output);(b/('clock-'+mode+'.json')).write_text(output)
 report={'status':'PASS_OFFLINE_STARTUP_CONTROL','arm':json.loads((b/'arm/build.json').read_text()),
  'vm':json.loads((b/'vm-tests.json').read_text()),'native':json.loads((b/'clock-native.json').read_text()),
  'sanitizers':json.loads((b/'clock-sanitizers.json').read_text()),'device_access':False,'playback':False}
 (b/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'status':report['status'],'arm_cases':report['vm']['case_count'],
  'clock_divider_combinations':report['native']['divider_combinations'],'device_access':False,'playback':False}))
if __name__=='__main__':main()
