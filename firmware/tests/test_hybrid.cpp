#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
extern "C" {
extern unsigned mpp_hybrid_enabled, mpp_hybrid_ready, mpp_hybrid_faults;
void mpp_hybrid_reset();
void mpp_hybrid_amp(const float*,const float*,float*,float*);
}
void require(bool ok) {if(!ok) {std::cerr<<"hybrid adapter failure\n";std::exit(1);}}
int main() {
  float left[8],right[8],out[8],other[8],expected[8];
  for(unsigned i=0;i<8;++i) {left[i]=float(i)/16;right[i]=-left[i];}
  mpp_hybrid_enabled=1;
  mpp_hybrid_amp(left,right,out,other); // Uninitialized model must bypass.
  for(unsigned i=0;i<8;++i) require(out[i]==left[i]&&other[i]==right[i]);
  mpp_hybrid_reset();require(mpp_hybrid_ready==1);
  mpp_hybrid_amp(left,right,expected,other);
  mpp_hybrid_reset();mpp_hybrid_amp(left,right,right,left); // Crossed alias.
  for(unsigned i=0;i<8;++i) require(left[i]==expected[i]&&right[i]==expected[i]);
  mpp_hybrid_enabled=0;mpp_hybrid_amp(left,right,out,other);
  for(unsigned i=0;i<8;++i) require(out[i]==left[i]&&other[i]==right[i]);
  mpp_hybrid_enabled=1;left[2]=std::numeric_limits<float>::infinity();
  mpp_hybrid_amp(left,right,out,other);require(mpp_hybrid_faults==1);
  for(unsigned i=0;i<8;++i) require(out[i]==0&&other[i]==0);
  mpp_hybrid_reset();require(mpp_hybrid_faults==0);
  for(unsigned i=0;i<8;++i) {left[i]=float(i)/16;right[i]=-left[i];}
  mpp_hybrid_amp(left,right,out,other);
  for(unsigned i=0;i<8;++i) require(out[i]==expected[i]&&std::isfinite(out[i]));
  std::cout<<"PASS: initialization, bypass, active crossed aliases, nonfinite silence and reset\n";
}
