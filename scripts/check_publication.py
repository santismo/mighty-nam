#!/usr/bin/env python3
"""Check tracked/release source for accidental private material. Read-only."""
from pathlib import Path
import re, subprocess, hashlib
root=Path(__file__).resolve().parents[1]
if (root/'.git').exists():
 names=subprocess.check_output(['git','ls-files','-co','--exclude-standard'],cwd=root,text=True).splitlines()
 paths=[root/p for p in sorted(set(names))]
else:
 ignored={'.git','.venv','build','__pycache__','.dart_tool','Pods','ephemeral','.symlinks','xcuserdata'}
 paths=[p for p in root.rglob('*') if p.is_file() and not(set(p.relative_to(root).parts)&ignored)]
allowed_models={'lstm.nam','wavenet.nam','wavenet_a1_standard.nam'}
licensed_models={
 'firmware/models/riffsmith/riffsmith-clean.nam':'433f93c73abfc86b1ab46adc8ec7e0eaa46a7286727708880c285c10a1642741',
 'firmware/models/riffsmith/riffsmith-bass-clean.nam':'af11453ec552c93acc9cf2de76de56b730a3cad4c18bffba9a71b9b84ca7eff6',
 'firmware/models/riffsmith/riffsmith-distorted.nam':'ec52e16296f96fdd1d07d1aaa699e33e17df253f026f785f135080e1eb5db007',
}
patterns=[re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|t3k_cs_[A-Za-z0-9]{15,})'),re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile('/' + r'Users/[^/\s]+/'),re.compile(r'(?:access_token|refresh_token)"\s*:\s*"[A-Za-z0-9_.-]{35,}"')]
errors=[]
for p in paths:
 rel=p.relative_to(root)
 if p.suffix in {'.bin','.elf','.dmg','.wav','.mp3','.zip','.dylib','.o','.a'}:errors.append(str(rel)+': generated/private binary')
 if p.suffix=='.nam' and not ((rel.parent==Path('firmware/models') and p.name in allowed_models) or (licensed_models.get(str(rel))==hashlib.sha256(p.read_bytes()).hexdigest())):errors.append(str(rel)+': unapproved capture')
 if p.is_symlink():errors.append(str(rel)+': unexpected symlink');continue
 try:s=p.read_text()
 except UnicodeDecodeError:continue
 for pattern in patterns:
  if pattern.search(s):errors.append(str(rel)+': private material pattern (value withheld)')
for required in ['LICENSE','THIRD_PARTY_NOTICES.md','app/LICENSE.md','firmware/models/riffsmith/LICENSE','firmware/models/riffsmith/provenance.json','app/assets/RIFFSMITH-LICENSE','firmware/third_party/nam/LICENSE','firmware/third_party/eigen/COPYING.MPL2','firmware/third_party/musl-math/COPYRIGHT']:
 if not (root/required).is_file():errors.append('Missing notice: '+required)
if errors:raise SystemExit('\n'.join(errors))
print(f'PASS publication check: {len(paths)} files; no blocked private paths, secrets, binaries or captures')
