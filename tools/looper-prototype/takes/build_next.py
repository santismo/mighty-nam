#!/usr/bin/env python3
"""NAMLNK29 independent takes and coherent preset programming. Offline only."""
import argparse,importlib.util,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('settings_build',HERE.parent/'settings/build_next.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
identity='NAMLNK29'
diagnostics=HERE/'diagnostics.cpp'
extra_sources=prior.extra_sources
sources=prior.sources+sorted(HERE.glob('*.hpp'))+sorted(HERE.glob('*.cpp'))+[Path(__file__)]
def file_flags(src):return ["-Oz"] if src.name!="audio.cpp" else []
def transform_core(core):
 core=prior.transform_core(core).replace('#include "settings/session.hpp"','#include "takes/session.hpp"')
 # Old tests introspected the destructive merge store's object offsets. N29
 # exports status and tests the actual methods; it does not share that layout.
 core=core[:core.index('\n#pragma clang diagnostic push')]+core[core.index('\n#pragma clang diagnostic pop')+len('\n#pragma clang diagnostic pop'):]
 core+='\nstatic_assert(sizeof(LoopSession)<4096,"Looper state budget");\nextern "C" void mpp_loop_takes(uint32_t* out){audio->store.status(out);}\n'
 core+='\nextern "C" void __aeabi_memcpy4(void* dst,const void* src,unsigned n){auto* d=(volatile unsigned char*)dst;auto* s=(const unsigned char*)src;for(unsigned i=0;i<n;++i)d[i]=s[i];}\n'
 core=core.replace('    if(op!=1)return 1;', """    if(op>=6 && op<=9)return audio->store.level(op-6,arg)?0:2;
    if(op==10)return audio->store.mute(arg/2,arg&1)?0:2;
    if(op==11){bool ok=audio->store.erase_take(arg);audio->sync();return ok?0:2;}
    if(op==12){
        if(control.loop!=Loop::playing || !audio->store.begin_take(arg))return 2;
        audio->capture1.reset();audio->capture2.reset();audio->overdubbing=true;return 0;
    }
    if(op!=1)return 1;""")
 core=core.replace('    else return 1;\n    audio->sync();', '''    else if(arg==11){bool ok=audio->store.undo();audio->sync();return ok?0:2;}
    else if(arg==12)return audio->store.redo()?0:2;
    else if(arg==13)return audio->set_overdub(true)?0:2;
    else if(arg==14)return audio->set_overdub(false)?0:2;
    else return 1;
    audio->sync();''')
 core=core.replace('audio->store.commits','audio->store.commit_count()')
 core=core.replace('!audio->rewind_pending) {','!audio->rewind_pending && !audio->store.swap_pending) {')
 core+='''
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Winvalid-offsetof"
extern "C" const unsigned mpp_loop_layout[]={sizeof(LoopSession),
 __builtin_offsetof(LoopSession,store)+__builtin_offsetof(TakeStore,length),
 __builtin_offsetof(LoopSession,store)+__builtin_offsetof(TakeStore,cursor),
 __builtin_offsetof(LoopSession,store)+__builtin_offsetof(TakeStore,decoder),
 __builtin_offsetof(LoopSession,play1),__builtin_offsetof(LoopSession,play_phase)};
#pragma clang diagnostic pop
'''
 return core
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('baseline',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 spec=importlib.util.spec_from_file_location('hardware_build',HERE.parent/'hardware/build_test.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
 build.build(a.baseline,a.output,sys.modules[__name__])
