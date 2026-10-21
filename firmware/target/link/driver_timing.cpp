// NAMLNK19. One-shot observational diagnostics; no peripheral writes, counter
// resets, IRQ masking, output control or continuous tracing. A snapshot is a
// time-bracketed sequence of reads, NOT an atomic DMA/FIFO or deadline proof.
#include "driver_timing.hpp"
#define CAPTURE __attribute__((section(".driver_capture")))
#define QUERY __attribute__((section(".driver_query")))
extern "C" {
extern volatile uint32_t mpp_dwt_reset_epoch;
extern volatile uint32_t mpp_irq_stats[10];
// state: idle=0, armed=1, entry captured=2, complete=3, no render=4.
volatile uint32_t mpp_driver_state, mpp_driver_generation;
volatile uint32_t mpp_driver_words[48];
static unsigned window;
// CITER is the upper half of the aligned DOFF/CITER word at TCD+0x14.
static const uint32_t addresses[] __attribute__((section(".driver_capture.constants")))={
 0xe0001000,0xe0001004,0x40071018,0x40071218,
 0x40071010,0x40071200,0x40071014,0x40071214,
 0x40404040,0x404040c0,0x40404008,0x40404088,
 0x40071018,0x40071218,0x40071010,0x40071200,
 0x40071014,0x40071214,0xe0001004,0xe0001000};
CAPTURE void mpp_driver_capture(unsigned phase,uint32_t tx){
 if(mpp_driver_state!=phase+1){
  if(!phase&&mpp_driver_state==2)mpp_driver_state=4;
  return;
 }
 auto* out=mpp_driver_words+phase*24;
 out[0]=mpp_dwt_reset_epoch;
 for(unsigned i=0;i<20;++i)out[1+i]=*(volatile uint32_t*)(uintptr_t)addresses[i];
 out[21]=mpp_dwt_reset_epoch;out[22]=mpp_irq_stats[0];out[23]=tx;
 __asm__ volatile("dmb":::"memory");
 mpp_driver_state=phase+2;
}
// ND 0..5 selects a read window only. 126 cancels; 127 explicitly arms one
// capture, without changing playback. Do not overwrite a pending observation.
QUERY void mpp_driver_control(unsigned action){
 if(*(volatile uint32_t*)0xe000ed04&511)return;
 if(action<6)window=action;
 if(action==126)mpp_driver_state=0;
 if(action==127&&mpp_driver_state!=1&&mpp_driver_state!=2){
  ++mpp_driver_generation;
  __asm__ volatile("dmb":::"memory");mpp_driver_state=1;
 }
}
QUERY uint32_t mpp_driver_page(unsigned page,uint32_t* value){
 if(page==118){*value=0xd1000000|((mpp_driver_generation&65535)<<8)|mpp_driver_state;return 0;}
 if(page<119||page>126)return 1;
 if(mpp_driver_state!=3)return 2;
 *value=mpp_driver_words[window*8+page-119];return 0;
}
}
