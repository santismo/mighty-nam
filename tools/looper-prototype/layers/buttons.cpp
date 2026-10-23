// MIT (c) 2026 santismo. Exact V3.0.5 runtime adapter; offline verification first.
// The stock bootloader/boot-button path is not patched. Stock volume buttons
// and POWER hold shutdown continue through the original dispatcher.
#include <stdint.h>
#include "../hardware/diagnostics.hpp"
extern "C" {
struct LinkStatus { uint32_t magic,schema,ready,callbacks,faults,model_crc,
    generation,runs,timer_max,running,context_rejections,last_output_bits; };
extern volatile LinkStatus mpp_link;
unsigned mpp_loop_control_tick(unsigned,unsigned);
bool mpp_loop_led_visible(unsigned);
}
namespace {
volatile uint32_t inputs,selection;
bool sampled;
uint32_t last_callbacks,sub_ms,milliseconds;
unsigned lock(){unsigned v;__asm__ volatile("mrs %0,primask\ncpsid i":"=r"(v)::"memory");return v;}
void unlock(unsigned v){__asm__ volatile("dsb\nisb\nmsr primask,%0"::"r"(v):"memory");}
}
extern "C" {
// Original prefix through 0xa066, followed by the untouched stock body. The
// wrapper performs the original 0x9f06 scan exactly once before consuming taps.
__attribute__((naked)) void mpp_loop_button_tail(){
 __asm__ volatile("push {r4,r5,r6,lr}\nldr r4,=0x20014968\nldr r5,=0x20005c80\nldr pc,=0x0000a069");
}
void mpp_loop_buttons(){
 ((void(*)())0x9f07)();
 auto* settings=*reinterpret_cast<volatile uint8_t**>(0x20014970);
 auto* bank=*reinterpret_cast<volatile uint8_t**>(0x20014978);
 auto* keys=reinterpret_cast<volatile uint8_t*>(0x20005c80);
 if(mpp_loop_allowed() && settings[0x5f]!=1) {
  // Bytes 0/3 are the stock debounced active-low PRESET/POWER states. The
  // foreground scanner captures levels; audio IRQ owns gesture and loop state.
  unsigned mask=lock(),target=selection;selection=0;
  if(target && target<=7 && (bank[0x13]&(1u<<(target-1))))settings[2]=target-1;
  inputs=(keys[0]?1u:0u)|(keys[3]?2u:0u)|(unsigned(settings[2])<<8)|(unsigned(bank[0x13])<<16);
  sampled=true;keys[8]=0;keys[11]=0;unlock(mask);
  if(target && target<=7 && settings[2]==target-1) {
   ((void(*)(unsigned))0x6a39)(target-1);
   ((void(*)(unsigned,unsigned))0x99c7)(target-1,0);
   ((void(*)(unsigned,unsigned))0x99c7)(target-1,1);
  }
 }
 mpp_loop_button_tail();
}
void mpp_loop_buttons_tick(){
 unsigned callbacks=mpp_link.callbacks,delta=callbacks-last_callbacks;last_callbacks=callbacks;
 // Six fixed eight-frame callbacks per millisecond at the unchanged 48 kHz.
 // Accumulate deltas to preserve button timing when the callback word wraps.
 if(delta<60000){sub_ms+=delta;milliseconds+=sub_ms/6;sub_ms%=6;}
 if(!sampled || selection)return;
 unsigned target=mpp_loop_control_tick(milliseconds,inputs);
 if(target)selection=target;
}
__attribute__((naked)) void mpp_loop_color_tail(unsigned){
 __asm__ volatile("subs r0,r0,#1\ncmp r0,#5\npush {r4}\nbls 1f\nldr pc,=0x0000617f\n1: ldr pc,=0x000060f5");
}
void mpp_loop_color(unsigned color){
 if(mpp_loop_led_visible(milliseconds))mpp_loop_color_tail(color);
 else *reinterpret_cast<volatile uint32_t*>(0x40c60088)=0x02404000u;
}
}
