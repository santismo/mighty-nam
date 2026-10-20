// Synthetic VM module; no persistent firmware placement or model loader implied.
#include "a2_lite.hpp"
static mpp::A2Lite model;
static unsigned last_control,ready;
extern "C" {
unsigned mpp_a2_load(const float* weights,unsigned count){last_control=~0u;ready=model.load(weights,count);return ready;}
void mpp_a2_reset(){model.reset();last_control=~0u;}
void mpp_a2_process(const float* left,const float* right,float* out_left,float* out_right){
 float x[8],r[8],y[8];
 for(unsigned i=0;i<8;++i){x[i]=left[i];r[i]=right[i];}
 unsigned p=*reinterpret_cast<const volatile unsigned*>(0x20005ad0u);
 if(p<0x20000000u||p>0x2003ff80u||!ready){for(unsigned i=0;i<8;++i)out_left[i]=out_right[i]=0;return;}
 unsigned control=*reinterpret_cast<const volatile unsigned char*>(p+3);
 if(control!=last_control){model.reset();last_control=control;}
 if(control&0x40u){for(unsigned i=0;i<8;++i){out_left[i]=x[i];out_right[i]=r[i];}return;}
 bool valid=true;for(float v:x)valid &= __builtin_isfinite(v);
 if(valid){model.process(x,y,8);for(float v:y)valid &= __builtin_isfinite(v);}
 if(!valid){model.reset();for(auto &v:y)v=0;}
 for(unsigned i=0;i<8;++i)out_left[i]=out_right[i]=y[i];
}
}
