#pragma once
namespace mpp::board {
// Freestanding C runtime helper. Caller supplies linker-resolved buffers;
// this function deliberately does not guess the MP-3 loader's memory map.
void initialize_data(const unsigned char* load,unsigned char* data,unsigned count,
                     unsigned char* zero,unsigned zero_count);
}
