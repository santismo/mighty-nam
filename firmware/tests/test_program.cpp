#include "mpp/program.hpp"
#include "../target/a2/a2_lite.hpp"
#include <fstream>
#include <vector>
#include <memory>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <cstring>
#include "../third_party/json/json.hpp"
using nlohmann::json;
void need(bool v,const char* m){if(!v)throw std::runtime_error(m);}
uint32_t crc(const uint8_t* p,size_t n){uint32_t v=~0u;while(n--){v^=*p++;for(int i=0;i<8;i++)v=(v>>1)^((0u-(v&1u))&0xedb88320u);}return ~v;}
void seal(std::vector<uint8_t>& b){uint32_t c=crc(b.data()+16,b.size()-16);for(int i=0;i<4;i++)b[12+i]=uint8_t(c>>(8*i));}
void model(void* ctx,const float* x,float* y,unsigned n){static_cast<mpp::A2Lite*>(ctx)->process(x,y,n);}
void custom(void*,const mpp::Stage& s,const float* x,float* y,unsigned n){for(unsigned i=0;i<n;i++)y[i]=x[i]*s.a+s.b;}
int main(int argc,char** argv){try{
 need(argc==3,"chain.bin model.nam required");std::ifstream f(argv[1],std::ios::binary);std::vector<uint8_t> binary((std::istreambuf_iterator<char>(f)),{});std::ifstream mf(argv[2]);auto j=json::parse(mf);auto weights=j.at("weights").get<std::vector<float>>();
 auto chain=std::make_unique<mpp::Chain>();auto a2=std::make_unique<mpp::A2Lite>();need(a2->load(weights.data(),weights.size()),"model load");chain->model(model,a2.get());
 need(chain->register_effect({64,{0,-1,0},{4,1,0},custom,nullptr,nullptr}),"extension registration");need(mpp::configure_program(*chain,binary.data(),binary.size()),"Dart program import");
 need(!chain->register_effect({65,{0,0,0},{1,1,1},custom,nullptr,nullptr}),"live registry mutation");
 for(size_t i=0;i<binary.size();i++){auto b=binary;b[i]^=1;need(!mpp::configure_program(*chain,b.data(),b.size()),"corruption accepted");}
 auto invalid=binary;invalid[18]=2;seal(invalid);need(!mpp::configure_program(*chain,invalid.data(),invalid.size()),"flags");
 invalid=binary;uint32_t nan=0x7fc00000;std::memcpy(invalid.data()+20,&nan,4);seal(invalid);need(!mpp::configure_program(*chain,invalid.data(),invalid.size()),"NaN parameter");
 std::vector<float> reference(48000*4);double energy=0;float peak=0;
 for(unsigned p=0;p<reference.size();p+=8){float x[8],y[8];for(unsigned k=0;k<8;k++)x[k]=p<48000?.08f*std::sin((p+k)*.0576f):0;need(chain->process(x,y,8),"process");for(unsigned k=0;k<8;k++){need(std::isfinite(y[k]),"finite");reference[p+k]=y[k];energy+=y[k]*y[k];peak=std::max(peak,std::abs(y[k]));}}
 need(energy>.001&&peak<8,"stability");chain->reset();a2->reset();
 for(unsigned p=0;p<reference.size();p+=16){float x[16],y[16];for(unsigned k=0;k<16;k++)x[k]=p<48000?.08f*std::sin((p+k)*.0576f):0;need(chain->process(x,y,16),"reset run");for(unsigned k=0;k<16;k++)need(y[k]==reference[p+k],"block boundary/restart invariance");}
 mpp::Stage disabled{mpp::Kind::nam,0,0,0,false};chain->model(nullptr,nullptr);need(chain->configure(&disabled,1),"disabled NAM config");float x=.5f,y=0;need(chain->process(&x,&y,1)&&y==x,"disabled NAM should bypass without model");
 mpp::Stage ext{static_cast<mpp::Kind>(64),2,.1f,0};need(chain->configure(&ext,1)&&chain->process(&x,&y,1)&&std::abs(y-1.1f)<1e-6,"extension");
 std::cout<<"{\"status\":\"PASS_APP_COMPILED_ALL_EFFECTS_A2_CHAIN\",\"samples_per_run\":"<<reference.size()<<",\"runs\":2,\"chain_state_bytes\":"<<sizeof(mpp::Chain)<<",\"a2_state_bytes\":"<<sizeof(mpp::A2Lite)<<",\"peak\":"<<peak<<",\"block_restart_exact\":true,\"custom_extension_passed\":true,\"physical_device_tested\":false,\"audio_playback\":false}\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
