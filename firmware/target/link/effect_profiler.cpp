// NAMLNK11: opt-in measurement of one selected stock-chain stage per block.
// Counter reads only; never changes the audio clock, counter or output state.
#include <stdint.h>
extern "C" {
extern uint16_t mpp_bypass_hold[11];
extern volatile uint32_t mpp_dwt_reset_epoch;
volatile uint32_t mpp_profile_selected; // zero disabled; stage id + 1 otherwise
volatile uint32_t mpp_profile_sequence, mpp_profile_generation;
volatile uint32_t mpp_profile_stats[11][8];
static uint32_t snapshot[90],snapshot_ready;
static uint32_t read32(uintptr_t a){return *(volatile uint32_t*)a;}
static void increment(volatile uint32_t& value){if(value!=0xffffffffu)++value;}
static bool asleep(unsigned stage){
 if(stage==0||stage==3||stage>9)return false;
 const auto* preset=(const volatile uint8_t*)(uintptr_t)read32(0x20005ad0);
 uint16_t& hold=mpp_bypass_hold[stage];
 if(!(preset[stage]&64)){hold=(stage==5||stage==7||stage==8)?65535:1200;return false;}
 if(!hold)return true;
 if(hold!=65535)--hold;
 return false;
}
using Callback=void(*)(const float*,const float*,float*,float*);
void mpp_profile_dispatch(unsigned stage,Callback callback,const float* l,const float* r,float* ol,float* orr){
 // Called only for the exact selected id from the audited dispatcher. The
 // mode cannot change inside this audio IRQ because commands require thread mode.
 ++mpp_profile_sequence;
 auto& s=mpp_profile_stats[stage];
 const uint32_t epoch=mpp_dwt_reset_epoch,ctrl=read32(0xe0001000);
 const uint32_t start=read32(0xe0001004);
 const bool sleeping=asleep(stage);
 if(sleeping){for(unsigned i=0;i<8;++i){float a=l[i],b=r[i];ol[i]=a;orr[i]=b;}}
 else callback(l,r,ol,orr);
 const uint32_t end=read32(0xe0001004),after=read32(0xe0001000);
 const uint32_t span=end-start;
 unsigned flags=0;
 if(!(ctrl&1)||ctrl!=after)flags|=1;
 if(epoch!=mpp_dwt_reset_epoch)flags|=2;
 if(!span||span>=0x80000000u)flags|=4;
 if(s[0]==0xffffffffu)flags|=8;
 increment(s[0]);
 if(flags){increment(s[2]);s[7]|=flags;}
 else {
  increment(s[1]);s[3]=span;
  // Match the IRQ recorder's explicit branch: Unicorn's protected-RAM
  // observer mishandles IT/predicated stores and can skip a later branch.
  const uint32_t maximum=s[4];
  __asm__ volatile("cmp %0,%1\nbls 1f\nstr %0,[%2]\n1:"
    ::"r"(span),"r"(maximum),"r"(&s[4]):"cc","memory");
 }
 const auto* preset=(const volatile uint8_t*)(uintptr_t)read32(0x20005ad0);
 if(preset[stage]&64)increment(s[5]);
 if(sleeping)increment(s[6]);
 ++mpp_profile_sequence;
}
// stage 0..10 selects; 127 disables; 126 disables and clears. No flash writes.
void mpp_profile_control(unsigned command){
 if(command>10&&command!=126&&command!=127)return;
 mpp_profile_selected=0;
 __asm__ volatile("dmb":::"memory");
 ++mpp_profile_sequence;
 if(command==126)for(auto& row:mpp_profile_stats)for(auto& value:row)value=0;
 ++mpp_profile_generation;
 mpp_profile_selected=command<=10?command+1:0;
 ++mpp_profile_sequence;
}
// 26 freezes a bounded snapshot, 27..116 read it. Existing pages are unchanged.
unsigned mpp_profile_page(unsigned page,uint32_t* value){
 if(page==26){
  snapshot_ready=0;
  for(unsigned attempt=0;attempt<3;++attempt){
   uint32_t sequence=mpp_profile_sequence;
   snapshot[0]=mpp_profile_selected;snapshot[1]=mpp_profile_generation;
   for(unsigned stage=0;stage<11;++stage)for(unsigned field=0;field<8;++field)
    snapshot[2+stage*8+field]=mpp_profile_stats[stage][field];
   __asm__ volatile("dmb":::"memory");
   if(!(sequence&1)&&sequence==mpp_profile_sequence){snapshot_ready=1;*value=0x46585031;return 0;}
  }
  return 2;
 }
 if(page<27||page>116)return 1;
 if(!snapshot_ready)return 3;
 *value=snapshot[page-27];return 0;
}
}
