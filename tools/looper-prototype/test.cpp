// MIT (c) 2026 santismo. Synthetic buttons only; no hardware/audio access.
#include "controls.hpp"
#include <assert.h>
#include <stdio.h>
#include <limits>
#include <initializer_list>
using namespace mighty_loop;
struct Test {
    Controls c; uint32_t t; bool pre=false,pow=false;
    explicit Test(uint32_t start=0):t(start) { wait(50); }
    void wait(unsigned ms) { for(unsigned i=0;i<ms;++i)c.update(++t,pre,pow); }
    void tap(bool power) { (power?pow:pre)=true;wait(80);(power?pow:pre)=false;wait(50); }
    void single() { tap(true);wait(Controls::double_ms+1); }
    void twice() { tap(true);wait(60);tap(true);wait(Controls::double_ms+1); }
    void hold(bool power,unsigned ms) { (power?pow:pre)=true;wait(ms);(power?pow:pre)=false;wait(400); }
};
void complete_sequence(uint32_t start) {
    Test x(start); x.twice(); assert(x.c.mode==Mode::looper && x.c.loop==Loop::empty);
    x.tap(false); assert(x.c.loop==Loop::armed);
    x.c.audio(.009f,8);x.c.audio(std::numeric_limits<float>::quiet_NaN(),8);
    assert(x.c.loop==Loop::armed && x.c.frames==0);
    x.c.audio(.02f,8); assert(x.c.loop==Loop::recording && x.c.frames==8);
    x.c.audio(.001f,800); x.tap(false);
    assert(x.c.loop==Loop::playing && x.c.frames==808);
    x.single(); assert(x.c.mode==Mode::presets && x.c.loop==Loop::playing);
    x.tap(false); assert(x.c.color==1 && x.c.loop==Loop::playing);
    x.single(); assert(x.c.mode==Mode::looper && x.c.loop==Loop::playing);
    x.tap(false); assert(x.c.loop==Loop::paused && x.c.frames==808 && x.c.color==1);
    x.single(); assert(x.c.mode==Mode::presets && x.c.loop==Loop::paused);
    x.tap(false); assert(x.c.color==2 && x.c.loop==Loop::paused);
    x.single();x.tap(false); assert(x.c.loop==Loop::playing && x.c.frames==808);
    x.twice();assert(x.c.mode==Mode::presets && x.c.loop==Loop::stopped && x.c.frames==808);
    x.single();x.tap(false);assert(x.c.loop==Loop::playing); // reenter + resume
    x.single();x.twice();assert(x.c.mode==Mode::presets && x.c.loop==Loop::stopped);
}
int main() {
    complete_sequence(0);complete_sequence(0xfffff900u); // wrap during normal use
    unsigned occupancy_cases=0;
    for(unsigned mask=0;mask<128;++mask) for(unsigned color=0;color<7;++color) for(int d:{-1,1}) {
        Controls c;c.occupied=mask;c.color=color;c.direction=d;
        int expected=color;
        for(int i=1;i<=7;++i) {int n=(int(color)+7+d*i)%7;if(mask&(1u<<n)){expected=n;break;}}
        c.advance_preset();assert(c.color==expected);++occupancy_cases;
    }
    Test h;h.hold(false,4000);assert(h.c.direction==-1 && h.c.color==0);
    h.tap(false);assert(h.c.color==2);h.hold(false,1000);assert(h.c.direction==1 && h.c.color==2);
    h.tap(false);assert(h.c.color==0);h.twice();h.hold(false,1000);assert(h.c.direction==1);
    Test p;p.hold(true,3000);assert(p.c.take_events()==request_shutdown && p.c.mode==Mode::presets);
    Test s;s.single();assert(s.c.take_events()==0); // no stock short-POWER mute
    s.tap(true);s.wait(60);s.pow=true;s.wait(2500);s.pow=false;s.wait(400);
    assert(s.c.take_events()==request_shutdown && s.c.mode==Mode::presets);
    Test bounce;
    for(int i=0;i<10;++i){bounce.pow=true;bounce.wait(10);bounce.pow=false;bounce.wait(10);}
    bounce.wait(400);assert(bounce.c.take_events()==0);
    Test boot;boot.c=Controls{};boot.pre=boot.pow=true;boot.wait(4000);
    assert(boot.c.take_events()==0);boot.pre=boot.pow=false;boot.wait(400);
    assert(boot.c.take_events()==0);boot.tap(false);assert(boot.c.color==1);
    Test a;a.twice();a.tap(false);a.single();assert(a.c.loop==Loop::empty && a.c.mode==Mode::presets);
    a.twice();a.tap(false);a.c.audio(.1f,8);a.single();assert(a.c.loop==Loop::playing && a.c.mode==Mode::presets);
    Test b;b.twice();b.tap(false);b.c.audio(.1f,8);b.twice();assert(b.c.loop==Loop::empty && b.c.frames==0);
    Test capacity;capacity.c.capacity=16;capacity.twice();capacity.tap(false);
    capacity.c.audio(.1f,8);capacity.c.audio(.1f,100000);assert(capacity.c.frames==16 && capacity.c.loop==Loop::playing);
    Test empty;empty.c.capacity=0;empty.twice();empty.tap(false);empty.c.audio(.1f,8);assert(empty.c.loop==Loop::armed);
    // A first POWER release must not change view until its double-tap window expires.
    Test d;d.twice();d.tap(false);d.c.audio(.1f,8);d.tap(false);d.c.take_events();
    d.tap(true);assert(d.c.mode==Mode::looper && d.c.take_events()==0);
    d.tap(true);assert(d.c.mode==Mode::presets && d.c.loop==Loop::stopped);
    printf("{\"status\":\"PASS_OFFLINE_LOOPER_CONTROLS\",\"occupancy_cases\":%u,\"control_state_bytes\":%zu,\"audio_buffer_allocated\":false,\"device_access\":false,\"host_audio_access\":false,\"firmware_integrated\":false,\"physical_buttons_verified\":false}\n",occupancy_cases,sizeof(Controls));
}
