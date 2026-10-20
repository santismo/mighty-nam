#pragma once
#include "rt1176_backend.hpp"
namespace mpp::hardware {
enum class ClockCheck : uint32_t {
 Derived=0, BusError, UnstableSnapshot, RootInactive, UnsupportedSource,
 PllUnready, ReferenceUnknown, InvalidReference, InvalidDivider, NonintegralRate
};
struct ClockReport {
 ClockCheck result;
 uint32_t root_control,root_status0,root_status1,arm_pll;
 uint32_t reference_hz,derived_hz;
};
// Read-only M7 ARM-PLL path. Caller must independently establish reference_hz.
// A derived rate is not a physical frequency measurement or a clock setup.
ClockCheck inspect_startup_clock(RegisterBus,uint32_t reference_hz,ClockReport&);
}
