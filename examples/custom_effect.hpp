#pragma once
#include "mpp/engine.hpp"
// Original example: compiled-in asymmetrical hard clipping. State/context can
// be supplied by another extension, but must outlive the Chain. Never allocate,
// lock, access files or wait in process(). Register before configuring a chain.
namespace nam_plug_example {
inline void asymmetry(void*,const mpp::Stage& s,const float* in,float* out,unsigned n){
 for(unsigned i=0;i<n;++i){float x=in[i]*s.a+s.b;out[i]=(x>1?1:x< -1?-1:x)-s.b;}
}
inline mpp::EffectExtension descriptor(){return {64,{1,-.5f,0},{20,.5f,0},asymmetry,nullptr,nullptr};}
// Register descriptor(), then use Kind(64) with a=drive, b=bias, c=0.
// The built-in UI catalog must also receive a matching definition before this
// effect can be edited there. No plug install or runtime timing is implied.
}
