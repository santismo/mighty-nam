#!/usr/bin/env python3
"""Compile next looper prototype into the audited RAM windows, offline only.

No updater container is produced. Includes exact stock button/LED adapters.
"""
import argparse, importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
identity='NAMLNK27'
diagnostics=HERE/'diagnostics.cpp'
extra_sources=[HERE/'buttons.cpp']
sources=sorted(HERE.glob('*.hpp'))+sorted(HERE.glob('*.cpp'))+[Path(__file__)]
def file_flags(src):
    # Keep the baseline guitar hook at O2. Size-optimize only this new loop
    # engine and diagnostics; ARM instruction budgets are measured separately.
    return ['-Os'] if src.name in ['core.cpp','diagnostics.cpp','buttons.cpp'] else []
def transform_core(core):
    core=core.replace('#include "compressed_audio.hpp"','#include "layers/session.hpp"')
    core=core.replace('CompressedAudio','LoopSession')
    core=core.replace('void mpp_listen_reset();','void mpp_listen_reset();\nvoid mpp_loop_buttons_tick();')
    core=core.replace('alignas(Controls) uint8_t controls_object[sizeof(Controls)];\nControls* controls;\n#define control (*controls)', '#define control (audio->controls)')
    core=core.replace('    controls=new(controls_object) Controls{};\n','')
    core=core.replace('        case 8:return audio->store.failed;','''        case 8:return audio->store.failed;
        case 9:return unsigned(control.mode) | (audio->overdubbing?2:0) |
                      (audio->store.dirty?4:0) | (control.direction<0?8:0);
        case 10:return audio->threshold_db | (audio->volume<<8) | ((audio->ratio==4?60u:30u)<<16);
        case 11:return audio->store.commits;
        case 12:return audio->meter_word();''')
    lo=core.index('unsigned mpp_loop_apply(');hi=core.index('void mpp_loop_capture(',lo)
    core=core[:lo]+'''unsigned mpp_loop_apply(unsigned cmd) {
    unsigned op=cmd>>8,arg=cmd&255;
    if(op==2)return audio->set_threshold(arg)?0:2;
    if(op==3)return audio->set_volume(arg)?0:2;
    if(op==4)return audio->set_seconds(arg)?0:2;
    if(op!=1)return 1;
    if(arg==1) {
        if(control.loop!=Loop::empty || audio->store.length)return 2;
        control.mode=Mode::looper;control.preset_tap();
    }else if(arg==2) {
        if(control.loop==Loop::empty)return 2;
        control.mode=Mode::looper;control.preset_tap();
    }else if(arg==3)control.power_single();
    else if(arg==4)control.power_double();
    else if(arg==5)control.clear();
    else if(arg==6)return audio->set_overdub(!audio->overdubbing)?0:2;
    else if(arg==7) {
        if(!audio->store.length || control.loop==Loop::recording)return 2;
        control.loop=Loop::playing;
    }else if(arg==8) {
        if(control.loop!=Loop::playing)return 2;
        control.loop=Loop::paused;
    }else if(arg==9)control.mode=Mode::looper;
    else if(arg==10) { if(control.mode==Mode::looper)control.power_single(); }
    else return 1;
    audio->sync();return 0;
}
''' +core[hi:]
    core=core.replace('(control.loop!=Loop::armed && control.loop!=Loop::recording)',
                      '(control.loop!=Loop::armed && control.loop!=Loop::recording && !audio->overdubbing)')
    core=core.replace('control.loop!=Loop::playing) {','control.loop!=Loop::playing && !audio->store.dirty && !audio->rewind_pending) {')
    core=core.replace('    mpp_loop_before_tick();','    mpp_loop_buttons_tick();\n    mpp_loop_before_tick();')
    core=core.replace('    mpp_loop_buttons_tick();','    if(audio)audio->meter_decay();\n    mpp_loop_buttons_tick();')
    marker='    if(!mpp_loop_allowed() || (control.loop!=Loop::armed'
    core=core.replace(marker,'    for(unsigned i=0;i<8;++i)audio->meter_sample(float(rx[4*i+3])*0x1p-31f,ready);\n'+marker)
    core=core.replace('''        bool playback=control.loop==Loop::playing;
        audio->frame(control,recorded_raw[i],playback?0:recorded_guitar[i],
                     playback?false:guitar_ready,0,0,l,r);
        bus[i]=playback?l:0;''','''        audio->frame(recorded_raw[i],recorded_guitar[i],guitar_ready,0,0,l,r);
        bus[i]=audio->loop_output;''')
    core+='''
extern "C" unsigned mpp_loop_control_tick(unsigned now,unsigned inputs) {
    if(!audio || !mpp_loop_allowed())return 0;
    control.color=(inputs>>8)&7;control.occupied=(inputs>>16)&127;
    control.update_debounced(now,inputs&1,inputs&2);
    unsigned events=control.take_events();audio->sync();
    return (events&mighty_loop::select_preset)?control.color+1:0;
}
extern "C" bool mpp_loop_led_visible(unsigned now) {
    return !audio || !mpp_loop_allowed() || control.preset_led_on(now);
}
'''
    core+='\n#pragma clang diagnostic push\n#pragma clang diagnostic ignored "-Winvalid-offsetof"\nstatic_assert(sizeof(LoopSession)==1608,"Update ARM fixture layout");\nstatic_assert(__builtin_offsetof(LoopSession,store)+__builtin_offsetof(OverdubStore,length)==80);\nstatic_assert(__builtin_offsetof(LoopSession,store)+__builtin_offsetof(OverdubStore,cursor)==84);\nstatic_assert(__builtin_offsetof(LoopSession,store)+__builtin_offsetof(OverdubStore,decoder)==96);\nstatic_assert(__builtin_offsetof(LoopSession,store)+__builtin_offsetof(OverdubStore,cached)==404);\nstatic_assert(__builtin_offsetof(LoopSession,play1)==920);\nstatic_assert(__builtin_offsetof(LoopSession,play_phase)==1572);\n#pragma clang diagnostic pop\n'
    return core
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('hardware_build',HERE.parent/'hardware/build_test.py')
    build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
    import sys
    build.build(a.baseline,a.output,sys.modules[__name__])
