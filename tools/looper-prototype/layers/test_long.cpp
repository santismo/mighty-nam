// MIT (c) 2026 santismo. Full-duration test; raw numeric buffers only, no audio I/O.
#include "session.hpp"
#include "../layout.hpp"
#include "../../../firmware/target/a2/a2_lite.hpp"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <vector>
using namespace mighty_loop;
int main(int argc,char** argv) {
    assert(argc==4);
    std::array<std::array<float,mpp::A2Lite::weight_count>,3> models{};
    for(unsigned i=0;i<3;++i){std::ifstream f(argv[i+1],std::ios::binary);assert(f);f.read((char*)models[i].data(),sizeof models[i]);assert(f);}
    unsigned recalls=0;uint32_t callbacks=0,layer_commits=0;
    for(unsigned seconds:{30u,60u}) {
        std::vector<uint8_t> first(layout::first_bytes+64,0x65),second(layout::second_bytes+64,0xa9);
        LoopSession s(first.data()+32,layout::first_bytes,second.data()+32,layout::second_bytes);
        assert(s.set_seconds(seconds));s.controls.power_double();s.controls.preset_tap();
        mpp::A2Lite nam;assert(nam.load(models[0].data(),mpp::A2Lite::weight_count));
        const unsigned duration=seconds*48000;
        float l=0,r=0;unsigned settling=0;
        for(unsigned base=0;base<duration*3;base+=8) {
            unsigned phase=base/duration;
            if(base==duration) {
                assert(s.store.length==720000 && s.controls.loop==Loop::playing);
                assert(s.set_overdub(true));s.controls.mode=Mode::presets;
            }
            if(base==duration*2)assert(s.set_overdub(false));
            if(base && base%(48000*5)==0) {
                unsigned model=base/(48000*5)%3;assert(nam.load(models[model].data(),mpp::A2Lite::weight_count));
                ++recalls;s.controls.mode=Mode::presets;s.controls.preset_tap();settling=1200;
            }
            float input[8],output[8];
            for(unsigned i=0;i<8;++i)input[i]=float(.04*std::sin((base+i)*.014*(phase+1)));
            nam.process(input,output,8);++callbacks;
            for(unsigned i=0;i<8;++i) {
                uint32_t before=s.played_frames;
                s.frame(.1f,output[i]*.2f,!settling,.03f,-.02f,l,r);
                assert(std::isfinite(l)&&std::isfinite(r)&&std::fabs(l)<=.875f&&std::fabs(r)<=.875f);
                if(phase)assert(s.played_frames==before+1);
            }
            if(settling)--settling;
        }
        assert(s.store.length==720000 && s.played_frames==duration*2 && !s.store.failed);
        assert(!s.store.dirty && s.store.commits>0 && s.store.commits<=2813);layer_commits+=s.store.commits;
        for(unsigned i=0;i<32;++i){assert(first[i]==0x65&&first[first.size()-1-i]==0x65);assert(second[i]==0xa9&&second[second.size()-1-i]==0xa9);}
        printf("%u-second record / overdub / playback passed at 8 frames\n",seconds);fflush(stdout);
    }
    printf("{\"status\":\"PASS_FULL_DURATION_NAM_LAYERS\",\"callbacks\":%u,\"nam_model_changes\":%u,\"committed_layer_blocks\":%u,\"loop_storage_bytes\":%u,\"host_audio_access\":false,\"device_access\":false,\"physical_timing_proven\":false}\n",callbacks,recalls,layer_commits,layout::first_bytes+layout::second_bytes);
}
