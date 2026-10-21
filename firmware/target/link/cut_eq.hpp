#pragma once
#include <stdint.h>
namespace mpp::cut {
// NAMLNK14 EQ type 4. Value 0 disables that filter; 1..100 is logarithmic.
// Low Cut: 20..1000 Hz. High Cut: 1000..20000 Hz. 12 dB/oct Butterworth.
struct Engine {
 float state[2][2][2], g[2], wet[2];
 void reset();
 void process(bool enabled,unsigned low,unsigned high,const float*,const float*,float*,float*,unsigned);
};
float frequency(unsigned value,bool high);
}
extern "C" void mpp_cut_eq_init();
extern "C" void mpp_cut_eq_process(const float*,const float*,float*,float*);
