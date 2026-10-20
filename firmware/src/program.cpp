#include "mpp/program.hpp"
#include <cstring>
namespace mpp {
namespace {
uint32_t word(const uint8_t* p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
uint32_t crc(const uint8_t* p,std::size_t n){uint32_t v=~0u;while(n--){v^=*p++;for(unsigned i=0;i<8;++i)v=(v>>1)^((0u-(v&1u))&0xedb88320u);}return ~v;}
float number(const uint8_t* p){uint32_t x=word(p);float f;std::memcpy(&f,&x,4);return f;}
}
bool configure_program(Chain& chain,const uint8_t* p,std::size_t size){
 if(!p||size<16||word(p)!=0x3143504eu||p[4]!=1||p[5]||word(p+8)!=48000) return false;
 unsigned n=unsigned(p[6])|(unsigned(p[7])<<8);
 if(n>max_stages||size!=16+16*n||word(p+12)!=crc(p+16,size-16))return false;
 Stage stages[max_stages]{};
 for(unsigned i=0;i<n;++i){const auto* b=p+16+16*i;unsigned k=unsigned(b[0])|(unsigned(b[1])<<8);
  if(b[2]>1||b[3])return false;
  stages[i]={static_cast<Kind>(k),number(b+4),number(b+8),number(b+12),b[2]!=0};
  const auto& s=stages[i];
  if((k==0&&(s.b!=0||s.c!=0))||(k==3&&(s.a!=0||s.b!=0||s.c!=0))||(k>=1&&k<=8&&k!=3&&k!=7&&s.c!=0))return false;
 }
 return chain.configure(stages,n);
}
}
