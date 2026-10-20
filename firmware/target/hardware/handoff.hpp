#pragma once
#include "rt1176_backend.hpp"
namespace mpp::hardware {
struct CoreState {uint32_t ipsr,control,primask;};
CoreState direct_core_state(); // ARM-only implementation; reads processor state.
struct HandoffSnapshot {uint32_t old_vtor,ccr,mpu_ctrl,itcm_ctrl,dtcm_ctrl,flexram_gpr17,root_m7,nvic_banks;};
// Only a stage-0 helper. Caller must already be privileged Thread mode with
// interrupts masked, valid MSP, initialized C storage, verified owned vector
// table/code/stack and callable backend. No proposed loader image is emitted.
bool prepare_core_handoff(RegisterBus,CoreState,uint32_t own_vector,HandoffSnapshot&);
}
