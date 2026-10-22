// NAMACP01: offline active-node dispatcher, independent of the DMA experiment.
#include "active_chain.hpp"
#include "fx_blocks.hpp"
#include "cut_eq.hpp"
#define BANK __attribute__((section(".banktext"),noinline))
#define LOW __attribute__((section(".driver_query"),noinline))
extern "C" void mpp_tail_resume(unsigned);
extern "C" void mpp_fx_graph_update(unsigned);
#ifdef MPP_USB_NAM_CONTROLS
extern "C" void mpp_nam_reset();
#endif
extern "C" void mpp_fx_graph_process(unsigned,float*,float*);
namespace {
mpp::graph::Plan plan;
uint8_t previous[24];
unsigned valid,previous_mask;
float audio[2][2][8];
uint32_t word(uintptr_t a){return *(volatile uint32_t*)a;}
}
extern "C" {
// count, rebuilds, last-block stock calls, last-block custom calls, invalid plans.
volatile uint32_t mpp_graph_stats[5];
LOW void mpp_driver_capture(unsigned,uint32_t){}
LOW void mpp_driver_control(unsigned){}
LOW uint32_t mpp_driver_page(unsigned page,uint32_t* value){
 if(page<118||page>123)return 1;
 *value=page==118?0xac010001:mpp_graph_stats[page-119];return 0;
}
LOW void mpp_graph_fades(float* l,float* r,const float* gain,unsigned count){
 for(unsigned n=0;n<count;++n)for(unsigned i=0;i<8;++i){l[i]*=gain[i];r[i]*=gain[i];}
}
BANK void mpp_active_dispatch(){
 const auto* p=(const uint8_t*)(uintptr_t)word(0x20005ad0);
 auto* l=(float*)0x2000d988;auto* r=(float*)0x2000d9a8;
 mpp_graph_stats[2]=mpp_graph_stats[3]=0;
 if((uintptr_t)p<0x20000000||(uintptr_t)p>0x2003ff80){
  for(unsigned i=0;i<8;++i)l[i]=r[i]=0;
  valid=0;plan.count=0;mpp_graph_stats[0]=0;++mpp_graph_stats[4];return;
 }
 uint8_t fx[32],key[24];mpp_fx_get(fx);
 for(unsigned i=0;i<9;++i){key[i]=p[i+1]&64;key[9+i]=p[90+i];}
 key[18]=fx[1];key[19]=fx[2];key[20]=fx[17];key[21]=fx[18];key[22]=p[89];key[23]=p[99];
 bool changed=!valid;
 for(unsigned i=0;i<24;++i)if(key[i]!=previous[i])changed=true;
 if(changed){
  if(!mpp::graph::compile(p,fx,plan)){
   plan.count=0;valid=0;++mpp_graph_stats[4];
  }else{
   unsigned mask=0;for(unsigned i=0;i<plan.count;++i)mask|=1u<<plan.nodes[i];
   for(unsigned id=7;id<=8;++id)if(valid&&(mask&(1u<<id))&&!(previous_mask&(1u<<id)))mpp_tail_resume(id);
   if((mask&(1u<<4))&&!(previous_mask&(1u<<4)))mpp_cut_eq_init();
   #ifdef MPP_USB_NAM_CONTROLS
   mpp_nam_reset();
   #endif
   mpp_fx_graph_update(mask);previous_mask=mask;
   for(unsigned i=0;i<24;++i)previous[i]=key[i];
   valid=1;++mpp_graph_stats[1];
  }
 }
 mpp_graph_stats[0]=plan.count;mpp_graph_stats[2]=mpp_graph_stats[3]=0;
 if(!valid){for(unsigned i=0;i<8;++i)l[i]=r[i]=0;return;}
 // Validate before the stock manager can index its stage descriptor table.
 // Keep that routing-state manager/loaders; replace its audio dispatcher.
 ((void(*)())0x121d5)();
 const auto* input_l=(const float*)(uintptr_t)word(0x200005d0);
 const auto* input_r=(const float*)(uintptr_t)word(0x200005d4);
 for(unsigned i=0;i<8;++i){audio[0][0][i]=input_l[i];audio[0][1][i]=input_r[i];}
 // Retain exact stock transition gain placement, without the unused callback
 // copies. At unity (normal playback) none of these gain loops execute.
 const auto* gain=(const float*)0x2000d9c8;
 bool fading=false;for(unsigned i=0;i<8;++i)if(gain[i]!=1.f)fading=true;
 unsigned at=0,fades=0;
 for(unsigned n=0;n<plan.count;++n){
  const unsigned id=plan.nodes[n];
  if(fading){
   mpp_graph_fades(audio[at][0],audio[at][1],gain,plan.fade_steps[n]-fades);fades=plan.fade_steps[n];
  }
  if(id>=11){mpp_fx_graph_process(id-11,audio[at][0],audio[at][1]);++mpp_graph_stats[3];}
  else{
   auto callback=(void(*)(const float*,const float*,float*,float*))(uintptr_t)word(0x20000530+id*12);
   if(id==4)callback=mpp_cut_eq_process;
   callback(audio[at][0],audio[at][1],audio[at^1][0],audio[at^1][1]);
   at^=1;++mpp_graph_stats[2];
  }
 }
 if(fading)mpp_graph_fades(audio[at][0],audio[at][1],gain,22-fades);
 for(unsigned i=0;i<8;++i){l[i]=audio[at][0][i];r[i]=audio[at][1][i];}
}
}
