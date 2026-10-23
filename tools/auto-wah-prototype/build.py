"""Build the integrated wah into an offline-only research ELF; no container."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args()
subprocess.run([sys.executable,str(ROOT/'firmware/tools/build_public_v3.py'),str(a.output),'--bluetooth-audio','--daisy-wah'],check=True)
f=a.output/'build/build.json';m=json.loads(f.read_text());m.update(status='OFFLINE_WAH_PROTOTYPE_NOT_FOR_INSTALLATION',research_only=True)
f.write_text(json.dumps(m,indent=2)+'\n')
