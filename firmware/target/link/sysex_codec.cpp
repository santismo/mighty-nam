#include "sysex_codec.hpp"
namespace mpp::link {
unsigned pack7(const uint8_t* in,unsigned n,uint8_t* out,unsigned cap){
 if(!in||!out||!n||n+(n+6)/7>cap)return 0;
 unsigned pos=0;
 for(unsigned i=0;i<n;){
  unsigned mask=pos++;out[mask]=0;
  for(unsigned b=0;b<7&&i<n;++b,++i){
   out[mask]|=(in[i]>>7)<<b;out[pos++]=in[i]&127;
  }
 }
 return pos;
}
unsigned unpack7(const uint8_t* in,unsigned n,uint8_t* out,unsigned cap){
 if(!in||!out||n<2||n%8==1||n-(n+7)/8>cap)return 0;
 // Validate all input before writing any output.
 for(unsigned i=0;i<n;++i)if(in[i]&128)return 0;
 const unsigned tail=n%8;
 if(tail&&(in[n-tail]>>(tail-1)))return 0;
 unsigned pos=0;
 for(unsigned i=0;i<n;){
  const unsigned mask=in[i++];
  for(unsigned b=0;b<7&&i<n;++b,++i)out[pos++]=in[i]|(((mask>>b)&1)<<7);
 }
 return pos;
}
}
