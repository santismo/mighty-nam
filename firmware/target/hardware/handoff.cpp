#include "handoff.hpp"
namespace mpp::hardware {
bool prepare_core_handoff(RegisterBus b,CoreState core,uint32_t vector,HandoffSnapshot& out){
 if(core.ipsr||core.control||core.primask!=1||(vector&1023)||vector>0x3fc00||!b.read||!b.write||!b.barrier)return false;
 auto rd=[&](uint32_t a,uint32_t& v){return b.read(b.context,4,a,&v);};
 auto wr=[&](uint32_t a,uint32_t v){return b.write(b.context,4,a,v);};
 HandoffSnapshot s{};uint32_t ictr,cpacr;
 if(!rd(0xe000ed08,s.old_vtor)||!rd(0xe000ed14,s.ccr)||!rd(0xe000ed94,s.mpu_ctrl)
  ||!rd(0xe000ef90,s.itcm_ctrl)||!rd(0xe000ef94,s.dtcm_ctrl)||!rd(0x400e4044,s.flexram_gpr17)
  ||!rd(0x40cc0000,s.root_m7)||!rd(0xe000e004,ictr)||!rd(0xe000ed88,cpacr))return false;
 s.nvic_banks=(ictr&15)+1;if(s.nvic_banks>8)return false;
 out=s;
 // Preserve enabled/dirty caches, MPU, FlexRAM and CPU clocks. Do not infer
 // ownership from their current state. No global cache invalidation is safe here.
 if(!wr(0xe000e010,0)||!wr(0xe000ed04,0x0a000000))return false; // clear pending SysTick/PendSV
 for(uint32_t i=0;i<s.nvic_banks;++i)if(!wr(0xe000e180+4*i,0xffffffff)||!wr(0xe000e280+4*i,0xffffffff))return false;
 if(!b.barrier(b.context)||!wr(0xe000ed08,vector)||!wr(0xe000ed88,cpacr|0xf00000)||!b.barrier(b.context))return false;
 // Watchdog shutdown requires its own verified unlock/update contract. This
 // helper does not claim loader independence or release interrupts.
 return true;
}
}
