#pragma once
#include <stdint.h>
extern "C" void mpp_reply_init();
extern "C" void mpp_reply_send(const uint8_t*,unsigned,unsigned);
extern "C" void mpp_reply_query(const uint8_t*,unsigned,unsigned);
