#include "tuner_capture.hpp"
#include "model_receiver.hpp"
#include "sysex_codec.hpp"
#include "listening.hpp"
namespace {
mpp::tuner::Capture capture;
uint8_t reply[280],wire[330];
void word(unsigned at,uint32_t value){for(unsigned i=0;i<4;++i)reply[at+i]=value>>(8*i);}
}
extern "C" void mpp_tuner_init(){capture.reset();}
extern "C" void mpp_tuner_feed(const int32_t* rx){
 if(!capture.enabled)return;
 if(mpp_listen_enabled){capture.stop();return;}
 capture.feed(rx);
}
extern "C" void mpp_tuner_query(const uint8_t* p,unsigned n,unsigned channel){
 if((*(volatile uint32_t*)0xe000ed04&511)||n!=13||p[8]!=1||p[9]>2||p[10]>15||
    p[11]>127||p[12]>127||!(p[11]|p[12])||(p[9]!=2&&p[10]))return;
 const unsigned op=p[9],page=p[10];unsigned error=0;
 if(op==0)capture.stop();
 if(op==1){if(mpp_listen_enabled)error=3;else capture.start();}
 if(op==2&&capture.count!=2048)error=1;
 for(auto& b:reply)b=0;
 word(0,0x31554e4d);reply[4]=1;reply[5]=op|128;reply[6]=page;reply[7]=error;
 word(8,p[11]|(p[12]<<7));word(12,capture.generation);
 reply[16]=12000&255;reply[17]=12000>>8;
 const unsigned count=capture.count;reply[18]=count&255;reply[19]=count>>8;
 if(op==2&&!error){
  for(unsigned i=0;i<128;++i){uint16_t s=(uint16_t)capture.samples[page*128+i];reply[20+i*2]=s;reply[21+i*2]=s>>8;}
 }
 word(276,mpp::link::crc32(reply,276));
 const uint8_t prefix[]={0xf0,0x43,0x58,0x70,4,2,'N','U',1};
 for(unsigned i=0;i<9;++i)wire[i]=prefix[i];
 unsigned size=mpp::link::pack7(reply,280,wire+9,320);
 if(size==320){wire[329]=0xf7;((void(*)(const uint8_t*,unsigned,unsigned))0xae81)(wire,330,channel);}
}
