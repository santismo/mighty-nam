// MIT (c) 2026 santismo. Offline settings/transport API for the next looper.
#pragma once
#include "../controls.hpp"
#include "../audio.hpp"
#include "../loop_filter.hpp"
#include "overdub_store.hpp"
namespace mighty_loop {
// Live guitar is always 48 kHz. Long mode applies a second 2:1 stage to the
// loop alone: 12 kHz / 60 seconds in the same 720,000-sample ADPCM store.
struct LoopSession {
    Controls controls{};
    OverdubStore store;
    LoopFilter capture1{},capture2{},play1{},play2{};
    int16_t history[64]{};
    unsigned history_count=0,history_next=0,record_phase=0,play_phase=0;
    unsigned ratio=2,volume=50,threshold_db=40;
    float gain=.5f;
    float loop_output=0;
    bool overdubbing=false,trigger=false,rewind_pending=false;
    Loop previous=Loop::empty;
    uint32_t played_frames=0;
    float input_peak=0;
    // 12 dB of storage headroom; playback compensates exactly. This reduces
    // hard clipping when combining several independently captured presets.
    static constexpr float storage_gain=.25f, playback_gain=4.f;
    void meter_decay() { input_peak*=.998333f; }
    void meter_sample(float raw,bool ready) {
        float v=ready?__builtin_fabsf(Audio::finite(raw)):0;
        if(v>input_peak)input_peak=v>1.f?1.f:v;
    }
    unsigned meter_word() const { return unsigned(input_peak*65535.f+.5f); }
    LoopSession(uint8_t* p,size_t n,uint8_t* q,size_t m,uint32_t capacity=720000):
        store(p,n,q,m,capacity) { controls.capacity=capacity*ratio; }
    LoopSession(uint8_t* p,size_t n,uint32_t capacity):store(p,n,capacity) {
        controls.capacity=capacity*ratio;
    }
    unsigned sample_rate() const { return 48000/ratio; }
    bool set_seconds(unsigned seconds) {
        if((seconds!=30 && seconds!=60) || controls.loop!=Loop::empty || store.length || store.dirty)return false;
        ratio=seconds==60?4:2;controls.capacity=store.capacity*ratio;return true;
    }
    bool set_volume(unsigned percent) {
        if(percent>100)return false;volume=percent;return true;
    }
    bool set_threshold(unsigned negative_db) {
        if(negative_db<12 || negative_db>60)return false;
        float value=1.f;
        for(unsigned i=0;i<negative_db;++i)value*=.8912509381337456f;
        controls.threshold=value;threshold_db=negative_db;return true;
    }
    bool set_overdub(bool enabled) {
        if(enabled && (controls.loop!=Loop::playing || !store.length || store.failed))return false;
        if(enabled && !overdubbing){capture1.reset();capture2.reset();}
        overdubbing=enabled;
        // New layers may use a different live preset; neither backing audio nor
        // loop playback is sent into the capture filter.
        return true;
    }
    void reset_playback() {
        if(!store.rewind_ready()){rewind_pending=true;return;}
        rewind_pending=false;play_phase=0;play1.reset();play2.reset();
    }
    void sync() {
        auto& c=controls;c.capacity=store.capacity*ratio;
        if(c.loop==Loop::empty && (store.length || store.dirty || previous!=Loop::empty)) {
            store.clear();overdubbing=false;reset_playback();
        }
        if(c.loop==Loop::armed && previous!=Loop::armed) {
            store.clear();c.frames=0;overdubbing=false;history_count=history_next=0;
            trigger=false;record_phase=0;capture1.reset();capture2.reset();reset_playback();
        }
        if((c.loop==Loop::stopped && previous!=c.loop) ||
           (c.loop==Loop::playing && previous==Loop::recording))reset_playback();
        if(c.loop!=Loop::playing)overdubbing=false;
        previous=c.loop;
    }
    void frame(float raw,float processed,bool ready,float backing_l,float backing_r,float& left,float& right) {
        sync();auto& c=controls;
        const float guitar=ready?Audio::finite(processed):0;
        // Complete at most four old samples per live frame while paused. This
        // bounds the work and preserves a partial layer through pause/stop.
        if(c.loop!=Loop::playing || rewind_pending)store.drain(4);
        if(rewind_pending && !store.dirty)reset_playback();
        bool was_recording=c.loop==Loop::recording;
        float decimated=0,addition=0;
        bool stored_sample=false;
        if(c.loop==Loop::armed || c.loop==Loop::recording) {
            float filtered=capture1.process(guitar);
            if(++record_phase==2) {
                if(ratio==2){record_phase=0;decimated=filtered;stored_sample=true;}
                else capture2.process(filtered);
            }else if(record_phase==4) {
                record_phase=0;decimated=capture2.process(filtered);stored_sample=true;
            }
        }else if(c.loop==Loop::playing && overdubbing) {
            float filtered=capture1.process(guitar);
            if(ratio==2)addition=filtered;
            else if(!(play_phase&1))addition=capture2.process(filtered);
        }
        if(c.loop==Loop::armed && ready && __builtin_fabsf(Audio::finite(raw))>=c.threshold)trigger=true;
        if(stored_sample && (c.loop==Loop::armed || c.loop==Loop::recording)) {
            if(c.loop==Loop::armed && trigger && store.capacity) {
                unsigned n=history_count<store.capacity?history_count:store.capacity-1;
                unsigned start=(history_next+64-n)%64;
                for(unsigned i=0;i<n;++i)store.append(history[(start+i)%64]);
                c.begin_record(n*ratio);
            }
            if(c.loop==Loop::recording) {
                if(store.append(Audio::encode(decimated*storage_gain)))c.audio(0,ratio);
                was_recording=true;
                if(c.loop==Loop::playing)reset_playback();
            }else if(c.loop==Loop::armed) {
                history[history_next]=Audio::encode(decimated*storage_gain);history_next=(history_next+1)%64;
                if(history_count<64)++history_count;
            }
        }
        // Loop gain is applied only at playback, never baked into overdubs.
        float target=float(volume)*.01f;gain+=(target-gain)*.001f;
        float loop=0;
        if(c.loop==Loop::playing && store.length && !was_recording && !rewind_pending) {
            // Align the overdub decimator with the playback clock. Its filter
            // states track live processed guitar, including preset settle zeros.
            float sample=0;
            if(play_phase==0)sample=float(store.next_layer(Audio::encode(addition*storage_gain),overdubbing))/32768.f*playback_gain;
            if(ratio==4) {
                float middle=0;
                if(!(play_phase&1))middle=play2.process(sample*2.f);
                loop=play1.process(middle*2.f)*gain;
            }else loop=play1.process(sample*2.f)*gain;
            play_phase=(play_phase+1)%ratio;++played_frames;
        }
        loop_output=loop;
        left=Audio::limit(guitar+loop+Audio::finite(backing_l));
        right=Audio::limit(guitar+loop+Audio::finite(backing_r));
        previous=c.loop;
    }
};
}
