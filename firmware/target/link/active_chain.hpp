#pragma once
#include <stdint.h>
namespace mpp::graph {
// Stock IDs 1..9; custom FX A/B use 11/12. No audio work for absent nodes.
struct Plan { uint8_t count=0, nodes[11]={}, fade_steps[11]={}; };
__attribute__((always_inline)) inline bool compile(const uint8_t* preset,const uint8_t* fx,Plan& out){
 Plan next; unsigned seen=0;
 if(preset[89]!=0||preset[99]!=10)return false;
 if(fx[2]>10||fx[18]>10||fx[2]==fx[18]||fx[1]>1||fx[17]>1)return false;
 unsigned stock=0;
 for(unsigned pos=0;pos<11;++pos){
  if(pos==fx[2]||pos==fx[18]){
   unsigned slot=pos==fx[2]?0:1;
   if(fx[slot*16+1]){next.fade_steps[next.count]=2*stock+3;next.nodes[next.count++]=11+slot;}
  }else{
   unsigned id=preset[90+stock++];
   if(id<1||id>9||(seen&(1u<<id)))return false;
   seen|=1u<<id;
   if(!(preset[id]&64)){next.fade_steps[next.count]=2*stock+1;next.nodes[next.count++]=id;}
  }
 }
 if(stock!=9||seen!=0x3fe)return false;
 out.count=next.count;
 volatile uint8_t* nodes=out.nodes;
 for(unsigned i=0;i<11;++i)nodes[i]=next.nodes[i];
 volatile uint8_t* steps=out.fade_steps;
 for(unsigned i=0;i<11;++i)steps[i]=next.fade_steps[i];
 return true;
}
}
