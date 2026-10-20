#pragma once
#include <stdint.h>

namespace mpp::link {
// Seven data bytes per high-bit mask. Canonical encoding, bounded by the caller.
unsigned pack7(const uint8_t* in, unsigned n, uint8_t* out, unsigned capacity);
unsigned unpack7(const uint8_t* in, unsigned n, uint8_t* out, unsigned capacity);
}
