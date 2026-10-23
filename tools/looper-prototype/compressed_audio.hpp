// MIT (c) 2026 santismo. Offline only; no reserved hardware RAM or button hooks.
#pragma once
#include "audio.hpp"
#include "ima_adpcm.hpp"
#include "loop_filter.hpp"

namespace mighty_loop {
// Only the recorded loop may run at 24 kHz. Live guitar remains at 48 kHz and
// passes straight through this mixer, without a frame queue or these FIRs.
// Calls must be serialized. Hardware requires a bounded command mailbox.
struct CompressedAudio {
    static constexpr unsigned pre_roll=64;
    AdpcmStore store;
    unsigned ratio, record_phase=0, play_phase=0;
    LoopFilter capture_filter{}, playback_filter{};
    int16_t history[pre_roll]{};
    unsigned history_count=0, history_next=0;
    bool trigger=false;
    Loop previous=Loop::empty;
    float level=.5f;
    uint32_t played_frames=0;
    CompressedAudio(uint8_t* memory,size_t bytes,unsigned sample_rate=24000,
                    uint32_t frames=720000):store(memory,bytes,frames),
        ratio(sample_rate==24000?2:1) {
        if(sample_rate!=24000 && sample_rate!=48000)store.capacity=0;
    }
    void reset_playback() { store.rewind();play_phase=0;playback_filter.reset(); }
    void sync(Controls& c) {
        c.capacity=store.capacity*ratio;
        if(c.loop==Loop::armed && previous!=Loop::armed) {
            store.clear();c.frames=0;history_count=history_next=0;
            trigger=false;record_phase=0;capture_filter.reset();reset_playback();
        }
        if(((c.loop==Loop::empty || c.loop==Loop::stopped) && previous!=c.loop) ||
           (c.loop==Loop::playing && previous==Loop::recording))reset_playback();
        previous=c.loop;
    }
    void frame(Controls& c,float raw_guitar,float processed_guitar,bool guitar_ready,
               float backing_left,float backing_right,float& left,float& right) {
        sync(c);
        const float guitar=guitar_ready?Audio::finite(processed_guitar):0.f;
        bool was_recording=c.loop==Loop::recording;
        if(c.loop==Loop::armed || c.loop==Loop::recording) {
            const float filtered=ratio==2?capture_filter.process(guitar):guitar;
            if(c.loop==Loop::armed && guitar_ready && store.capacity &&
               __builtin_fabsf(Audio::finite(raw_guitar))>=c.threshold)trigger=true;
            if(++record_phase==ratio) {
                record_phase=0;
                if(c.loop==Loop::armed && trigger) {
                    const unsigned n=history_count<store.capacity?history_count:store.capacity-1;
                    const unsigned start=(history_next+pre_roll-n)%pre_roll;
                    for(unsigned i=0;i<n;++i)store.append(history[(start+i)%pre_roll]);
                    c.begin_record(n*ratio);
                }
                if(c.loop==Loop::recording) {
                    if(store.append(Audio::encode(filtered)))c.audio(0.f,ratio);
                    was_recording=true;
                    if(c.loop==Loop::playing)reset_playback();
                } else if(c.loop==Loop::armed) {
                    history[history_next]=Audio::encode(filtered);
                    history_next=(history_next+1)%pre_roll;
                    if(history_count<pre_roll)++history_count;
                }
            }
        }
        float loop=0;
        if(c.loop==Loop::playing && store.length && !was_recording) {
            float sample=play_phase==0?float(store.next())/32768.f:0.f;
            loop=(ratio==2?playback_filter.process(sample*2.f):sample)*Audio::finite(level);
            play_phase=(play_phase+1)%ratio;++played_frames;
        }
        left=Audio::limit(guitar+loop+Audio::finite(backing_left));
        right=Audio::limit(guitar+loop+Audio::finite(backing_right));
        previous=c.loop;
    }
};
} // namespace mighty_loop
