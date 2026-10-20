#pragma once
#include <stdint.h>
namespace mpp::board {
// An abstract bus, allowing the same control logic to be tested without pins.
// Backend must implement open-drain/release, pull-ups and bounded clock stretching.
struct I2cBus {
 void* context;
 bool (*start)(void*);
 bool (*write_byte)(void*,uint8_t); // True on ACK, false on NACK/timeout.
 void (*stop)(void*);
 bool (*healthy)(void*)=nullptr; // Optional sticky status, including STOP failure.
};
bool codec_write_register(I2cBus&,uint8_t reg,uint8_t value);
// Replays recovered register values only to the supplied bus abstraction.
// Reset/clock timing and physical muting remain responsibilities of board bring-up.
bool codec_replay_stock_config(I2cBus&);
}
