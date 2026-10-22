#include "../target/link/nam_controls.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
using namespace mpp::tone;
int main(){
 uint8_t p[6],preset[128]={};defaults(p);assert(valid(p));decode(preset,p);assert(p[0]==48&&p[4]==100);
 for(unsigned j=0;j<6;++j){auto old=p[j];p[j]=127;assert(!valid(p));p[j]=old;}
 float d[8],r[8],l[8],o[8];for(int i=0;i<8;i++){d[i]=.1f*i;r[i]=-.02f*i;l[i]=.01f*i;}
 Engine e{};e.reset();assert(e.prepare(d,p)==d);e.finish(d,r,l,o);for(int i=0;i<8;i++)assert(l[i]==.01f*i&&o[i]==l[i]);
 p[4]=0;p[5]=60;e.reset();e.prepare(d,p);e.finish(d,r,l,o);for(int i=0;i<8;i++){assert(fabs(l[i]-d[i]*pow(10,6./20))<1e-6);assert(fabs(o[i]-r[i]*pow(10,6./20))<1e-6);}
 defaults(p);p[0]=36;e.reset();const float* in=e.prepare(d,p);for(int i=0;i<8;i++)assert(fabs(in[i]-d[i]*pow(10,-6./20))<1e-6);
 const double freq[3]={3.,700.,21000.};double energy[3][3]={};
 for(int band=0;band<3;band++)for(int f=0;f<3;f++){
  defaults(p);p[band+1]=24;e.reset();
  for(int n=0;n<2000;n++){for(int i=0;i<8;i++)d[i]=l[i]=.1f*sin(6.283185307179586*freq[f]*(n*8+i)/48000);e.prepare(d,p);e.finish(d,d,l,o);if(n>1000)for(float y:l)energy[band][f]+=y*y;}
 }
 assert(energy[0][0]>energy[0][2]*6);assert(energy[2][2]>energy[2][0]*6);assert(energy[1][1]>energy[1][0]*4&&energy[1][1]>energy[1][2]*3);
 for(int n=0;n<10000;n++){for(int j=0;j<6;j++)p[j]=(n%2)?0:(j==0||j==5?96:j==4?100:24);e.prepare(d,p);for(int i=0;i<8;i++)l[i]=sinf(n+i);e.finish(d,d,l,o);for(float y:l)assert(std::isfinite(y));}
 puts("PASS NAM controls: neutral identity, gain, stereo dry mix, spectral bands, bounds and switching");
}
