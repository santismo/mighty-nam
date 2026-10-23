// MIT (c) 2026 santismo. Native, silent tests; files only, no audio API.
#include "compressed_audio.hpp"
#include "../../firmware/target/a2/a2_lite.hpp"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>
using namespace mighty_loop;
static void save(const std::string& path,const void* p,size_t n) {
    std::ofstream f(path,std::ios::binary);assert(f);f.write(static_cast<const char*>(p),n);assert(f);
}
static uint64_t hash(const std::vector<uint8_t>& x) {
    uint64_t h=14695981039346656037ull;for(auto b:x){h^=b;h*=1099511628211ull;}return h;
}
static void small_tests(const std::string& out) {
    uint32_t random=71;std::vector<int16_t> pcm(131071);
    for(auto& x:pcm){random=1664525*random+1013904223;x=int16_t(random>>16);}
    std::vector<uint8_t> memory(AdpcmStore::required(uint32_t(pcm.size()))+32,0xa5);
    AdpcmStore s(memory.data()+16,memory.size()-32,uint32_t(pcm.size()));
    for(auto x:pcm)assert(s.append(x));assert(!s.append(1));
    std::vector<int16_t> decoded;for(size_t i=0;i<pcm.size()*2;++i)decoded.push_back(s.next());
    for(size_t i=0;i<pcm.size();++i)assert(decoded[i]==decoded[i+pcm.size()]);
    for(unsigned i=0;i<16;++i)assert(memory[i]==0xa5 && memory[memory.size()-1-i]==0xa5);
    save(out+"/codec-pcm.raw",pcm.data(),pcm.size()*2);
    save(out+"/codec.blocks",memory.data()+16,memory.size()-32);
    save(out+"/codec-decoded.raw",decoded.data(),pcm.size()*2);
    s.rewind();memory[18]=89;assert(s.next()==0 && s.failed);
    s.clear();assert(s.append(-32768) && !s.failed);assert(s.next()==-11);
    for(unsigned capacity:{0u,1u,2u,255u,256u,257u,511u}) {
        std::vector<uint8_t> b(AdpcmStore::required(capacity));
        AdpcmStore store(b.data(),b.size(),capacity);
        for(unsigned i=0;i<capacity;++i)assert(store.append(int16_t(i*37)));
        assert(!store.append(0));
        for(unsigned i=0;i<capacity*3;++i)store.next();assert(!store.failed);
    }
    uint8_t too_small[131]{};AdpcmStore rejected(too_small,sizeof too_small,256);
    assert(rejected.capacity==0 && !rejected.append(1));
    assert(AdpcmStore(nullptr,742500,1440000).capacity==0);
    assert(AdpcmStore(too_small,sizeof too_small,0xffffffff).capacity==0);
    for(unsigned rate:{24000u,48000u}) {
        std::vector<uint8_t> b(AdpcmStore::required(511));
        CompressedAudio a(b.data(),b.size(),rate,511);Controls c;
        c.power_double();c.preset_tap();float l=0,r=0;
        // Threshold input, backing, and nonfinite samples must not trigger.
        for(unsigned i=0;i<200;++i)a.frame(c,NAN,NAN,true,.2f,-.2f,l,r);
        assert(c.loop==Loop::armed && !c.frames && l==.2f && r==-.2f);
        a.frame(c,.2f,.1f,true,0,0,l,r);
        for(unsigned i=0;i<1100 && c.loop!=Loop::playing;++i)a.frame(c,.2f,.1f,true,0,0,l,r);
        assert(c.loop==Loop::playing && c.frames==511*a.ratio && a.store.length==511);
        auto saved=b;auto count=a.played_frames;
        for(unsigned i=0;i<4096;++i)a.frame(c,0,0,false,0,0,l,r);
        assert(a.played_frames-count==4096 && b==saved);
        c.preset_tap();auto cursor=a.store.cursor;count=a.played_frames;
        for(unsigned i=0;i<512;++i)a.frame(c,1,.123f,true,0,0,l,r);
        assert(c.loop==Loop::paused && cursor==a.store.cursor && count==a.played_frames && l==.123f);
        c.preset_tap();a.frame(c,0,0,true,0,0,l,r);assert(a.played_frames==count+1);
        c.power_double();a.frame(c,0,0,true,0,0,l,r);assert(a.store.cursor==0 && l==0);
        assert(b==saved);
        // Manual close can end at either phase of the 24 kHz recorder.
        Controls d;CompressedAudio manual(b.data(),b.size(),rate,511);d.power_double();d.preset_tap();
        for(unsigned i=0;i<101;++i)manual.frame(d,.1f,.02f,true,0,0,l,r);
        d.preset_tap();assert(d.loop==Loop::playing && d.frames==manual.store.length*manual.ratio);
        manual.frame(d,0,0,false,0,0,l,r);assert(manual.played_frames==1);
    }
}
int main(int argc,char** argv) {
    assert(argc==5);std::string out=argv[1];small_tests(out);
    std::array<std::array<float,mpp::A2Lite::weight_count>,3> weights{};
    for(unsigned k=0;k<3;++k){std::ifstream f(argv[k+2],std::ios::binary);assert(f);f.read(reinterpret_cast<char*>(weights[k].data()),sizeof weights[k]);assert(f);}
    mpp::A2Lite nam;assert(nam.load(weights[0].data(),mpp::A2Lite::weight_count));
    std::vector<uint8_t> b48(AdpcmStore::required(1440000)),b24(AdpcmStore::required(720000));
    CompressedAudio a48(b48.data(),b48.size(),48000,1440000),a24(b24.data(),b24.size());
    Controls c48,c24;c48.power_double();c48.preset_tap();c24.power_double();c24.preset_tap();
    // Force a threshold crossing on the first frame, so exact-duration reference
    // signals are independent of a model's input sensitivity or warmup state.
    std::vector<int16_t> ref48,ref24;ref48.reserve(1440000);ref24.reserve(720000);
    LoopFilter filter;float left=0,right=0;unsigned switches=0;
    AdpcmStore reference_reader48(b48.data(),b48.size(),1440000),reference_reader24(b24.data(),b24.size(),720000);
    LoopFilter reference_playback_filter;
    const unsigned record_frames=48000*30,play_frames=48000*60;
    for(unsigned base=0;base<record_frames+play_frames;base+=8) {
        if(base && base%(48000*5)==0) {
            unsigned model=(base/(48000*5))%3;assert(nam.load(weights[model].data(),mpp::A2Lite::weight_count));++switches;
            if(base>=record_frames) { c48.mode=c24.mode=Mode::presets;c48.preset_tap();c24.preset_tap(); }
        }
        float input[8],output[8];
        for(unsigned j=0;j<8;++j) {
            double t=double(base+j)/48000;
            double pluck=std::exp(-3*std::fmod(t,.5));
            input[j]=float(.07*pluck*(std::sin(2*3.141592653589793*110*t)+.35*std::sin(2*3.141592653589793*220*t)+.2*std::sin(2*3.141592653589793*441*t)));
        }
        nam.process(input,output,8);
        bool ready=base<record_frames || (base%(48000*5)>=9600); // 200 ms guitar-only settling
        for(unsigned j=0;j<8;++j) {
            assert(std::isfinite(output[j]));float processed=Audio::limit(output[j]*.25f);
            if(base<record_frames) {
                ref48.push_back(Audio::encode(processed));float f=filter.process(processed);
                if((base+j)&1)ref24.push_back(Audio::encode(f));
            }
            auto before48=a48.played_frames,before24=a24.played_frames;
            a48.frame(c48,.1f,processed,ready,.03f,-.02f,left,right);
            assert(std::isfinite(left)&&std::fabs(left)<=.875f&&std::fabs(right)<=.875f);
            if(base>=record_frames) {
                float expected_loop=float(reference_reader48.next())/32768.f*.5f;
                assert(left==Audio::limit((ready?processed:0.f)+expected_loop+.03f));
            }
            a24.frame(c24,.1f,processed,ready,.03f,-.02f,left,right);
            assert(std::isfinite(left)&&std::fabs(left)<=.875f&&std::fabs(right)<=.875f);
            if(base>=record_frames) {
                float expected_sample=((base+j)&1)?0.f:float(reference_reader24.next())/32768.f;
                float expected_loop=reference_playback_filter.process(expected_sample*2.f)*.5f;
                assert(left==Audio::limit((ready?processed:0.f)+expected_loop+.03f));
            }
            if(base>=record_frames){assert(a48.played_frames==before48+1);assert(a24.played_frames==before24+1);}
        }
        if(base+8==record_frames) {
            assert(c48.loop==Loop::playing && c24.loop==Loop::playing);
            assert(c48.frames==record_frames && c24.frames==record_frames);
            assert(a48.store.length==1440000 && a24.store.length==720000);
            reference_reader48.length=1440000;reference_reader24.length=720000;
            save(out+"/record48.blocks",b48.data(),b48.size());save(out+"/record24.blocks",b24.data(),b24.size());
            std::printf("Recorded full 30 seconds through real A2 Lite at 8 frames\n");std::fflush(stdout);
        }
    }
    assert(a48.played_frames==play_frames && a24.played_frames==play_frames);
    save(out+"/reference48.raw",ref48.data(),ref48.size()*2);save(out+"/reference24.raw",ref24.data(),ref24.size()*2);
    // Backing/live input and changing NAM models cannot rewrite the completed recording.
    std::vector<uint8_t> saved48(b48.size()),saved24(b24.size());
    std::ifstream f48(out+"/record48.blocks",std::ios::binary),f24(out+"/record24.blocks",std::ios::binary);
    f48.read(reinterpret_cast<char*>(saved48.data()),saved48.size());f24.read(reinterpret_cast<char*>(saved24.data()),saved24.size());
    assert(b48==saved48 && b24==saved24);
    std::ofstream report(out+"/compressed-native.json");
    report<<"{\n  \"status\": \"PASS_OFFLINE\",\n  \"NAM\": \"actual portable A2 Lite implementation, three public captures\",\n  \"live_rate\": 48000,\n  \"callback_frames\": 8,\n  \"record_seconds\": 30,\n  \"playback_seconds\": 60,\n  \"model_reloads\": "<<switches<<",\n  \"record_bytes_48k\": "<<b48.size()<<",\n  \"record_bytes_24k\": "<<b24.size()<<",\n  \"host_audio_state_bytes\": "<<sizeof(CompressedAudio)<<",\n  \"host_controls_bytes\": "<<sizeof(Controls)<<",\n  \"immutable_playback_hash48\": \""<<hash(b48)<<"\",\n  \"immutable_playback_hash24\": \""<<hash(b24)<<"\",\n  \"zero_missing_or_repeated_playback_frames\": true,\n  \"preset_flash_timing_modeled\": false,\n  \"device_access\": false,\n  \"audio_device_opened\": false\n}\n";
    std::puts("PASS: full-duration compressed loops, native NAM, preset changes, pause/resume, guards");
}
