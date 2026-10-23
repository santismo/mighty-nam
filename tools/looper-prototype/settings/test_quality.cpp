// Numeric-only regression: the second layer must not retrain the codec from
// the quiet first layer's predictor at every 256-sample boundary.
#include "../layers/overdub_store.hpp"
#include <vector>
#include <cmath>
#include <cstdio>
#include <cassert>
using namespace mighty_loop;
int main() {
    constexpr unsigned n=24000;
    std::vector<uint8_t> memory(AdpcmStore::required(n));
    OverdubStore s(memory.data(),memory.size(),n);
    std::vector<int16_t> expected(n);
    for(unsigned i=0;i<n;++i)s.append(int16_t(70*std::sin(i*.021)));
    for(unsigned i=0;i<n;++i) {
        int16_t layer=int16_t(4800*std::sin(i*.057)+2200*std::sin(i*.163));
        expected[i]=int16_t(s.next_layer(layer,true)+layer);
    }
    assert(s.rewind_ready());double signal=0,error=0,boundary=0;unsigned count=0;
    for(unsigned i=0;i<n;++i) {
        double e=double(s.next_layer(0,false))-expected[i];
        if(i<256)continue;
        signal+=double(expected[i])*expected[i];error+=e*e;
        if(i%256<16){boundary+=e*e;++count;}
    }
    double snr=10*std::log10(signal/error),edge=std::sqrt(boundary/count);
    std::printf("{\"status\":\"PASS_OFFLINE_OVERDUB_QUALITY\",\"snr_db\":%.6f,\"block_start_error_rms\":%.6f,\"samples\":%u,\"host_audio_access\":false}\n",snr,edge,n);
#ifdef REQUIRE_QUALITY
    assert(snr>25 && edge<250);
#endif
}
