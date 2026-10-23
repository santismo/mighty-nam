// MIT (c) 2026 santismo. Candidate device-address layout, OFFLINE ONLY.
// These are two fixed OCRAM windows, not FlexRAM/TCM or ECC aliases. Their
// ownership has bounded offline evidence; physical safety is NOT established.
#pragma once
#include <stdint.h>
namespace mighty_loop::layout {
constexpr uintptr_t first=0x202a0020, second=0x2031c020;
constexpr unsigned first_bytes=2048*132, second_bytes=765*132;
constexpr uintptr_t code=0x20314020, state=0x20318020;
static_assert(first+first_bytes<0x202e4000);
static_assert(second+second_bytes<0x20340000);
static_assert(first_bytes+second_bytes==371316);
}
