#include "timing_recorder.h"
static void maximum(uint32_t* value, uint32_t x) { if (x > *value) *value=x; }
uint32_t mpp_timing_observe(mpp_timing_stats* s, const mpp_timing_config* c,
                          const mpp_timing_stamp* a, const mpp_timing_stamp* b) {
 uint32_t f=0;
 if (!c->cpu_hz || !c->ref_hz || !c->deadline_ticks ||
     c->reserve_ticks >= c->deadline_ticks ||
     c->max_span_ticks < c->deadline_ticks || c->max_span_ticks >= 0x80000000u)
   f |= MPP_T_CONFIG;
 if (!(a->flags & b->flags & MPP_TIMING_READY)) f |= MPP_T_UNTRUSTED;
 if (a->reset_epoch != b->reset_epoch ||
     (s->initialized && a->reset_epoch != s->last_reset_epoch)) f |= MPP_T_RESET;
 if (a->clock_epoch != b->clock_epoch ||
     (s->initialized && a->clock_epoch != s->last_clock_epoch)) f |= MPP_T_CLOCK;
 if (a->sequence != b->sequence || a->release_ref != b->release_ref ||
     (s->initialized && a->sequence != s->last_sequence+1u)) f |= MPP_T_SEQUENCE;
 const uint32_t cyc=b->cycle-a->cycle, dt=b->ref-a->ref;
 const uint32_t response=b->ref-a->release_ref, late=a->ref-a->release_ref;
 if (!cyc || !dt || dt > c->max_span_ticks || response > c->max_span_ticks ||
     late > c->max_span_ticks || response < dt || response < late) f |= MPP_T_SPAN;
 const uint64_t x=(uint64_t)cyc*c->ref_hz, y=(uint64_t)dt*c->cpu_hz;
 const uint64_t error=x>y ? x-y : y-x;
 if (error > (uint64_t)c->cycle_tolerance*c->ref_hz) f |= MPP_T_RATIO;
 s->initialized=1; s->last_sequence=b->sequence;
 s->last_reset_epoch=b->reset_epoch; s->last_clock_epoch=b->clock_epoch;
 if (s->samples==0xffffffffu) { s->flags |= f | MPP_T_COUNT_OVERFLOW; return f | MPP_T_COUNT_OVERFLOW; }
 ++s->samples;
 if (f) ++s->rejected;
 else {
   ++s->valid;
   maximum(&s->max_cycles,cyc); maximum(&s->max_duration_ticks,dt);
   maximum(&s->max_response_ticks,response); maximum(&s->max_entry_lateness_ticks,late);
   if (response >= c->deadline_ticks) { ++s->deadline_misses; f |= MPP_T_DEADLINE; }
   if (response >= c->deadline_ticks-c->reserve_ticks) { ++s->headroom_misses; f |= MPP_T_HEADROOM; }
 }
 s->flags |= f;
 return f;
}
void mpp_timing_zero_tx32(volatile uint32_t* p) {
 for (uint32_t i=0;i<32;++i) p[i]=0;
}
