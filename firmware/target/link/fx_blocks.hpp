#pragma once
#include <stdint.h>
namespace mpp::fx {
constexpr unsigned config_bytes=32, delay_size=2048;
// Each independent slot: mode, enabled, absolute position in 11-block chain,
// semitones+12, mix, rate, depth, feedback, sensitivity, resonance; six zeros.
bool valid(const uint8_t*);
void defaults(uint8_t*);
struct Engine {
 float delay[2][delay_size], allpass[2][4], feedback[2];
#ifdef MPP_PITCH_QUALITY_PROTOTYPE
 // Five one-sample lag refinements reuse the ring; no extra audio buffer.
 float fine_difference[5];unsigned fine_center,fine_count,fine_anchor,filter_active;
#endif
 float phase, pitch_phase, envelope, wet, ratio;
 float pitch_window,target_window,yin_sum,yin_previous,yin_before;unsigned yin_lag;
 unsigned write, filled, previous_mode, previous_position, previous_enabled;
 void reset();
 void process(const uint8_t*,float*,float*,unsigned);
};
}
extern "C" {
void mpp_fx_init();
void mpp_fx_get(uint8_t*);
bool mpp_fx_set(const uint8_t*);
void mpp_fx_before(unsigned,float*,float*);
void mpp_fx_query(const uint8_t*,unsigned,unsigned);
void mpp_fx_saved(unsigned,uint8_t*);
}
