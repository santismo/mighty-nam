#include "model_receiver.hpp"


namespace mpp::link {
static void copy(uint8_t* a,const uint8_t* b,unsigned n){for(unsigned i=0;i<n;i++)a[i]=b[i];}
static bool equal(const uint8_t* a,const uint8_t* b,unsigned n){for(unsigned i=0;i<n;i++)if(a[i]!=b[i])return false;return true;}
static uint32_t rd(const uint8_t* p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
static void wr(uint8_t* p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=uint8_t(v>>(8*i));}
uint32_t crc32(const uint8_t* p,unsigned n){uint32_t c=0xffffffff;for(unsigned i=0;i<n;i++){c^=p[i];for(unsigned b=0;b<8;b++)c=(c>>1)^((c&1)?0xedb88320:0);}return c^0xffffffff;}
static bool valid_slot(const uint8_t* p){
 const uint32_t header[]={0x3241504d,1,48000,1871,7484};
 for(unsigned i=0;i<5;i++)if(rd(p+4*i)!=header[i])return false;
 if(rd(p+24)!=1||rd(p+28)!=0||rd(p+20)!=crc32(p+32,7484))return false;
 for(unsigned i=32;i<7516;i+=4)if((rd(p+i)&0x7f800000)==0x7f800000)return false;
 for(unsigned i=7516;i<slot_bytes;i++)if(p[i]!=0xff)return false;
 return true;
}
void ModelReceiver::reset(){
 // Volatile bank deliberately has no pretend persistence across any reset.
 active_valid_=staging_valid_=false;session_=received_=expected_=committed_=0;
 for(auto& byte:active_)byte=0;for(auto& byte:staging_)byte=0;
}
#ifdef MPP_PRESET_BANK
__attribute__((section(".banktext"))) bool ModelReceiver::restore_slot(const uint8_t* p){
 if(!p||!valid_slot(p))return false;
 copy(active_,p,slot_bytes);active_valid_=true;staging_valid_=false;
 session_=received_=expected_=committed_=0;return true;
}
#endif
bool ModelReceiver::exchange(const uint8_t* p,unsigned n,uint8_t* out,unsigned cap,unsigned& out_n){
 out_n=0;
 if(!p||!out||cap<48||n<24||n>max_packet)return false;
 const unsigned len=unsigned(p[6])|(unsigned(p[7])<<8);
 if(rd(p)!=0x314c504d||p[4]!=1||n!=24+len||rd(p+20)!=crc32(p,20)||rd(p+16)!=crc32(p+24,len))return false;
 const unsigned op=p[5];const uint32_t session=rd(p+8),offset=rd(p+12);const auto* data=p+24;uint32_t status=0;
 switch(op){
 case 1:
  if(session||offset||len)status=1;break;
 case 2:
  if(len!=8||offset||!session){status=1;break;}
  if(rd(data)!=slot_bytes){status=3;break;}
  if(staging_valid_){if(session_!=session||expected_!=rd(data+4))status=4;}
  else if(session==committed_)status=4;
  else {session_=session;received_=0;expected_=rd(data+4);staging_valid_=true;}
  break;
 case 3:
  if(!staging_valid_||session!=session_){status=2;break;}
  if(!len||offset>slot_bytes||len>slot_bytes-offset){status=3;break;}
  if(offset<received_){if(len>received_-offset||!equal(staging_+offset,data,len))status=4;}
  else if(offset!=received_)status=4;
  else {copy(staging_+offset,data,len);received_+=len;}
  break;
 case 4:
  if(len||offset||!session){status=1;break;}
  if(!staging_valid_&&committed_==session)break;
  if(!staging_valid_||session!=session_){status=2;break;}
  if(received_!=slot_bytes){status=6;break;}
  if(crc32(staging_,slot_bytes)!=expected_||!valid_slot(staging_)){status=5;break;}
  copy(active_,staging_,slot_bytes);active_valid_=true;staging_valid_=false;committed_=session;break;
 case 5:
  if(len||offset||!session){status=1;break;}
  if(session!=session_){status=2;break;}
  staging_valid_=false;received_=0;break;
 case 6:
  if(len||offset||session!=session_)status=2;break;
 default:status=1;
 }
 for(unsigned i=0;i<48;i++)out[i]=0;wr(out,0x314c504d);out[4]=1;out[5]=uint8_t(op|0x80);out[6]=24;wr(out+8,session);
 const uint32_t fields[]={status,received_,active_crc(),slot_bytes,max_payload,3};
 for(unsigned i=0;i<6;i++)wr(out+24+4*i,fields[i]);
 wr(out+16,crc32(out+24,24));wr(out+20,crc32(out,20));out_n=48;return true;
}
bool ModelReceiver::load_active(A2Lite& engine,bool quiet) const{
 float weights[1871];
 return load_active(engine,quiet,weights,1871);
}
bool ModelReceiver::load_active(A2Lite& engine,bool quiet,float* weights,unsigned count) const{
 if(!quiet||!active_valid_||!weights||count!=1871)return false;
 for(unsigned i=0;i<1871;i++){uint32_t bits=rd(active_+32+4*i);__builtin_memcpy(weights+i,&bits,4);}
 return engine.load(weights,1871);
}
}
