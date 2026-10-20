#pragma once
#include "engine.hpp"
#include <cstddef>
#include <cstdint>
namespace mpp {
// Transactional validation: a rejected program leaves the old chain intact.
// The caller must stop processing before configure_program; no flash or I/O.
bool configure_program(Chain&, const uint8_t*, std::size_t);
}
