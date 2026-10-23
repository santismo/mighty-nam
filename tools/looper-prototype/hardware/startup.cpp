// Copied into a bounded retired AMP code gap. Runs after baseline AMP init,
// before stock SAI/DMA setup. No constructor or loop-RAM dependency here.
#include <stdint.h>
extern "C" {
extern uint32_t __loop_code_start[],__loop_code_end[],__loop_code_load[];
void mpp_base_init();void mpp_loop_boot();
__attribute__((section(".loop_startup"))) void mpp_loop_startup(){
 mpp_base_init();
 for(unsigned i=0;__loop_code_start+i<__loop_code_end;++i)__loop_code_start[i]=__loop_code_load[i];
 __asm__ volatile("dsb":::"memory");
 for(uintptr_t p=(uintptr_t)__loop_code_start&~31u;p<(uintptr_t)__loop_code_end;p+=32)
  *(volatile uint32_t*)0xe000ef68=p; // DCCMVAC: clean copied code to PoC
 __asm__ volatile("dsb":::"memory");
 *(volatile uint32_t*)0xe000ef50=0; // ICIALLU after code clean
 __asm__ volatile("dsb\nisb":::"memory");
 mpp_loop_boot();
}
}
