#pragma once
#include <stdint.h>
namespace mpp::tone {
float gain(unsigned);unsigned record(const uint8_t*);
void defaults(uint8_t*);bool valid(const uint8_t*);void decode(const uint8_t*,uint8_t*);
struct Engine {
 float low,high,gain[6],input[8];bool ready;
 void reset();const float* prepare(const float*,const uint8_t*);
 void finish(const float*,const float*,float*,float*);
};
}
extern "C" {
const float* mpp_nam_input(const float*);
void mpp_nam_output(const float*,const float*,float*,float*);
void mpp_nam_query(const uint8_t*,unsigned,unsigned);
void mpp_usb_begin(bool);
void mpp_usb_finish(float*,float*);
}
