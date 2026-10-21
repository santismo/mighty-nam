#include <stdint.h>

// Executed from low app code before copied bank code is ready. Only the exact
// stock codec-startup write call is redirected here; no live register writer.
extern "C" {
volatile uint32_t mpp_codec_startup_seen;
#ifdef MPP_GLOBAL_BUFFER
__attribute__((section(".codec_startup")))
#endif
unsigned mpp_codec_startup_write(unsigned device,unsigned reg,uint8_t* data,unsigned size){
 if(device==0x20 && reg<21 && size==1 && (uintptr_t)data==0x20000284u+reg){
  if(reg==0){
   mpp_codec_startup_seen=0x434f4431;
   // Stock reads all 21 registers after its writes. Its read helper returns
   // zero even on NACK, so sentinel values expose failed reads instead.
   *(volatile uint8_t*)0x200002b8=0xff;
   *(volatile uint8_t*)0x200002c2=0xff;
  }
  if(reg==10 && mpp_codec_startup_seen==0x434f4431 && (*data==0 || *data==0x22))
   *data=0x22; // AD1SD / AD2SD; keep sharp roll-off and all other settings.
 }
 return ((unsigned(*)(unsigned,unsigned,uint8_t*,unsigned))0xda35)(device,reg,data,size);
}
__attribute__((section(".banktext"))) uint32_t mpp_codec_filter_page(){
 const uint32_t adc=*(volatile uint8_t*)0x200002b8,dac=*(volatile uint8_t*)0x200002c2;
 const uint32_t flags=(mpp_codec_startup_seen==0x434f4431?1:0)|
   (*(volatile uint8_t*)0x2000028e==0x22?2:0)|(adc==0x22?4:0)|(dac==0x0a?8:0);
 // Page 117: schema C1, observation flags, ADC readback, DAC readback.
 // Read-only cached startup observations, not a physical part-ID or live read.
 return 0xc1000000u|(flags<<16)|(adc<<8)|dac;
}
}
