// NAMLNK30 stock amp overlay. Tables are supplied locally from official firmware.
// No NAM RAM move, no new output queue, no device or flash-write command.
#include <stdint.h>
extern "C" {
extern uint32_t __extra_code_start[],__extra_code_end[],__extra_code_load[];
void old_loop_startup();void old_loop_service();
__attribute__((section(".tone"),aligned(32))) uint8_t mpp_amp_tone[68];
void mpp_fx_get(uint8_t*);void mpp_reply_send(const uint8_t*,unsigned,unsigned);
void old_loop_query(const uint8_t*,unsigned,unsigned);
bool old_loop_read(void*,uint32_t,uint8_t*,unsigned);
bool old_loop_erase(void*,uint32_t);
bool old_loop_program(void*,uint32_t,const uint8_t*,unsigned);
void stock_engine_process(void*,const uint8_t*,float*,float*,unsigned);
extern uint8_t stock_engines[];
}
namespace {
struct State { uint8_t config[16];volatile unsigned ready;float wet;uint32_t calls,prepares,rejections,io_status,io_address,io_count; } state;
bool supported(unsigned n){return n>=1&&n<=29;}
struct Meta { uint32_t bytes,init,process,source,tone,checksum; };
const Meta& meta(unsigned id){return ((const Meta*)0x30b90000)[id-1];}
bool equal(const uint8_t* a,const uint8_t* b){for(unsigned i=0;i<16;++i)if(a[i]!=b[i])return false;return true;}
__attribute__((noinline)) uintptr_t coefficients(unsigned id){return meta(id).source;}
void cache_sync(uintptr_t start,unsigned size){
 __asm__ volatile("dsb":::"memory");
 for(uintptr_t p=start&~31u;p<start+size;p+=32)*(volatile uint32_t*)0xe000ef68=p;
 __asm__ volatile("dsb":::"memory");*(volatile uint32_t*)0xe000ef50=0;
 __asm__ volatile("dsb\nisb":::"memory");
}
bool prepare(unsigned id){
 const auto& m=meta(id);if(m.bytes>0x7e0)return false;
 auto* dest=(volatile uint8_t*)0x2031a800;const auto* source=(const volatile uint8_t*)(0x30b80000+(id-1)*0x800);
 for(unsigned i=0;i<m.bytes;++i)dest[i]=source[i];
 uint32_t sum=2166136261u;for(unsigned i=0;i<m.bytes;++i)sum=(sum^dest[i])*16777619u;
 if(m.bytes&&sum!=m.checksum)return false;
 if(m.bytes)cache_sync(0x2031a800,m.bytes);
 if(m.tone!=0xffffffffu)for(unsigned i=0;i<sizeof(mpp_amp_tone);++i)mpp_amp_tone[i]=((const volatile uint8_t*)m.source)[m.tone+i];
 return true;
}
void barrier(){__asm__ volatile("dmb":::"memory");}
void flash_cache(uint32_t address,unsigned n){
 // NOR is read-only through AHB. Invalidate, never clean dirty lines back
 // to flash. The existing driver still owns writes and FlexSPI SWRESET.
 __asm__ volatile("dsb":::"memory");
 for(uint32_t p=address&~31u;p<address+n;p+=32)*(volatile uint32_t*)0xe000ef5c=p;
 __asm__ volatile("dsb\nisb":::"memory");
}
bool storage_result(unsigned op,uint32_t address,bool ok){
 state.io_address=address;state.io_status=(op<<24)|(++state.io_count&0xffffu)|(ok?0:0x80000000u);return ok;
}
}
extern "C" {
__attribute__((noinline)) void mpp_extra_init(){for(unsigned i=0;i<sizeof(state);++i)((volatile uint8_t*)&state)[i]=0;((void(*)())0x58b7)();}
__attribute__((section(".extra_boot"))) void mpp_extra_startup(){
 for(unsigned i=0;__extra_code_start+i<__extra_code_end;++i)__extra_code_start[i]=__extra_code_load[i];
 __asm__ volatile("dsb":::"memory");
 for(uintptr_t p=(uintptr_t)__extra_code_start&~31u;p<(uintptr_t)__extra_code_end;p+=32)*(volatile uint32_t*)0xe000ef68=p;
 __asm__ volatile("dsb":::"memory");*(volatile uint32_t*)0xe000ef50=0;
 __asm__ volatile("dsb\nisb":::"memory");
 old_loop_startup();mpp_extra_init();
}
// Replace only the chain-level table lookup. Other stock table users and
// every nonzero setting retain their exact previous gain, including smoothing.
__attribute__((naked,section(".master_zero"))) void mpp_master_zero(){
 __asm__ volatile("cmp r2, #0\nite eq\nmoveq r7, #0\nldrne.w r7, [r6, r2, lsl #2]\nbx lr");
}
bool mpp_extra_valid(const uint8_t* p){
 if(!p||p[2]==p[18])return false;unsigned amps=0;
 for(unsigned j=0;j<2;++j){const auto* c=p+16*j;
  if(c[0]<1||c[0]>8||c[1]>1||c[2]>10)return false;
  if(c[0]==8){if(!supported(c[3])||++amps>1)return false;
   for(unsigned i=4;i<11;++i)if(c[i]>100)return false;
   for(unsigned i=11;i<16;++i)if(c[i])return false;
  }else{
   if(c[3]>24)return false;
   for(unsigned i=4;i<10;++i)if(c[i]>100)return false;
   for(unsigned i=10;i<16;++i)if(c[i])return false;
  }
 }return true;
}
void mpp_extra_service(){
 old_loop_service();uint8_t pair[32];mpp_fx_get(pair);
 const uint8_t* c=nullptr;
 for(unsigned j=0;j<2;++j)if(pair[16*j]==8&&pair[16*j+1])c=pair+16*j;
 if(!c||!mpp_extra_valid(pair)){state.ready=0;state.wet=0;return;}
 if(state.ready&&equal(c,state.config))return;
 state.ready=0;barrier();state.wet=0;
 // The legacy loader at 0x533c is NEVER called: it would overwrite NAM.
 if(!prepare(c[3])){++state.rejections;return;}
 auto* controls=(volatile uint8_t*)0x200039b0;
 controls[0]=controls[12]=controls[13]=c[3];controls[14]=0;
 for(unsigned i=0;i<6;++i)controls[i+1]=c[5+i];
 if(c[3]==1||c[3]==5||c[3]==18||c[3]==21)controls[6]=c[10]>=50?1:0;
 ((void(*)())0x5375)(); // owned 4 KiB amp scratch + original tone state
 ((void(*)(uintptr_t,uintptr_t,uintptr_t))0x5149)(0x2000d44c,0x2000d4fc,0x20000374);
 const uintptr_t source=coefficients(c[3]);
 ((void(*)(uintptr_t,uintptr_t,uintptr_t,unsigned))meta(c[3]).init)(source,0x2031b000,0x2000d44c,1);
 for(unsigned i=0;i<16;++i)state.config[i]=c[i];
 ++state.prepares;barrier();state.ready=1;
}
void mpp_extra_process(unsigned slot,float* l,float* r){
 if(slot>1)return;uint8_t pair[32];mpp_fx_get(pair);const auto* c=pair+16*slot;
 if(c[0]!=8){stock_engine_process(stock_engines+16560*slot,c,l,r,8);return;}
 if(!c[1]||!state.ready||!equal(c,state.config))return;
 float in[8],out[8];for(unsigned i=0;i<8;++i)in[i]=l[i]*.2f;
 ((void(*)(const float*,float*,uintptr_t,uintptr_t,unsigned))meta(c[3]).process)
  (in,out,coefficients(c[3]),0x2031b000,8);
 const float target=c[4]*.01f;
 for(unsigned i=0;i<8;++i){
  state.wet+=.00390625f;if(state.wet>target)state.wet=target;
  if(!__builtin_isfinite(out[i])){++state.rejections;state.ready=0;return;}
  const float y=out[i]*8.f; // original AMP wrapper 0x56f6 gain
  l[i]+=state.wet*(y-l[i]);r[i]+=state.wet*(y-r[i]);
 }++state.calls;
}
void mpp_extra_query(const uint8_t* p,unsigned n,unsigned channel){
 unsigned size=n;if(size==10&&p[9]==247)--size;
 if(size==9&&channel<=1&&p[0]==240&&p[1]==67&&p[2]==88&&p[3]==112&&p[4]==4&&p[5]==2&&p[6]==78&&p[7]==80&&p[8]>=124&&p[8]<=127){
  uint8_t out[15]={240,67,88,112,4,2,1,p[8],0};
  const uint32_t value=p[8]==126?0x5354011d:p[8]==127?0x4e300002:p[8]==124?state.io_status:state.io_address;
  for(unsigned i=0;i<5;++i)out[9+i]=(value>>(i*7))&127;out[14]=247;mpp_reply_send(out,15,channel);return;
 }
 old_loop_query(p,n,channel);
}
bool mpp_extra_erase(void* context,uint32_t address){
 bool ok=old_loop_erase(context,address);
 if(ok)flash_cache(address,4096);
 return storage_result(1,address,ok);
}
bool mpp_extra_program(void* context,uint32_t address,const uint8_t* source,unsigned n){
 bool ok=old_loop_program(context,address,source,n);
 if(ok)flash_cache(address,n);
 return storage_result(n==4?3:2,address,ok);
}
}
