#!/usr/bin/env python3
"""Package an existing signed app. No device access, installation or audio."""
import argparse, hashlib, json, platform, plistlib, re, shutil, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('app',type=Path);p.add_argument('output',type=Path)
a=p.parse_args();root=Path(__file__).resolve().parents[1]
if platform.system()!='Darwin':p.error('Creating a DMG requires macOS and hdiutil.')
app=a.app.resolve()
if not (app/'Contents/Info.plist').is_file():p.error('Expected a built mighty-nam.app bundle')
info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
version=info['CFBundleShortVersionString']
if not re.fullmatch(r'\d+\.\d+\.\d+',version):p.error('Unexpected app version')
subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
signature=subprocess.run(['codesign','-d','--verbose=2',str(app)],capture_output=True,text=True,check=True).stderr
if 'Authority=Apple Development:' not in signature:
 p.error('Sign this preview with the same Apple Development identity used for previous builds before packaging; ad-hoc signatures can cause repeated Keychain approvals.')
a.output.mkdir(parents=True,exist_ok=True)
dmg=a.output.resolve()/f'mighty-nam-{version}-macOS.dmg'
if dmg.exists():p.error('Output exists; choose an empty output directory.')
with tempfile.TemporaryDirectory(prefix='nam-plug-installer-') as tmp:
 stage=Path(tmp)/'mighty-nam';stage.mkdir()
 subprocess.run(['ditto',str(app),str(stage/'mighty-nam.app')],check=True)
 (stage/'Applications').symlink_to('/Applications')
 for name in ['LICENSE','THIRD_PARTY_NOTICES.md']:
  shutil.copy2(root/name,stage/name)
 licenses=stage/'Licenses';licenses.mkdir()
 shutil.copy2(root/'app/LICENSE.md',licenses/'Mightier-Amp-and-mighty-nam-MIT.txt')
 shutil.copy2(root/'app/plugins/nam_device/LICENSE',licenses/'NAM-Device-MIT.txt')
 (stage/'Install mighty-nam.txt').write_text(f'''mighty-nam {version} — Mac preview by santismo

1. Drag mighty-nam.app onto the Applications shortcut.
2. Open mighty-nam from Applications. Eject this disk image afterward.
3. Connect the Mighty Plug Pro by USB in normal mode.

The app installer does not change the plug firmware or system audio.
NAM device control requires compatible custom firmware; read the guide first.
The app is universal Intel/Apple silicon and declares macOS 10.15 minimum.
This local preview is development signed, not Apple notarized. If macOS blocks launch,
first attempt to open it, then review System Settings > Privacy & Security
and use Open Anyway if you choose to trust this release. Do not disable
Gatekeeper globally. Older macOS versions place this under System Preferences.

Guide: https://github.com/santismo/mighty-nam/blob/main/docs/guide.html
Source: https://github.com/santismo/mighty-nam
License: MIT for original project contributions; third-party notices retained.

Seven onboard presets require NAMLNK10 or newer.
Keep headphones unplugged for initial device/firmware checks.
''')
 subprocess.run(['hdiutil','create','-volname','mighty-nam','-srcfolder',str(stage),'-format','UDZO','-ov',str(dmg)],check=True)
subprocess.run(['hdiutil','verify',str(dmg)],check=True)
record={'file':dmg.name,'sha256':hashlib.sha256(dmg.read_bytes()).hexdigest(),'bytes':dmg.stat().st_size,'app_version':version,'signing':'Apple Development; not notarized','installs_firmware':False}
(dmg.parent/'SHA256SUMS.txt').write_text(record['sha256']+'  '+dmg.name+'\n')
(dmg.parent/'installer.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
