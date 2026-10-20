#pragma once
#include <stdint.h>
// Only NAMLNK07. Starts muted; never touches host audio or flash.
extern "C" {
extern volatile uint32_t mpp_listen_enabled, mpp_listen_warm;
void mpp_listen_reset();
void mpp_listen_prepare();
void mpp_listen_render(const float*,const float*,int32_t*);
uint32_t mpp_listen_page();
#ifdef MPP_OUTPUT_BUFFER
extern volatile uint32_t mpp_output_delay_blocks;
void mpp_buffer_set(unsigned samples);
uint32_t mpp_buffer_page();
#endif
}
