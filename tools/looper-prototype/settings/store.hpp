// MIT (c) 2026 santismo. Versioned, two-copy global settings. No NUX code.
#pragma once
#include <stdint.h>
namespace mighty_loop {
struct SettingsIO {
 void* context;
 bool (*read)(void*,uint32_t,uint8_t*,unsigned);
 bool (*erase)(void*,uint32_t);
 bool (*program)(void*,uint32_t,const uint8_t*,unsigned);
};
struct SettingsStore {
 SettingsIO io;
 static constexpr unsigned size=256,base=0x303a4000,commit=0x454e4f44;
 static constexpr unsigned defaults=50|(100<<8)|(30<<16);
 enum Result:unsigned {ok,empty,invalid,io_error,exhausted};
 static uint32_t word(const uint8_t* p,unsigned i){return p[i]|(p[i+1]<<8)|(p[i+2]<<16)|(uint32_t(p[i+3])<<24);}
 static void put(uint8_t* p,unsigned i,uint32_t v){for(unsigned j=0;j<4;++j)p[i+j]=v>>(j*8);}
 static uint32_t crc(const uint8_t* p,unsigned n){uint32_t c=~0u;while(n--){c^=*p++;for(unsigned j=0;j<8;++j)c=(c>>1)^(0xedb88320u&-(c&1));}return ~c;}
 static bool same(const uint8_t* a,const uint8_t* b){for(unsigned i=0;i<size;++i)if(a[i]!=b[i])return false;return true;}
 static bool buffer(unsigned n){return n==8||n==16||n==32;}
 static bool settings(unsigned w){unsigned t=w&255,v=(w>>8)&255,s=(w>>16)&255;return !(w>>24)&&t>=12&&t<=60&&v<=100&&(s==30||s==60);}
 static unsigned loop(const uint8_t* p){return word(p,4)==2?word(p,16):defaults;}
 static bool valid(const uint8_t* p){
  unsigned version=word(p,4);
  if(word(p,0)!=0x3142474e||(version!=1&&version!=2)||!word(p,8)||!buffer(word(p,12))||
     word(p,248)!=crc(p,248)||word(p,252)!=commit||(version==2&&!settings(word(p,16))))return false;
  for(unsigned i=version==1?16:20;i<248;++i)if(p[i]!=255)return false;
  return true;
 }
 unsigned load(uint8_t* a,uint8_t* b,unsigned* selected=nullptr){
  if(!a||!b||a==b)return invalid;
  if(!io.read(io.context,base,a,size)||!io.read(io.context,base+4096,b,size))return io_error;
  bool va=valid(a),vb=valid(b);if(!va&&!vb)return empty;
  unsigned which=!va||(vb&&word(b,8)>word(a,8));
  if(which)for(unsigned i=0;i<size;++i)a[i]=b[i];
  if(selected)*selected=which;return ok;
 }
 // A zero argument preserves the stored value; it never saves a live edit by
 // accident when the other setting is written. A valid loop word is nonzero.
 unsigned save(unsigned samples,unsigned loop_word,uint8_t* a,uint8_t* b){
  if((samples&&!buffer(samples))||(loop_word&&!settings(loop_word)))return invalid;
  unsigned selected=1,result=load(a,b,&selected);
  if(result!=ok&&result!=empty)return result;
  unsigned generation=result==ok?word(a,8):0;
  if(!samples)samples=result==ok?word(a,12):8;
  if(!loop_word)loop_word=result==ok?loop(a):defaults;
  if(result==ok&&word(a,4)==2&&word(a,12)==samples&&loop(a)==loop_word)return ok;
  if(generation==0xffffffff)return exhausted;
  for(unsigned i=0;i<size;++i)a[i]=255;
  put(a,0,0x3142474e);put(a,4,2);put(a,8,generation+1);put(a,12,samples);put(a,16,loop_word);put(a,248,crc(a,248));
  unsigned target=base+(selected^1)*4096;
  if(!io.erase(io.context,target)||!io.program(io.context,target,a,size)||!io.read(io.context,target,b,size)||!same(a,b))return io_error;
  put(a,252,commit);
  if(!io.program(io.context,target+252,a+252,4)||!io.read(io.context,target,b,size)||!same(a,b)||!valid(b))return io_error;
  return ok;
 }
};
}
