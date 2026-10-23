#!/usr/bin/env python3
"""NAMLNK28: saved loop settings and direct button gestures, offline build only."""
import argparse,importlib.util,sys,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('layers_build',HERE.parent/'layers/build_next.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
identity='NAMLNK28'
diagnostics=HERE/'diagnostics.cpp'
extra_sources=[HERE.parent/'layers/buttons.cpp',HERE/'storage.cpp']
sources=prior.sources+sorted(HERE.glob('*.hpp'))+sorted(HERE.glob('*.cpp'))+[Path(__file__)]
def file_flags(src):return ['-Os'] if src.name!='audio.cpp' else []
def transform_core(core):
 core=prior.transform_core(core).replace('#include "layers/session.hpp"','#include "settings/session.hpp"')
 core=core.replace('    unsigned events=control.take_events();audio->sync();', '    unsigned events=control.take_events();audio->sync();\n    if(events&mighty_loop::toggle_overdub)audio->set_overdub(!audio->overdubbing);')
 core=core.replace('    if(!audio || !mpp_loop_allowed())return 0;', '    extern volatile bool mpp_loop_saving;\n    if(!audio || !mpp_loop_allowed() || mpp_loop_saving)return 0;')
 # The new tap-then-hold state adds four bytes to Controls, before the store.
 offsets={1608:1612,80:84,84:88,96:100,404:408,920:924,1572:1576}
 core=re.sub(r'==([0-9]+)',lambda m:'=='+str(offsets.get(int(m[1]),int(m[1]))),core)
 return core
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('baseline',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 spec=importlib.util.spec_from_file_location('hardware_build',HERE.parent/'hardware/build_test.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
 build.build(a.baseline,a.output,sys.modules[__name__])
