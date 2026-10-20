#pragma once
#include <algorithm>
#include <cmath>
#include <fstream>
#include <set>
#include <stdexcept>
#include <vector>
#include "NAM/get_dsp.h"
#include "mpp/engine.hpp"
namespace host {
using json=nlohmann::json;
inline void require(bool ok,const std::string& why) { if(!ok) throw std::runtime_error(why); }
inline json read_json(const std::filesystem::path& p) { std::ifstream f(p); require(bool(f),"Cannot open "+p.string()); json j; f>>j; return j; }
inline void keys(const json& j,std::initializer_list<const char*> names) {
  require(j.is_object(),"Expected object"); std::set<std::string> allowed(names.begin(),names.end());
  for(auto it=j.begin();it!=j.end();++it) require(allowed.count(it.key()),"Unsupported field: "+it.key());
}
inline unsigned integer(const json& j,const char* name,unsigned low,unsigned high) {
  require(j.at(name).is_number_integer(),std::string(name)+" must be integer");
  int n=j.at(name); require(n>=int(low)&&n<=int(high),std::string(name)+" out of bounds"); return unsigned(n);
}
inline void validate_model(const json& j,bool assume48=false) {
  nam::verify_config_version(j.at("version").get<std::string>());
  double rate=j.value("sample_rate",-1.0);
  require(rate==48000 || (rate==-1 && assume48),"Model must specify 48000 Hz; old models require assume_48000=true");
  const auto& c=j.at("config"); unsigned count=0;
  if(j.at("architecture")=="LSTM") {
    keys(c,{"input_size","hidden_size","num_layers","in_channels","out_channels"});
    require(c.at("input_size")==1 && c.value("in_channels",1)==1 && c.value("out_channels",1)==1,"Only mono models supported");
    unsigned h=integer(c,"hidden_size",1,64), layers=integer(c,"num_layers",1,4);
    for(unsigned i=0;i<layers;++i) count+=4*h*((i?h:1)+h)+6*h;
    count+=h+1;
  } else if(j.at("architecture")=="WaveNet") {
    keys(c,{"layers","head","head_scale"}); require(c.at("head").is_null(),"External WaveNet head unsupported");
    require(std::isfinite(c.at("head_scale").get<float>()),"Invalid head scale");
    const auto& ls=c.at("layers"); require(ls.is_array()&&ls.size()>0&&ls.size()<=4,"Invalid layer arrays");
    unsigned previous=1, previous_head=0;
    for(const auto& l:ls) {
      keys(l,{"input_size","condition_size","head_size","channels","kernel_size","dilations","activation","gated","head_bias"});
      unsigned ci=integer(l,"input_size",1,64), ch=integer(l,"channels",1,64), head=integer(l,"head_size",1,64), k=integer(l,"kernel_size",1,8);
      require(ci==previous && l.at("condition_size")==1,"Invalid channel connection");
      require(!previous_head||previous_head==ch,"Invalid skip connection");
      require(l.at("gated")==false && l.at("activation")=="Tanh","Only classic ungated Tanh WaveNet supported");
      const auto& ds=l.at("dilations"); require(ds.is_array()&&!ds.empty()&&ds.size()<=16,"Invalid dilations");
      for(const auto& d:ds) require(d.is_number_integer()&&d.get<int>()>=1&&d.get<int>()<=4096,"Invalid dilation");
      count+=ci*ch+unsigned(ds.size())*(ch*ch*k+ch+ch+ch*ch+ch)+head*ch+(l.at("head_bias").get<bool>()?head:0);
      previous=ch; previous_head=head;
    }
    require(previous_head==1,"Only mono output supported"); count+=1;
  } else throw std::runtime_error("Supported architectures: mono LSTM and classic WaveNet; v0.7 containers are unsupported");
  const auto& ws=j.at("weights"); require(ws.is_array()&&ws.size()==count,"Model weight count mismatch");
  for(const auto& w:ws) require(w.is_number()&&std::isfinite(w.get<float>()),"Nonfinite model weight");
}
inline std::unique_ptr<nam::DSP> load_model(const json& j,bool assume48=false) {
  validate_model(j,assume48); auto m=nam::get_dsp(j); m->Reset(48000,128); return m;
}
inline void callback(void* ctx,const float* in,float* out,unsigned n) {
  float* p=const_cast<float*>(in); static_cast<nam::DSP*>(ctx)->process(&p,&out,int(n));
}
inline std::vector<mpp::Stage> stages(const json& j) {
  require(j.is_array(),"stages must be array"); std::vector<mpp::Stage> result;
  for(const auto& s:j) {
    keys(s,{"type","a","b","c"}); auto name=s.at("type").get<std::string>(); mpp::Kind kind;
    if(name=="gain") kind=mpp::Kind::gain; else if(name=="drive") kind=mpp::Kind::drive;
    else if(name=="distortion") kind=mpp::Kind::distortion; else if(name=="nam") kind=mpp::Kind::nam;
    else if(name=="tremolo") kind=mpp::Kind::tremolo; else if(name=="chorus") kind=mpp::Kind::chorus;
    else if(name=="pitch") kind=mpp::Kind::pitch; else if(name=="delay") kind=mpp::Kind::delay;
    else if(name=="reverb") kind=mpp::Kind::reverb; else throw std::runtime_error("Unknown effect: "+name);
    result.push_back({kind,s.value("a",0.0f),s.value("b",0.0f),s.value("c",0.0f)});
  } return result;
}
}
