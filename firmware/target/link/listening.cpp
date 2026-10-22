#include "listening.hpp"
// This section replaces only the retired stock audio callback's body. Its
// entry is already redirected, and the shared literal pools remain untouched.
#define AUDIO_BODY __attribute__((section(".retired_audio"),noinline))
extern "C" {
volatile uint32_t mpp_listen_enabled, mpp_listen_warm;
static volatile uint32_t ramp;
static uint8_t previous[99];
#ifdef MPP_OUTPUT_BUFFER
// Stock DSP and DMA stay at eight frames. These are additional output blocks,
// never a larger processing deadline. Zero is the NAMLNK08 minimum latency.
volatile uint32_t mpp_output_delay_blocks;
static int32_t output_delay[48];
static unsigned delay_write,delay_count;
AUDIO_BODY void mpp_buffer_set(unsigned samples){
 if(samples!=8&&samples!=16&&samples!=32)return;
 mpp_listen_reset();
 mpp_output_delay_blocks=samples/8-1;
}
AUDIO_BODY uint32_t mpp_buffer_page(){
 #ifdef MPP_GLOBAL_BUFFER
 extern unsigned mpp_global_error;
 return (48000u<<16)|((2u|(mpp_global_error<<4))<<8)|((mpp_output_delay_blocks+1)*8);
#else
 return (48000u<<16)|(1u<<8)|((mpp_output_delay_blocks+1)*8);
#endif
}
#endif

AUDIO_BODY void mpp_listen_reset(){
 mpp_listen_enabled=0;mpp_listen_warm=1200;ramp=0;
#ifdef MPP_OUTPUT_BUFFER
 delay_write=delay_count=0;
#endif
}
AUDIO_BODY void mpp_listen_prepare(){
 const uint32_t addr=*(volatile uint32_t*)0x20005ad0;
 if(addr<0x20000000||addr>0x2003ff80){mpp_listen_reset();return;}
 const volatile uint8_t* preset=(const volatile uint8_t*)(uintptr_t)addr;
 // Includes effect types, bypass, parameters, preset level and chain order.
 // Changes settle with NAM bypassed/read-only primed and the output muted.
 // 1200 blocks = 200 ms at the stock 48 kHz, eight-frame block size.
 for(unsigned i=1;i<99;++i){
#ifdef MPP_USB_NAM_CONTROLS
  if((i>=27&&i<=35)||i==84)continue;
#endif
  uint8_t value=preset[i];
  if(value!=previous[i]){previous[i]=value;mpp_listen_warm=1200;}
 }
 if(mpp_listen_warm){--mpp_listen_warm;ramp=0;}
}
AUDIO_BODY uint32_t mpp_listen_page(){
 return mpp_listen_enabled|(mpp_listen_warm?2:0)|(ramp==1024?4:0);
}
AUDIO_BODY void mpp_listen_render(const float* l,const float* r,int32_t* tx){
 if(!mpp_listen_enabled||mpp_listen_warm){ramp=0;
#ifdef MPP_OUTPUT_BUFFER
  delay_write=delay_count=0;
#endif
  return;}
 for(unsigned i=0;i<8;++i){
  if(ramp<1024)++ramp;
  // 21.3 ms fade to a fixed -18.06 dB pad, AFTER stereo output protection.
  // Ceiling is then 0.109375 full scale. This is a conservative first-listen
  // level, not a calibrated acoustic/headphone-volume guarantee.
  float gain=(float)ramp*0x1p18f;
  int32_t a=(int32_t)(l[i]*gain),b=(int32_t)(r[i]*gain);
#ifdef MPP_OUTPUT_BUFFER
  if(mpp_output_delay_blocks){
   const unsigned at=delay_write*16+i*2;
   int32_t old_l=delay_count>=mpp_output_delay_blocks?output_delay[at]:0;
   int32_t old_r=delay_count>=mpp_output_delay_blocks?output_delay[at+1]:0;
   output_delay[at]=a;output_delay[at+1]=b;a=old_l;b=old_r;
  }
#endif
  // Matches stock 0x14e8c..0x14ec6 + packer 0x15028: L,R,L,R.
  tx[4*i]=tx[4*i+2]=a;tx[4*i+1]=tx[4*i+3]=b;
 }
#ifdef MPP_OUTPUT_BUFFER
 if(mpp_output_delay_blocks){
  if(++delay_write==mpp_output_delay_blocks)delay_write=0;
  if(delay_count<mpp_output_delay_blocks)++delay_count;
 }
#endif
}
}
