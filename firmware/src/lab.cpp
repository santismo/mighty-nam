#include "host.hpp"
#include <chrono>
#include <cstring>
#include <iostream>
#include <cstdint>
using host::require;
namespace {
unsigned u16(const unsigned char* p) {return p[0]|(unsigned(p[1])<<8);}
unsigned u32(const unsigned char* p) {return u16(p)|(u16(p+2)<<16);}
void word(std::ofstream& f,unsigned x,unsigned bytes) { for(unsigned i=0;i<bytes;++i) f.put(char(x>>(8*i))); }
std::vector<float> read_wav(const std::string& path) {
  std::ifstream f(path,std::ios::binary|std::ios::ate); require(bool(f),"Cannot open input WAV");
  auto size=f.tellg(); require(size>=44 && size<=48000*4*600,"Input must be <= 10 minutes mono WAV");
  std::vector<unsigned char> b(static_cast<size_t>(size)); f.seekg(0); f.read(reinterpret_cast<char*>(b.data()),size);
  require(!memcmp(b.data(),"RIFF",4)&&!memcmp(b.data()+8,"WAVE",4),"Expected RIFF WAV");
  require(u32(b.data()+4)==b.size()-8,"Invalid RIFF size");
  unsigned format=0,bits=0,align=0; size_t data=0,nbytes=0;
  for(size_t pos=12;pos+8<=b.size();) {
    unsigned len=u32(b.data()+pos+4); size_t start=pos+8;
    require(len<=b.size()-start,"Truncated WAV chunk");
    if(!memcmp(b.data()+pos,"fmt ",4)) {
      require(len>=16 && !format,"Invalid fmt chunk"); format=u16(b.data()+start);
      require(u16(b.data()+start+2)==1 && u32(b.data()+start+4)==48000,"WAV must be mono 48000 Hz; no resampling is performed");
      align=u16(b.data()+start+12); bits=u16(b.data()+start+14);
    } else if(!memcmp(b.data()+pos,"data",4)) {require(!data,"Multiple data chunks unsupported");data=start;nbytes=len;}
    pos=start+len+(len&1);
  }
  require(data && ((format==1&&bits==16)||(format==3&&bits==32)) && align==bits/8 && nbytes%align==0,"Use mono PCM16 or IEEE float32 WAV");
  std::vector<float> samples(nbytes/align);
  for(size_t i=0;i<samples.size();++i) {
    const auto* p=b.data()+data+i*align;
    if(format==1) samples[i]=float(int16_t(u16(p)))/32768; else {uint32_t v=u32(p); std::memcpy(&samples[i],&v,4);}
    require(std::isfinite(samples[i]),"Nonfinite input sample");
  } return samples;
}
void write_wav(const std::string& path,const std::vector<float>& v) {
  std::ofstream f(path,std::ios::binary); require(bool(f),"Cannot write output WAV");
  f.write("RIFF",4); word(f,36+unsigned(v.size())*4,4);f.write("WAVEfmt ",8);word(f,16,4);word(f,3,2);word(f,1,2);
  word(f,48000,4);word(f,192000,4);word(f,4,2);word(f,32,2);f.write("data",4);word(f,unsigned(v.size())*4,4);
  for(float x:v) {uint32_t u;std::memcpy(&u,&x,4);word(f,u,4);} require(bool(f),"WAV write failed");
}
}
int main(int argc,char** argv) {
  try {
    require(argc==4||argc==5,"Usage: mpp_lab MODEL.nam CHAIN.json OUTPUT.wav [INPUT.wav]; without input, generate a silent-to-speakers synthetic test file");
    auto config=host::read_json(argv[2]);host::keys(config,{"stages","assume_48000","engine","seconds"});
    auto model_json=host::read_json(argv[1]);bool assume=config.value("assume_48000",false);
    host::validate_model(model_json,assume);nam::activations::Activation::disable_fast_tanh();
    auto chain=std::make_unique<mpp::Chain>();auto stages=host::stages(config.at("stages"));
    require(chain->configure(stages.data(),unsigned(stages.size())),"Invalid stage parameters or duplicate stateful effect");
    std::unique_ptr<nam::DSP> reference; mpp::Lstm compact;std::string engine=config.value("engine",std::string("official"));
    if(engine=="compact") {
      const auto& c=model_json.at("config");require(model_json.at("architecture")=="LSTM"&&c.at("num_layers")==1,"Compact engine requires single-layer LSTM");
      auto weights=model_json.at("weights").get<std::vector<float>>(); require(compact.load(c.at("hidden_size"),weights.data(),unsigned(weights.size())),"Compact model does not fit (hidden size <=16)");
      float z[128]{},scratch[128];for(int i=0;i<188;++i) compact.process(z,scratch,128);chain->model(mpp::Lstm::callback,&compact);
    } else {require(engine=="official","Unknown engine");reference=host::load_model(model_json,assume);chain->model(host::callback,reference.get());}
    std::vector<float> input;
    if(argc==5) input=read_wav(argv[4]); else {
      double seconds=config.value("seconds",3.0);require(std::isfinite(seconds)&&seconds>=0.1&&seconds<=60,"seconds must be 0.1..60");
      input.resize(size_t(seconds*48000));
      for(size_t i=0;i<input.size();++i) {double t=double(i)/48000;input[i]=float(0.1*std::exp(-3*std::fmod(t,0.5))*(std::sin(6.283185307*110*t)+0.3*std::sin(6.283185307*220*t)));}
    }
    require(!input.empty(),"Input WAV must contain samples");
    std::vector<float> output(input.size());std::vector<double> times;times.reserve((input.size()+47)/48);
    auto total_start=std::chrono::steady_clock::now();
    for(size_t pos=0;pos<input.size();pos+=48) {
      unsigned n=unsigned(std::min<size_t>(48,input.size()-pos));auto start=std::chrono::steady_clock::now();
      require(chain->process(input.data()+pos,output.data()+pos,n),"DSP processing failed");
      times.push_back(std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count());
    }
    double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-total_start).count();
    float peak=0;double sum=0;unsigned above=0;for(float x:output) {require(std::isfinite(x),"Nonfinite output");peak=std::max(peak,std::abs(x));sum+=double(x)*x;if(std::abs(x)>1)++above;}
    write_wav(argv[3],output);std::sort(times.begin(),times.end());
    host::json report={{"mode","OFFLINE_FILES_ONLY_NO_AUDIO_OR_USB_ACCESS"},{"engine",engine},{"samples",input.size()},{"sample_rate",48000},{"block_frames",48},{"audio_seconds",double(input.size())/48000},{"compute_seconds",elapsed},{"realtime_factor_mac_only",elapsed/(double(input.size())/48000)},{"peak",peak},{"rms",std::sqrt(sum/output.size())},{"samples_above_full_scale",above},{"rejected_nonfinite",chain->rejected_samples()},{"block_p50_us",times[times.size()/2]},{"block_p99_us",times[size_t(0.99*(times.size()-1))]},{"block_max_us",times.back()},{"chain_storage_bytes_host",sizeof(mpp::Chain)},{"compact_model_storage_bytes",sizeof(mpp::Lstm)},{"nux_execution_tested",false}};
    std::cout<<report.dump(2)<<'\n';return 0;
  } catch(const std::exception& e) {std::cerr<<"Error: "<<e.what()<<'\n';return 1;}
}
