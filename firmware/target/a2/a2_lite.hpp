#pragma once
// Fixed A2-Lite topology only. Model configuration must pass the host validator.
// No heap, JSON, I/O, transcendental functions or block-size-dependent state.
namespace mpp {
class A2Lite {
public:
 static constexpr unsigned weight_count=1871, layer_count=23, history_floats=19062;
 bool load(const float* weights,unsigned count);
 void reset();
 void process(const float* input,float* output,unsigned frames);
 void prime_working_set() const;
private:
 float weights_[weight_count]{};
 float history_[history_floats]{};
 float head_[48]{};
 unsigned pos_[layer_count]{},head_pos_=0,ready_=0;
};
}
