#include "audio_module.hpp"
#include "model_weights.hpp"
#include "mpp/engine.hpp"
namespace {
mpp::Chain chain;
mpp::Lstm model;
bool ready=false;
}
extern "C" bool mpp_audio_initialize() {
  ready=false;
  if(!model.load(embedded_model::hidden,embedded_model::weights,embedded_model::count)) return false;
  const mpp::Stage stages[]={{mpp::Kind::gain,0.8f,0,0},{mpp::Kind::nam,0,0,0},
      {mpp::Kind::delay,250,0.3f,0.15f},{mpp::Kind::reverb,0.65f,0.15f,0},{mpp::Kind::gain,0.5f,0,0}};
  if(!chain.configure(stages,5)) return false;
  chain.model(mpp::Lstm::callback,&model);
  float zero[128]{},scratch[128];for(unsigned i=0;i<188;++i) model.process(zero,scratch,128);
  ready=true;return true;
}
extern "C" bool mpp_audio_process(const float* input,float* output,unsigned frames) {
  return ready && chain.process(input,output,frames);
}
