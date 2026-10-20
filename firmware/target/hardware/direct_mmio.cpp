#include "handoff.hpp"
#if !defined(__arm__) || !defined(__ARM_ARCH_7EM__)
#error This adapter is Cortex-M7 code, never a Mac host backend.
#endif
namespace mpp::hardware {
CoreState direct_core_state(){CoreState s;
 __asm volatile("mrs %0, ipsr":"=r"(s.ipsr));
 __asm volatile("mrs %0, control":"=r"(s.control));
 __asm volatile("mrs %0, primask":"=r"(s.primask));
 return s;
}
RegisterBus direct_mmio_bus(){return {nullptr,
 [](void*,unsigned w,uint32_t a,uint32_t* v){
  if(!v||!a||(a&(w-1)))return false;
  if(w==1)*v=*reinterpret_cast<volatile uint8_t*>(a);
  else if(w==2)*v=*reinterpret_cast<volatile uint16_t*>(a);
  else if(w==4)*v=*reinterpret_cast<volatile uint32_t*>(a);
  else return false;return true;
 },
 [](void*,unsigned w,uint32_t a,uint32_t v){
  if(!a||(a&(w-1)))return false;
  if(w==1)*reinterpret_cast<volatile uint8_t*>(a)=uint8_t(v);
  else if(w==2)*reinterpret_cast<volatile uint16_t*>(a)=uint16_t(v);
  else if(w==4)*reinterpret_cast<volatile uint32_t*>(a)=v;
  else return false;return true;
 },
 [](void*){__asm volatile("dsb sy\n\tisb sy":::"memory");return true;}};}
}
