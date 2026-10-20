#!/usr/bin/env python3
"""Build offline Mac reference bridge against separately obtained, pinned Core."""
from pathlib import Path
import argparse,subprocess
p=argparse.ArgumentParser(description=__doc__);p.add_argument('core',type=Path);p.add_argument('output',type=Path)
p.add_argument('--reference-order',action='store_true',help='Use reference operation grouping in the compact engine')
a=p.parse_args();r=Path(__file__).resolve().parents[1]
commit=subprocess.check_output(['git','-C',str(a.core),'rev-parse','HEAD'],text=True).strip()
if commit!='ab72c078cd141be60d963d357bd501d56cc9606b':raise ValueError('Expected verified NAM Core v0.5.2 commit')
if subprocess.check_output(['git','-C',str(a.core),'diff','--name-only','HEAD','--','NAM'],text=True).strip():raise ValueError('Reference Core sources must be unmodified')
a.output.parent.mkdir(parents=True,exist_ok=True)
src=sorted((a.core/'NAM').glob('*.cpp'))+sorted((a.core/'NAM').glob('*/*.cpp'))
subprocess.run(['clang++','-std=c++20','-O2','-ffp-contract=off','-DNAM_SAMPLE_FLOAT',
 *(['-DMPP_REFERENCE_ORDER'] if a.reference_order else []),'-fPIC','-shared','-I'+str(a.core),'-I'+str(r/'third_party/eigen'),'-I'+str(a.core/'Dependencies/nlohmann'),'-I'+str(r/'target/a2'),str(r/'research/a2_host_bridge.cpp'),str(r/'target/a2/a2_lite.cpp'),*map(str,src),'-o',str(a.output)],check=True)
print('Built offline reference bridge; generic official WaveNet, no A2 fast path')
