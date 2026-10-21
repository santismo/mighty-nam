#include "fx_blocks.hpp"
#include <cmath>
#include <cstdio>
#include <cassert>
#include <limits>
#include <initializer_list>
int main(){
 using namespace mpp::fx;static Engine a,b;uint8_t c[32];defaults(c);assert(valid(c));
 for(unsigned mode=1;mode<=7;mode++)for(unsigned mix: {0u,100u})for(unsigned depth:{0u,100u}){
  defaults(c);c[0]=mode;c[1]=1;c[4]=mix;c[6]=depth;c[7]=100;c[8]=100;c[9]=100;c[3]=24;
  a.reset();b.reset();
  for(unsigned n=0;n<6000;n++){float l[8],r[8],x[8],y[8];for(unsigned i=0;i<8;i++){float t=float(n*8+i)/48000;l[i]=x[i]=.2f*std::sin(2*3.14159265f*110*t);r[i]=y[i]=.15f*std::sin(2*3.14159265f*330*t);}
   a.process(c,l,r,8);b.process(c,x,y,8);for(unsigned i=0;i<8;i++){assert(std::isfinite(l[i])&&std::isfinite(r[i]));assert(std::fabs(l[i])<8&&std::fabs(r[i])<8);assert(l[i]==x[i]&&r[i]==y[i]);}}
 }
 defaults(c);a.reset();for(unsigned n=0;n<200;n++){float l[8],r[8];for(unsigned i=0;i<8;i++){l[i]=.123f;r[i]=-.456f;}a.process(c,l,r,8);for(unsigned i=0;i<8;i++){assert(l[i]==.123f&&r[i]==-.456f);}}
 // Independent states and state-reset/re-enable/type-change stress.
 for(unsigned n=0;n<10000;n++){defaults(c);c[0]=n%7+1;c[1]=n%3!=0;c[2]=n%11;c[18]=(c[2]+1)%11;c[3]=n%25;c[4]=100;c[7]=100;float l[8]={.1f},r[8]={-.2f};a.process(c,l,r,8);for(float f:l)assert(std::isfinite(f));}
 float bad[8]={std::numeric_limits<float>::quiet_NaN()},r[8]={0};c[1]=1;a.process(c,bad,r,8);for(float f:bad)assert(std::isfinite(f));
 // Export only synthetic test samples to stdout for frequency analysis.
 for(int shift=-12;shift<=12;shift++){defaults(c);c[1]=1;c[3]=shift+12;a.reset();for(unsigned n=0;n<12000;n++){float l[8],r[8];for(unsigned i=0;i<8;i++)l[i]=r[i]=.2f*std::sin(2*3.14159265f*220*float(n*8+i)/48000);a.process(c,l,r,8);if(n>=6000)for(float f:l)std::fwrite(&f,4,1,stdout);}}
}
