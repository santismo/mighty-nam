#include "fx_blocks.hpp"
#include <cmath>
#include <cstdio>
#include <initializer_list>
int main(){using namespace mpp::fx;static Engine e;uint8_t c[32];
 const float notes[]={82.406889f,110,146.832384f,196,246.941651f,329.627557f,659.255114f,880};
 for(float frequency:notes)for(int harmonic=0;harmonic<2;harmonic++)for(int shift:{-12,-7,-1,0,1,7,12}){
  defaults(c);c[1]=1;c[3]=shift+12;e.reset();
  for(unsigned n=0;n<12000;n++){float l[8],r[8];for(unsigned i=0;i<8;i++){float p=2*3.141592653589793*frequency*double(n*8+i)/48000;l[i]=r[i]=.2f*(std::sin(p)+(harmonic?.35f*std::sin(2*p)+.2f*std::sin(3*p):0));}e.process(c,l,r,8);if(n>=6000)for(float x:l)std::fwrite(&x,4,1,stdout);}
 }
}
