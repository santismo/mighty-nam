#include "../target/link/tuner_capture.hpp"
#include <cassert>
#include <climits>
#include <cstring>
#include <cstdio>
#include <initializer_list>
int main(){
 mpp::tuner::Capture c;int32_t rx[32];unsigned cases=0;
 for(unsigned fill: {0u,165u,255u}) {
  std::memset(&c,fill,sizeof(c));c.reset();assert(!c.enabled&&!c.count&&!c.generation);
  for(int value: {INT_MIN,INT_MAX,0,65535,-65535}) {
   for(auto& x:rx)x=value;
   c.start();unsigned g=c.generation;
   for(unsigned i=0;i<1024;++i)c.feed(rx);
   assert(!c.enabled&&c.count==2048&&c.generation==g);
   for(auto x:c.samples)assert(x==(value>>16));
   c.feed(rx);assert(c.count==2048);c.stop();assert(!c.count&&!c.enabled);++cases;
  }
 }
 c.reset();c.start();
 for(unsigned block=0;block<1024;++block){
  for(unsigned i=0;i<32;++i)rx[i]=(int32_t)((block*32+i)*2654435761u);
  int16_t expected[2];for(unsigned j=0;j<2;++j){int sum=0;for(unsigned i=0;i<4;++i)sum+=rx[(j*4+i)*4+3]>>16;expected[j]=sum>>2;}
  c.feed(rx);assert(c.samples[block*2]==expected[0]&&c.samples[block*2+1]==expected[1]);++cases;
 }
 c.start();c.feed(rx);c.stop();c.feed(rx);assert(c.count==0);c.reset();assert(c.generation==0);
 printf("PASS %u capture cases; ASAN/UBSAN; no device access\n",cases);
}
