// NAMLNK06 offline diagnostic: enclose the original V1.5.6 audio IRQ body.
// Raw DWT cycles, NOT a calibrated deadline or DMA-release measurement.
// Does not enable/reset counters or change clocks. The stock delay reset is
// preserved and counted by a separate exact-site hook.
#include <stdint.h>
#ifdef MPP_DRIVER_TIMING
#include "driver_timing.hpp"
#endif
extern "C" {
// sequence, accepted, rejected, flags, last cycles, maximum cycles,
// entry CTRL, exit CTRL, entry reset epoch, exit reset epoch.
volatile uint32_t mpp_irq_stats[10];
volatile uint32_t mpp_dwt_reset_epoch;
uint32_t mpp_irq_snapshot_words[10];
static uint32_t snapshot_ready;

#ifdef MPP_OUTPUT_BUFFER
__attribute__((section(".retired_audio")))
#endif
__attribute__((naked)) void mpp_track_dwt_reset() {
 __asm__ volatile(
  "push {r0,r1}\n"
  "str r5, [r6, #4]\n" // displaced stock reset
  "ldr r3, [r6]\n"     // displaced stock CTRL read
  "ldr r0, =mpp_dwt_reset_epoch\n"
  "ldr r1, [r0]\n"
  "add.w r1, r1, #1\n" // preserve condition flags and all other live registers
  "str r1, [r0]\n"
  "pop {r0,r1}\n"
  "bx lr\n");
}

void mpp_link_irq() {
 auto& s=mpp_irq_stats;
 ++s[0]; // odd while an IRQ sample is being published
 const uint32_t epoch=mpp_dwt_reset_epoch;
 const uint32_t ctrl=*(volatile uint32_t*)0xe0001000u;
 const uint32_t start=*(volatile uint32_t*)0xe0001004u;
#ifdef MPP_DRIVER_TIMING
 mpp_driver_capture(0,0);
#endif
 ((void(*)(void))0x11d95u)();
 const uint32_t end=*(volatile uint32_t*)0xe0001004u;
 const uint32_t after=*(volatile uint32_t*)0xe0001000u;
 const uint32_t last_epoch=mpp_dwt_reset_epoch;
 const uint32_t span=end-start;
 s[6]=ctrl;s[7]=after;s[8]=epoch;s[9]=last_epoch;
 uint32_t flags=0;
 if(!(ctrl&1)||ctrl!=after)flags|=1;
 if(epoch!=last_epoch)flags|=2;
 if(!span||span>=0x80000000u)flags|=4;
 if(s[1]==0xffffffffu||s[2]==0xffffffffu)flags|=8;
 if(flags){s[3]|=flags;if(s[2]!=0xffffffffu)++s[2];}
 else {
  s[4]=span;
  // An explicit branch avoids Unicorn's Thumb IT/store instrumentation defect
  // when the protected-RAM harness observes this write. Same unsigned maximum.
  const uint32_t maximum=s[5];
  __asm__ volatile("cmp %0,%1\nbls 1f\nstr %0,[%2]\n1:"
    ::"r"(span),"r"(maximum),"r"(&s[5]):"cc","memory");
  ++s[1];
 }
 ++s[0]; // even, including intentional unsigned sequence wrap
}

// Page 12 latches a bounded coherent snapshot; 13..22 read it. Error 2 means
// all three attempts were interrupted; error 3 means no snapshot is available.
// No IRQ masking, timer writes, audio pause, or unbounded foreground spinning.
uint32_t mpp_irq_page(unsigned page,uint32_t* value) {
 if(page==12){
  snapshot_ready=0;
  for(unsigned attempt=0;attempt<3;++attempt){
   uint32_t sequence=mpp_irq_stats[0];
   for(unsigned i=0;i<10;++i)mpp_irq_snapshot_words[i]=mpp_irq_stats[i];
   __asm__ volatile("dmb":::"memory");
   if(!(sequence&1)&&sequence==mpp_irq_stats[0]){
    snapshot_ready=1;*value=0x54494d31;return 0;
   }
  }
  return 2;
 }
 if(page<13||page>=23)return 1;
 if(!snapshot_ready)return 3;
 *value=mpp_irq_snapshot_words[page-13];return 0;
}
}
