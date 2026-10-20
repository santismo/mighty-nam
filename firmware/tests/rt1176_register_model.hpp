#pragma once
#include "../target/hardware/rt1176_backend.hpp"
#include <unordered_map>
#include <vector>
#include <stdexcept>
namespace mpp::hardware::test {
struct Write {uint32_t address,value;unsigned width;};
// Semantic register model, not a timing/electrical emulator. AI transfers must
// toggle; I2C bytes are reconstructed from GPIO edges, not high-level requests.
struct RegisterModel {
 std::unordered_map<uint32_t,uint32_t> words,analog;
 std::vector<Write> writes;
 std::vector<uint8_t> codec_bytes;
 unsigned barriers=0,reads=0,ai_transfers=0,starts=0,stops=0,nack_byte=0;
 uint32_t tick=0,tick_step=1000000,fail_read=0,fail_write=0;
 bool ai_stuck=false,ldo_busy=false,pll_stuck=false,scl_stuck=false,sda_stuck=false,dma_busy=false;
 bool fail_stop=false,bad_width=false,transaction=false,ack=false;
 unsigned pulses=0;uint8_t accumulator=0;
 uint32_t ldo=0;
 bool torn_snapshot=false;unsigned next_reads=0;
 RegisterModel(){words[0xe000ed14]=0x30000;words[0xe000e004]=6;}
 RegisterBus bus(){return {this,
  [](void* p,unsigned w,uint32_t a,uint32_t* v){return static_cast<RegisterModel*>(p)->read(w,a,*v);},
  [](void* p,unsigned w,uint32_t a,uint32_t v){return static_cast<RegisterModel*>(p)->write(w,a,v);},
  [](void* p){++static_cast<RegisterModel*>(p)->barriers;return true;}};}
 uint32_t get(uint32_t a,unsigned w=4){uint32_t v=words[a&~3u];return (v>>(8*(a&3)))&(w==4?0xffffffffu:((1u<<(8*w))-1));}
 void put(uint32_t a,uint32_t v,unsigned w=4){auto& x=words[a&~3u];uint32_t mask=w==4?0xffffffffu:((1u<<(8*w))-1);x=(x&~(mask<<(8*(a&3))))|((v&mask)<<(8*(a&3)));}
 bool width_ok(unsigned w,uint32_t a){
  if((w!=1&&w!=2&&w!=4)||(a&(w-1)))return false;
  if(a>=0x40070018&&a<0x40070020)return w==1;
  if(a>=0x40071000&&a<0x40071400){unsigned o=a&31;return w==((o==4||o==6||o==20||o==22||o==28||o==30)?2:4);}
  return w==4;
 }
 uint32_t pins(){uint32_t dir=get(0x40c6c004);return ((~dir)&0x6000)&~((scl_stuck?0x2000:0)|(sda_stuck||ack?0x4000:0));}
 bool read(unsigned w,uint32_t a,uint32_t& v){
  ++reads;if(!width_ok(w,a)){bad_width=true;return false;}if(a==fail_read)return false;
  if(a==0xe0001004){tick+=tick_step;v=tick;return true;}
  if(a==0x40c6c008){v=pins();return true;}
  if(a==0x40c84500&&ldo_busy){v=0x40000000;return true;}
  if((a==0x4007101c||a==0x4007121c)&&dma_busy){v=0x40;return true;}
  if(a==0x40c84300&&!pll_stuck&&ai_transfers>4){put(a,get(a)|0x20000000);}
  if(a==0x40071018&&torn_snapshot&&++next_reads==2)put(a,get(a)^32);
  v=get(a,w);return true;
 }
 bool write(unsigned w,uint32_t a,uint32_t v){
  if(!width_ok(w,a)){bad_width=true;return false;}if(a==fail_write)return false;
  writes.push_back({a,v,w});
  // No flash, USB, fuses, reset-controller or FlexSPI pin accesses permitted.
  if((a>=0x30000000&&a<0x40000000)||(a>=0x400e81c8&&a<=0x400e81e0))throw std::runtime_error("forbidden model write");
  uint32_t old=get(a,w);
  if(a==0x40c6c004){
   bool old_scl=!(old&0x2000),new_scl=!(v&0x2000),old_sda=!(old&0x4000),new_sda=!(v&0x4000);
   if(old_scl&&new_scl&&old_sda&&!new_sda){transaction=true;pulses=0;accumulator=0;ack=false;++starts;}
   if(old_scl&&new_scl&&!old_sda&&new_sda){transaction=false;ack=false;++stops;if(fail_stop)sda_stuck=true;}
   if(transaction&&!old_scl&&new_scl&&!scl_stuck){
    ++pulses;
    if(pulses%9==0)ack=(nack_byte!=codec_bytes.size()+1);
    else accumulator=uint8_t((accumulator<<1)|(new_sda?1:0));
   }
   if(transaction&&old_scl&&!new_scl&&pulses&&pulses%9==0){codec_bytes.push_back(accumulator);accumulator=0;ack=false;}
  }
  put(a,v,w);
  if(a==0x40c84880&&((old^v)&0x100)&&!ai_stuck){
   ++ai_transfers;unsigned reg=v&255;
   if(v&0x10000)put(0x40c848a0,analog[reg]);
   else{uint32_t data=get(0x40c84890);if((reg&15)==4)analog[reg-4]|=data;else if((reg&15)==8)analog[reg-8]&=~data;else analog[reg]=data;}
   put(a,get(a)^0x200);
  }
  if(a==0x40c84500&&((old^v)&0x10000)){
   if(get(0x40c84820)&0x10000)put(0x40c84840,ldo);else ldo=get(0x40c84830);
  }
  for(uint32_t base:{0x40c5c000u,0x40c60000u,0x40c6c000u}){
   if(a==base+0x88)put(base,get(base)&~v);
   if(a==base+0x84)put(base,get(base)|v);
  }
  if(a==0x4007001a)put(0x4007000c,get(0x4007000c)&~(1u<<(v&31)));
  if(a==0x4007001b)put(0x4007000c,get(0x4007000c)|(1u<<(v&31)));
  if(a==0x4007001f)put(0x40070024,get(0x40070024)&~(1u<<(v&31)));
  if(a==0x4007001e)put(0x4007002c,get(0x4007002c)&~(1u<<(v&31)));
  return true;
 }
 void complete(unsigned rx,unsigned tx,uint32_t base=0x202c0000){
  put(0x40071018,base+512+32*rx);put(0x40071218,base+576+32*tx);put(0x40070024,1);
 }
 unsigned count_write(uint32_t a)const{unsigned n=0;for(auto w:writes)if(w.address==a)++n;return n;}
};
}
