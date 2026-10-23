#include "fx_blocks.hpp"
#include "autowah.h"
#include <cstring>
#include <cmath>
extern "C" void run_fx(float* l,float* r,unsigned n,const unsigned char* c){
 mpp::fx::Engine e;std::memset(&e,0xa5,sizeof(e));e.reset();
 for(unsigned i=0;i<n;i+=8)e.process(c+4*i,l+i,r+i,8);
}
extern "C" void upstream(float* x,unsigned n,float sensitivity){
 daisysp::Autowah e;e.Init(48000);e.SetWah(1);e.SetDryWet(100);e.SetLevel(1);
 for(unsigned i=0;i<n;++i)x[i]=e.Process(x[i]*sensitivity)/sensitivity;
}
