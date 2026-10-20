#include "../target/link/sysex_codec.hpp"
#include <array>
#include <cstdio>
#include <cassert>
#include <cstring>
#include <random>
int main(){
 std::array<uint8_t,282> raw{}, decoded{};
 std::array<uint8_t,322> wire{},bad{};
 std::mt19937 gen(82719);
 unsigned cases=0;
 for(unsigned n=1;n<=280;++n)for(unsigned repeat=0;repeat<8;++repeat){
  for(auto& b:raw)b=uint8_t(gen());
  wire.fill(0xa5);decoded.fill(0xa5);
  unsigned size=mpp::link::pack7(raw.data(),n,wire.data()+1,320);
  assert(size==n+(n+6)/7&&wire[0]==0xa5&&wire[size+1]==0xa5);
  assert(mpp::link::unpack7(wire.data()+1,size,decoded.data()+1,280)==n);
  assert(decoded[0]==0xa5&&decoded[n+1]==0xa5&&!memcmp(raw.data(),decoded.data()+1,n));
  assert(!mpp::link::pack7(raw.data(),n,wire.data()+1,size-1));
  assert(!mpp::link::unpack7(wire.data()+1,size,decoded.data()+1,n-1));
  for(unsigned i=1;i<=size;++i){
   bad=wire;bad[i]|=128;decoded.fill(0xa5);
   assert(!mpp::link::unpack7(bad.data()+1,size,decoded.data()+1,280));
   for(auto b:decoded)assert(b==0xa5);
  }
  if(n%7){bad=wire;bad[1+(size/8)*8]|=1<<(n%7);assert(!mpp::link::unpack7(bad.data()+1,size,decoded.data()+1,280));}
  ++cases;
 }
 assert(!mpp::link::unpack7(wire.data(),1,decoded.data(),280));
 assert(!mpp::link::pack7(nullptr,1,wire.data(),320));
 std::printf("PASS %u codec cases, bounds and invalid input checks\n",cases);
}
