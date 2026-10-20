// NAMLNK01: volatile model transfer and silent A2 processing. Exact V1.5.6
// driver bridge. No flash programming, reset command or audible output.
#include "model_receiver.hpp"
#include "sysex_codec.hpp"
extern "C" {
struct LinkStatus {
 uint32_t magic,schema,ready,callbacks,faults,model_crc,generation,runs;
 uint32_t timer_max,running,context_rejections,last_output_bits;
};
volatile LinkStatus mpp_link;
unsigned mpp_hybrid_ready;
extern const uint8_t mpp_probe_identity[8]={'N','A','M','L','N','K','0','1'};
float mpp_link_output[8];
}
static mpp::A2Lite model;
static mpp::link::ModelReceiver receiver;
static float load_scratch[1871];
static uint8_t packet[280],response[48],wire[65];
static uint32_t loaded_session;
static uint32_t rd(uint32_t addr){return *(volatile uint32_t*)(uintptr_t)addr;}
static void barrier(){__asm__ volatile("dmb":::"memory");}
extern "C" void mpp_stock_amp_init(){
 mpp_hybrid_ready=0;
 volatile uint8_t* p=(volatile uint8_t*)&mpp_link;
 for(unsigned i=0;i<sizeof(mpp_link);++i)p[i]=0;
 receiver.reset();
 loaded_session=0;
 for(auto& f:mpp_link_output)f=0;
 mpp_link.magic=0x4e4c4b31;mpp_link.schema=1;
 // There is intentionally no saved model after a restart. Audio remains zero.
 barrier();mpp_link.ready=1;mpp_hybrid_ready=1;
}
extern "C" void mpp_stock_amp_process(const float*,const float*,float* l,float* r){
 for(unsigned i=0;i<8;++i)l[i]=r[i]=0;
}
extern "C" void mpp_probe_audio(const int32_t* rx,int32_t* tx){
 const uint32_t r=(uint32_t)(uintptr_t)rx,t=(uint32_t)(uintptr_t)tx;
 if(!((r==0x20016800&&t==0x20016900)||(r==0x20016880&&t==0x20016980))){
  ++mpp_link.faults;mpp_link.running=0;return;
 }
 ((void(*)(void))0x15639)();
 for(unsigned i=0;i<32;++i)tx[i]=0;
 ++mpp_link.callbacks;
 barrier();
 if(!mpp_link.ready||!mpp_link.running)return;
 if(rd(0x400ec000)!=0x46||rd(0x400ec004)!=23||rd(0x400ec00c)!=1||
    rd(0x400ec010)!=100000||rd(0x2000e48c)!=24000000){
  ++mpp_link.faults;mpp_link.running=0;return;
 }
 ((void(*)(void))0x11663)();
 float x[8];for(unsigned i=0;i<8;++i)x[i]=(float)rx[i*4+3]*0x1p-31f;
 model.process(x,mpp_link_output,8);
 for(float y:mpp_link_output)if(!__builtin_isfinite(y)){
  ++mpp_link.faults;mpp_link.running=0;
 }
 uint32_t bits;__builtin_memcpy(&bits,mpp_link_output+7,4);
 mpp_link.last_output_bits=bits;++mpp_link.runs;
 ((float(*)(void))0x11671)();
 const uint32_t ticks=rd(0x2000e490);
 if(ticks>mpp_link.timer_max)mpp_link.timer_max=ticks;
 if(!ticks||ticks>=150||rd(0x400ec000)!=0x46){
  ++mpp_link.faults;mpp_link.running=0;
 }
}
extern "C" void mpp_probe_version(const uint8_t* p,unsigned n,unsigned channel){
 if(n!=4||channel>1||p[0]!=0xf0||p[1]!=0x43||p[2]!=0x58||p[3]||p[4]!=0xf7)return;
 uint8_t out[45]={0xf0,0x43,0x58,0x10};
 const uint8_t product[8]={'P','L','U','G','P','R','O',0};
 for(unsigned i=0;i<8;++i){out[4+i]=mpp_probe_identity[i];out[36+i]=product[i];}
 out[28]=0x10;out[44]=0xf7;
 ((void(*)(const uint8_t*,unsigned,unsigned))0xae81)(out,45,channel);
}
extern "C" void mpp_probe_query(const uint8_t* p,unsigned n,unsigned channel){
 if(n<9||n>329||channel>1||p[0]!=0xf0||p[1]!=0x43||p[2]!=0x58||
    p[3]!=0x70||p[4]!=4||p[5]!=2||p[6]!='N'||p[n]!=0xf7)return;
 if(p[7]=='P'&&n==9&&p[8]<128){
  const unsigned page=p[8];uint32_t value=page<12?rd((uint32_t)(uintptr_t)&mpp_link+4*page):0;
  uint8_t out[8]={1,(uint8_t)page,(uint8_t)(page>=12),0,0,0,0,0};
  for(unsigned i=0;i<5;++i)out[3+i]=(value>>(7*i))&127;
  ((void(*)(unsigned,unsigned,const uint8_t*,unsigned,unsigned))0xa18b)(4,2,out,8,channel);
  return;
 }
 if(p[7]!='L'||p[8]!=1||!mpp_link.ready)return;
 // This bridge may only change the engine from thread mode. A foreground
 // handler cannot overlap an in-flight ISR on this single core; subsequent
 // audio interrupts observe running=0 while validation/loading takes place.
 if(rd(0xe000ed04)&511){++mpp_link.context_rejections;return;}
 unsigned size=mpp::link::unpack7(p+9,n-9,packet,sizeof(packet)),out_n=0;
 if(!size)return;
 const uint32_t previous=mpp_link.running;
 mpp_link.running=0;barrier();
 bool ok=receiver.exchange(packet,size,response,sizeof(response),out_n);
 uint32_t run=previous;
 uint32_t session;__builtin_memcpy(&session,packet+8,4);
 if(ok&&packet[5]==4&&response[24]==0&&session!=loaded_session){
  run=receiver.load_active(model,true,load_scratch,1871);
  if(run){mpp_link.model_crc=receiver.active_crc();++mpp_link.generation;loaded_session=session;}
  else ++mpp_link.faults;
 }
 // Do not restore a previous running flag over a fault latched by an ISR.
 if(mpp_link.faults)run=0;
 barrier();mpp_link.running=run;
 if(!ok)return;
 // The stock command-4 builder has a fixed 15-byte buffer. Use the same
 // bounded transmitter as identity replies, with our own complete frame.
 const uint8_t prefix[9]={0xf0,0x43,0x58,0x70,4,2,'N','L',1};
 for(unsigned i=0;i<9;++i)wire[i]=prefix[i];
 unsigned encoded=mpp::link::pack7(response,out_n,wire+9,sizeof(wire)-10);
 if(encoded){
  wire[9+encoded]=0xf7;
  ((void(*)(const uint8_t*,unsigned,unsigned))0xae81)(wire,encoded+10,channel);
 }
}
extern "C" void __aeabi_memclr4(void* dst,unsigned n){
 volatile uint8_t* p=(volatile uint8_t*)dst;while(n--)*p++=0;
}
static_assert(sizeof(LinkStatus)==48);
