#include "../target/hardware/startup_clock.hpp"
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
using namespace mpp::hardware;
namespace {
unsigned checks=0;
void require(bool x){++checks;if(!x){std::fprintf(stderr,"clock assertion %u failed\n",checks);std::abort();}}
struct Model {
 uint32_t words[4]={0x400,0x400,0,0x20006000|104};
 unsigned reads=0,fail=0,change=0;
 RegisterBus bus(){return {this,[](void* c,unsigned width,uint32_t addr,uint32_t* out){
  auto& m=*static_cast<Model*>(c);++m.reads;
  if(m.reads==m.fail)return false;
  if(width!=4)return false;
  constexpr uint32_t addresses[]={0x40cc0000,0x40cc0020,0x40cc0024,0x40c84200};
  for(unsigned i=0;i<4;++i)if(addr==addresses[i]){*out=m.words[i]^(m.reads==m.change?1:0);return true;}
  return false;
 },nullptr,nullptr};}
};
ClockCheck check(Model& m,uint32_t ref=24000000){ClockReport r;auto result=inspect_startup_clock(m.bus(),ref,r);require(result==r.result);if(result!=ClockCheck::Derived)require(r.derived_hz==0);return result;}
}
int main(){
 Model m;ClockReport r;
 require(inspect_startup_clock(m.bus(),24000000,r)==ClockCheck::Derived);require(r.derived_hz==624000000);
 for(unsigned fail=1;fail<=8;++fail){Model x;x.fail=fail;require(check(x)==ClockCheck::BusError);}
 for(unsigned read=5;read<=8;++read){Model x;x.change=read;require(check(x)==ClockCheck::UnstableSnapshot);}
 for(uint32_t mask:{0x10000000u,0x20000000u,0x40000000u,0x80000000u}){Model x;x.words[1]|=mask;require(check(x)==ClockCheck::UnstableSnapshot);}
 for(uint32_t mask:{0x01000000u,0x04000000u,0x00010000u,0x00100000u}){Model x;x.words[2]|=mask;require(check(x)==ClockCheck::UnstableSnapshot);}
 {Model x;x.words[0]^=1;require(check(x)==ClockCheck::UnstableSnapshot);}
 {Model x;x.words[0]|=0x01000000;x.words[1]|=0x01000000;require(check(x)==ClockCheck::RootInactive);}
 {Model x;x.words[1]|=0x08000000;require(check(x)==ClockCheck::RootInactive);}
 for(unsigned mux=0;mux<8;++mux)if(mux!=4){Model x;x.words[0]=x.words[1]=mux<<8;require(check(x)==ClockCheck::UnsupportedSource);}
 for(uint32_t mask:{0x80000000u,0x40000000u,0x20000u,0x1000u,0x20000000u,0x2000u,0x4000u}){
  Model x;x.words[3]^=mask;require(check(x)==ClockCheck::PllUnready);
 }
 {Model x;require(check(x,0)==ClockCheck::ReferenceUnknown);}
 for(uint32_t ref:{1u,23999999u,26000000u,0xffffffffu}){Model x;require(check(x,ref)==ClockCheck::InvalidReference);}
 for(uint32_t feedback:{0u,103u,209u,255u}){Model x;x.words[3]=(x.words[3]&~255u)|feedback;require(check(x)==ClockCheck::InvalidDivider);}
 // Independent 64-bit rational oracle for all accepted register dividers.
 unsigned combinations=0;
 for(uint32_t f=104;f<=208;++f)for(uint32_t post=0;post<4;++post)for(uint32_t div=1;div<=256;++div){
  Model x;x.words[0]=x.words[1]=0x400|(div-1);x.words[3]=0x20006000|(post<<15)|f;
  auto result=inspect_startup_clock(x.bus(),24000000,r);
  uint64_t numerator=uint64_t(24000000)*f;
  uint64_t denominator=2*(post==3?1:(2<<post))*div;
  if(numerator%denominator)require(result==ClockCheck::NonintegralRate&&r.derived_hz==0);
  else require(result==ClockCheck::Derived&&r.derived_hz==numerator/denominator);
  ++combinations;
 }
 require(inspect_startup_clock({nullptr,nullptr,nullptr,nullptr},24000000,r)==ClockCheck::BusError);
 std::printf("{\"status\":\"PASS_READ_ONLY_CLOCK_AUDIT\",\"assertions\":%u,\"divider_combinations\":%u,\"hardware_measured\":false,\"device_access\":false,\"playback\":false}\n",checks,combinations);
}
