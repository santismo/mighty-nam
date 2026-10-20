// Bounded continuous silent A2 trial using the exact stock V1.5.6 bridge.
// Never puts model output in DMA buffers. Reuses ONLY the stock GPT1 start/
// stop services after checking their configuration. No new clock configuration.
// 60,000 consecutive eight-sample batches after 5,999 warmup callbacks.
// Stop after the current batch on a timing/configuration/half-sequence fault.
// Measurements exclude IRQ entry/exit and final timer-result accounting.
// Alternating DMA halves cannot prove that no even number of releases was lost.
#include <stdint.h>
#include "../a2/a2_lite.hpp"

extern "C" {
struct Bench {
 uint32_t magic,schema,ready,blocks,bad_buffer,last_rx,last_tx;
 uint32_t load_status,runs,invalid_cycles,last_cycles,max_cycles,min_cycles;
 uint32_t sum_lo,sum_hi,last_output_bits,nonfinite_outputs,phase;
 uint32_t dwt_before,dwt_after,demcr_before,demcr_after,repeated_half;
 uint32_t timer_invalid,timer_last,timer_max,timer_min,timer_sum_lo,timer_sum_hi;
 uint32_t timer_limit_hits,timer_source_hz,timer_control;
};
volatile Bench mpp_bench;
unsigned mpp_hybrid_ready;
extern const uint8_t mpp_probe_identity[8]={'N','A','M','A','2','C','0','1'};
float mpp_bench_output[8];
}
static mpp::A2Lite model;
static uint32_t input_position;
static uint32_t read32(uint32_t p){return *(volatile const uint32_t*)(uintptr_t)p;}
static void barrier(){__asm__ volatile("dmb" ::: "memory");}
static const uint32_t regs[24]={0xe000ed00u,0xe000ed14u,0xe000ed94u,0xe000ef90u,
 0xe000ef94u,0x400e4048u,0x400e4040u,0x400e4044u,0x40cc0000u,0x40cc0020u,
 0x40cc0024u,0x40c84200u,0xe000ed08u,0xe000ed88u,0x40038000u,0x40c10000u,
 0x400ec000u,0x400ec004u,0x400ec010u,0x400ec00cu,
 0x40cc0700u,0x40cc0720u,0x40cc0724u,0x40cc6800u};

extern "C" void mpp_stock_amp_init(){
 mpp_hybrid_ready=0;
 volatile uint8_t* p=(volatile uint8_t*)&mpp_bench;
 for(unsigned i=0;i<sizeof(Bench);++i)p[i]=0;
 input_position=0;
 mpp_bench.magic=0x4d504232u;mpp_bench.schema=2;mpp_bench.min_cycles=0xffffffffu;mpp_bench.timer_min=0xffffffffu;
 for(unsigned i=0;i<8;++i)mpp_bench_output[i]=0;
 const auto* h=(volatile const uint32_t*)0x30384000u;
 mpp_bench.load_status=1;
 if(h[0]==0x3241504du&&h[1]==1&&h[2]==48000&&h[3]==1871&&h[4]==7484&&h[6]==1&&h[7]==0){
  mpp_bench.load_status=2;
  const auto* bytes=(volatile const uint8_t*)0x30384020u;uint32_t crc=~0u;
  for(unsigned i=0;i<7484;++i){crc^=bytes[i];for(unsigned j=0;j<8;++j)crc=(crc>>1)^((0u-(crc&1u))&0xedb88320u);}
  if((crc^~0u)==h[5]){
   mpp_bench.load_status=3;
   if(model.load((const float*)0x30384020u,1871))mpp_bench.load_status=0;
  }
 }
 // A rejected model leaves the diagnostic responsive but never calls DSP.
 if(mpp_bench.load_status)mpp_bench.phase=3;
 barrier();mpp_bench.ready=1;mpp_hybrid_ready=1;
}

extern "C" void mpp_stock_amp_process(const float*,const float*,float* l,float* r){
 for(unsigned i=0;i<8;++i)l[i]=r[i]=0;
}

extern "C" void mpp_probe_audio(const int32_t* rx,int32_t* tx){
 uint32_t r=(uint32_t)(uintptr_t)rx,t=(uint32_t)(uintptr_t)tx;
 if(!((r==0x20016800u&&t==0x20016900u)||(r==0x20016880u&&t==0x20016980u))){
  if(mpp_bench.bad_buffer!=0xffffffffu)++mpp_bench.bad_buffer;
  mpp_bench.phase=4;return;
 }
 bool active=mpp_bench.ready&&mpp_bench.phase<2&&mpp_bench.blocks>=5999;
 if(active){
  mpp_bench.timer_control=read32(0x400ec000u);
  mpp_bench.timer_source_hz=read32(0x2000e48cu);
  if(mpp_bench.timer_control!=0x46u||read32(0x400ec004u)!=23||
     read32(0x400ec00cu)!=1||read32(0x400ec010u)!=100000||
     mpp_bench.timer_source_hz!=24000000){
   ++mpp_bench.timer_invalid;mpp_bench.phase=4;active=false;
  }else ((void(*)(void))0x11663u)();
 }
 uint32_t previous_tx=mpp_bench.last_tx;
 ((void(*)(void))0x15639u)(); // Preserve the now-tested button/service timing.
 for(unsigned i=0;i<32;++i)tx[i]=0;
 barrier();mpp_bench.last_rx=r;mpp_bench.last_tx=t;
 if(mpp_bench.blocks!=0xffffffffu)++mpp_bench.blocks;
 if(!active)return;
 mpp_bench.phase=1;
 float x[8];
 for(unsigned i=0;i<8;++i)x[i]=(float)((int)(input_position++&255u)-128)*(1.0f/512.0f);
 uint32_t ctrl=read32(0xe0001000u),demcr=read32(0xe000edfcu);
 uint32_t begin=read32(0xe0001004u);
 model.process(x,mpp_bench_output,8);
 uint32_t end=read32(0xe0001004u),after=read32(0xe0001000u),de_after=read32(0xe000edfcu);
 mpp_bench.dwt_before=ctrl;mpp_bench.dwt_after=after;
 mpp_bench.demcr_before=demcr;mpp_bench.demcr_after=de_after;
 uint32_t dt=end-begin;mpp_bench.last_cycles=dt;
 // Reject disabled, missing, changed, zero or implausibly long counter spans.
 // Undetected concurrent counter reset remains an explicit interpretation limit.
 if(!(ctrl&after&1u)||(ctrl&(1u<<25))||ctrl!=after||
    !(demcr&de_after&(1u<<24))||demcr!=de_after||!dt||dt>=0x80000000u){
  ++mpp_bench.invalid_cycles;mpp_bench.phase=4;
 }else{
  if(dt>mpp_bench.max_cycles)mpp_bench.max_cycles=dt;
  if(dt<mpp_bench.min_cycles)mpp_bench.min_cycles=dt;
  uint32_t old=mpp_bench.sum_lo;mpp_bench.sum_lo=old+dt;
  if(mpp_bench.sum_lo<old)++mpp_bench.sum_hi;
 }
 for(unsigned i=0;i<8;++i)if(!__builtin_isfinite(mpp_bench_output[i])){
  ++mpp_bench.nonfinite_outputs;mpp_bench.phase=3;
 }
 uint32_t bits;__builtin_memcpy(&bits,&mpp_bench_output[7],sizeof(bits));mpp_bench.last_output_bits=bits;
 ++mpp_bench.runs;
 if(mpp_bench.runs>1&&previous_tx==t){++mpp_bench.repeated_half;mpp_bench.phase=4;}
 // Includes housekeeping, zeroing, synthetic input, A2, DWT accounting and
 // output validation. Timer services are the original stock implementation.
 ((float(*)(void))0x11671u)();
 uint32_t ticks=read32(0x2000e490u);mpp_bench.timer_last=ticks;
 if(!ticks||ticks>=100000||read32(0x400ec000u)!=0x46u){
  ++mpp_bench.timer_invalid;mpp_bench.phase=4;
 }else{
  if(ticks>mpp_bench.timer_max)mpp_bench.timer_max=ticks;
  if(ticks<mpp_bench.timer_min)mpp_bench.timer_min=ticks;
  uint32_t old=mpp_bench.timer_sum_lo;mpp_bench.timer_sum_lo=old+ticks;
  if(mpp_bench.timer_sum_lo<old)++mpp_bench.timer_sum_hi;
  // Conservative conditional 150-us body threshold (nominal period 166.7us).
  // This bounds further processing; it cannot preempt an already late batch.
  if(ticks>=150){++mpp_bench.timer_limit_hits;mpp_bench.phase=4;}
 }
 if(mpp_bench.runs>=60000&&mpp_bench.phase==1)mpp_bench.phase=2;
}

extern "C" void mpp_probe_version(const uint8_t* p,unsigned n,unsigned channel){
 if(n!=4||p[0]!=0xf0||p[1]!=0x43||p[2]!=0x58||p[3]!=0||p[4]!=0xf7||channel>1)return;
 uint8_t reply[45]={};reply[0]=0xf0;reply[1]=0x43;reply[2]=0x58;reply[3]=0x10;
 const uint8_t product[8]={'P','L','U','G','P','R','O',0};
 for(unsigned i=0;i<8;++i){reply[i+4]=mpp_probe_identity[i];reply[i+36]=product[i];}
 reply[28]=0x10;reply[44]=0xf7;
 ((void(*)(const uint8_t*,unsigned,unsigned))0xae81u)(reply,45,channel);
}

extern "C" void mpp_probe_query(const uint8_t* p,unsigned n,unsigned channel){
 if(n!=9||channel>1||p[0]!=0xf0||p[1]!=0x43||p[2]!=0x58||p[3]!=0x70||
    p[4]!=4||p[5]!=2||p[6]!='N'||p[7]!='P'||p[8]>=128||p[9]!=0xf7)return;
 unsigned page=p[8];uint32_t value=0;uint8_t status=0;
 if(page<32)value=read32((uint32_t)(uintptr_t)&mpp_bench+4*page);
 else if(page>=32&&page<56)value=read32(regs[page-32]);
 else status=1;
 uint8_t reply[8]={1,(uint8_t)page,status,0,0,0,0,0};
 for(unsigned i=0;i<5;++i)reply[3+i]=(value>>(7*i))&127u;
 ((void(*)(unsigned,unsigned,const uint8_t*,unsigned,unsigned))0xa18bu)(4,2,reply,8,channel);
}
extern "C" void __aeabi_memclr4(void* dst,unsigned n){
 volatile uint8_t* p=(volatile uint8_t*)dst;while(n--)*p++=0;
}
static_assert(sizeof(Bench)==128);
