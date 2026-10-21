// NAMDMP02 OFFLINE ONLY. Masked, bounded publication with an early fallback.
// The four-word reserve assumes the complete snapshot/copy/DSB fits in 4096
// DWT cycles and that an IRQ interval exceeds 100000 cycles. Both assumptions
// need hardware validation. A post-copy overrun is detectable, NOT reversible.
#include "dma_deadline.hpp"
#include "driver_timing.hpp"
#define BANK __attribute__((section(".banktext"),noinline))
extern "C" {
extern volatile uint32_t mpp_dwt_reset_epoch;
extern volatile uint32_t mpp_irq_stats[10];
int32_t mpp_dma_pcm[32];
// mode, early commits, current commits, rejected commits, last reason,
// last margin in serial words, last masked transaction cycles, overrun count.
volatile uint32_t mpp_dma_stats[8];
static uint32_t entry_cycles,entry_ctrl,entry_epoch;
static uint32_t rd(uint32_t a){return *(volatile uint32_t*)a;}
static void increment(volatile uint32_t& x){if(x!=0xffffffffu)++x;}

BANK void mpp_driver_capture(unsigned phase,uint32_t){
 if(!phase){entry_epoch=mpp_dwt_reset_epoch;entry_ctrl=rd(0xe0001000);entry_cycles=rd(0xe0001004);}
}
BANK void mpp_driver_control(unsigned){} // No runtime latch reset or implicit output control.
BANK uint32_t mpp_driver_page(unsigned page,uint32_t* out){
 if(page<118||page>126)return 1;
 *out=page==118?0xd2000002:mpp_dma_stats[page-119];return 0;
}

// Returns only after restoring the caller's PRIMASK, on success and rejection.
// DMA remains running. No SAI/TCD/clock writes and no speculative TX writes.
BANK unsigned mpp_dma_commit(int32_t* tx,const int32_t* from,unsigned current){
 uint32_t mask;
 __asm__ volatile("mrs %0,primask\ncpsid i":"=r"(mask)::"memory");
 const uint32_t start=rd(0xe0001004),t=(uint32_t)(uintptr_t)tx;
 unsigned reason=0,slack=0;
 if((t!=0x20016900&&t!=0x20016980)||!(mpp_irq_stats[0]&1))reason=1;
 else if(!(entry_ctrl&1)||rd(0xe0001000)!=entry_ctrl||mpp_dwt_reset_epoch!=entry_epoch||
         (uint32_t)(start-entry_cycles)>100000u)reason=2;
 else {
  const uint32_t source=rd(0x40071200),citer=rd(0x40071214),next=rd(0x40071218);
  const uint32_t fifo=rd(0x40404040),csr=rd(0x40404008),rxcsr=rd(0x40404088);
  const uint32_t rxnext=rd(0x40071018),rx=rd(0x40071010);
  const uint32_t other=(t^128u),prior=other+64u;
  const uint32_t expected_next=0x20016ae0u+((t-0x20016900u)^128u)/4u;
  const unsigned occupancy=((fifo>>16)-(fifo&63u))&63u;
  const unsigned distance=source==t?0:16;
  if(!((source==t&&(citer>>16)==2&&next==expected_next)||
       (source==prior&&(citer>>16)==1&&next==0x20016ae0u+(t-0x20016900u)/4u))||
       (citer&65535u))reason=3;
  else if(rxnext!=0x20016aa0u+(t-0x20016900u)/4u||
          (rx!=(other-256u)&&rx!=(other-192u)))reason=4;
  else if(rd(0x4040400c)!=8u||occupancy>32||occupancy<=8||
          ((csr|rxcsr)&0xc0000u))reason=5;
  else {
   slack=occupancy-8+distance;
   if(slack<=4)reason=6;
   else if(source!=rd(0x40071200)||citer!=rd(0x40071214)||next!=rd(0x40071218)||
           rxnext!=rd(0x40071018)||rx!=rd(0x40071010))reason=7;
  }
 }
 // Reserve the second half of the transaction budget for the stores + DSB.
 if(!reason&&((uint32_t)(rd(0xe0001004)-start)>=2048u||
    rd(0xe0001000)!=entry_ctrl||mpp_dwt_reset_epoch!=entry_epoch))reason=8;
 if(!reason){
  for(unsigned i=0;i<32;++i)tx[i]=from?from[i]:0;
  __asm__ volatile("dsb":::"memory");
  const uint32_t elapsed=rd(0xe0001004)-start;
  mpp_dma_stats[6]=elapsed;
  if(elapsed>=4096u){reason=9;increment(mpp_dma_stats[7]);}
  else increment(mpp_dma_stats[current?2:1]);
 }
 if(reason){mpp_dma_stats[0]=1;increment(mpp_dma_stats[3]);}
 mpp_dma_stats[4]=reason;mpp_dma_stats[5]=slack;
 __asm__ volatile("msr primask,%0"::"r"(mask):"memory");
 return !reason;
}
BANK void mpp_dma_prefill(int32_t* tx,unsigned playing){
 mpp_dma_commit(tx,playing?mpp_dma_pcm:nullptr,0);
}
BANK void mpp_dma_finish(int32_t* tx,unsigned valid){
 if(!valid||!mpp_dma_stats[0])mpp_dma_commit(tx,valid?mpp_dma_pcm:nullptr,1);
}
}
