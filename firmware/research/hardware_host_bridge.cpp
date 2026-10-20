#include "../tests/rt1176_register_model.hpp"
using namespace mpp::standalone;
using namespace mpp::hardware;
struct Host {
 Prototype app;DmaMemory memory;test::RegisterModel registers;
 Rt1176Backend backend{registers.bus(),{0x202c0000,600000000,2048},memory};
 bool boot(const float* w,unsigned n,unsigned slot){registers.tick_step=1000000;bool ok=app.boot(backend.port(),backend.codec_bus(),{0x202c0000,slot,16,100000},memory,w,n);registers.tick_step=100;return ok;}
};
extern "C" {
void* standalone_create(const float* w,unsigned n,unsigned slot){auto* h=new Host;if(!h->boot(w,n,slot)){delete h;return nullptr;}return h;}
int standalone_step(void* p,const int32_t* input,float* output,unsigned sequence){
 auto& h=*static_cast<Host*>(p);unsigned half=sequence&1;
 for(unsigned i=0;i<32;++i)h.memory.rx[half*32+i]=input[i];
 h.registers.complete(half,1-half);Event event;
 if(h.backend.poll_release(event)!=Release::Ready||event.sequence!=sequence||!h.app.audio_event(event))return 0;
 for(unsigned i=0;i<8;++i)output[i]=h.app.diagnostic_samples()[i];
 for(auto x:h.memory.tx)if(x)return 0;return 1;
}
int standalone_restart(void* p,const float* w,unsigned n,unsigned slot){return static_cast<Host*>(p)->boot(w,n,slot);}
void standalone_status(void* p,Status* result){*result=static_cast<Host*>(p)->app.status();}
void standalone_destroy(void* p){delete static_cast<Host*>(p);}
}
