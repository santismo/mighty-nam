#include "fx_blocks.hpp"
#include "reply_transport.hpp"
#ifdef MPP_RESPONSIVE_CONTROLS
extern "C" {volatile unsigned mpp_fx_active;}
#endif
#ifdef MPP_ACTIVE_CHAIN_PROTOTYPE
extern "C" volatile uint32_t mpp_listen_warm;
#endif
namespace {
mpp::fx::Engine engines[2];uint8_t settings[2][32];volatile unsigned selected;
uint32_t word(uintptr_t a){return *(volatile uint32_t*)a;}
}
extern "C" void mpp_fx_init(){mpp::fx::defaults(settings[0]);mpp::fx::defaults(settings[1]);selected=0;for(auto& e:engines)e.reset();mpp_reply_init();
#ifdef MPP_RESPONSIVE_CONTROLS
 mpp_fx_active=0;
#endif
}
extern "C" void mpp_fx_get(uint8_t* out){const auto* p=settings[selected];for(unsigned i=0;i<32;++i)out[i]=p[i];}
extern "C" bool mpp_fx_set(const uint8_t* input){
 if(!mpp::fx::valid(input))return false;unsigned next=selected^1;
 for(unsigned i=0;i<32;++i)settings[next][i]=input[i];
#ifdef MPP_ACTIVE_CHAIN_PROTOTYPE
 // Publish transition settling before the configuration. The old-block
 // renderer runs before the graph, so detecting this inside DSP is too late.
 const auto* old=settings[selected];
 if(old[1]!=input[1]||(old[1]&&old[2]!=input[2])||
    old[17]!=input[17]||(old[17]&&old[18]!=input[18]))mpp_listen_warm=1200;
#endif
 __asm__ volatile("dmb":::"memory");selected=next;
#ifdef MPP_RESPONSIVE_CONTROLS
 mpp_fx_active=input[1]||input[17]||engines[0].wet!=0||engines[1].wet!=0;
#endif
 return true;
}
extern "C" void mpp_fx_before(unsigned boundary,float* l,float* r){
 if(boundary>9)return;const auto* c=settings[selected];
#ifdef MPP_RESPONSIVE_CONTROLS
 if(!c[1]&&!c[17]&&engines[0].wet==0&&engines[1].wet==0){mpp_fx_active=0;return;}
#endif
 unsigned first=c[2]<c[18]?0:1;
 for(unsigned i=0;i<2;++i){unsigned slot=first^i;const auto* p=c+16*slot;
  if(unsigned(p[2])-i==boundary)engines[slot].process(p,l,r,8);}
}
#ifdef MPP_ACTIVE_CHAIN_PROTOTYPE
extern "C" void mpp_fx_graph_update(unsigned mask){
 for(unsigned slot=0;slot<2;++slot)if(!(mask&(1u<<(11+slot))))engines[slot].reset();
}
extern "C" void mpp_fx_graph_process(unsigned slot,float* l,float* r){
 if(slot<2)engines[slot].process(settings[selected]+16*slot,l,r,8);
}
#endif
extern "C" uint32_t mpp_bank_page();
extern "C" void mpp_fx_query(const uint8_t* p,unsigned n,unsigned channel){
 if(word(0xe000ed04)&511||n<13||p[8]!=1||p[9]>2||!(p[11]|p[12])||p[11]>127||p[12]>127)return;
 unsigned op=p[9],slot=p[10]==127?255:p[10],error=0;uint8_t config[32];
 const unsigned active=mpp_bank_page()&255;
 if(op==1){
  if(n!=51||slot!=active||p[18]>15)return;
  uint32_t model=0;for(unsigned i=0;i<5;++i){if(p[14+i]>127)return;model|=uint32_t(p[14+i])<<(7*i);}
  extern volatile uint32_t mpp_link[];
  if(p[13]!=0||model!=mpp_link[5]||!mpp_fx_set(p+19))error=2;
 }else if(n!=13)return;
 if(op==2){if(slot>6)return;mpp_fx_saved(slot,config);}else mpp_fx_get(config);
 uint8_t out[48];for(unsigned i=0;i<9;++i)out[i]=p[i];out[9]=op|64;out[10]=p[10];out[11]=p[11];out[12]=p[12];out[13]=error;out[14]=active==255?127:active;
 for(unsigned i=0;i<32;++i)out[15+i]=config[i];out[47]=247;mpp_reply_send(out,48,channel);
}
