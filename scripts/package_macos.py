#!/usr/bin/env python3
"""Package an existing signed app. No device access, installation or audio."""
import argparse, hashlib, json, platform, shutil, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('app',type=Path);p.add_argument('output',type=Path)
a=p.parse_args();root=Path(__file__).resolve().parents[1]
if platform.system()!='Darwin':p.error('Creating a DMG requires macOS and hdiutil.')
app=a.app.resolve()
if not (app/'Contents/Info.plist').is_file():p.error('Expected a built NAM Plug.app bundle')
subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
a.output.mkdir(parents=True,exist_ok=True)
dmg=a.output.resolve()/'NAM-Plug-0.3.0-macOS.dmg'
if dmg.exists():p.error('Output exists; choose an empty output directory.')
with tempfile.TemporaryDirectory(prefix='nam-plug-installer-') as tmp:
 stage=Path(tmp)/'NAM Plug';stage.mkdir()
 subprocess.run(['ditto',str(app),str(stage/'NAM Plug.app')],check=True)
 (stage/'Applications').symlink_to('/Applications')
 for name in ['LICENSE','THIRD_PARTY_NOTICES.md']:
  shutil.copy2(root/name,stage/name)
 licenses=stage/'Licenses';licenses.mkdir()
 shutil.copy2(root/'app/LICENSE.md',licenses/'Mightier-Amp-and-NAM-Plug-MIT.txt')
 shutil.copy2(root/'app/plugins/nam_device/LICENSE',licenses/'NAM-Device-MIT.txt')
 (stage/'Install NAM Plug.txt').write_text('''NAM Plug 0.3 — Mac preview by santismo

1. Drag NAM Plug.app onto the Applications shortcut.
2. Open NAM Plug from Applications. Eject this disk image afterward.
3. Connect the Mighty Plug Pro by USB in normal mode.

The app installer does not change the plug firmware or system audio.
NAM device control requires compatible custom firmware; read the guide first.
The app is universal Intel/Apple silicon and declares macOS 10.15 minimum.
This preview is ad-hoc signed, not Apple notarized. If macOS blocks launch,
first attempt to open it, then review System Settings > Privacy & Security
and use Open Anyway if you choose to trust this release. Do not disable
Gatekeeper globally. Older macOS versions place this under System Preferences.

Guide: https://santismo.github.io/nam-plug/guide.html
Source: https://github.com/santismo/nam-plug
License: MIT for original project contributions; third-party notices retained.

Seven onboard presets require NAMLNK10, which still awaits hardware testing.
Keep headphones unplugged for initial device/firmware checks.
''')
 subprocess.run(['hdiutil','create','-volname','NAM Plug','-srcfolder',str(stage),'-format','UDZO','-ov',str(dmg)],check=True)
subprocess.run(['hdiutil','verify',str(dmg)],check=True)
record={'file':dmg.name,'sha256':hashlib.sha256(dmg.read_bytes()).hexdigest(),'bytes':dmg.stat().st_size,'app_version':'0.3.0','signing':'ad-hoc; not notarized','installs_firmware':False}
(dmg.parent/'SHA256SUMS.txt').write_text(record['sha256']+'  '+dmg.name+'\n')
(dmg.parent/'installer.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
