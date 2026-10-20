#include "../src/host.hpp"
#include <iostream>
#include "NAM/lstm.h"
#include "../target/audio_module.hpp"
#include <limits>
#include <random>
#include <memory>
using host::require;
namespace {
std::vector<float> run(mpp::Chain& c,const std::vector<float>& x,unsigned block) {
  std::vector<float> y(x.size());for(size_t i=0;i<x.size();i+=block) require(c.process(x.data()+i,y.data()+i,unsigned(std::min<size_t>(block,x.size()-i))),"process failed");return y;
}
float difference(const std::vector<float>& a,const std::vector<float>& b) {float e=0;for(size_t i=0;i<a.size();++i)e=std::max(e,std::abs(a[i]-b[i]));return e;}
void lstm_equivalence(const host::json& j) {
  host::validate_model(j);mpp::Lstm compact;auto ws=j.at("weights").get<std::vector<float>>();
  auto official=std::make_unique<nam::lstm::LSTM>(1,1,1,1,j.at("config").at("hidden_size"),ws,48000);
  require(compact.load(j.at("config").at("hidden_size"),ws.data(),unsigned(ws.size())),"compact load failed");
  // Construct reference directly to compare learned initial state before any prewarm.
  std::mt19937 random(7);std::uniform_real_distribution<float> dist(-0.4f,0.4f);
  float peak_error=0;float x[48],a[48],b[48];
  for(unsigned block=0;block<1000;++block) {
    for(auto& v:x)v=dist(random);host::callback(official.get(),x,a,48);compact.process(x,b,48);
    for(unsigned i=0;i<48;++i) {require(std::isfinite(a[i])&&std::isfinite(b[i]),"LSTM finite");peak_error=std::max(peak_error,std::abs(a[i]-b[i]));}
  }
  std::cout<<"LSTM H="<<j.at("config").at("hidden_size")<<" 48000-sample max error="<<peak_error<<'\n';
  require(peak_error<0.00001f,"compact LSTM differs from official NAM");
}
}
int main(int argc,char** argv) {
 try {
  require(argc==2,"models directory required");std::filesystem::path models=argv[1];nam::activations::Activation::disable_fast_tanh();
  float module_in[48]{},module_out[48];
  require(!mpp_audio_process(module_in,module_out,48),"uninitialized target module accepted");
  require(mpp_audio_initialize()&&mpp_audio_process(module_in,module_out,48),"target module init/process");
  for(float v:module_out) require(std::isfinite(v),"target module finite");
  auto c=std::make_unique<mpp::Chain>();mpp::Stage delay{mpp::Kind::delay,10,0.5,1};require(c->configure(&delay,1),"delay config");
  std::vector<float> impulse(2000);impulse[0]=1;auto y=run(*c,impulse,48);
  require(y[0]==0&&std::abs(y[480]-1)<1e-7&&std::abs(y[960]-0.5)<1e-7,"delay timing/feedback");
  c->reset();require(difference(y,run(*c,impulse,17))==0,"delay reset/block invariance");
  std::vector<mpp::Stage> stages={{mpp::Kind::drive,2,0.5,0},{mpp::Kind::distortion,3,0.2,0},{mpp::Kind::tremolo,3,0.5,0},{mpp::Kind::chorus,0.8,0.3,0},{mpp::Kind::pitch,7,0.5,0},{mpp::Kind::delay,80,0.5,0.3},{mpp::Kind::reverb,0.7,0.4,0}};
  std::vector<float> signal(48000);for(size_t i=0;i<signal.size();++i) signal[i]=0.2f*std::sin(float(i)*0.041f);
  require(c->configure(stages.data(),unsigned(stages.size())),"full chain config");auto whole=run(*c,signal,128);
  c->reset();auto split=run(*c,signal,17);require(difference(whole,split)==0,"all-effects block invariance");
  double energy=0;for(float x:whole){require(std::isfinite(x)&&std::abs(x)<4,"effect stability");energy+=double(x)*x;}require(energy>0.01,"effect output nonzero");
  mpp::Stage invalid{mpp::Kind::delay,0,1,0};require(!c->configure(&invalid,1),"unsafe delay accepted");
  mpp::Stage duplicates[2]={{mpp::Kind::pitch,0,0,0},{mpp::Kind::pitch,0,0,0}};require(!c->configure(duplicates,2),"duplicate state accepted");
  float one=1,out=0;require(!c->process(&one,&out,129),"oversize block accepted");
  require(c->configure(nullptr,0),"bypass config");float nan=std::numeric_limits<float>::quiet_NaN();require(c->process(&nan,&out,1)&&out==0&&c->rejected_samples()==1,"nonfinite handling");
  mpp::Stage missing{mpp::Kind::nam,0,0,0};require(c->configure(&missing,1)&&!c->process(&one,&out,1),"missing NAM accepted");
  // Pitch check: steady sinusoid should move approximately one octave upward.
  mpp::Stage pitch{mpp::Kind::pitch,12,1,0};require(c->configure(&pitch,1),"pitch config");
  for(size_t i=0;i<signal.size();++i) signal[i]=0.2f*std::sin(float(i)*6.283185307f*220/48000);
  auto shifted=run(*c,signal,48);unsigned crossings=0;for(size_t i=12001;i<shifted.size();++i)if(shifted[i-1]<=0&&shifted[i]>0)++crossings;
  float hz=float(crossings)/0.75f;require(hz>420&&hz<460,"pitch frequency shift");std::cout<<"Experimental +12 pitch measured "<<hz<<" Hz from 220 Hz\n";
  auto fixture=host::read_json(models/"lstm.nam");lstm_equivalence(fixture);
  std::mt19937 gen(42);std::uniform_real_distribution<float> dist(-0.1f,0.1f);
  for(unsigned h:{1u,16u}) {auto j=fixture;j["config"]["hidden_size"]=h;std::vector<float> w(4*h*(h+1)+7*h+1);for(auto& v:w)v=dist(gen);j["weights"]=w;lstm_equivalence(j);}
  auto bad=fixture;bad["weights"].erase(bad["weights"].begin());bool rejected=false;try{host::validate_model(bad);}catch(...){rejected=true;}require(rejected,"truncated model accepted");
  bad=fixture;bad["version"]="0.7.0";rejected=false;try{host::validate_model(bad);}catch(...){rejected=true;}require(rejected,"unsupported version accepted");
  for(const char* filename:{"wavenet.nam","wavenet_a1_standard.nam"}) {
    auto j=host::read_json(models/filename);auto model=host::load_model(j,true);auto other=host::load_model(j,true);
    float x[48]{},a[48],b[48];x[0]=0.1f;host::callback(model.get(),x,a,48);
    host::callback(other.get(),x,b,17);host::callback(other.get(),x+17,b+17,31);
    float maxerr=0;for(int i=0;i<48;++i){require(std::isfinite(a[i]),"WaveNet finite");maxerr=std::max(maxerr,std::abs(a[i]-b[i]));}require(maxerr<1e-5,"WaveNet block invariance");
    std::cout<<filename<<" loaded, prewarmed, variable-block output verified\n";
  }
  std::cout<<"PASS: offline DSP, invalid input rejection, reference equivalence; no audio device or USB access\n";return 0;
 } catch(const std::exception& e){std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
