#pragma once
#include <stdint.h>
extern "C" {
extern int32_t mpp_dma_pcm[32];
void mpp_dma_prefill(int32_t* tx, unsigned playing);
void mpp_dma_finish(int32_t* tx, unsigned valid);
}
