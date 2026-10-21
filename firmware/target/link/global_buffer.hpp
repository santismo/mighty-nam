#pragma once
#include "preset_bank.hpp"

namespace mpp::settings {
// Two sectors inside the already-audited retired AMP resource, beyond the
// copied-code source (0x303a0000..0x303a4000) and outside all seven presets.
constexpr uint32_t base=0x303a4000, end=base+8192;
constexpr unsigned bytes=256;
class BufferStore {
 public:
  explicit BufferStore(presets::IO io):io_(io){}
  presets::Result load(uint8_t*,uint8_t*,unsigned* copy=nullptr);
  presets::Result save(unsigned,uint8_t*,uint8_t*);
  static bool valid(const uint8_t*);
 private:
  presets::IO io_;
};
}
