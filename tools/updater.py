#!/usr/bin/env python3
"""NAM Plug release verification. No erase, flash, reset or playback commands.

A manifest's hashes detect mismatched bytes; they are not an author signature.
Use releases and manifests from a source you trust. The factory USB writer is
still the official NUX utility; this tool can open it after local validation.
"""
import argparse,hashlib,json,sys,subprocess
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
 return h.hexdigest()
def verify(manifest,image,restore):
 j=json.loads(manifest.read_text());need=lambda value,msg: (_ for _ in ()).throw(ValueError(msg)) if not value else None
 need(j.get('schema')=='nam-plug-release-1' and j.get('target')=='NUX-MP3','Unsupported target or release schema')
 f=j['firmware'];need(isinstance(f['identity'],str) and len(f['identity'])==8 and f['identity'].startswith('NAM'),'Invalid custom identity')
 need(image.stat().st_size==f['bytes'] and sha(image)==f['sha256'],'Image does not match release manifest')
 need(restore.stat().st_size==j['restore']['bytes'] and sha(restore)==j['restore']['sha256'],'Restore image does not match manifest')
 need(j['loader']['vid']==0x9527 and j['loader']['pid']==0xc157 and j['loader']['identifier']=='20220615','Unsupported loader')
 return {'status':'RELEASE_FILES_VERIFIED','identity':f['identity'],'sha256':f['sha256'],'restore_sha256':j['restore']['sha256'],'image':str(image.resolve()),'manifest_is_author_signature':False,'device_access':False,'flash_performed':False,'audio_playback':False,'installation_backend':'NUX Device Updater for macOS','next_step':'Enter update mode, identify the loader, and select this exact image in the official updater.'}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path);p.add_argument('image',type=Path);p.add_argument('--restore',type=Path,required=True);p.add_argument('--open-official',action='store_true',help='Open the official utility after validation; does not select a file or begin flashing');a=p.parse_args()
 row=verify(a.manifest,a.image,a.restore)
 if a.open_official:
  if sys.platform!='darwin':raise ValueError('Official updater handoff currently requires macOS')
  app=Path('/Applications/NUX Device Updater.app');
  if not app.is_dir():raise ValueError('Install the official NUX Device Updater first')
  subprocess.run(['open','-a',str(app)],check=True);row['official_updater_opened']=True
 print(json.dumps(row,indent=2))
if __name__=='__main__':
 try:main()
 except (ValueError,KeyError,OSError,json.JSONDecodeError) as e:print('Release rejected: '+str(e),file=sys.stderr);sys.exit(1)
