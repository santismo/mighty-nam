// MIT (c) 2026 santismo. No autonomous recording, flash test or output muting.
#include "../hardware/diagnostics.hpp"
#include "../layout.hpp"
using namespace mighty_loop;
extern "C" {
extern uint32_t __loop_bss_start[],__loop_bss_end[],__loop_code_start[],__loop_code_end[],__loop_code_load[];
extern volatile uint32_t mpp_dwt_reset_epoch;
void mpp_loop_init();unsigned mpp_loop_state(unsigned);void mpp_base_service();void mpp_base_irq();
void mpp_base_query(const uint8_t*,unsigned,unsigned);
void mpp_reply_send(const uint8_t*,unsigned,unsigned);
volatile uint32_t mpp_loop_diag[40];
}
namespace {
volatile unsigned pending,command_sequence;
uint32_t snapshot[40],snapshot_ready,scan_offset,guard_offset;
uint32_t last_start,last_epoch,last_ctrl;
volatile bool touched;
constexpr uintptr_t bases[]={layout::first,layout::second};
constexpr unsigned sizes[]={layout::first_bytes,layout::second_bytes};
constexpr uintptr_t guards[]={layout::first-32,layout::first+layout::first_bytes,
 layout::second-32,layout::second+layout::second_bytes,0x20314000,0x20317fe0,0x20318000,0x20319fe0};
unsigned rd(uintptr_t p){return *(volatile uint32_t*)p;}
void wr(uintptr_t p,unsigned v){*(volatile uint32_t*)p=v;}
void barrier(){__asm__ volatile("dmb":::"memory");}
uint32_t pattern(uintptr_t p,unsigned pass){return (uint32_t(p)^0xa5296d83u)^(pass?0xffffffffu:0u);}
void cache(uintptr_t lo,unsigned n){
 __asm__ volatile("dsb":::"memory");
 for(uintptr_t p=lo&~31u;p<lo+n;p+=32)wr(0xe000ef70,p); // DCCIMVAC
 __asm__ volatile("dsb\nisb":::"memory");
}
void maximum(volatile uint32_t& x,unsigned n){if(n>x)x=n;}
unsigned lock(){unsigned v;__asm__ volatile("mrs %0,primask\ncpsid i":"=r"(v)::"memory");return v;}
void unlock(unsigned v){__asm__ volatile("dsb\nisb\nmsr primask,%0"::"r"(v):"memory");}
bool writable(){return !pending && mpp_loop_state(3)==0 && !mpp_loop_state(0);}
}
extern "C" {
bool mpp_loop_allowed(){return mpp_loop_diag[2]==2 && !mpp_loop_diag[3];}
void mpp_loop_fail(unsigned flags,uintptr_t address){
 mpp_loop_diag[3]|=flags;if(!mpp_loop_diag[4])mpp_loop_diag[4]=address;
 // Disable only this diagnostic looper; never change guitar/master/listen state.
}
void mpp_loop_boot(){
 for(volatile uint32_t* p=__loop_bss_start;p<__loop_bss_end;++p)*p=0;
 mpp_loop_diag[0]=0x4c4f5031;mpp_loop_diag[1]=2;mpp_loop_diag[2]=1;
 mpp_loop_diag[35]=rd(0xe000ed14);mpp_loop_diag[36]=rd(0xe000ed94);
 mpp_loop_init();
 // Detect copy mismatch independently of the cache-clean loop in the stub.
 unsigned fold=2166136261u;
 for(unsigned i=0;__loop_code_start+i<__loop_code_end;++i){
  unsigned v=__loop_code_start[i];if(v!=__loop_code_load[i])mpp_loop_fail(1,(uintptr_t)(__loop_code_start+i));
  fold=(fold^v)*16777619u;
 }
 mpp_loop_diag[34]=fold;
 // Both ranges are filled together, then read together: catches aliases between
 // them as well as address/data errors. No audio DMA has been started yet.
 for(unsigned pass=0;pass<2;++pass){
  for(unsigned k=0;k<2;++k)for(uintptr_t p=bases[k];p<bases[k]+sizes[k];p+=4)wr(p,pattern(p,pass));
  for(unsigned k=0;k<2;++k)cache(bases[k],sizes[k]);
  for(unsigned k=0;k<2;++k)for(uintptr_t p=bases[k];p<bases[k]+sizes[k];p+=4)
   if(rd(p)!=pattern(p,pass))mpp_loop_fail(2,p);
  ++mpp_loop_diag[6];
 }
 for(uintptr_t g:guards)for(unsigned i=0;i<8;++i)wr(g+4*i,0x6c705200u+i);
 mpp_loop_diag[5]=sizes[0]+sizes[1];mpp_loop_diag[15]=mpp_loop_state(7);
 barrier();mpp_loop_diag[2]=2;
}
void mpp_loop_before_tick(){
 if(mpp_loop_state(3)!=0)touched=true;
 unsigned cmd=pending;
 if(cmd){
  unsigned error=mpp_loop_allowed()?mpp_loop_apply(cmd):3;
  if(cmd==257&&!error)touched=true;
  mpp_loop_diag[14]=error;mpp_loop_diag[13]=command_sequence;barrier();pending=0;
 }
 // One guard word per IRQ; all 64 are revisited in 10.7 ms at eight samples.
 uintptr_t p=guards[guard_offset/8]+4*(guard_offset%8);
 if(rd(p)!=0x6c705200u+guard_offset%8)mpp_loop_fail(4,p);
 guard_offset=(guard_offset+1)%64;++mpp_loop_diag[32];
}
void mpp_loop_service(){
 mpp_base_service();
 if(!mpp_loop_allowed()||touched)return;
 // Read-only idle ownership sweep, 256 bytes per foreground call. An IRQ can
 // interrupt it. No background fill or cache operation during guitar playback.
 for(unsigned i=0;i<64;++i){
  uintptr_t p=scan_offset<sizes[0]?bases[0]+scan_offset:bases[1]+scan_offset-sizes[0];
  unsigned value=rd(p);
  // Arming can interrupt this read and legitimately replace the test pattern.
  // Check the IRQ-published flag after the load, before diagnosing corruption.
  if(touched)return;
  if(value!=pattern(p,1)){mpp_loop_fail(8,p);break;}
  scan_offset+=4;if(scan_offset==sizes[0]+sizes[1]){scan_offset=0;++mpp_loop_diag[7];}
 }
 mpp_loop_diag[33]=scan_offset;
}
void mpp_loop_irq(){
 auto* d=mpp_loop_diag;++d[16];
 unsigned epoch=mpp_dwt_reset_epoch,ctrl=rd(0xe0001000),start=rd(0xe0001004),state=mpp_loop_state(3);
 mpp_base_irq();
 unsigned end=rd(0xe0001004),after=rd(0xe0001000),last=mpp_dwt_reset_epoch,span=end-start;
 bool valid=(ctrl&1)&&ctrl==after&&epoch==last&&span&&span<0x80000000u;
 if(valid){
  ++d[17];d[19]=span;maximum(d[20],span);maximum(d[state==2?23:state==3?24:25],span);
  unsigned period=start-last_start;
  if(last_ctrl==ctrl&&last_epoch==epoch&&period&&period<0x80000000u){
   if(!d[21]||period<d[21])d[21]=period;maximum(d[22],period);
  }
 }else{++d[18];if(epoch!=last)++d[26];}
 last_start=start;last_epoch=last;last_ctrl=valid?after:0;
 d[27]|=(rd(0x40404008)|rd(0x40404088))&0xc0000u;
 barrier();++d[16];
}
void mpp_loop_query(const uint8_t* p,unsigned n,unsigned channel){
 unsigned size=n;if(size>=10&&size<=330&&p[size-1]==247)--size;
 if(size<8||p[7]!='O'){mpp_base_query(p,n,channel);return;}
 if(size!=13||channel>1||rd(0xe000ed04)&511||p[0]!=240||p[1]!=67||p[2]!=88||p[3]!=112||p[4]!=4||p[5]!=2||p[6]!=78||p[8]!=1||p[9]>4||p[10]>127||p[11]>127||p[12]>127||!(p[11]|p[12])||p[13]!=247)return;
 unsigned error=0,action=p[10];
 if(p[9]){
  if((p[9]==1 && (!action || action>10)) ||
     (p[9]==2 && (action<12 || action>60)) ||
     (p[9]==3 && action>100) || (p[9]==4 && action!=30 && action!=60))error=1;
  else if(!mpp_loop_allowed())error=3;
  else if(pending)error=2;
  else{++command_sequence;barrier();pending=(unsigned(p[9])<<8)|action;}
 }else if(action==0 || action==5){
  snapshot_ready=0;
  for(unsigned attempt=0;attempt<3;++attempt){
   unsigned seq=mpp_loop_diag[16];
   for(unsigned i=0;i<40;++i)snapshot[i]=mpp_loop_diag[i];
   for(unsigned i=0;i<4;++i)snapshot[8+i]=mpp_loop_state(i==0?3:i==1?0:i==2?1:2);
   snapshot[37]=mpp_loop_state(9);snapshot[38]=mpp_loop_state(10);snapshot[39]=mpp_loop_state(11);
   snapshot[12]=pending;snapshot[28]=mpp_loop_state(4);snapshot[29]=mpp_loop_state(5);snapshot[30]=mpp_loop_state(6);
   barrier();if(!(seq&1)&&seq==mpp_loop_diag[16]){snapshot_ready=1;break;}
  }
  if(!snapshot_ready)error=2;
 }else if(action>5)error=1;
 else if(!snapshot_ready)error=2;
 uint8_t out[55];for(unsigned i=0;i<13;++i)out[i]=p[i];out[9]=p[9]|64;out[13]=error;
 constexpr unsigned compact[]={8,9,10,12,13,14,38,3};
 for(unsigned i=0;i<8;++i){unsigned value=!p[9]&&snapshot_ready&&action==5?
  (i==0?snapshot[8]|(snapshot[37]<<8):snapshot[compact[i]]):!p[9]&&snapshot_ready&&action<5?snapshot[action*8+i]:i==0?command_sequence:0;
  for(unsigned j=0;j<5;++j)out[14+i*5+j]=(value>>(j*7))&127;}
 out[54]=247;mpp_reply_send(out,sizeof out,channel);
}
bool mpp_loop_erase(void*,uint32_t address){
 unsigned mask=lock();bool allowed=writable();
 if(!allowed||!((address>=0x30384000&&address<0x303a0000)||(address>=0x303a4000&&address<0x303a6000))||(address&4095)){
  unlock(mask);extern bool mpp_loop_no_erase(void*,uint32_t);return mpp_loop_no_erase(nullptr,address);}
 int result=((int(*)(uint32_t))0x841d)(address);unlock(mask);++mpp_loop_diag[31];return result==0;
}
bool mpp_loop_program(void*,uint32_t address,const uint8_t* src,unsigned n){
 unsigned mask=lock();bool allowed=writable();
 if(!allowed||!src||n!=256-(address&255)||!((address>=0x30384000&&address+n<=0x303a0000)||(address>=0x303a4000&&address+n<=0x303a6000))){
  unlock(mask);extern bool mpp_loop_no_program(void*,uint32_t,const uint8_t*,unsigned);return mpp_loop_no_program(nullptr,address,src,n);}
 int result=((int(*)(const uint8_t*,uint32_t))0x84ad)(src,address);unlock(mask);++mpp_loop_diag[31];return result==0;
}
}
