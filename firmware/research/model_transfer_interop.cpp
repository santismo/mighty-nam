// Replay Dart-generated traffic through the C++ RAM receiver. Files only.
#include "../target/link/model_receiver.hpp"
#include <fstream>
#include <iterator>
#include <vector>
#include <cstring>
#include <cmath>
#include <cstdio>
static uint32_t rd(const uint8_t* p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
static std::vector<uint8_t> read(const char* path){std::ifstream f(path,std::ios::binary);if(!f)throw "cannot read input";return {std::istreambuf_iterator<char>(f),{}};}
int main(int argc,char** argv){
 try{
  if(argc!=4)throw "usage: interop REQUESTS REPLIES EXPECTED_SLOT";
  auto requests=read(argv[1]),expected=read(argv[3]);if(expected.size()!=8192)throw "slot size";
  std::ofstream output(argv[2],std::ios::binary);if(!output)throw "cannot write replies";
  mpp::link::ModelReceiver receiver;unsigned frames=0;
  for(size_t i=0;i<requests.size();){
   if(requests.size()-i<4)throw "truncated length";uint32_t size=rd(requests.data()+i);i+=4;
   if(size>requests.size()-i)throw "truncated packet";
   uint8_t reply[48];unsigned reply_size=0;
   if(!receiver.exchange(requests.data()+i,size,reply,48,reply_size))throw "packet rejected";
   uint8_t length[4]={uint8_t(reply_size),0,0,0};output.write(reinterpret_cast<char*>(length),4);output.write(reinterpret_cast<char*>(reply),reply_size);
   i+=size;frames++;
  }
  if(!receiver.has_model()||std::memcmp(receiver.active_slot(),expected.data(),8192))throw "model mismatch";
  mpp::A2Lite a,b;float weights[1871];for(unsigned i=0;i<1871;i++){uint32_t bits=rd(expected.data()+32+4*i);std::memcpy(weights+i,&bits,4);}
  if(!receiver.load_active(a,true)||!b.load(weights,1871))throw "load failed";
  float input[1024],x[1024],y[1024],restarted[1024];for(unsigned i=0;i<1024;i++)input[i]=0.2f*std::sin(float(i)*0.04f);
  a.process(input,x,1024);b.process(input,y,1024);for(unsigned i=0;i<1024;i++)if(!std::isfinite(x[i])||x[i]!=y[i])throw "DSP mismatch";
  if(!receiver.load_active(a,true))throw "reload failed";a.process(input,restarted,1024);
  if(std::memcmp(x,restarted,sizeof(x)))throw "restart mismatch";
  std::printf("{\"status\":\"PASS\",\"frames\":%u,\"dsp_samples\":1024,\"reload_bit_identical\":true,\"playback\":false}\n",frames);
 }catch(const char* e){std::fprintf(stderr,"%s\n",e);return 1;}return 0;
}
