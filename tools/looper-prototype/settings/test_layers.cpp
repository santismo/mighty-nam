// MIT (c) 2026 santismo. Silent ASan/UBSan transport and codec checks.
#include "session.hpp"
#include "../layout.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <vector>
#include <cstring>
using namespace mighty_loop;
static int16_t input(unsigned i) { return int16_t(3000*std::sin(i*.043)+1700*std::sin(i*.12)); }
static void partial_layers(unsigned length,unsigned start,unsigned finish,bool pause) {
    std::vector<uint8_t> memory(AdpcmStore::required(length)+32,0xa5);
    OverdubStore s(memory.data()+16,memory.size()-32,length);
    for(unsigned i=0;i<length;++i)assert(s.append(input(i)));
    auto old=memory,expected=memory;
    // Independent block transcode oracle: preserve the encoded prefix, then
    // rewrite the entire suffix, including original samples after overdub ends.
    const unsigned first=start/256*256,last=(finish-1)/256*256;
    Ima encoder;
    for(unsigned b=first;b<=last;b+=256) {
        const auto* original=old.data()+16+b/256*132;
        auto* target=expected.data()+16+b/256*132;
        Ima decoder;
        unsigned v=original[0]|(unsigned(original[1])<<8);
        decoder.predictor=v>=32768?int(v)-65536:int(v);decoder.index=original[2];
        if(b==first)encoder=decoder;
        else {unsigned seed=uint16_t(encoder.predictor);target[0]=uint8_t(seed);target[1]=uint8_t(seed>>8);target[2]=uint8_t(encoder.index);}
        for(unsigned i=b;i<length && i<b+256;++i) {
            unsigned j=i-b,p=original[4+j/2],n=j&1?p&15:p>>4;
            int sample=decoder.decode(n);
            if(i<start){encoder=decoder;continue;}
            if(i<finish)sample+=700;
            unsigned e=encoder.encode(int16_t(sample));
            target[4+j/2]=uint8_t(j&1?(target[4+j/2]&240)|e:(target[4+j/2]&15)|(e<<4));
        }
    }
    AdpcmStore reference(old.data()+16,old.size()-32,length);reference.length=length;
    for(unsigned i=0;i<length;++i) {
        assert(s.next_layer(700,i>=start && i<finish)==reference.next());
        if(i+1==finish && pause) {
            auto cursor=s.cursor;
            while(s.dirty)s.drain(4);
            assert(s.cursor==cursor); // paused time does not change loop phase
        }
    }
    assert(!s.dirty && !s.failed && s.length==length && memory==expected);
    assert(s.rewind_ready());reference=AdpcmStore(expected.data()+16,expected.size()-32,length);reference.length=length;
    for(unsigned i=0;i<length*3;++i)assert(s.next_layer(0,false)==reference.next());
    assert(memory==expected);
    for(unsigned i=0;i<16;++i)assert(memory[i]==0xa5 && memory[memory.size()-1-i]==0xa5);
}
static void controls() {
    // Remote arming followed by a short physical tap; no second debounce.
    for(Mode mode:{Mode::presets,Mode::looper}) {
        Controls c;c.mode=mode;c.loop=Loop::recording;c.frames=12000;
        c.update_debounced(0,false,false);c.update_debounced(30,false,false);
        c.update_debounced(40,true,false);c.update_debounced(50,false,false);
        assert(c.loop==Loop::playing && c.color==0 && (c.take_events()&finish_record));
    }
    Controls c;c.loop=Loop::armed;
    assert(c.preset_led_on(0) && c.preset_led_on(249) && !c.preset_led_on(250) && !c.preset_led_on(499));
    c.loop=Loop::playing;assert(c.preset_led_on(499));
}
static void session_tests(unsigned seconds) {
    constexpr unsigned n=769;
    std::vector<uint8_t> m(AdpcmStore::required(n));LoopSession s(m.data(),m.size(),n);
    assert(s.set_seconds(seconds));assert(s.sample_rate()==(seconds==30?24000:12000));
    assert(!s.set_seconds(45) && !s.set_volume(101) && !s.set_threshold(11) && !s.set_threshold(61));
    assert(s.set_threshold(40) && std::fabs(s.controls.threshold-.01f)<1e-7f);
    s.meter_sample(.02f,true);assert(s.meter_word()>=1310 && s.input_peak>s.controls.threshold);
    for(unsigned i=0;i<1200;++i)s.meter_decay();assert(s.input_peak<s.controls.threshold);
    s.meter_sample(1.f,false);s.meter_sample(NAN,true);assert(s.input_peak<s.controls.threshold);
    assert(!s.set_overdub(true));s.controls.power_double();s.controls.preset_tap();
    float l,r;
    for(unsigned i=0;i<100;++i)s.frame(NAN,NAN,true,.1f,-.1f,l,r);
    assert(s.controls.loop==Loop::armed && l==.1f && r==-.1f);
    assert(!s.set_seconds(seconds==30?60:30));
    for(unsigned i=0;i<n*s.ratio;++i)s.frame(.1f,.1f,true,0,0,l,r);
    assert(s.controls.loop==Loop::playing && s.store.length==n && s.controls.frames==n*s.ratio);
    auto initial=m;
    assert(s.set_overdub(true));s.controls.mode=Mode::presets;
    for(unsigned i=0;i<n*s.ratio;++i) {
        if(i%64==0)s.controls.preset_tap();
        s.frame(.1f,.04f,i%48!=0,.2f,-.2f,l,r);
        assert(std::isfinite(l) && std::isfinite(r) && std::fabs(l)<=.875f && std::fabs(r)<=.875f);
    }
    s.set_overdub(false);
    s.controls.mode=Mode::looper;s.controls.preset_tap();s.sync();
    assert(!s.overdubbing && s.controls.loop==Loop::paused);
    auto cursor=s.store.cursor;
    for(unsigned i=0;i<100;++i)s.frame(.1f,.2f,true,.3f,-.3f,l,r);
    assert(cursor==s.store.cursor && !s.store.dirty && m!=initial && l==.5f);
    auto layer=m;assert(s.set_volume(0));
    s.controls.preset_tap();
    for(unsigned i=0;i<20000;++i)s.frame(0,0,false,0,0,l,r);
    assert(std::fabs(l)<1e-8f && m==layer); // volume never rewrites loop
    s.controls.clear();s.sync();assert(!s.store.length && s.controls.loop==Loop::empty);
    assert(s.set_seconds(seconds==30?60:30));
}
int main() {
    controls();unsigned cases=0;
    for(unsigned n:{1u,2u,255u,256u,257u,513u,769u})
      for(unsigned start=0;start<n;start+=n<4?1:17)
        for(unsigned end=start+1;end<=n;end+=n<4?1:19)
          for(bool pause:{false,true}){partial_layers(n,start,end,pause);++cases;}
    session_tests(30);session_tests(60);
    // The split used on hardware stays exactly the same for both durations.
    assert(AdpcmStore::required(720000)==layout::first_bytes+layout::second_bytes);
    printf("{\"status\":\"PASS_OFFLINE_LAYERS\",\"partial_layer_cases\":%u,\"storage_bytes\":%zu,\"session_host_bytes\":%zu,\"device_access\":false,\"host_audio_access\":false}\n",cases,AdpcmStore::required(720000),sizeof(LoopSession));
}
