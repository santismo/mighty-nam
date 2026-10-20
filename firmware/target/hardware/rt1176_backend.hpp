#pragma once
#include "../standalone/prototype.hpp"
namespace mpp::hardware {
// Every peripheral access is width-explicit. The host supplies a register model;
// direct_mmio.cpp is ARM-only and is never linked into a host executable.
struct RegisterBus {
 void* context;
 bool (*read)(void*,unsigned width,uint32_t address,uint32_t*);
 bool (*write)(void*,unsigned width,uint32_t address,uint32_t value);
 bool (*barrier)(void*);
};
struct BackendConfig {
 uint32_t dma_address;
 uint32_t cpu_hz; // Must be established by handoff/clock setup, not guessed.
 uint32_t poll_limit;
};
enum class Release { Pending, Ready, Fault };
class Rt1176Backend {
public:
 Rt1176Backend(RegisterBus bus,BackendConfig cfg,standalone::DmaMemory& memory)
  :bus_(bus),cfg_(cfg),memory_(memory){}
 standalone::Port port();
 board::I2cBus codec_bus();
 Release poll_release(standalone::Event&); // Diagnostic polling; IRQ stays masked.
 bool running()const{return running_;}
 bool bus_healthy()const{return !i2c_fault_;}
private:
 RegisterBus bus_;BackendConfig cfg_;standalone::DmaMemory& memory_;
 bool stopped_=false,prepared_=false,pins_=false,installed_=false,running_=false;
 bool i2c_fault_=false,have_release_=false,sai_reset_=false;
 uint32_t sequence_=0,last_rx_=0,last_tx_=0,configured_sai_=0;
 bool read(uint32_t,uint32_t&,unsigned=4);
 bool write(uint32_t,uint32_t,unsigned=4);
 bool barrier();
 bool modify(uint32_t,uint32_t clear,uint32_t set);
 bool wait(uint32_t,uint32_t mask,uint32_t value,unsigned=4);
 bool request(standalone::Request);
 bool ticks(uint32_t&);
 bool delay_us(uint32_t);
 bool cache(uint32_t,uint32_t,uint32_t);
 bool analog(bool ldo,bool read,uint32_t reg,uint32_t& value);
 bool audio_ldo();
 bool hold();bool stop();bool prepare();bool pins();bool install();bool start();
 bool gpio_line(uint32_t,bool release);bool scl_high();
 bool i2c_start();bool i2c_byte(uint8_t);bool i2c_stop();
};
// Cortex-M7 only. Also linked into the offline entry diagnostic; no upload API.
RegisterBus direct_mmio_bus();
}
