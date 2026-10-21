#include "preset_runtime.hpp"
#include "preset_bank.hpp"
#include "model_receiver.hpp"
#include "sysex_codec.hpp"
#include "listening.hpp"
#ifdef MPP_FX_BLOCKS
#include "fx_blocks.hpp"
#include "reply_transport.hpp"
#endif
using namespace mpp::presets;
namespace {
alignas(4) uint8_t record[8192],scratch[8192],model_slot[8192];
uint8_t headers[7][256],input[132],output[276],wire[330];
unsigned current,occupied,pending;
#ifdef MPP_FX_BLOCKS
uint8_t saved_fx[7][32];
#endif
bool booting,resume_output;
uint32_t rd(uint32_t a){return *(volatile uint32_t*)(uintptr_t)a;}
uint8_t* ptr(uint32_t a){return (uint8_t*)(uintptr_t)a;}
uint32_t lock(){uint32_t p;__asm__ volatile("mrs %0, primask\ncpsid i":"=r"(p)::"memory");return p;}
void unlock(uint32_t p){__asm__ volatile("dsb\nisb\nmsr primask, %0"::"r"(p):"memory");}
bool bounds(uint32_t a,unsigned n){return a>=base&&a<end&&n&&n<=end-a;}
bool read(void*,uint32_t a,uint8_t* b,unsigned n){
 if(!bounds(a,n))return false;
 uint32_t p=lock();int result=((int(*)(void*,uint32_t,unsigned))0xc081)(b,a,n);unlock(p);return result==0;
}
bool erase(void*,uint32_t a){
 if(!bounds(a,4096)||(a&4095))return false;
 uint32_t p=lock();int result=((int(*)(uint32_t))0xbfa5)(a);unlock(p);return result==0;
}
bool program(void*,uint32_t a,const uint8_t* b,unsigned n){
 // The stock primitive writes to the end of its 256-byte page. Only allow
 // precisely that span, including the four-byte final commit at page end.
 if(!bounds(a,n)||n!=256-(a&255))return false;
 uint32_t p=lock();int result=((int(*)(const void*,uint32_t))0xc035)(b,a);unlock(p);return result==0;
}
Bank bank(){return Bank({nullptr,read,erase,program});}
void copy(uint8_t* a,const uint8_t* b,unsigned n){for(unsigned i=0;i<n;++i)a[i]=b[i];}
void mask(){ptr(rd(0x20005ae0))[0x13]=occupied?occupied:127;}
Result read_slot(unsigned slot){
 auto result=bank().read(slot,record,scratch);
 if(result==ok){copy(headers[slot],record,256);occupied|=1u<<slot;
#ifdef MPP_FX_BLOCKS
  if(word(record,7808)==0x33315846)copy(saved_fx[slot],record+7812,32);else mpp::fx::defaults(saved_fx[slot]);
#endif
 }
 else if(result==empty){for(auto& b:headers[slot])b=0;occupied&=~(1u<<slot);}
 mask();return result;
}
Result recall(unsigned slot,bool listen){
 mpp_bank_pause();auto result=read_slot(slot);current=slot;
 if(result!=ok){mpp_bank_clear();return result;}
 Bank::unpack_model(record,model_slot);
 if(!mpp_bank_load(model_slot)){mpp_bank_clear();return invalid;}
 const uint32_t destinations[]={0x20005af0,0x20005b70,0x20012230};
 for(uint32_t dest:destinations)copy(ptr(dest),record+128,128);
 ptr(rd(0x20005ad8))[2]=slot;
#ifdef MPP_FX_BLOCKS
 mpp_fx_set(saved_fx[slot]);
#endif
 mpp_buffer_set(word(record,24));mpp_bank_resume(listen);
 return ok;
}
}
extern "C" void mpp_bank_init(){
 current=pending=255;occupied=0;booting=true;resume_output=false;
 for(auto& h:headers)for(auto& b:h)b=0;
#ifdef MPP_FX_BLOCKS
 for(auto& c:saved_fx)mpp::fx::defaults(c);
#endif
}
extern "C" void mpp_bank_request(unsigned slot){
 if(slot>=7)return;
#ifdef MPP_RESPONSIVE_CONTROLS
 if(pending==255 && slot==current)return; // One saved color wraps to itself: keep playing.
#endif
#ifdef MPP_RESPONSIVE_CONTROLS
 if(pending==255)resume_output=mpp_listen_enabled!=0;
#else
 resume_output=mpp_listen_enabled!=0;
#endif
 mpp_bank_pause();pending=slot;
}
extern "C" void mpp_bank_service(){
 if(rd(0xe000ed04)&511)return;
 if(booting){
  booting=false;mpp_bank_pause();
  for(unsigned i=0;i<7;++i)read_slot(i);
  unsigned selected=ptr(rd(0x20005ad8))[2];
  if(selected>=7||!(occupied&(1u<<selected))){selected=0;while(selected<7&&!(occupied&(1u<<selected)))++selected;}
  if(selected<7)recall(selected,word(headers[selected],20)==1);
  pending=255;return;
 }
 if(pending<7){unsigned slot=pending;pending=255;recall(slot,resume_output);}
}
extern "C" uint32_t mpp_bank_page(){return (1u<<24)|(occupied<<8)|current;}
extern "C" void mpp_bank_query(const uint8_t* p,unsigned n,unsigned channel){
 if((rd(0xe000ed04)&511)||booting||pending<7)return;
 unsigned size=mpp::link::unpack7(p+9,n-9,input,sizeof(input));
 if(size<20||word(input,0)!=0x3031504e||input[4]!=1||input[6]>=7||input[7]||
    !word(input,8)||input[14]||input[15]||unsigned(input[12]|(input[13]<<8))+20!=size||
    word(input,size-4)!=mpp::link::crc32(input,size-4))return;
 unsigned op=input[5],slot=input[6],error=invalid;
 if(op==1&&size==20)error=ok;
 if(op==3&&size==20){
  bool listen=mpp_listen_enabled!=0;error=recall(slot,listen);
 }
 if(op==2&&size==132){
  const uint8_t* model=mpp_bank_model();const uint8_t* fx=ptr(rd(0x20005ad0));const uint8_t* body=input+16;
  if(model&&word(body,0)==mpp::link::crc32(model,8192)&&word(body,4)==mpp::link::crc32(fx,128)){
   mpp_bank_pause();
   #ifdef MPP_FX_BLOCKS
   uint8_t extra[32];mpp_fx_get(extra);
   error=bank().save(slot,model,fx,body+16,body+48,word(body,8),word(body,12),record,scratch,extra);
#else
   error=bank().save(slot,model,fx,body+16,body+48,word(body,8),word(body,12),record,scratch);
#endif
   if(error==ok){read_slot(slot);current=slot;ptr(rd(0x20005ad8))[2]=slot;}
   mpp_bank_resume(false);
  }
 }
 for(auto& b:output)b=0;
 put(output,0,0x3031504e);output[4]=1;output[5]=op|128;output[6]=slot;output[7]=error;
 copy(output+8,input+8,4);output[12]=0;output[13]=1;output[14]=current;output[15]=occupied;
 copy(output+16,headers[slot],256);put(output,272,mpp::link::crc32(output,272));
 const uint8_t prefix[]={0xf0,0x43,0x58,0x70,4,2,'N','S',1};copy(wire,prefix,9);
 unsigned encoded=mpp::link::pack7(output,276,wire+9,sizeof(wire)-10);
 if(encoded){wire[9+encoded]=0xf7;
#ifdef MPP_FX_BLOCKS
 mpp_reply_send(wire,encoded+10,channel);
#else
 ((void(*)(const uint8_t*,unsigned,unsigned))0xae81)(wire,encoded+10,channel);
#endif
}
}

#ifdef MPP_FX_BLOCKS
extern "C" void mpp_fx_saved(unsigned slot,uint8_t* out){if(slot<7)copy(out,saved_fx[slot],32);}
#endif
