#include "../target/link/active_chain.hpp"
#include <cassert>
#include <algorithm>
#include <cstdio>
int main(){
 unsigned cases=0;uint8_t p[128]={},f[32]={};
 p[99]=10;
 const uint8_t order[]={5,1,2,3,9,4,6,7,8};
 for(unsigned reverse=0;reverse<2;++reverse){
  for(unsigned i=0;i<9;++i)p[90+i]=order[reverse?8-i:i];
  for(unsigned mask=0;mask<512;++mask)for(unsigned a=0;a<11;++a)for(unsigned b=0;b<11;++b)if(a!=b)
   for(unsigned enabled=0;enabled<4;++enabled){
    for(unsigned id=1;id<=9;++id)p[id]=(mask&(1u<<(id-1)))?1:65;
    f[2]=a;f[18]=b;f[1]=enabled&1;f[17]=(enabled>>1)&1;
    mpp::graph::Plan plan;assert(mpp::graph::compile(p,f,plan));
    // Independent oracle: insert both FX into a full list, then remove absent nodes.
    uint8_t all[11]={};std::copy(p+90,p+99,all);
    unsigned first=a<b?a:b,second=a<b?b:a;
    std::move_backward(all+first,all+9,all+10);all[first]=a<b?11:12;
    std::move_backward(all+second,all+10,all+11);all[second]=a<b?12:11;
    unsigned n=0,stock=0;for(auto id:all){bool present=id>=11?f[(id-11)*16+1]:!(p[id]&64);if(present){assert(plan.nodes[n]==id);assert(plan.fade_steps[n]==2*stock+3);++n;}if(id<11)++stock;}
    assert(n==plan.count);++cases;
   }
 }
 mpp::graph::Plan sentinel;sentinel.count=1;sentinel.nodes[0]=3;
 p[90]=0;assert(!mpp::graph::compile(p,f,sentinel)&&sentinel.count==1&&sentinel.nodes[0]==3);
 p[90]=p[91];assert(!mpp::graph::compile(p,f,sentinel));
 f[2]=f[18];assert(!mpp::graph::compile(p,f,sentinel));
 std::printf("PASS %u active-chain membership/order combinations; invalid input preserves plan\n",cases);
}
