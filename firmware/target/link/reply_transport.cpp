#include "reply_transport.hpp"
namespace {
uint8_t cache[328],page[56];unsigned size,generation;
void emit(unsigned index){
 const unsigned pages=(size+39)/40;if(!size||index>=pages)return;
 const uint8_t prefix[]={240,67,88,112,4,2,'N','R',1};
 for(unsigned i=0;i<9;++i)page[i]=prefix[i];
 page[9]=generation&127;page[10]=generation>>7;page[11]=index;page[12]=pages;page[13]=size&127;page[14]=size>>7;
 unsigned count=size-index*40;if(count>40)count=40;
 for(unsigned i=0;i<count;++i)page[15+i]=cache[index*40+i];page[15+count]=247;
 ((void(*)(const uint8_t*,unsigned,unsigned))0xae81)(page,16+count,1);
}
}
extern "C" void mpp_reply_init(){size=generation=0;}
extern "C" void mpp_reply_send(const uint8_t* data,unsigned n,unsigned channel){
 if(channel>1||n<2||n>330||data[0]!=240||data[n-1]!=247)return;
 if(!channel||n<=64){((void(*)(const uint8_t*,unsigned,unsigned))0xae81)(data,n,channel);return;}
 for(unsigned i=1;i+1<n;++i)if(data[i]>127)return;
 size=n-2;for(unsigned i=0;i<size;++i)cache[i]=data[i+1];generation=generation%16383+1;emit(0);
}
extern "C" void mpp_reply_query(const uint8_t* p,unsigned n,unsigned channel){
 if(channel!=1||n!=12||p[8]!=1||p[9]>127||p[10]>127||p[9]+128u*p[10]!=generation)return;
 emit(p[11]);
}
