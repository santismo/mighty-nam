#pragma once
#include <stdint.h>
namespace mpp::board {
constexpr unsigned slots=4, frames=8, words=slots*frames;
constexpr uint32_t sai1=0x40404000, sai_rx=sai1+0xa0, sai_tx=sai1+0x20;
// Explicitly serialized DMA descriptor layout, matching RT1176 eDMA TCD.
struct Tcd {
 uint32_t saddr; int16_t soff; uint16_t attr; uint32_t nbytes; int32_t slast;
 uint32_t daddr; int16_t doff; uint16_t citer; uint32_t next; uint16_t csr,biter;
};
static_assert(sizeof(Tcd)==32);
// Caller supplies verified DMA-visible addresses. Builds in RAM only; no MMIO.
bool make_tcd_ring(Tcd (&out)[4], uint32_t rx, uint32_t tx, uint32_t descriptors);
// Read the current RX TCD next pointer after scatter/gather reload.
bool completed_rx_half(uint32_t current_next,uint32_t descriptors,unsigned& half);
struct RegisterValue {uint32_t address,value;};
// Configuration values decoded from saved V1.5.6, assuming reset register state.
// Does not enable the engines; target/hardware supplies the register backend.
extern const RegisterValue sai_configuration[12];
extern const uint8_t stock_codec_registers[21];
constexpr uint8_t codec_address_7bit=0x10;
constexpr unsigned codec_sda_gpio=11, codec_sda_bit=14, codec_scl_gpio=11, codec_scl_bit=13;
constexpr unsigned codec_reset_gpio=8, codec_reset_bit=0;
void unpack_q31(const int32_t* interleaved, float (&channels)[4][8]);
void pack_q31(const float (&channels)[4][8], int32_t* interleaved);
using Processor=bool(*)(void*,const float*,float*,unsigned);
class AudioBridge {
public:
 // Channels must be supplied explicitly: physical guitar/headphone routing is
 // not yet verified. Output remains zero until set_muted(false) is called.
 bool configure(unsigned input_slot, unsigned output_mask, Processor, void*);
 void set_muted(bool value) {muted_=value;}
 bool process(const int32_t* rx, int32_t* tx);
private:
 unsigned input_=0, mask_=0; Processor process_=nullptr; void* context_=nullptr;
 bool configured_=false, muted_=true;
 float planar_[4][8]{}, mono_[8]{};
};
}
