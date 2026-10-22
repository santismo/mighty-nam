// Exact V1.5.6 USB PCM rings, class controls and gain routines retained in stock.
// No descriptor, endpoint, clock or DMA scheduling changes.
#include "nam_controls.hpp"
#include "listening.hpp"
extern "C" void mpp_usb_begin(bool running){
 // Audio IRQ can precede USB class initialization during cold boot.
 if(*(volatile uint32_t*)0x2000b01c!=0x2000dac8){
  for(unsigned i=0;i<16;++i){((float*)0x20015a10)[i]=0;((float*)0x20015b10)[i]=0;}return;
 }
 if(!running||!mpp_listen_enabled||mpp_listen_warm)
  for(unsigned i=0;i<16;++i)((float*)0x20015a10)[i]=0;
 ((void(*)())0x1488d)(); // Record gain/limiter on previous completed stereo block.
 ((void(*)())0xcced)();  // Consume host playback, publish record PCM to USB rings.
 ((void(*)())0x14915)(); // Stock USB playback gain/limiter.
}
extern "C" void mpp_usb_finish(float* l,float* r){
 auto* record=(float*)0x20015a10;const auto* play=(const float*)0x20015b10;
 for(unsigned i=0;i<8;++i){
  float a=l[i]*.625f,b=r[i]*.625f;
  // Recording is pre-headphone volume and excludes host return (no loopback).
  record[i]=__builtin_isfinite(a)?(a>.875f?.875f:a<-.875f?-.875f:a):0;
  record[8+i]=__builtin_isfinite(b)?(b>.875f?.875f:b<-.875f?-.875f:b):0;
  l[i]+=play[i]*1.6f;r[i]+=play[8+i]*1.6f;
 }
}
