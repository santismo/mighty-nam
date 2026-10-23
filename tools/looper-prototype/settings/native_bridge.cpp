// MIT (c) 2026 santismo. Native oracle only; never linked into firmware.
#include "session.hpp"
#include <new>
using namespace mighty_loop;
alignas(LoopSession) static unsigned char object[sizeof(LoopSession)];
static LoopSession* a;
extern "C" {
void lp_init(uint8_t* p,unsigned bytes,unsigned rate,unsigned samples) {
    a=new(object) LoopSession(p,bytes,samples);a->set_seconds(rate==12000?60:30);
}
void lp_command(unsigned cmd) {
    auto& c=a->controls;
    if(cmd==0){c.mode=Mode::looper;c.preset_tap();}
    if(cmd==1){c.mode=Mode::looper;c.preset_tap();}
    if(cmd==2)c.power_single();
    if(cmd==3)c.power_double();
    if(cmd==4)c.clear();
    if(cmd==5)a->set_overdub(!a->overdubbing);
    a->sync();
}
void lp_fixture_play(unsigned n){a->store.length=n;a->controls.frames=n*a->ratio;a->controls.loop=Loop::playing;a->controls.mode=Mode::presets;}
void lp_fixture_block(unsigned cursor){a->store.cursor=cursor;a->store.decoder={};a->play_phase=0;a->play1.reset();a->play2.reset();a->store.cached=a->store.dirty=false;}
unsigned lp_state(unsigned key){
    switch(key){case 0:return a->store.length;case 1:return a->store.cursor;
        case 5:return a->played_frames;case 6:return a->store.failed;default:return 0;}
}
void lp_process8(const float* raw,const float* guitar,float* out,unsigned ready){
    for(unsigned i=0;i<8;++i){float l,r;a->frame(raw[i],guitar[i],ready,0,0,l,r);out[i]=a->loop_output;out[i+8]=r;}
}
}
