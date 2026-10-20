// Offline C bridge. Official Core uses the generic Eigen path (no A2 fast define).
#include "NAM/get_dsp.h"
#include "NAM/model_config.h"
#include "NAM/wavenet/model.h"
#include "a2_lite.hpp"
#include <fstream>
#include <cstdio>
class ZeroStateReference: public nam::wavenet::WaveNet {
public: using WaveNet::WaveNet; using WaveNet::SetMaxBufferSize;
};
extern "C" {
void* a2_ref_create(const char* path){try{
 std::ifstream f(path); nlohmann::json j;f>>j;
 nam::verify_config_version(j.at("version"));
 auto c=nam::wavenet::parse_config_json(j.at("config"),48000.);
 auto m=std::make_unique<ZeroStateReference>(c.in_channels,c.layer_array_params,c.head_scale,c.with_head,c.head_params,j.at("weights").get<std::vector<float>>(),std::move(c.condition_dsp),48000.);
 // Fresh model and buffer allocation, no implicit prewarming. Both engines
 // start with identical zero history, then consume identical test input.
 m->SetMaxBufferSize(1024);return m.release();
 }catch(const std::exception& e){std::fprintf(stderr,"Reference: %s\n",e.what());return nullptr;}}
void a2_ref_process(void* p,float* x,float* y,unsigned n){static_cast<nam::DSP*>(p)->process(&x,&y,n);}
void a2_ref_destroy(void* p){delete static_cast<nam::DSP*>(p);}
void* a2_small_create(const float* w,unsigned n){auto* m=new mpp::A2Lite;if(!m->load(w,n)){delete m;return nullptr;}return m;}
void a2_small_process(void* p,float* x,float* y,unsigned n){static_cast<mpp::A2Lite*>(p)->process(x,y,n);}
void a2_small_reset(void* p){static_cast<mpp::A2Lite*>(p)->reset();}
void a2_small_destroy(void* p){delete static_cast<mpp::A2Lite*>(p);}
unsigned a2_small_size(){return sizeof(mpp::A2Lite);}
}
