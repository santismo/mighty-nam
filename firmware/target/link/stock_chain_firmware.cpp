// Exact V1.5.6 stock-effects bridge with RAM A2. NAMLNK02..06 stay silent;
// NAMLNK07 adds explicitly armed listening. No flash or reset commands.
#include "model_receiver.hpp"
#ifdef MPP_USB_NAM_CONTROLS
#include "nam_controls.hpp"
#endif
#ifdef MPP_DMA_DEADLINE_PROTOTYPE
#include "dma_deadline.hpp"
#endif
#ifdef MPP_DRIVER_TIMING
#include "driver_timing.hpp"
#endif
#ifdef MPP_CUT_EQ
#include "cut_eq.hpp"
#endif
#include "sysex_codec.hpp"
#ifdef MPP_ADC_SHORT_DELAY
extern "C" uint32_t mpp_codec_filter_page();
#endif
#ifdef MPP_FX_BLOCKS
#include "fx_blocks.hpp"
#include "reply_transport.hpp"
#endif
#ifdef MPP_TUNER
extern "C" void mpp_tuner_init();
extern "C" void mpp_tuner_feed(const int32_t*);
extern "C" void mpp_tuner_query(const uint8_t*,unsigned,unsigned);
#endif
#ifdef MPP_PRESET_BANK
#include "preset_runtime.hpp"
#define BANK_TEXT __attribute__((section(".banktext")))
#else
#define BANK_TEXT
#endif
#ifdef MPP_LISTENING
#include "listening.hpp"
#endif
#ifdef MPP_IRQ_TIMING
extern "C" uint32_t mpp_irq_page(unsigned,uint32_t*);
#endif
#ifdef MPP_EFFECT_PROFILER
extern "C" uint32_t mpp_profile_page(unsigned,uint32_t*);
extern "C" void mpp_profile_control(unsigned);
#endif
extern "C" {
struct LinkStatus {
 uint32_t magic,schema,ready,callbacks,faults,model_crc,generation,runs;
 uint32_t timer_max,running,context_rejections,last_output_bits;
};
volatile LinkStatus mpp_link;
unsigned mpp_hybrid_ready;
#ifdef MPP_FAST_BYPASS
#if defined(MPP_PITCH_QUALITY_RELEASE)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','2','2'};
#elif defined(MPP_PITCH_QUALITY_PROTOTYPE)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','P','I','T','0','1'};
#elif defined(MPP_USB_NAM_CONTROLS)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','2','1'};
#elif defined(MPP_ACTIVE_CHAIN_RELEASE)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','2','0'};
#elif defined(MPP_ACTIVE_CHAIN_PROTOTYPE)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','A','C','P','0','1'};
#elif defined(MPP_DMA_DEADLINE_PROTOTYPE)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','D','M','P','0','2'};
#elif defined(MPP_DMA_CURRENT_PROTOTYPE)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','D','M','P','0','1'};
#elif defined(MPP_DRIVER_TIMING)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','1','9'};
#elif defined(MPP_GLOBAL_BUFFER)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','1','8'};
#elif defined(MPP_ADC_SHORT_DELAY)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','1','7'};
#elif defined(MPP_M7_POINTER_TAPS)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','1','6'};
#elif defined(MPP_RESPONSIVE_CONTROLS)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','1','5'};
#elif defined(MPP_CUT_EQ)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','1','4'};
#elif defined(MPP_FX_BLOCKS)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','1','3'};
#elif defined(MPP_TUNER)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','1','2'};
#elif defined(MPP_EFFECT_PROFILER)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','1','1'};
#elif defined(MPP_PRESET_BANK)
__attribute__((section(".banktext.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','1','0'};
#elif defined(MPP_OUTPUT_BUFFER)
__attribute__((section(".retired_audio.constants")))
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','0','9'};
#elif defined(MPP_EARLY_OUTPUT)
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','0','8'};
#elif defined(MPP_LISTENING)
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','0','7'};
#elif defined(MPP_IRQ_TIMING)
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','0','6'};
#elif defined(MPP_PRIME_STATE)
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','0','5'};
#elif defined(MPP_M7_DENSE)
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','0','4'};
#else
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','0','3'};
#endif
#ifdef MPP_DRIVER_TIMING
uint16_t mpp_bypass_hold[11];
// Reuse the stock type-change handoff in foreground; never load overlays in IRQ.
// 65534 denotes a used tail effect put to sleep, distinct from fresh bypass.
extern "C" BANK_TEXT void mpp_tail_resume(unsigned stage){
 const auto* preset=*(const volatile uint8_t**)0x20005ad0;
 unsigned type=preset[stage]&63;
 const unsigned maximum=stage==7?5:6;
 if(type<1||type>maximum)type=1;
 auto* base=(volatile uint8_t*)(stage==7?0x20003a08u:0x200041d8u);
 base[0]=type;base[1]=0;
 *(volatile uint32_t*)(base+12)=127;
 *(volatile uint32_t*)(base+(stage==7?44:40))=0;
}

// Entered only from the exact V1.5.6 dispatcher patch at 0x12302.
// r6 = remaining stages, r4 = descriptor+8; r9/r7 and r8/r5
// are input/output L/R. Preserve all live registers except scratch r0-r3.
// Original pre/post routing fades and BLX callback return address remain intact.
#ifndef MPP_ACTIVE_CHAIN_PROTOTYPE
extern "C" BANK_TEXT __attribute__((naked)) void mpp_fast_dispatch(){
 __asm__ volatile(
#ifdef MPP_FX_BLOCKS
#ifdef MPP_RESPONSIVE_CONTROLS
  "ldr r0, =mpp_fx_active\n"
  "ldr r0, [r0]\n"
  "cmp r0, #0\n"
  "beq 8f\n"
#endif
  "cmp r6, #11\n"
  "beq 8f\n"
  "push {r0-r3,r12,lr}\n"
  "rsb r0, r6, #10\n"
  "mov r1, r9\n"
  "mov r2, r7\n"
  "bl mpp_fx_before\n"
  "pop {r0-r3,r12,lr}\n"
  "8:\n"
#endif
  "ldr r1, =0x20005ad0\n"
  "ldr r1, [r1]\n"
  "rsb r0, r6, #100\n"
  "ldrb r0, [r1, r0]\n"
#ifdef MPP_CUT_EQ
  "cmp r0, #4\n"
  "bne 7f\n"
  "ldr r12, =mpp_cut_eq_process\n"
  "7:\n"
#endif
#ifdef MPP_EFFECT_PROFILER
  "ldr r2, =mpp_profile_selected\n"
  "ldr r2, [r2]\n"
  "adds r3, r0, #1\n"
  "cmp r2, r3\n"
  "beq 9f\n"
#endif
  "cmp r0, #9\n"
  "bhi 3f\n"
  "cmp r0, #0\n"
  "beq 3f\n"
  "cmp r0, #3\n"
  "beq 3f\n"
  "mov r3, r0\n"
  "ldrb r1, [r1, r0]\n"
  "ldr r2, =mpp_bypass_hold\n"
  "add r2, r2, r0, lsl #1\n"
  "tst r1, #64\n"
  "bne 1f\n"
  "cmp r0, #7\n"
  "beq 10f\n"
  "cmp r0, #8\n"
  "bne 11f\n"
  "10: ldrh r1, [r2]\n"
  "movw r3, #65534\n"
  "cmp r1, r3\n"
  "bne 12f\n"
  "push {r0-r3,r12,lr}\n"
  "bl mpp_tail_resume\n"
  "pop {r0-r3,r12,lr}\n"
  // Finish sleeping two blocks before the existing 1200-block mute settles.
  "12: movw r0, #1198\n"
  "b 6f\n"
  "11: cmp r0, #5\n"
  "beq 5f\n"
  "movw r0, #1200\n"
  "b 6f\n"
  "5: movw r0, #65535\n"
  "6:\n"
  "strh r0, [r2]\n"
  "b 3f\n"
  "1: ldrh r0, [r2]\n"
  "cbz r0, 2f\n"
  "movw r1, #65534\n"
  "cmp r0, r1\n"
  "beq 2f\n"
  "movw r1, #65535\n"
  "cmp r0, r1\n"
  "beq 3f\n"
  "subs r0, #1\n"
  "bne 13f\n"
  "cmp r3, #7\n"
  "beq 14f\n"
  "cmp r3, #8\n"
  "bne 13f\n"
  "14: movw r0, #65534\n"
  "13: strh r0, [r2]\n"
  "b 3f\n"
  // After 9600 samples of stock bypass processing, suspend dry-bypass effects.
  // Initially bypassed blocks have no previous tail, so can sleep immediately.
  // Load both inputs before writing either output to support in-place buffers.
  "2: movs r0, #0\n"
  "4: ldr r1, [r9, r0]\n"
  "ldr r2, [r7, r0]\n"
  "str r1, [r8, r0]\n"
  "str r2, [r5, r0]\n"
  "adds r0, #4\n"
  "cmp r0, #32\n"
  "bne 4b\n"
  "adds r4, #28\n"
  "ldr pc, =0x1230f\n"
  "3: mov r3, r5\n"
  "mov r2, r8\n"
  "mov r1, r7\n"
  "mov r0, r9\n"
  "adds r4, #28\n"
  "ldr pc, =0x1230d\n"
#ifdef MPP_EFFECT_PROFILER
  // Stage in r0. Forward the original callback and all four audio pointers.
  // Original SP is eight-byte aligned; retain LR and the routing's live regs.
  "9: sub sp, #16\n"
  "str r8, [sp]\n"
  "str r5, [sp, #4]\n"
  "str lr, [sp, #8]\n"
  "mov r1, r12\n"
  "mov r2, r9\n"
  "mov r3, r7\n"
  "bl mpp_profile_dispatch\n"
  "ldr lr, [sp, #8]\n"
  "add sp, #16\n"
  "adds r4, #28\n"
  "ldr pc, =0x1230f\n"
#endif
 );
}
#endif
#else
uint16_t mpp_bypass_hold[11];
// Entered only from the exact V1.5.6 dispatcher patch at 0x12302.
// r6 = remaining stages, r4 = descriptor+8; r9/r7 and r8/r5
// are input/output L/R. Preserve all live registers except scratch r0-r3.
// Original pre/post routing fades and BLX callback return address remain intact.
extern "C" __attribute__((naked)) void mpp_fast_dispatch(){
 __asm__ volatile(
#ifdef MPP_FX_BLOCKS
#ifdef MPP_RESPONSIVE_CONTROLS
  "ldr r0, =mpp_fx_active\n"
  "ldr r0, [r0]\n"
  "cmp r0, #0\n"
  "beq 8f\n"
#endif
  "cmp r6, #11\n"
  "beq 8f\n"
  "push {r0-r3,r12,lr}\n"
  "rsb r0, r6, #10\n"
  "mov r1, r9\n"
  "mov r2, r7\n"
  "bl mpp_fx_before\n"
  "pop {r0-r3,r12,lr}\n"
  "8:\n"
#endif
  "ldr r1, =0x20005ad0\n"
  "ldr r1, [r1]\n"
  "rsb r0, r6, #100\n"
  "ldrb r0, [r1, r0]\n"
#ifdef MPP_CUT_EQ
  "cmp r0, #4\n"
  "bne 7f\n"
  "ldr r12, =mpp_cut_eq_process\n"
  "7:\n"
#endif
#ifdef MPP_EFFECT_PROFILER
  "ldr r2, =mpp_profile_selected\n"
  "ldr r2, [r2]\n"
  "adds r3, r0, #1\n"
  "cmp r2, r3\n"
  "beq 9f\n"
#endif
  "cmp r0, #9\n"
  "bhi 3f\n"
  "cmp r0, #0\n"
  "beq 3f\n"
  "cmp r0, #3\n"
  "beq 3f\n"
  "ldrb r1, [r1, r0]\n"
  "ldr r2, =mpp_bypass_hold\n"
  "add r2, r2, r0, lsl #1\n"
  "tst r1, #64\n"
  "bne 1f\n"
  // Gate/delay/reverb retain small bypass residuals in stock V1.5.6.
  // Once used, keep their stock path alive; do not truncate those signals.
  "cmp r0, #5\n"
  "beq 5f\n"
  "cmp r0, #7\n"
  "beq 5f\n"
  "cmp r0, #8\n"
  "beq 5f\n"
  "movw r0, #1200\n"
  "b 6f\n"
  "5: movw r0, #65535\n"
  "6:\n"
  "strh r0, [r2]\n"
  "b 3f\n"
  "1: ldrh r0, [r2]\n"
  "cbz r0, 2f\n"
  "movw r1, #65535\n"
  "cmp r0, r1\n"
  "beq 3f\n"
  "subs r0, #1\n"
  "strh r0, [r2]\n"
  "b 3f\n"
  // After 9600 samples of stock bypass processing, suspend dry-bypass effects.
  // Initially bypassed blocks have no previous tail, so can sleep immediately.
  // Load both inputs before writing either output to support in-place buffers.
  "2: movs r0, #0\n"
  "4: ldr r1, [r9, r0]\n"
  "ldr r2, [r7, r0]\n"
  "str r1, [r8, r0]\n"
  "str r2, [r5, r0]\n"
  "adds r0, #4\n"
  "cmp r0, #32\n"
  "bne 4b\n"
  "adds r4, #28\n"
  "ldr pc, =0x1230f\n"
  "3: mov r3, r5\n"
  "mov r2, r8\n"
  "mov r1, r7\n"
  "mov r0, r9\n"
  "adds r4, #28\n"
  "ldr pc, =0x1230d\n"
#ifdef MPP_EFFECT_PROFILER
  // Stage in r0. Forward the original callback and all four audio pointers.
  // Original SP is eight-byte aligned; retain LR and the routing's live regs.
  "9: sub sp, #16\n"
  "str r8, [sp]\n"
  "str r5, [sp, #4]\n"
  "str lr, [sp, #8]\n"
  "mov r1, r12\n"
  "mov r2, r9\n"
  "mov r3, r7\n"
  "bl mpp_profile_dispatch\n"
  "ldr lr, [sp, #8]\n"
  "add sp, #16\n"
  "adds r4, #28\n"
  "ldr pc, =0x1230f\n"
#endif
 );
}
#endif
#else
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','0','2'};
#endif
float mpp_link_output[8];
static float chain_right[8];
}
static mpp::A2Lite model;
static mpp::link::ModelReceiver receiver;
static float load_scratch[1871];
static uint8_t packet[280],response[48],wire[65];
static uint32_t loaded_session;
static uint32_t rd(uint32_t addr){return *(volatile uint32_t*)(uintptr_t)addr;}
static void barrier(){__asm__ volatile("dmb":::"memory");}
#ifdef MPP_IRQ_TIMING
// Stereo-linked, eight-sample output headroom guard. The peak scan uses the
// ordered positive IEEE-754 bits, so NaNs/infinities cannot evade the check.
// Ordinary levels are bit-identical; overload applies one gain to both sides.
// This is bounded block protection, not a listening-validated release limiter.
extern "C" __attribute__((noinline))
#ifdef MPP_LISTENING
__attribute__((section(".retired_audio")))
#endif
void mpp_output_protect(float* l,float* r){
 uint32_t peak=0x3f600000; // 0.875 = -1.16 dBFS ceiling
 for(unsigned i=0;i<8;++i){
  uint32_t a,b;__builtin_memcpy(&a,l+i,4);__builtin_memcpy(&b,r+i,4);
  a&=0x7fffffff;b&=0x7fffffff;
  if(a>peak)peak=a;if(b>peak)peak=b;
 }
 if(peak>=0x7f800000){
  for(unsigned i=0;i<8;++i)l[i]=r[i]=0;
  ++mpp_link.faults;mpp_link.running=0;return;
 }
 if(peak==0x3f600000)return;
 float p;__builtin_memcpy(&p,&peak,4);
 // Two float ULPs below the ceiling leave room for division/multiply rounding.
 float gain=0x1.bffffcp-1f/p;
 // Round the positive gain down by one representable float. In particular,
 // subnormal division near FLT_MAX must never round the gain above its ratio.
 uint32_t g;__builtin_memcpy(&g,&gain,4);
 if(g)--g;
 __builtin_memcpy(&gain,&g,4);
 for(unsigned i=0;i<8;++i){l[i]*=gain;r[i]*=gain;}
}
#endif
extern "C" void mpp_stock_amp_init(){
#ifdef MPP_PRESET_BANK
 extern uint32_t __bank_start[],__bank_end[],__bank_load[];
 for(unsigned i=0;__bank_start+i<__bank_end;++i)__bank_start[i]=__bank_load[i];
 __asm__ volatile("dsb":::"memory");
 for(uintptr_t p=(uintptr_t)__bank_start;p<(uintptr_t)__bank_end;p+=32)
  *(volatile uint32_t*)0xe000ef68=p;
 __asm__ volatile("dsb":::"memory");
 *(volatile uint32_t*)0xe000ef50=0;
 __asm__ volatile("dsb\nisb":::"memory");
 mpp_bank_init();
#ifdef MPP_FX_BLOCKS
 mpp_fx_init();
#ifdef MPP_CUT_EQ
 mpp_cut_eq_init();
#endif
#endif
#ifdef MPP_TUNER
 mpp_tuner_init();
#endif
#endif
 mpp_hybrid_ready=0;
 volatile uint8_t* p=(volatile uint8_t*)&mpp_link;
 for(unsigned i=0;i<sizeof(mpp_link);++i)p[i]=0;
 receiver.reset();
 loaded_session=0;
#ifdef MPP_LISTENING
#ifdef MPP_OUTPUT_BUFFER
 mpp_buffer_set(8);
#else
 mpp_listen_reset();
#endif
#endif
#ifdef MPP_FAST_BYPASS
 for(auto& hold:mpp_bypass_hold)hold=0;
#endif
 for(auto& f:mpp_link_output)f=0;
 mpp_link.magic=0x4e4c4b31;mpp_link.schema=1;
 // No model runs before foreground startup. With MPP_PRESET_BANK, the bank
 // service later validates and recalls its saved capture; legacy builds stay empty.
 barrier();mpp_link.ready=1;mpp_hybrid_ready=1;
}
extern "C" void mpp_stock_amp_process(const float* left,const float* right,float* l,float* r){
 const uint32_t preset=rd(0x20005ad0);
 if(preset<0x20000000||preset>0x2003ff80){++mpp_link.faults;mpp_link.running=0;return;}
 if(
#ifdef MPP_LISTENING
 mpp_listen_warm||
#endif
 (*(volatile uint8_t*)(uintptr_t)(preset+3)&0x40)){
#ifdef MPP_PRIME_STATE
  model.prime_working_set();
#endif
  for(unsigned i=0;i<8;++i){float a=left[i],b=right[i];l[i]=a;r[i]=b;}return;
 }
#ifdef MPP_USB_NAM_CONTROLS
 model.process(mpp_nam_input(left),l,8);mpp_nam_output(left,right,l,r);
#else
 model.process(left,l,8);
 for(unsigned i=0;i<8;++i)r[i]=l[i];
#endif
}
extern "C" void mpp_probe_audio(const int32_t* rx,int32_t* tx){
 const uint32_t r=(uint32_t)(uintptr_t)rx,t=(uint32_t)(uintptr_t)tx;
 if(!((r==0x20016800&&t==0x20016900)||(r==0x20016880&&t==0x20016980))){
#ifdef MPP_LISTENING
  mpp_listen_reset();
#endif
  ++mpp_link.faults;mpp_link.running=0;return;
 }
 ((void(*)(void))0x15639)();
#ifdef MPP_TUNER
 mpp_tuner_feed(rx);
#endif
#ifndef MPP_DMA_DEADLINE_PROTOTYPE
 for(unsigned i=0;i<32;++i)tx[i]=0;
#endif
 #ifdef MPP_USB_NAM_CONTROLS
 mpp_usb_begin(mpp_link.ready&&mpp_link.running);
 #endif
 ++mpp_link.callbacks;
 barrier();
 if(!mpp_link.ready||!mpp_link.running){
#ifdef MPP_DMA_DEADLINE_PROTOTYPE
  mpp_dma_prefill(tx,0);
#endif
  return;
 }
 if(rd(0x400ec000)!=0x46||rd(0x400ec004)!=23||rd(0x400ec00c)!=1||
    rd(0x400ec010)!=100000||rd(0x2000e48c)!=24000000){
#ifdef MPP_LISTENING
  mpp_listen_reset();
#endif
  ++mpp_link.faults;mpp_link.running=0;
#ifdef MPP_DMA_DEADLINE_PROTOTYPE
  mpp_dma_prefill(tx,0);
#endif
  return;
 }
 ((void(*)(void))0x11663)();
#ifdef MPP_LISTENING
 mpp_listen_prepare();
#ifdef MPP_DMA_DEADLINE_PROTOTYPE
 mpp_dma_prefill(tx,mpp_listen_enabled&&!mpp_listen_warm);
#endif
#if defined(MPP_EARLY_OUTPUT) && !defined(MPP_DMA_CURRENT_PROTOTYPE)
 // Match stock's one-block output pipeline: its packer runs at 0x14c2e,
 // before the next chain invocation at 0x14d5c. Publish the previous protected
 // result before NAM can delay the TX refill. Mute/settling gates it here;
 // a fault below still clears this DMA half and disarms further output.
 mpp_listen_render(mpp_link_output,chain_right,tx);
#ifdef MPP_DRIVER_TIMING
 mpp_driver_capture(1,(uint32_t)(uintptr_t)tx);
#endif
#endif
#endif
 float x[8];for(unsigned i=0;i<8;++i)x[i]=(float)rx[i*4+3]*0x1p-31f;
 // Use the unmodified stock mono-input/master-volume wrapper and dispatcher.
 // The replacement AMP entry supplies NAM at its current movable chain slot.
 ((void(*)(const float*,float*,float*))0xe935)(x,mpp_link_output,chain_right);
#ifdef MPP_USB_NAM_CONTROLS
 mpp_usb_finish(mpp_link_output,chain_right);
#endif
#ifdef MPP_LISTENING
 // Preserve the stock global headphone-volume/mute smoothing before bounding.
 ((void(*)(float*,float*,float*,float*))0xe881)(
   mpp_link_output,chain_right,mpp_link_output,chain_right);
#endif
#ifdef MPP_IRQ_TIMING
 mpp_output_protect(mpp_link_output,chain_right);
#else
 for(float y:mpp_link_output)if(!__builtin_isfinite(y)){
  ++mpp_link.faults;mpp_link.running=0;
 }
#endif
 uint32_t bits;__builtin_memcpy(&bits,mpp_link_output+7,4);
 mpp_link.last_output_bits=bits;++mpp_link.runs;
#if defined(MPP_LISTENING) && !defined(MPP_EARLY_OUTPUT) && !defined(MPP_DMA_CURRENT_PROTOTYPE)
 if(mpp_link.running)mpp_listen_render(mpp_link_output,chain_right,tx);
#endif
 ((float(*)(void))0x11671)();
 const uint32_t ticks=rd(0x2000e490);
 if(ticks>mpp_link.timer_max)mpp_link.timer_max=ticks;
 if(!ticks||ticks>=150||rd(0x400ec000)!=0x46){
  ++mpp_link.faults;mpp_link.running=0;
 }
#if defined(MPP_DMA_CURRENT_PROTOTYPE) && !defined(MPP_DMA_DEADLINE_PROTOTYPE)
 // Offline experiment only. The image builder separately changes TX's FIFO
 // watermark to eight. Existing GPT guards do NOT establish DMA ownership:
 // late publication can still race a fetch. No updater may package this ID.
 if(mpp_link.running){
  mpp_listen_render(mpp_link_output,chain_right,tx);
  __asm__ volatile("dsb":::"memory");
  mpp_driver_capture(1,(uint32_t)(uintptr_t)tx);
 }
#endif
#ifdef MPP_DMA_DEADLINE_PROTOTYPE
 // Render once into private staging. Never clear or render directly into a
 // half that DMA may already be fetching. Late blocks keep the early fallback.
 for(unsigned i=0;i<32;++i)mpp_dma_pcm[i]=0;
 if(mpp_link.running)mpp_listen_render(mpp_link_output,chain_right,mpp_dma_pcm);
 mpp_dma_finish(tx,mpp_link.running);
#endif
#ifdef MPP_LISTENING
 // Disarm after a processing fault. In the guarded experiment an already
 // queued fallback cannot be recalled; the next safe prefill writes silence.
 if(!mpp_link.running){
  mpp_listen_reset();
#ifndef MPP_DMA_DEADLINE_PROTOTYPE
  for(unsigned i=0;i<32;++i)tx[i]=0;
#endif
 }
#endif
}
extern "C" BANK_TEXT void mpp_probe_version(const uint8_t* p,unsigned n,unsigned channel){
#ifdef MPP_STOCK_V3
 // The V3 receive-ring assembler includes F7 in its reported length.
 if(n==5&&p[4]==0xf7)--n;
#endif
 if(n!=4||channel>1||p[0]!=0xf0||p[1]!=0x43||p[2]!=0x58||p[3]||p[4]!=0xf7)return;
 uint8_t out[45]={0xf0,0x43,0x58,0x10};
#ifdef MPP_OUTPUT_BUFFER
 static const uint8_t product[8] __attribute__((section(".retired_audio.constants")))={'P','L','U','G','P','R','O',0};
#else
 const uint8_t product[8]={'P','L','U','G','P','R','O',0};
#endif
 for(unsigned i=0;i<8;++i){out[4+i]=mpp_probe_identity[i];out[36+i]=product[i];}
 out[28]=0x10;out[44]=0xf7;
 ((void(*)(const uint8_t*,unsigned,unsigned))0xae81)(out,45,channel);
}
extern "C" BANK_TEXT void mpp_probe_query(const uint8_t* p,unsigned n,unsigned channel){
#ifdef MPP_STOCK_V3
 if(n>=10&&n<=330&&p[n-1]==0xf7)--n;
#endif
 if(n<9||n>329||channel>1||p[0]!=0xf0||p[1]!=0x43||p[2]!=0x58||
    p[3]!=0x70||p[4]!=4||p[5]!=2||p[6]!='N'||p[n]!=0xf7)return;
#ifdef MPP_FX_BLOCKS
#ifdef MPP_USB_NAM_CONTROLS
 if(p[7]=='G'||p[7]=='V'){mpp_nam_query(p,n,channel);return;}
#endif
 if(p[7]=='R'){mpp_reply_query(p,n,channel);return;}
 if(p[7]=='F'){mpp_fx_query(p,n,channel);return;}
#endif
#ifdef MPP_TUNER
 if(p[7]=='U'){mpp_tuner_query(p,n,channel);return;}
#endif
#ifdef MPP_EFFECT_PROFILER
 if(p[7]=='T'&&n==9){
  if(!(rd(0xe000ed04)&511))mpp_profile_control(p[8]);
  return;
 }
#endif
#ifdef MPP_PRESET_BANK
 if(p[7]=='S'&&p[8]==1){mpp_bank_query(p,n,channel);return;}
#endif
#ifdef MPP_LISTENING
 // Explicit volatile listen arm. Query page 23 acknowledges the resulting
 // state. Restart, any model transfer, and fault return to muted.
#ifdef MPP_OUTPUT_BUFFER
 if(n==9&&(p[7]=='A'||p[7]=='B')){
  if(rd(0xe000ed04)&511)return;
  if(p[7]=='B'){
#ifdef MPP_GLOBAL_BUFFER
   mpp_global_buffer_set(p[8]);
#else
   mpp_buffer_set(p[8]);
#endif
   return;}

  if(p[8]>1)return;
#else
 if(p[7]=='A'&&n==9&&p[8]<2){
  if(rd(0xe000ed04)&511)return;
#endif
  mpp_listen_reset();
  barrier();
  if(p[8]&&mpp_link.ready&&mpp_link.running&&!mpp_link.faults)
   mpp_listen_enabled=1;
  return;
 }
#endif
#ifdef MPP_DRIVER_TIMING
 if(p[7]=='D'&&n==9){mpp_driver_control(p[8]);return;}
#endif
 if(p[7]=='P'&&n==9&&p[8]<128){
  const unsigned page=p[8];uint32_t value=page<12?rd((uint32_t)(uintptr_t)&mpp_link+4*page):0;
  unsigned error=page>=12;
#ifdef MPP_IRQ_TIMING
  if(page>=12)error=mpp_irq_page(page,&value);
#endif
#ifdef MPP_EFFECT_PROFILER
  if(page>=26)error=mpp_profile_page(page,&value);
#endif
#ifdef MPP_DRIVER_TIMING
  if(page>=118)error=mpp_driver_page(page,&value);
#endif
#ifdef MPP_ADC_SHORT_DELAY
  if(page==117){value=mpp_codec_filter_page();error=0;}
#endif
#ifdef MPP_LISTENING
  if(page==23){value=mpp_listen_page();error=0;}
#endif
#ifdef MPP_OUTPUT_BUFFER
  if(page==24){value=mpp_buffer_page();error=0;}
#ifdef MPP_PRESET_BANK
  if(page==25){value=mpp_bank_page();error=0;}
#endif
#endif
  uint8_t out[8]={1,(uint8_t)page,(uint8_t)error,0,0,0,0,0};
  for(unsigned i=0;i<5;++i)out[3+i]=(value>>(7*i))&127;
  ((void(*)(unsigned,unsigned,const uint8_t*,unsigned,unsigned))0xa18b)(4,2,out,8,channel);
  return;
 }
 if(p[7]!='L'||p[8]!=1||!mpp_link.ready)return;
 // This bridge may only change the engine from thread mode. A foreground
 // handler cannot overlap an in-flight ISR on this single core; subsequent
 // audio interrupts observe running=0 while validation/loading takes place.
 if(rd(0xe000ed04)&511){++mpp_link.context_rejections;return;}
 unsigned size=mpp::link::unpack7(p+9,n-9,packet,sizeof(packet)),out_n=0;
 if(!size)return;
 const uint32_t previous=mpp_link.running;
 mpp_link.running=0;barrier();
#ifdef MPP_LISTENING
 mpp_listen_reset();
#endif
 bool ok=receiver.exchange(packet,size,response,sizeof(response),out_n);
 uint32_t run=previous;
 uint32_t session;__builtin_memcpy(&session,packet+8,4);
 if(ok&&packet[5]==4&&response[24]==0&&session!=loaded_session){
  run=receiver.load_active(model,true,load_scratch,1871);
  if(run){mpp_link.model_crc=receiver.active_crc();++mpp_link.generation;loaded_session=session;}
  else ++mpp_link.faults;
 }
 // Do not restore a previous running flag over a fault latched by an ISR.
 if(mpp_link.faults)run=0;
#ifdef MPP_PRIME_STATE
 // Slot checksums scan separate RAM. Prepare the active model only after
 // every receiver/status operation, just before publishing a running engine.
 if(run)model.prime_working_set();
#endif
 barrier();mpp_link.running=run;
 if(!ok)return;
 // The stock command-4 builder has a fixed 15-byte buffer. Use the same
 // bounded transmitter as identity replies, with our own complete frame.
#ifdef MPP_OUTPUT_BUFFER
 static const uint8_t prefix[9] __attribute__((section(".retired_audio.constants")))={0xf0,0x43,0x58,0x70,4,2,'N','L',1};
#else
 const uint8_t prefix[9]={0xf0,0x43,0x58,0x70,4,2,'N','L',1};
#endif
 for(unsigned i=0;i<9;++i)wire[i]=prefix[i];
 unsigned encoded=mpp::link::pack7(response,out_n,wire+9,sizeof(wire)-10);
 if(encoded){
  wire[9+encoded]=0xf7;
  ((void(*)(const uint8_t*,unsigned,unsigned))0xae81)(wire,encoded+10,channel);
 }
}
extern "C"
#ifdef MPP_LISTENING
__attribute__((section(".retired_audio"),noinline))
#endif
void __aeabi_memclr4(void* dst,unsigned n){
 volatile uint8_t* p=(volatile uint8_t*)dst;while(n--)*p++=0;
}
static_assert(sizeof(LinkStatus)==48);

#ifdef MPP_PRESET_BANK
extern "C" BANK_TEXT const uint8_t* mpp_bank_model(){return receiver.active_slot();}
extern "C" BANK_TEXT void mpp_bank_pause(){
 mpp_link.running=0;barrier();mpp_listen_reset();
 volatile uint32_t* dma=(volatile uint32_t*)0x20016900;
 for(unsigned i=0;i<64;++i)dma[i]=0;
}
extern "C" BANK_TEXT void mpp_bank_clear(){
 receiver.reset();loaded_session=0;mpp_link.model_crc=0;mpp_link.running=0;
}
extern "C" BANK_TEXT void mpp_bank_resume(bool listen){
 bool run=receiver.has_model()&&!mpp_link.faults;
 if(run)model.prime_working_set();
 barrier();mpp_link.running=run;
 if(run&&listen)mpp_listen_enabled=1;
}
extern "C" BANK_TEXT bool mpp_bank_load(const uint8_t* slot){
 if(!receiver.restore_slot(slot)||!receiver.load_active(model,true,load_scratch,1871))return false;
 loaded_session=0;mpp_link.model_crc=receiver.active_crc();++mpp_link.generation;return true;
}
// This hook also runs during stock initialization, BEFORE copied bank code is
// ready. Retain the original three RAM copies and only queue NAM recall once
// initialization has published mpp_hybrid_ready.
extern "C" void mpp_stock_preset_select(unsigned slot){
 if(slot>=7)return;
 if(mpp_hybrid_ready){mpp_bank_request(slot);
#ifdef MPP_RESPONSIVE_CONTROLS
  return; // Never replace live settings with stock defaults while a recall is pending.
#endif
 }
 const uint8_t* from=(const uint8_t*)(uintptr_t)(0x2000920c+128*slot);
 const uint32_t destinations[]={0x20005af0,0x20005b70,0x20012230};
 for(uint32_t dst:destinations){auto* p=(uint8_t*)(uintptr_t)dst;for(unsigned i=0;i<128;++i)p[i]=from[i];}
}
#endif
