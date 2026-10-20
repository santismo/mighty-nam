#pragma once
#include <stdint.h>
#include "../a2/a2_lite.hpp"

namespace mpp::link {
constexpr unsigned slot_bytes=8192, max_payload=256, max_packet=280;
uint32_t crc32(const uint8_t*, unsigned);
// Private application protocol; never the factory HID/DFU protocol. RAM only.
// Feed complete framed packets from a FUTURE custom transport. No driver,
// flash API, reset operation or arbitrary address is exposed by this object.
class ModelReceiver {
 public:
  void reset();
  bool exchange(const uint8_t* request,unsigned length,uint8_t* response,unsigned capacity,unsigned& response_length);
  bool has_model() const {return active_valid_;}
  uint32_t active_crc() const {return active_valid_?crc32(active_,slot_bytes):0;}
  const uint8_t* active_slot() const {return active_valid_?active_:nullptr;}
#ifdef MPP_PRESET_BANK
  bool restore_slot(const uint8_t*);
#endif
  // Caller must serialize exchange/load_active and stop DSP first. This is not
  // an ISR-safe hot-swap. The receiver itself never starts or unmutes audio.
  bool load_active(A2Lite& engine,bool audio_quiescent) const;
  // Target callers provide RAM scratch rather than consuming 7.5 KiB of stack.
  bool load_active(A2Lite& engine,bool audio_quiescent,
                   float* scratch,unsigned count) const;
 private:
  alignas(4) uint8_t active_[slot_bytes]{}, staging_[slot_bytes]{};
  uint32_t session_=0,received_=0,expected_=0,committed_=0;
  bool active_valid_=false,staging_valid_=false;
};
}
