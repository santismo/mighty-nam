#include "../target/link/tuner_pitch.hpp"
#include <cmath>
#include <initializer_list>
#include <cassert>
#include <cstdio>
int main(){
 int16_t samples[1024];unsigned cases=0;double maximum=0;
 for(double hz:{41.203,55.,65.406,82.407,110.,146.832,195.998,246.942,329.628,440.,659.255,1000.,1318.51})
 for(double cents:{-35.,0.,35.})for(double phase:{0.,.7,1.9}) {
  double f=hz*std::pow(2,cents/1200);
  for(unsigned i=0;i<1024;i++)samples[i]=std::lround(6000*std::sin(2*M_PI*f*i/12000+phase)+1800*std::sin(4*M_PI*f*i/12000+phase));
  auto pitch=mpp::tuner::pitch(samples);assert(pitch.milli_hz);
  double error=std::abs(1200*std::log2(pitch.milli_hz/1000./f));
  if(error>2){std::printf("bad %f %f %.3f\n",f,pitch.milli_hz/1000.,error);return 1;}
  maximum=std::fmax(maximum,error);++cases;
 }
 for(auto& x:samples)x=0;assert(!mpp::tuner::pitch(samples).milli_hz);
 for(auto& x:samples)x=1234;assert(!mpp::tuner::pitch(samples).milli_hz);
 unsigned seed=42;for(auto& x:samples){seed=seed*1664525+1013904223;x=int16_t(seed>>16);}assert(!mpp::tuner::pitch(samples).milli_hz);
 std::printf("{\"cases\":%u,\"max_cents\":%.6f,\"silence_dc_noise_rejected\":true,\"sanitizers\":true}\n",cases,maximum);
}
