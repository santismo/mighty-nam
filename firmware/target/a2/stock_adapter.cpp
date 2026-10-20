// Exact V1.5.6 offline candidate only. Model lives in retired stock AMP data.
// No flash writes, USB or audio driver code. CRC is integrity, not authentication.
#include "a2_lite.hpp"
static mpp::A2Lite model;
static unsigned last_control;
extern "C" {
// Historical harness name retained for the common stock boot ordering check.
unsigned mpp_hybrid_ready;
unsigned mpp_a2_load_status;
void mpp_stock_amp_init(){
 mpp_hybrid_ready=0;last_control=~0u;mpp_a2_load_status=1;
 const auto* h=reinterpret_cast<const volatile unsigned*>(0x30384000u);
 if(h[0]!=0x3241504du||h[1]!=1u||h[2]!=48000u||h[3]!=1871u||h[4]!=7484u||h[6]!=1u||h[7]!=0u)return;
 mpp_a2_load_status=2;
 const auto* bytes=reinterpret_cast<const volatile unsigned char*>(0x30384020u);
 unsigned crc=~0u;
 for(unsigned i=0;i<7484;++i){crc^=bytes[i];for(unsigned bit=0;bit<8;++bit)crc=(crc>>1)^((0u-(crc&1u))&0xedb88320u);}
 if((crc^~0u)!=h[5])return;
 mpp_a2_load_status=3;
 if(!model.load(reinterpret_cast<const float*>(0x30384020u),1871))return;
 mpp_hybrid_ready=1;mpp_a2_load_status=0;
}
void mpp_stock_amp_process(const float* left,const float* right,float* out_left,float* out_right){
 float x[8],r[8],y[8];
 for(unsigned i=0;i<8;++i){x[i]=left[i];r[i]=right[i];}
 unsigned p=*reinterpret_cast<const volatile unsigned*>(0x20005ad0u);
 if(p<0x20000000u||p>0x2003ff80u||!mpp_hybrid_ready){for(unsigned i=0;i<8;++i)out_left[i]=out_right[i]=0;return;}
 unsigned control=*reinterpret_cast<const volatile unsigned char*>(p+3);
 if(control!=last_control){model.reset();last_control=control;}
 if(control&0x40u){for(unsigned i=0;i<8;++i){out_left[i]=x[i];out_right[i]=r[i];}return;}
 bool valid=true;for(float v:x)valid &= __builtin_isfinite(v);
 if(valid){model.process(x,y,8);for(float v:y)valid &= __builtin_isfinite(v);}
 if(!valid){model.reset();for(auto &v:y)v=0;}
 for(unsigned i=0;i<8;++i)out_left[i]=out_right[i]=y[i];
}
}
