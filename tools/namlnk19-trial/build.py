#!/usr/bin/env python3
"""Compile NAMLNK19 physical-check tools without running them or opening MIDI/audio."""
import argparse,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args()
here=Path(__file__).resolve().parent;root=here.parents[1];out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
native=root/'app/plugins/nam_device/macos/Classes'
base=[native/'NamLinkWire.swift',native/'NamMidi.swift'];helpers=here/'physical_helpers.swift'
for name,extra in {'inspect':[here/'inspect.swift'],'restore':[helpers,here/'restore_supplement.swift',here/'restore.swift'],'timing':[helpers,here/'timing.swift'],'global':[helpers,here/'global.swift'],'verify-restart':[helpers,here/'verify_restart.swift']}.items():
 subprocess.run(['swiftc','-O',*map(str,base+extra),'-o',str(out/name)],check=True)
for name,source in [('mpp_driver_client',root/'firmware/tools/mpp_driver_client.c'),('driver-header',here/'driver-header.c')]:
 subprocess.run(['clang','-Wall','-Wextra','-Werror','-Wno-deprecated-declarations','-I',str(root/'firmware/tools'),str(source),'-framework','CoreMIDI','-framework','CoreFoundation','-o',str(out/name)],check=True)
print('Compiled only. No device or audio operations performed.')
