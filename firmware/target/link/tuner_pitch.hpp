#pragma once
#include <stdint.h>
namespace mpp::tuner {
struct Pitch { uint32_t milli_hz,confidence; };
// Foreground only. No allocation, transcendental functions, IRQ work or audio output.
// 1024 samples at 12 kHz, matching the controller's YIN and harmonic refinement.
inline Pitch pitch(const int16_t* x) {
 constexpr unsigned window=512,maxlag=301;
 float values[maxlag+1];float cumulative=0,mean=0,energy=0;
 for(unsigned i=0;i<1024;++i)mean+=x[i];mean/=1024;
 for(unsigned i=0;i<1024;++i){const float d=x[i]-mean;energy+=d*d;}
 if(energy<1099512.f)return {0,0};
 auto difference=[&](unsigned lag){float sum=0;for(unsigned i=0;i<window;++i){const float d=float(x[i])-x[i+lag];sum+=d*d;}return sum;};
 values[0]=1;
 for(unsigned lag=1;lag<=maxlag;++lag){float d=difference(lag);cumulative+=d;values[lag]=cumulative>0?d*lag/cumulative:1;}
 unsigned lag=4;
 for(;lag<maxlag;++lag)if(values[lag]<.12f){while(lag+1<=maxlag&&values[lag+1]<values[lag])++lag;break;}
 if(lag>=maxlag||values[lag]>.1f)return {0,0};
 auto offset=[](float l,float c,float r){float d=l-2*c+r;if(d<=0)return 0.f;float o=.5f*(l-r)/d;return o<-1?-1.f:o>1?1.f:o;};
 float period=lag+offset(values[lag-1],values[lag],values[lag+1]);
 unsigned multiple=unsigned((window-8)/period);if(multiple>8)multiple=8;if(!multiple)return {0,0};
 unsigned expected=unsigned(period*multiple+.5f),radius=unsigned(period*.45f);if(radius<1)radius=1;if(radius>3)radius=3;
 unsigned first=expected>radius+2?expected-radius:2,last=expected+radius;if(last>window-2)last=window-2;
 unsigned best=first;float minimum=difference(first);
 for(unsigned i=first+1;i<=last;++i){float d=difference(i);if(d<minimum){minimum=d;best=i;}}
 float hz=12000.f*multiple/(best+offset(difference(best-1),minimum,difference(best+1)));
 if(!__builtin_isfinite(hz)||hz<40||hz>1400)return {0,0};
 return {uint32_t(hz*1000+.5f),uint32_t((1-values[lag])*1000000+.5f)};
}
}
