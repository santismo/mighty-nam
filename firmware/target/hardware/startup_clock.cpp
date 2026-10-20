#include "startup_clock.hpp"
namespace mpp::hardware {
ClockCheck inspect_startup_clock(RegisterBus bus,uint32_t reference,ClockReport& out){
 out={ClockCheck::BusError,0,0,0,0,reference,0};
 auto finish=[&](ClockCheck r){out.result=r;return r;};
 if(!bus.read)return out.result;
 constexpr uint32_t addresses[]={0x40cc0000,0x40cc0020,0x40cc0024,0x40c84200};
 uint32_t a[4],b[4];
 for(unsigned i=0;i<4;++i)if(!bus.read(bus.context,4,addresses[i],&a[i]))return out.result;
 for(unsigned i=0;i<4;++i)if(!bus.read(bus.context,4,addresses[i],&b[i]))return out.result;
 out.root_control=a[0];out.root_status0=a[1];out.root_status1=a[2];out.arm_pll=a[3];
 for(unsigned i=0;i<4;++i)if(a[i]!=b[i])return finish(ClockCheck::UnstableSnapshot);
 if((a[1]&0xf0000000)||((a[0]^a[1])&0x010007ff)||
    (a[2]&0x05000000)||((a[2]>>16)&15)!=((a[2]>>20)&15))
  return finish(ClockCheck::UnstableSnapshot);
 if((a[0]&0x01000000)||(a[1]&0x09000000))return finish(ClockCheck::RootInactive);
 if(((a[1]>>8)&7)!=4)return finish(ClockCheck::UnsupportedSource);
 // Reject hardware-managed PLL state, bypass, gating and startup. Only the
 // software-owned, stable ARM PLL path has a supported rate calculation here.
 if((a[3]&0xc0021000)||((a[3]&0x20006000)!=0x20006000))return finish(ClockCheck::PllUnready);
 if(!reference)return finish(ClockCheck::ReferenceUnknown);
 // This implementation deliberately supports the documented nominal 24MHz
 // reference only. Other references need a separate validated clock contract.
 if(reference!=24000000)return finish(ClockCheck::InvalidReference);
 const uint32_t feedback=a[3]&255,post=(a[3]>>15)&3;
 if(feedback<104||feedback>208)return finish(ClockCheck::InvalidDivider);
 const uint32_t divisor=2*(post==3?1u:(2u<<post))*((a[1]&255)+1);
 // Bound the reference before multiplication; no uint64 divide helper needed.
 const uint32_t half_reference=reference/2;
 const uint32_t numerator=half_reference*feedback;
 const uint32_t half_divisor=divisor/2;
 if(numerator%half_divisor)return finish(ClockCheck::NonintegralRate);
 out.derived_hz=numerator/half_divisor;
 return finish(ClockCheck::Derived);
}
}
