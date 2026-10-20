#pragma once
// Portable, mono, fixed-storage experimental DSP. No device or USB code.
namespace mpp {
constexpr unsigned sample_rate=48000, max_block=128, max_stages=12;
enum class Kind { gain, drive, distortion, nam, tremolo, chorus, pitch, delay, reverb };
struct Stage { Kind kind; float a, b, c; bool enabled=true; };
using ModelProcess = void (*)(void*, const float*, float*, unsigned);
// Compiled-in extensions own their context. Register only while no chain is
// configured, and configure/process only under the caller's stopped-DSP lock.
struct EffectExtension {
  unsigned id; // 64..127, one stateful instance per registered ID
  float minimum[3], maximum[3];
  void (*process)(void*, const Stage&, const float*, float*, unsigned);
  void (*reset)(void*);
  void* context;
};
class Chain {
public:
  bool register_effect(const EffectExtension&);
  bool configure(const Stage*, unsigned);
  void reset();
  void model(ModelProcess fn, void* context) { model_=fn; context_=context; }
  bool process(const float*, float*, unsigned);
  unsigned rejected_samples() const { return rejected_; }
private:
  Stage stages_[max_stages]{}; unsigned count_=0;
  ModelProcess model_=nullptr; void* context_=nullptr;
  float scratch_[2][max_block]{};
  float delay_[48000]{}, chorus_[2048]{}, pitch_[4096]{}, comb_[4][1800]{};
  unsigned delay_pos_=0, chorus_pos_=0, pitch_pos_=0, comb_pos_[4]{}, rejected_=0;
  float trem_phase_=0, chorus_phase_=0, pitch_phase_=0;
  EffectExtension extensions_[4]{}; unsigned extension_count_=0;
  const EffectExtension* extension(unsigned) const;
};
// Restricted native NAM subset: one mono LSTM layer, hidden size 1..16.
class Lstm {
public:
  bool load(unsigned hidden, const float* weights, unsigned count);
  void reset();
  void process(const float*, float*, unsigned);
  static void callback(void* ctx, const float* in, float* out, unsigned n) {
    static_cast<Lstm*>(ctx)->process(in,out,n);
  }
private:
  unsigned h_=0; float weights_[1201]{}, hidden_[16]{}, cell_[16]{};
};
}
