#pragma once
#include "platform.hpp"
#include "../board/audio_transport.hpp"
#include "../board/codec_control.hpp"
#include "../a2/a2_lite.hpp"
namespace mpp::standalone {
struct alignas(32) DmaMemory {
 int32_t rx[64]{};
 int32_t tx[64]{};
 board::Tcd descriptors[4]{};
};
static_assert(sizeof(DmaMemory)==640);
struct Config {
 uint32_t dma_address; // Logical bus address; physical ownership remains unproven.
 uint32_t input_slot;
 uint32_t pll_poll_limit;
 uint32_t deadline_ticks; // Backend clock units; physical calibration unverified.
};
enum class State : uint32_t { Reset, Starting, RunningSilent, Fault };
enum class Error : uint32_t { None, Port, Configuration, ClockTimeout, Codec, Model,
 Sequence, Buffer, Timing, Nonfinite };
struct Event {
 uint32_t sequence,rx_half,tx_writable_half;
};
struct Status {
 State state;
 Error error;
 uint32_t blocks,samples,maximum_ticks,expected_sequence,cleanup_failed;
};
class Prototype {
public:
 bool boot(Port,board::I2cBus,Config,DmaMemory&,const float*,unsigned);
 bool audio_event(Event);
 void stop();
 const Status& status()const{return status_;}
 const float* diagnostic_samples()const{return output_;}
private:
 bool fail(Error);
 bool cleanup();
 Port port_{};
 Config config_{};
 DmaMemory* dma_=nullptr;
 Status status_{};
 uint32_t last_rx_=0,last_tx_=0;
 bool have_event_=false,dma_ready_=false;
 mpp::A2Lite model_{};
 float input_[8]{},output_[8]{};
};
}
