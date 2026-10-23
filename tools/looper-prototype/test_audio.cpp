// MIT (c) 2026 santismo. Memory-only samples; no sound device or files played.
#include "audio.hpp"
#include <assert.h>
#include <stdio.h>
#include <math.h>
#include <limits>
#include <initializer_list>
using namespace mighty_loop;
static void sample(Audio& a,Controls& c,float raw,float wet,bool ready=true) {
    float l,r;a.frame(c,raw,wet,ready,0,0,l,r);
    assert(__builtin_isfinite(l) && __builtin_isfinite(r));
}
int main() {
    unsigned switches=0;uint64_t playback_frames=0;
    for(unsigned block:{8,16,32}) {
        int16_t memory[4098]{};memory[0]=1234;memory[4097]=-1234;
        Audio a(memory+1,4096);Controls c;
        c.power_double();c.preset_tap();
        for(unsigned i=0;i<100;++i)sample(a,c,.005f,float(i)/1000);
        assert(c.loop==Loop::armed);
        sample(a,c,.02f,.1f);assert(c.frames==65 && c.loop==Loop::recording);
        assert(a.storage[0]==Audio::encode(.036f) && a.storage[63]==Audio::encode(.099f));
        for(unsigned i=0;i<512;++i)sample(a,c,.01f,.1f*sinf(i*.1f));
        c.preset_tap();assert(c.loop==Loop::playing && c.frames==577);
        c.power_single();assert(c.mode==Mode::presets);
        // All seven live presets, each with a synthetic 200 ms reload/settling
        // interval. The expected loop never resets or enters the new guitar FX.
        c.occupied=127;uint32_t expected=0;
        for(unsigned preset=0;preset<7;++preset) {
            c.preset_tap();++switches;
            for(unsigned frame=0;frame<24000;frame+=block)for(unsigned j=0;j<block;++j) {
                bool ready=frame+j>=9600;
                float guitar=ready?.03f*float(preset+1):0.f,l,r;
                float loop=float(a.storage[expected])/32768.f*.5f;
                a.frame(c,.3f,guitar,ready,.02f,-.02f,l,r);
                assert(l==Audio::limit(guitar+loop+.02f));
                assert(r==Audio::limit(guitar+loop-.02f));
                expected=(expected+1)%c.frames;assert(a.cursor==expected);++playback_frames;
            }
        }
        c.power_single();c.preset_tap();const uint32_t pos=a.cursor;
        for(int i=0;i<1000;++i)sample(a,c,1,.2f);
        assert(c.loop==Loop::paused && a.cursor==pos);
        c.power_single();c.preset_tap();c.power_single();c.preset_tap();
        sample(a,c,0,0);assert(a.cursor==(pos+1)%c.frames);
        c.power_double();sample(a,c,0,0);assert(c.loop==Loop::stopped && a.cursor==0);
        c.power_single();c.preset_tap();sample(a,c,0,0);assert(a.cursor==1);
        a.seam_frames=32;
        for(unsigned i=0;i<c.frames*3;++i)sample(a,c,0,0);
        assert(memory[0]==1234 && memory[4097]==-1234);
    }
    // Saturation, nonfinite input, exact capacity stop, trigger near buffer end,
    // zero storage, and capture exclusion of stereo backing audio.
    for(unsigned capacity:{0,1,2,8,63,64,65,100}) {
        int16_t storage[102]{};storage[0]=12;storage[capacity+1]=34;
        Audio a(storage+1,capacity);Controls c;c.power_double();c.preset_tap();
        for(int i=0;i<128;++i)sample(a,c,0,.125f);
        float l,r;a.frame(c,1,.25f,true,.8f,-.8f,l,r);
        for(unsigned i=0;i<capacity+1;++i)sample(a,c,1,.25f);
        assert(c.frames==capacity);assert(c.loop==(capacity?Loop::playing:Loop::armed));
        if(capacity)assert(a.storage[capacity-1]==8192);
        assert(storage[0]==12 && storage[capacity+1]==34);
        a.frame(c,std::numeric_limits<float>::quiet_NaN(),INFINITY,true,INFINITY,-INFINITY,l,r);
        assert(__builtin_isfinite(l) && __builtin_isfinite(r) && fabsf(l)<=.875f && fabsf(r)<=.875f);
    }
    printf("{\"status\":\"PASS_OFFLINE_LOOPER_AUDIO\",\"format\":\"PCM16 mono 48 kHz\",\"block_sizes\":[8,16,32],\"preset_reload_simulations\":%u,\"continuous_playback_frames\":%llu,\"simulated_guitar_settling_ms\":200,\"pre_roll_frames\":64,\"audio_state_bytes_host\":%zu,\"device_access\":false,\"host_audio_access\":false,\"firmware_integrated\":false,\"physical_RAM_allocated\":false,\"interrupt_stalls_modeled\":false}\n",switches,(unsigned long long)playback_frames,sizeof(Audio));
}
