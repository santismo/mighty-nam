#include "nam_controls.hpp"
#include "reply_transport.hpp"
namespace {mpp::tone::Engine engine;unsigned generation;}
extern "C" volatile uint32_t mpp_link[];
extern "C" uint32_t mpp_bank_page();
extern "C" void mpp_nam_reset(){engine.reset();}
extern "C" const float* mpp_nam_input(const float* dry){
 if(generation!=mpp_link[6]){engine.reset();generation=mpp_link[6];}
 uint8_t p[6];mpp::tone::decode(*(const uint8_t**)0x20005ad0,p);return engine.prepare(dry,p);
}
extern "C" void mpp_nam_output(const float* a,const float* b,float* l,float* r){engine.finish(a,b,l,r);}
extern "C" void mpp_nam_query(const uint8_t* p,unsigned n,unsigned channel){
 if((*(volatile uint32_t*)0xe000ed04&511)||n<13||p[8]!=1||p[9]>1||!(p[11]|p[12]))return;
 for(unsigned i=8;i<n;++i)if(p[i]>127)return;
 const bool recording=p[7]=='V';
 unsigned op=p[9],active=mpp_bank_page()&255,slot=p[10]==127?255:p[10],error=0;
 auto* preset=*(uint8_t**)0x20005ad0;
 if((uintptr_t)preset<0x20000000||(uintptr_t)preset>0x2003ff80)return;
 if(op){
  if(n!=(recording?20u:25u)||p[18]>15)return;
  uint32_t crc=0;for(unsigned i=0;i<5;++i)crc|=uint32_t(p[14+i])<<(7*i);
  if(slot!=active||p[13]||crc!=mpp_link[5]||(recording?p[19]>96:!mpp::tone::valid(p+19)))error=2;
  else{
   unsigned irq;__asm__ volatile("mrs %0, primask\ncpsid i":"=r"(irq)::"memory");
   const uintptr_t addresses[4]={(uintptr_t)preset,0x20005af0,0x20005b70,0x20012230};
   for(uintptr_t address:addresses){
    auto* q=(volatile uint8_t*)address;
    if(recording){uint8_t controls[6];mpp::tone::decode((const uint8_t*)address,controls);for(unsigned i=0;i<6;++i)q[27+i]=controls[i];q[35]=p[19];q[33]=78;q[34]=2;}
    else{const bool keep=q[33]==78&&q[34]==2;for(unsigned i=0;i<6;++i)q[27+i]=p[19+i];q[33]=78;q[34]=keep?2:1;}
   }
   __asm__ volatile("dmb\nmsr primask, %0"::"r"(irq):"memory");
  }
 }else if(n!=13)return;
 uint8_t out[22];for(unsigned i=0;i<13;++i)out[i]=p[i];out[9]=op|64;out[13]=error;out[14]=active==255?127:active;
 if(recording){out[15]=mpp::tone::record(preset);out[16]=247;mpp_reply_send(out,17,channel);}
 else{mpp::tone::decode(preset,out+15);out[21]=247;mpp_reply_send(out,22,channel);}
}
