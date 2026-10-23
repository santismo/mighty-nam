#include "controls.hpp"
#include <cassert>
#include <cstdio>
using namespace mighty_loop;
int main(){
 Controls c;unsigned now=40;
 auto wait=[&](unsigned n,bool preset=false,bool power=false){for(unsigned i=0;i<n;++i)c.update(++now,preset,power);};
 auto tap=[&](){wait(60,true);wait(60);};
 auto hold=[&](){wait(900,true);wait(100);};
 wait(60);tap();assert(c.color==1);tap();assert(c.color==2);hold();assert(c.color==1&&c.direction==1);hold();assert(c.color==0);tap();assert(c.color==1);
 // Long holds are one step, never a direction toggle or repeat.
 wait(4000,true);wait(80);assert(c.color==0);tap();assert(c.color==1);
 c.mode=Mode::looper;c.loop=Loop::playing;c.frames=1000;c.take_events();wait(400);hold();
 assert(c.loop==Loop::playing&&(c.take_events()&toggle_overdub));
 wait(400);hold();assert(c.loop==Loop::playing&&(c.take_events()&toggle_overdub));
 tap();assert(c.loop==Loop::paused);wait(400);tap();assert(c.loop==Loop::playing);
 wait(400);tap();hold();assert(c.loop==Loop::empty&&c.frames==0&&(c.take_events()&clear_loop));
 wait(400);tap();assert(c.loop==Loop::armed);wait(400);hold();assert(c.loop==Loop::armed);
 c.audio(1,100);assert(c.loop==Loop::recording);wait(400);hold();assert(c.loop==Loop::recording);
 tap();assert(c.loop==Loop::playing);wait(400);hold();assert(c.loop==Loop::playing&&(c.take_events()&toggle_overdub));
 // Millisecond wrap and buttons held at boot must not trigger clears.
 Controls b;b.mode=Mode::looper;b.loop=Loop::playing;b.frames=100;
 for(unsigned i=0;i<1200;++i)b.update(i,true,false);assert(!b.take_events());
 for(unsigned i=1200;i<1300;++i)b.update(i,false,false);assert(b.loop==Loop::playing);
 puts("{\"status\":\"PASS_LOOP_GESTURES\",\"tap_forward_hold_previous\":true,\"hold_overdub\":true,\"tap_hold_clear\":true,\"recording_preserved\":true}");
}
