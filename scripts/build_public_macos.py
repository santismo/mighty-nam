#!/usr/bin/env python3
"""Build a public Mac preview in a neutral path, strip debug paths, and sign ad hoc.

Does not install or launch the app, access the plug, or change audio settings.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--flutter', default='flutter')
parser.add_argument('--config', type=Path, required=True,
                    help='JSON containing only the publishable TONE3000_CLIENT_ID')
parser.add_argument('--output', type=Path, required=True)
a = parser.parse_args()
root = Path(__file__).resolve().parents[1]
config = json.loads(a.config.read_text())
if (set(config) != {'TONE3000_CLIENT_ID'} or
        not isinstance(config['TONE3000_CLIENT_ID'], str) or
        not config['TONE3000_CLIENT_ID'].startswith('t3k_pub_')):
    parser.error('Only a publishable client ID may enter a public build')
output = a.output.resolve()
if output.exists():
    parser.error('Output exists; choose a new output path')
flutter = shutil.which(a.flutter)
if not flutter:
    parser.error('Flutter executable not found')
with tempfile.TemporaryDirectory(prefix='mighty-nam-public-', dir='/tmp') as temp:
    stage = Path(temp).resolve()
    app = stage / 'app'
    shutil.copytree(root / 'app', app, ignore=shutil.ignore_patterns(
        'build', '.dart_tool', 'Pods', 'ephemeral', '.symlinks',
        'xcuserdata', '*.xcuserstate', 'tone3000.json'))
    config_path = stage / 'public-client.json'
    config_path.write_text(json.dumps(config))
    subprocess.run([flutter, 'pub', 'get'], cwd=app, check=True)
    subprocess.run([flutter, 'build', 'macos', '--release',
                    '--dart-define-from-file=' + str(config_path)], cwd=app, check=True)
    built = app / 'build/macos/Build/Products/Release/mighty-nam.app'
    # Keep dynamic exports while removing local/debug symbol tables.
    for path in built.rglob('*'):
        if path.is_symlink() or not path.is_file():
            continue
        kind = subprocess.check_output(['file', '-b', str(path)], text=True)
        if 'Mach-O' in kind:
            subprocess.run(['strip', '-S', '-x', str(path)], check=True)
    subprocess.run(['codesign', '--force', '--deep', '--sign', '-',
                    '--entitlements', str(app / 'macos/Runner/Release.entitlements'),
                    str(built)], check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(built)], check=True)
    for path in built.rglob('*'):
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            if b'/Users/' in data or b'/Users/' in data.replace(b'\0', b''):
                raise RuntimeError('Private build path remains in ' + str(path.relative_to(built)))
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ditto', str(built), str(output)], check=True)
print('Built public preview:', output.name)
