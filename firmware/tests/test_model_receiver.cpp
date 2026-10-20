#include "../target/link/model_receiver.hpp"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>
using namespace mpp::link;
static unsigned checks;
#define CHECK(x) do {++checks;if(!(x)){std::fprintf(stderr,"failed %s:%d: %s\n",__FILE__,__LINE__,#x);return 1;}} while(0)
static uint32_t rd(const uint8_t* p){uint32_t v=0;for(unsigned i=0;i<4;i++)v|=uint32_t(p[i])<<(8*i);return v;}
static void wr(uint8_t* p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=uint8_t(v>>(8*i));}
static std::vector<uint8_t> packet(unsigned op,uint32_t session,uint32_t offset,std::vector<uint8_t> data={}){
 std::vector<uint8_t> p(24+data.size());wr(p.data(),0x314c504d);p[4]=1;p[5]=op;p[6]=data.size();p[7]=data.size()>>8;wr(p.data()+8,session);wr(p.data()+12,offset);
 std::memcpy(p.data()+24,data.data(),data.size());wr(p.data()+16,crc32(data.data(),data.size()));wr(p.data()+20,crc32(p.data(),20));return p;
}
static unsigned send(ModelReceiver& r,const std::vector<uint8_t>& p){uint8_t out[48];unsigned n=0;if(!r.exchange(p.data(),p.size(),out,48,n))return 999;return rd(out+24);}
static std::vector<uint8_t> begin(uint32_t s,const std::vector<uint8_t>& slot){std::vector<uint8_t> body(8);wr(body.data(),8192);wr(body.data()+4,crc32(slot.data(),8192));return packet(2,s,0,body);}
static bool stage(ModelReceiver& r,uint32_t s,const std::vector<uint8_t>& slot){
 if(send(r,begin(s,slot)))return false;
 for(unsigned i=0;i<8192;i+=256)if(send(r,packet(3,s,i,{slot.begin()+i,slot.begin()+i+256})))return false;
 return true;
}
int main(){
 std::vector<uint8_t> slot(8192,0xff);std::memset(slot.data(),0,7516);
 uint32_t header[]={0x3241504d,1,48000,1871,7484,0,1,0};for(unsigned i=0;i<8;i++)wr(slot.data()+i*4,header[i]);
 wr(slot.data()+7512,0x3f800000);wr(slot.data()+20,crc32(slot.data()+32,7484));
 ModelReceiver r; mpp::A2Lite engine;
 CHECK(!r.has_model());CHECK(!r.load_active(engine,true));CHECK(crc32(reinterpret_cast<const uint8_t*>("123456789"),9)==0xcbf43926);
 CHECK(send(r,packet(1,0,0))==0);CHECK(send(r,packet(1,1,0))==1);
 CHECK(stage(r,1,slot));CHECK(send(r,packet(4,1,0))==0);CHECK(r.has_model());CHECK(r.active_crc()==crc32(slot.data(),slot.size()));
 CHECK(!r.load_active(engine,false));CHECK(r.load_active(engine,true));
 float scratch[1873]={};scratch[0]=12;scratch[1872]=34;
 CHECK(!r.load_active(engine,true,nullptr,1871));
 CHECK(!r.load_active(engine,true,scratch+1,1870));
 CHECK(r.load_active(engine,true,scratch+1,1871));
 CHECK(scratch[0]==12&&scratch[1872]==34);
 float input[256],output[256];for(unsigned i=0;i<256;i++)input[i]=0.1f;engine.process(input,output,256);for(float y:output)CHECK(y==0);
 CHECK(send(r,packet(4,1,0))==0);CHECK(send(r,begin(1,slot))==4);
 CHECK(send(r,begin(2,slot))==0);CHECK(send(r,begin(2,slot))==0);CHECK(send(r,begin(3,slot))==4);
 CHECK(send(r,packet(3,3,0,{1}))==2);CHECK(send(r,packet(3,2,0xffffffff,{1}))==3);CHECK(send(r,packet(3,2,0,{}))==3);
 CHECK(send(r,packet(3,2,2,{1}))==4);CHECK(send(r,packet(4,2,0))==6);
 CHECK(send(r,packet(3,2,0,{1,2}))==0);CHECK(send(r,packet(3,2,0,{1,2}))==0);CHECK(send(r,packet(3,2,0,{1,3}))==4);
 CHECK(send(r,packet(5,2,0))==0);CHECK(r.active_crc()==crc32(slot.data(),slot.size()));
 // Every possible single-byte corruption of a valid packet is rejected.
 auto p=packet(2,8,0,{1,2,3,4,5,6,7,8});for(unsigned i=0;i<p.size();i++){auto bad=p;bad[i]^=1;CHECK(send(r,bad)==999);}
 for(unsigned n=0;n<24;n++)CHECK(send(r,std::vector<uint8_t>(n))==999);
 CHECK(send(r,std::vector<uint8_t>(281))==999);
 uint8_t response[48];unsigned out_n=1;auto hello=packet(1,0,0);
 CHECK(!r.exchange(hello.data(),hello.size(),response,47,out_n));CHECK(out_n==0);
 // Models with correct transport CRC but invalid semantic content never commit.
 for(unsigned variant=0;variant<5;variant++){
  auto bad=slot;
  if(variant==0)bad[0]=0;
  if(variant==1)wr(bad.data()+8,44100);
  if(variant==2){wr(bad.data()+32,0x7fc00001);wr(bad.data()+20,crc32(bad.data()+32,7484));}
  if(variant==3)bad[8191]=0;
  if(variant==4)bad[20]^=1;
  CHECK(stage(r,20+variant,bad));CHECK(send(r,packet(4,20+variant,0))==5);CHECK(r.active_crc()==crc32(slot.data(),slot.size()));
  CHECK(send(r,packet(5,20+variant,0))==0);
 }
 // Reset after every chunk boundary, including before final commit.
 for(unsigned cutoff=0;cutoff<=32;cutoff++){
  r.reset();CHECK(send(r,begin(55,slot))==0);
  for(unsigned i=0;i<cutoff;i++)CHECK(send(r,packet(3,55,i*256,{slot.begin()+i*256,slot.begin()+(i+1)*256}))==0);
  r.reset();CHECK(!r.has_model());CHECK(send(r,packet(4,55,0))==2);CHECK(send(r,packet(3,55,0,{1}))==2);
 }
 CHECK(stage(r,88,slot));CHECK(send(r,packet(4,88,0))==0);CHECK(r.load_active(engine,true));r.reset();CHECK(!r.has_model());
 // Deterministic malformed-packet fuzz: cannot create a model from random input.
 uint32_t random=0x12345678;for(unsigned i=0;i<10000;i++){
  std::vector<uint8_t> noise(i%300);for(auto& b:noise){random^=random<<13;random^=random>>17;random^=random<<5;b=random;}
  send(r,noise);CHECK(!r.has_model());
 }
 std::printf("{\"status\":\"PASS\",\"assertions\":%u,\"receiver_bytes\":%zu,\"dsp_bytes\":%zu,\"device_access\":false,\"playback\":false}\n",checks,sizeof(r),sizeof(engine));return 0;
}
