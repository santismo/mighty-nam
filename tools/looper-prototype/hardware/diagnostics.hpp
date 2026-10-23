// MIT (c) 2026 santismo. Opt-in looper RAM/timing trial.
#pragma once
#include <stdint.h>
extern "C" {
bool mpp_loop_allowed();
void mpp_loop_before_tick();
unsigned mpp_loop_apply(unsigned);
void mpp_loop_fail(unsigned,uintptr_t);
extern volatile uint32_t mpp_loop_diag[40];
}
