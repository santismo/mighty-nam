#pragma once
#include <stdint.h>
extern "C" {
void mpp_bank_init();
#ifdef MPP_GLOBAL_BUFFER
void mpp_global_buffer_set(unsigned);
#endif
void mpp_bank_service();
void mpp_bank_request(unsigned);
void mpp_bank_query(const uint8_t*,unsigned,unsigned);
uint32_t mpp_bank_page();
const uint8_t* mpp_bank_model();
bool mpp_bank_load(const uint8_t*);
void mpp_bank_pause();
void mpp_bank_clear();
void mpp_bank_resume(bool);
}
