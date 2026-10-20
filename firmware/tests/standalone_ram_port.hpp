#pragma once
#include "../target/standalone/platform.hpp"
#include "../target/board/codec_control.hpp"
namespace mpp::standalone::test {
// A deterministic RAM-only peripheral simulator, shared by native and ARM
// tests. It has no MMIO dereferences, audio APIs, USB APIs or device backend.
struct RamPort {
 Request trace[128]{};
 uint32_t calls=0,fail_call=0,read_calls=0,fail_read=0;
 uint32_t control=0,lock_after=1,lock_polls=0,waiting=0;
 uint32_t muted=0,running=0,prepared=0,installed=0;
 uint32_t fail_stop=0;
 uint32_t codec_starts=0,codec_stops=0,codec_bytes=0,nack_byte=0;
 uint8_t codec_trace[63]{};
 uint32_t tick=0,tick_step=100,tick_calls=0,fail_tick=0;
 static bool request(void* ptr,Request r){
  auto& s=*static_cast<RamPort*>(ptr);if(s.calls<128)s.trace[s.calls]=r;
  if(++s.calls==s.fail_call)return false;
  switch(r.op){
   case Op::HoldOutputs:s.muted=1;break;
   case Op::StopAudio:if(s.fail_stop)return false;s.running=0;break;
   case Op::PrepareMemory:s.prepared=1;break;
   case Op::AnalogWrite:if(r.a==8&&r.b==0x2000){s.waiting=1;s.control&=~0x20000000u;}break;
   case Op::Write32:if(r.a==0x40c84300)s.control=r.b;break;
   case Op::InstallDma:if(!s.prepared||!s.muted)return false;s.installed=1;break;
   case Op::StartAudio:if(!s.installed||!s.muted)return false;s.running=1;break;
   default:break;
  }return true;
 }
 static bool read(void* ptr,uint32_t addr,uint32_t* value){
  auto& s=*static_cast<RamPort*>(ptr);if(++s.read_calls==s.fail_read||addr!=0x40c84300)return false;
  if(s.waiting&&++s.lock_polls>=s.lock_after&&s.lock_after)s.control|=0x20000000;
  *value=s.control;return true;
 }
 static bool ticks(void* ptr,uint32_t* value){auto& s=*static_cast<RamPort*>(ptr);if(++s.tick_calls==s.fail_tick)return false;*value=s.tick;s.tick+=s.tick_step;return true;}
 static bool start(void* ptr){++static_cast<RamPort*>(ptr)->codec_starts;return true;}
 static bool byte(void* ptr,uint8_t v){auto& s=*static_cast<RamPort*>(ptr);if(s.codec_bytes<63)s.codec_trace[s.codec_bytes]=v;return ++s.codec_bytes!=s.nack_byte;}
 static void stop(void* ptr){++static_cast<RamPort*>(ptr)->codec_stops;}
 Port port(){return {this,request,read,ticks};}
 board::I2cBus bus(){return {this,start,byte,stop};}
};
}
