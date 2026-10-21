#pragma once
#include <stdint.h>
extern "C" {
void mpp_driver_capture(unsigned phase,uint32_t tx);
void mpp_driver_control(unsigned action);
uint32_t mpp_driver_page(unsigned page,uint32_t* value);
}
