// Offline stock-dispatcher experiment. No physical placement is established.
#include "mpp/engine.hpp"
#include "model_weights.hpp"
namespace { mpp::Lstm model; }
extern "C" {
unsigned mpp_hybrid_enabled = 0;
unsigned mpp_hybrid_ready = 0;
unsigned mpp_hybrid_faults = 0;
void mpp_hybrid_reset() {
  mpp_hybrid_ready = model.load(embedded_model::hidden,
                              embedded_model::weights, embedded_model::count);
  mpp_hybrid_faults = 0;
}
// Stock V1.5.6 stage ABI inferred from 0x122d0 and 0x5578: four float planes,
// always eight frames. Mono NAM consumes left and duplicates to both outputs.
// Both input planes are copied first, allowing in-place and crossed aliasing.
void mpp_hybrid_amp(const float* left, const float* right,
                    float* out_left, float* out_right) {
  float l[8], r[8], y[8];
  bool bad = false;
  for (unsigned i=0;i<8;++i) {
    l[i] = left[i]; r[i] = right[i];
    if (!__builtin_isfinite(l[i]) || !__builtin_isfinite(r[i])) bad = true;
  }
  if (bad) {
    ++mpp_hybrid_faults; model.reset();
    for (unsigned i=0;i<8;++i) out_left[i]=out_right[i]=0;
    return;
  }
  if (!mpp_hybrid_enabled || !mpp_hybrid_ready) {
    for (unsigned i=0;i<8;++i) {out_left[i]=l[i];out_right[i]=r[i];}
    return;
  }
  model.process(l,y,8);
  for (auto x:y) if (!__builtin_isfinite(x)) bad=true;
  if (bad) {++mpp_hybrid_faults;model.reset();}
  for (unsigned i=0;i<8;++i) out_left[i]=out_right[i]=bad ? 0 : y[i];
}
}
