#pragma once
#include <stdint.h>

namespace mpp::presets {
constexpr unsigned count=7, record_bytes=8192, model_bytes=7516;
constexpr uint32_t base=0x30384000, end=base+count*2*record_bytes;
constexpr uint32_t magic=0x3142504e, commit=0x454e4f44;
// Each color has two independently erasable copies. Never erase the newest
// valid copy; write/read back the other copy, then program its commit marker.
struct IO {
 void* context;
 bool (*read)(void*,uint32_t,uint8_t*,unsigned);
 bool (*erase)(void*,uint32_t);
 bool (*program)(void*,uint32_t,const uint8_t*,unsigned);
};
enum Result : unsigned { ok=0, empty=1, invalid=2, io_error=3, exhausted=4 };
uint32_t word(const uint8_t*,unsigned);
void put(uint8_t*,unsigned,uint32_t);
bool valid_model(const uint8_t*);
bool valid_effects(const uint8_t*);
class Bank {
 public:
  explicit Bank(IO io):io_(io){}
  // Scratch buffers are caller-owned and never overlap model/audio storage.
  Result read(unsigned slot,uint8_t* record,uint8_t* scratch,unsigned* copy=nullptr);
  Result save(unsigned slot,const uint8_t* model,const uint8_t* effects,
              const uint8_t* sha,const uint8_t* name,unsigned flags,unsigned buffer,
              uint8_t* record,uint8_t* scratch);
  static bool valid(const uint8_t*,unsigned);
  static void unpack_model(const uint8_t* record,uint8_t* model);
 private:
  IO io_;
};
}
