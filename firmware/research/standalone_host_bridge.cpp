#include "../target/standalone/prototype.hpp"
#include "../tests/standalone_ram_port.hpp"
using namespace mpp::standalone;
struct Host {Prototype app;DmaMemory dma;test::RamPort port;};
extern "C" {
void* standalone_create(const float* weights,unsigned n,unsigned slot){
 auto* h=new Host;
 if(!h->app.boot(h->port.port(),h->port.bus(),{0x202c0000,slot,8,1000},h->dma,weights,n)){delete h;return nullptr;}return h;
}
int standalone_step(void* ptr,const int32_t* rx,float* diagnostic,unsigned sequence){
 auto& h=*static_cast<Host*>(ptr);unsigned half=sequence&1;
 for(unsigned i=0;i<32;++i)h.dma.rx[half*32+i]=rx[i];
 if(!h.app.audio_event({sequence,half,half}))return 0;
 for(unsigned i=0;i<8;++i)diagnostic[i]=h.app.diagnostic_samples()[i];
 for(int32_t x:h.dma.tx)if(x)return 0;
 return 1;
}
int standalone_restart(void* ptr,const float* weights,unsigned n,unsigned slot){auto& h=*static_cast<Host*>(ptr);return h.app.boot(h.port.port(),h.port.bus(),{0x202c0000,slot,8,1000},h.dma,weights,n);}
void standalone_status(void* ptr,Status* result){*result=static_cast<Host*>(ptr)->app.status();}
unsigned standalone_trace(void* ptr,Request* out){auto& h=*static_cast<Host*>(ptr);unsigned n=h.port.calls<128?h.port.calls:128;for(unsigned i=0;i<n;++i)out[i]=h.port.trace[i];return n;}
void standalone_destroy(void* ptr){delete static_cast<Host*>(ptr);}
}
