#ifndef MPP_TIMING_RECORDER_H
#define MPP_TIMING_RECORDER_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* OFFLINE DEVELOPMENT MODULE: no MMIO, device transport or installed hook.
 * Future backend prerequisites: independently calibrated reference clock;
 * DWT reset epoch tracking covering every reset writer; measured audio deadline;
 * hardware-derived release time/sequence (not an ISR invocation count).
 * One ISR writer. Read stats only with the writer stopped or a coherent snapshot.
 * Time spans must be less than half the 32-bit reference-counter range,
 * and measured cycle spans must be less than one full DWT-counter wrap.
 * The READY bit is a backend assertion, not something this module can establish.
 */
enum { MPP_TIMING_READY=1 };
enum {
 MPP_T_CONFIG=1, MPP_T_UNTRUSTED=2, MPP_T_RESET=4, MPP_T_CLOCK=8,
 MPP_T_SEQUENCE=16, MPP_T_SPAN=32, MPP_T_RATIO=64,
 MPP_T_DEADLINE=128, MPP_T_HEADROOM=256, MPP_T_COUNT_OVERFLOW=512
};
typedef struct {
 uint32_t cpu_hz, ref_hz, deadline_ticks, reserve_ticks;
 uint32_t max_span_ticks, cycle_tolerance;
} mpp_timing_config;
typedef struct {
 uint32_t cycle, ref, reset_epoch, clock_epoch, sequence, release_ref, flags;
} mpp_timing_stamp;
typedef struct {
 uint32_t samples, valid, rejected, flags, initialized;
 uint32_t last_sequence, last_reset_epoch, last_clock_epoch;
 uint32_t max_cycles, max_duration_ticks, max_response_ticks, max_entry_lateness_ticks;
 uint32_t deadline_misses, headroom_misses;
} mpp_timing_stats;
/* Zero-initialize stats at the start of each calibrated test run. No printing,
 * allocation, division, clock reconfiguration or DWT reset occurs here. */
uint32_t mpp_timing_observe(mpp_timing_stats*, const mpp_timing_config*,
                          const mpp_timing_stamp*, const mpp_timing_stamp*);
/* Run DSP first, then clear ALL 32 words of the completed 8-frame/4-slot buffer.
 * This helper alone does not prove hardware silence: DMA ownership, startup,
 * cache visibility, every output route and physical muting require integration. */
void mpp_timing_zero_tx32(volatile uint32_t*);
#ifdef __cplusplus
}
#endif
#endif
