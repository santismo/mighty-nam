#pragma once
#include <stdint.h>
namespace mpp::standalone {
// Every callback must be bounded and report failure. The original VM port uses
// RAM only; target/hardware adds register algorithms, tested against a model.
enum class Op : uint32_t {
 HoldOutputs=1, StopAudio, PrepareMemory, PreparePins, AudioLdo,
 AnalogWrite, AnalogModify, Write32, DelayUnits, CodecReset,
 InstallDma, PublishTx, AcquireRx, StartAudio
};
struct Request { Op op; uint32_t a=0,b=0,c=0,d=0; };
struct Port {
 void* context;
 bool (*request)(void*,Request);
 bool (*read32)(void*,uint32_t,uint32_t*);
 bool (*ticks)(void*,uint32_t*);
};
inline bool issue(const Port& p,Op op,uint32_t a=0,uint32_t b=0,uint32_t c=0,uint32_t d=0) {
 return p.request && p.request(p.context,{op,a,b,c,d});
}
enum class ClockResult : uint32_t { Ready, PortError, LockTimeout };
ClockResult configure_audio_clock(const Port&,unsigned poll_limit);
}
