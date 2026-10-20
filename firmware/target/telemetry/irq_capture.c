/* Exact public V1.5.6 OFFLINE OVERLAY. No timer setup, flash, USB or audio API.
 * GPT2 is a candidate, not hardware-proven unused. Leave armed zero until its
 * ownership, clock and DMA timing are established. The stock C runtime clears
 * this state on cold/warm initialization. Read coherent stats with writer stopped.
 * This is bounded raw capture; it does NOT assert clock calibration or deadlines.
 * Instrumentation after the end timestamp and exception entry/exit are excluded.
 */
#include <stdint.h>
typedef struct {
 uint32_t armed, count, invalid, flags;
 uint32_t begin_ref, end_ref, begin_cycle, end_cycle;
 uint32_t previous_entry, last_interval, maximum_interval;
 uint32_t maximum_duration, last_dma_pointer;
} mpp_irq_capture_state;
volatile mpp_irq_capture_state mpp_irq_capture;
#define REG(a) (*(volatile uint32_t*)(a))
#define STOCK_IRQ ((void (*)(void))0x00011d95u)
#define GPT2 0x400f0000u
void mpp_capture_irq(void) {
 if (mpp_irq_capture.armed!=0x54494d45u) { STOCK_IRQ(); return; }
 uint32_t cr=REG(GPT2), pr=REG(GPT2+4), ir=REG(GPT2+12);
 uint32_t start=REG(GPT2+0x24), cycle=REG(0xe0001004u);
 STOCK_IRQ();
 uint32_t end=REG(GPT2+0x24), end_cycle=REG(0xe0001004u);
 mpp_irq_capture.begin_ref=start; mpp_irq_capture.end_ref=end;
 mpp_irq_capture.begin_cycle=cycle; mpp_irq_capture.end_cycle=end_cycle;
 mpp_irq_capture.last_dma_pointer=REG(0x40071018u);
 uint32_t duration=end-start;
 if (cr!=0x741u || pr || ir || REG(GPT2)!=cr || REG(GPT2+4)!=pr ||
     REG(GPT2+12)!=ir || !duration || duration>=0x80000000u) {
  mpp_irq_capture.flags|=1u;
  if (mpp_irq_capture.invalid!=0xffffffffu) ++mpp_irq_capture.invalid;
  return;
 }
 if (mpp_irq_capture.count==0xffffffffu) { mpp_irq_capture.flags|=2u; return; }
 if (mpp_irq_capture.count) {
  uint32_t interval=start-mpp_irq_capture.previous_entry;
  mpp_irq_capture.last_interval=interval;
  if(interval>mpp_irq_capture.maximum_interval) mpp_irq_capture.maximum_interval=interval;
 }
 mpp_irq_capture.previous_entry=start;
 if(duration>mpp_irq_capture.maximum_duration) mpp_irq_capture.maximum_duration=duration;
 ++mpp_irq_capture.count;
}
