// Exact MP3_OR_V3.0.5 input converter at e6b0 separates RX slots 0/1
// into the stereo pair passed to the Bluetooth EQ at 122bc. Slot 2 is
// headset-microphone input; slot 3 is guitar. Only the stereo pair belongs
// in backing-track playback. No NAM, preset gain, EQ or pitch is applied.
#include <stdint.h>
#ifndef MPP_STOCK_V3
#error Bluetooth audio routing requires the audited V3 stock layout
#endif
extern "C" {
float mpp_bluetooth_output[16];
__attribute__((section(".retired_audio"),noinline))
void mpp_bluetooth_capture(const int32_t* rx){
 // Stock headphone master at 653c has just advanced its smoother. Read its
 // completed gain without advancing it again or changing guitar samples.
 // Phone volume remains the source gain. This gain is independent of USB.
 const float gain=*(volatile float*)0x200006f8;
 for(unsigned i=0;i<8;++i){
  mpp_bluetooth_output[i]=(float)rx[4*i]*0x1p-31f*gain;
  mpp_bluetooth_output[8+i]=(float)rx[4*i+1]*0x1p-31f*gain;
 }
}
}
