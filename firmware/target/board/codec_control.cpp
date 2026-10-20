#include "codec_control.hpp"
#include "audio_transport.hpp"
namespace mpp::board {
bool codec_write_register(I2cBus& bus,uint8_t reg,uint8_t value) {
 if(!bus.start||!bus.write_byte||!bus.stop||reg>=21)return false;
 if(!bus.start(bus.context)){bus.stop(bus.context);return false;}
 bool ok=bus.write_byte(bus.context,codec_address_7bit<<1)
   &&bus.write_byte(bus.context,reg)&&bus.write_byte(bus.context,value);
 bus.stop(bus.context);return ok&&(!bus.healthy||bus.healthy(bus.context));
}
bool codec_replay_stock_config(I2cBus& bus) {
 for(unsigned reg=0;reg<21;++reg)if(!codec_write_register(bus,reg,stock_codec_registers[reg]))return false;
 return true;
}
}
