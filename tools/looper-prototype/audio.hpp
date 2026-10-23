// MIT (c) 2026 santismo. Offline only; no chosen hardware RAM address or I/O.
#pragma once
#include "controls.hpp"
#include <stddef.h>

namespace mighty_loop {
// PCM16 mono prototype. The caller owns the entire storage lifetime. In firmware
// this must be separate from every guitar/preset reset and stock clear routine.
// Calls are serialized here; an interrupt-safe command mailbox is still needed.
struct Audio {
    static constexpr unsigned pre_roll=64;
    int16_t* storage;
    uint32_t capacity, cursor=0;
    int16_t history[pre_roll]{};
    unsigned history_count=0, history_next=0;
    Loop previous=Loop::empty;
    float level=.5f;
    unsigned seam_frames=0; // optional edge fade; no period shortening or latency

    Audio(int16_t* memory,uint32_t frames):storage(memory),capacity(memory?frames:0) {}
    static float finite(float x) { return __builtin_isfinite(x)?x:0.f; }
    static float limit(float x) { x=finite(x);return x>.875f?.875f:x<-.875f?-.875f:x; }
    static int16_t encode(float x) {
        x=finite(x);x=x>32767.f/32768.f?32767.f/32768.f:x<-1.f?-1.f:x;
        return int16_t(x*32768.f);
    }
    void sync(Controls& c) {
        c.capacity=capacity;
        if(c.frames>capacity)c.frames=capacity;
        if(c.loop==Loop::armed && previous!=Loop::armed) {
            history_count=history_next=0;cursor=0;
        }
        if(c.loop==Loop::empty || c.loop==Loop::stopped ||
           (c.loop==Loop::playing && previous==Loop::recording))cursor=0;
        previous=c.loop;
    }
    // Record only post-effects guitar, never backing music or the loop itself.
    // raw_guitar is the threshold input. guitar_ready=false models preset-load
    // settling: only live guitar is absent; loop cursor/mix continue unchanged.
    void frame(Controls& c,float raw_guitar,float processed_guitar,bool guitar_ready,
               float backing_left,float backing_right,float& left,float& right) {
        sync(c);
        const float guitar=guitar_ready?finite(processed_guitar):0.f;
        const float peak=__builtin_fabsf(finite(raw_guitar));
        bool recorded=false;
        if(c.loop==Loop::armed && guitar_ready && peak>=c.threshold && capacity) {
            const unsigned n=history_count<capacity?history_count:capacity-1;
            const unsigned start=(history_next+pre_roll-n)%pre_roll;
            for(unsigned i=0;i<n;++i)storage[i]=history[(start+i)%pre_roll];
            c.begin_record(n);
        }
        if(c.loop==Loop::recording) {
            if(c.frames<capacity)storage[c.frames]=encode(guitar);
            c.audio(0.f,1);recorded=true;
            if(c.loop==Loop::playing)cursor=0;
        } else if(c.loop==Loop::armed) {
            history[history_next]=encode(guitar);history_next=(history_next+1)%pre_roll;
            if(history_count<pre_roll)++history_count;
        }
        float loop=0.f;
        if(c.loop==Loop::playing && c.frames && !recorded) {
            if(cursor>=c.frames)cursor=0;
            float gain=1.f;
            unsigned edge=seam_frames<c.frames/2?seam_frames:c.frames/2;
            if(edge) {
                if(cursor<edge)gain=float(cursor+1)/float(edge+1);
                if(c.frames-cursor<=edge)gain=float(c.frames-cursor)/float(edge+1);
            }
            loop=float(storage[cursor])/32768.f*gain*finite(level);
            cursor=(cursor+1)%c.frames;
        }
        left=limit(guitar+loop+finite(backing_left));
        right=limit(guitar+loop+finite(backing_right));
        previous=c.loop;
    }
};
} // namespace mighty_loop
