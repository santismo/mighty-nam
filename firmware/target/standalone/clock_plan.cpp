#include "platform.hpp"
namespace mpp::standalone {
// Recovered V1.5.6 PLL transaction plan. AI bus handshakes and calibrated delays
// are implemented in the register backend, exercised with a host model only.
// No ROM or NUX function is called.
ClockResult configure_audio_clock(const Port& p,unsigned limit) {
 constexpr uint32_t ctrl=0x40c84300,stable=0x20000000,enable=0x2000,gate=0x4000;
 uint32_t v=0;
 auto rd=[&](){return p.read32 && p.read32(p.context,ctrl,&v);};
 auto aw=[&](uint32_t reg,uint32_t value){return issue(p,Op::AnalogWrite,reg,value);};
 auto wr=[&](uint32_t value){return issue(p,Op::Write32,ctrl,value);};
 if(!limit||limit>65536||!issue(p,Op::AudioLdo)||!rd())return ClockResult::PortError;
 const bool warm=(v&(stable|enable))==(stable|enable);
 if(!aw(4,0x10000))return ClockResult::PortError;
 if(warm) {
  if(!wr(v&~enable)||!rd()||!wr(v|gate)||!aw(8,0x8000)||!aw(8,0x4000)||!aw(8,0x400000))return ClockResult::PortError;
 }
 if(!rd()||!wr(v|enable)||!aw(8,0x4000)||!aw(0x30,10000)||!aw(0x20,7630)
    ||!issue(p,Op::AnalogModify,0,32,0x7f,0)
    ||!issue(p,Op::AnalogModify,0,1,0x0e000000,25)
    ||!aw(4,0x400000)||!issue(p,Op::DelayUnits,100)
    ||!aw(4,0x6000)||!aw(4,0x2000)||!issue(p,Op::DelayUnits,225)||!aw(8,0x2000))return ClockResult::PortError;
 bool locked=false;
 for(unsigned i=0;i<limit;++i){if(!rd())return ClockResult::PortError;if(v&stable){locked=true;break;}}
 if(!locked)return ClockResult::LockTimeout;
 if(!aw(4,0x8000)||!rd()||!wr(v&~gate)||!aw(8,0x10000))return ClockResult::PortError;
 // Saved SAI1 root selects audio PLL and divides by 16. Reference frequency
 // and runtime trimming remain unmeasured; 48 kHz is a model contract only.
 if(!issue(p,Op::Write32,0x40cc2000,0x40f)
    ||!issue(p,Op::Write32,0x400e4000,0x100)
    ||!issue(p,Op::Write32,0x40cc6f60,1))return ClockResult::PortError;
 return ClockResult::Ready;
}
}
