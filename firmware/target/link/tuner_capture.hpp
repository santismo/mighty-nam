#pragma once
#include <stdint.h>
namespace mpp::tuner {
// Single audio-IRQ producer, foreground consumer. A completed capture is
// immutable until the next explicit start. It always stops at 2048 samples.
struct Capture {
 volatile unsigned enabled, count, generation;
 int16_t samples[2048];
 static void barrier(){__asm__ volatile("":::"memory");}
 void reset(){enabled=0;barrier();count=0;generation=0;}
 void stop(){enabled=0;barrier();count=0;}
 void start(){stop();++generation;barrier();enabled=1;}
 void feed(const int32_t* rx){
  if(!enabled)return;
  unsigned at=count;if(at>=2048)return;
  // 48 kHz -> 12 kHz boxcar decimation, before NAM or any stock effect.
  // Shift each input before summing so even full-scale input cannot overflow.
  for(unsigned j=0;j<2;++j){
   int32_t sum=0;for(unsigned i=0;i<4;++i)sum+=rx[(j*4+i)*4+3]>>16;
   samples[at+j]=(int16_t)(sum>>2);
  }
  barrier();count=at+2;
  if(at==2046)enabled=0;
 }
};
}
