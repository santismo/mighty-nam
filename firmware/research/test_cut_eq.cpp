#include "../target/link/cut_eq.hpp"
#include <cassert>
#include <initializer_list>
#include <cmath>
#include <cstdio>
#include <limits>
using mpp::cut::Engine;
static double gain(unsigned lo,unsigned hi,double f){
 Engine e;e.reset();double in=0,out=0;
 for(unsigned b=0;b<12000;++b){float l[8],r[8],a[8],z[8];for(unsigned i=0;i<8;++i){l[i]=.2f*std::sin(2*3.141592653589793*f*(b*8+i)/48000);r[i]=-l[i];}e.process(true,lo,hi,l,r,a,z,8);for(unsigned i=0;i<8;++i){assert(std::isfinite(a[i]));assert(std::abs(a[i]+z[i])<1e-6);if(b>6000){in+=l[i]*l[i];out+=a[i]*a[i];}}}
 return 10*std::log10(out/in);
}
int main(){
 unsigned count=0;
 for(unsigned v: {1u,25u,50u,75u,100u}){
  for(bool high: {false,true}){double f=mpp::cut::frequency(v,high);double db=gain(high?0:v,high?v:0,f);assert(std::abs(db+3.0103)<.05);++count;}
 }
 assert(gain(100,0,100)<-39);assert(gain(0,1,10000)<-39);
 assert(gain(1,100,1000)>-.02);assert(gain(100,1,1000)<-6.0);
 Engine e;e.reset();float l[8],r[8],a[8],b[8];for(unsigned i=0;i<8;++i){l[i]=.03125f*i;r[i]=-.017f*i;}
 e.process(true,0,0,l,r,a,b,8);for(unsigned i=0;i<8;++i)assert(a[i]==l[i]&&b[i]==r[i]);
 for(unsigned i=0;i<10000;++i){e.process(i%101!=0,i%101,(i*17)%101,l,r,a,b,8);for(unsigned j=0;j<8;++j)assert(std::isfinite(a[j])&&std::abs(a[j])<2);}
 for(unsigned i=0;i<100;++i)e.process(false,100,1,l,r,a,b,8);
 for(unsigned i=0;i<8;++i)assert(a[i]==l[i]&&b[i]==r[i]);
 // In-place stereo agrees with separate buffers, including opposite channels.
 Engine x,y;x.reset();y.reset();for(unsigned i=0;i<1000;++i){float c[8],d[8];for(unsigned j=0;j<8;++j){c[j]=l[j];d[j]=r[j];}x.process(true,60,70,l,r,a,b,8);y.process(true,60,70,c,d,c,d,8);for(unsigned j=0;j<8;++j)assert(a[j]==c[j]&&b[j]==d[j]);}
 l[3]=std::numeric_limits<float>::infinity();e.process(true,1,100,l,r,a,b,8);assert(a[3]==0&&b[3]==0);
 printf("PASS: %u cutoff checks, slopes, combined response, rapid switching, stereo, in-place, exact bypass, finite output; no audio playback.\n",count);
}
