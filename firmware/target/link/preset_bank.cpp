#include "preset_bank.hpp"
#include "model_receiver.hpp"
namespace mpp::presets {
static void copy(uint8_t* a,const uint8_t* b,unsigned n){for(unsigned i=0;i<n;++i)a[i]=b[i];}
static bool equal(const uint8_t* a,const uint8_t* b,unsigned n){for(unsigned i=0;i<n;++i)if(a[i]!=b[i])return false;return true;}
uint32_t word(const uint8_t* p,unsigned at){uint32_t v=0;for(unsigned i=0;i<4;++i)v|=uint32_t(p[at+i])<<(8*i);return v;}
void put(uint8_t* p,unsigned at,uint32_t v){for(unsigned i=0;i<4;++i)p[at+i]=v>>(8*i);}
static bool name_valid(const uint8_t* p){
 // UTF-8 bytes are retained verbatim; reject control characters and require a
 // bounded terminator. The controller validates UTF-8 before sending a name.
 bool end=false;for(unsigned i=0;i<64;++i){if(!p[i])end=true;else if(end||p[i]<32||p[i]==127)return false;}
 return end&&p[0];
}
bool valid_model(const uint8_t* p){
 const uint32_t h[]={0x3241504d,1,48000,1871,7484};
 for(unsigned i=0;i<5;++i)if(word(p,4*i)!=h[i])return false;
 if(word(p,24)!=1||word(p,28)||word(p,20)!=link::crc32(p+32,7484))return false;
 for(unsigned i=32;i<model_bytes;i+=4)if((word(p,i)&0x7f800000)==0x7f800000)return false;
 return true;
}
bool valid_effects(const uint8_t* p){
 const uint8_t ids[]={1,2,4,5,6,7,8,9},max[]={3,13,2,1,13,5,6,34};
 for(unsigned i=0;i<128;++i)if(p[i]>127)return false;
 for(unsigned i=0;i<8;++i)if(!(p[ids[i]]&63)||(p[ids[i]]&63)>max[i])return false;
 if(!(p[3]&63))return false;
 unsigned mask=0;for(unsigned i=90;i<99;++i){if(p[i]<1||p[i]>9||(mask&(1u<<p[i])))return false;mask|=1u<<p[i];}
 const uint8_t starts[]={15,20,36,49,54,61,70,75},sizes[]={4,6,12,4,6,8,4,6};
 for(unsigned j=0;j<8;++j)for(unsigned i=0;i<sizes[j];++i)if(p[starts[j]+i]>100)return false;
 return true;
}
bool Bank::valid(const uint8_t* p,unsigned slot){
 if(slot>=count||word(p,0)!=magic||word(p,4)!=1||word(p,8)!=slot||!word(p,12)||
    word(p,20)>1||!(word(p,24)==8||word(p,24)==16||word(p,24)==32)||word(p,28)||
    word(p,8188)!=commit||word(p,8184)!=link::crc32(p,8184)||
    !name_valid(p+64)||!valid_effects(p+128)||!valid_model(p+256))return false;
 // The reconstructed 8 KiB model CRC includes its canonical FF padding.
 uint32_t c=0xffffffff;
 for(unsigned i=0;i<8192;++i){c^=i<model_bytes?p[256+i]:255;
  for(unsigned b=0;b<8;++b)c=(c>>1)^((c&1)?0xedb88320:0);}
 return (c^0xffffffff)==word(p,16);
}
Result Bank::read(unsigned slot,uint8_t* a,uint8_t* b,unsigned* selected){
 if(slot>=count||!a||!b||a==b)return invalid;
 uint32_t addr=base+slot*2*record_bytes;
 // An I/O error is not an empty bank. Do not authorize a later overwrite on
 // the basis of an unreadable newest copy.
 if(!io_.read(io_.context,addr,a,record_bytes)||!io_.read(io_.context,addr+record_bytes,b,record_bytes))return io_error;
 bool va=valid(a,slot),vb=valid(b,slot);
 if(!va&&!vb)return empty;
 unsigned which=(!va||(vb&&word(b,12)>word(a,12)))?1:0;
 if(which)copy(a,b,record_bytes);
 if(selected)*selected=which;
 return ok;
}
Result Bank::save(unsigned slot,const uint8_t* model,const uint8_t* fx,const uint8_t* sha,const uint8_t* name,unsigned flags,unsigned buffer,uint8_t* a,uint8_t* b){
 if(slot>=count||!model||!fx||!sha||!name||!a||!b||a==b||flags>1||
    !(buffer==8||buffer==16||buffer==32)||!valid_model(model)||!valid_effects(fx)||!name_valid(name))return invalid;
 for(unsigned i=model_bytes;i<8192;++i)if(model[i]!=255)return invalid;
 unsigned selected=1;auto result=read(slot,a,b,&selected);
 if(result!=ok&&result!=empty)return result;
 uint32_t generation=result==ok?word(a,12):0;
 if(result==ok&&word(a,20)==flags&&word(a,24)==buffer&&equal(a+32,sha,32)&&equal(a+64,name,64)&&
    equal(a+128,fx,128)&&equal(a+256,model,model_bytes))return ok;
 if(generation==0xffffffff)return exhausted;
 for(unsigned i=0;i<record_bytes;++i)a[i]=255;
 put(a,0,magic);put(a,4,1);put(a,8,slot);put(a,12,generation+1);
 put(a,16,link::crc32(model,8192));put(a,20,flags);put(a,24,buffer);put(a,28,0);
 copy(a+32,sha,32);copy(a+64,name,64);copy(a+128,fx,128);copy(a+256,model,model_bytes);
 put(a,8184,link::crc32(a,8184));
 uint32_t target=base+(slot*2+(selected^1))*record_bytes;
 for(unsigned off=0;off<record_bytes;off+=4096)if(!io_.erase(io_.context,target+off))return io_error;
 for(unsigned off=0;off<record_bytes;off+=256)if(!io_.program(io_.context,target+off,a+off,256))return io_error;
 if(!io_.read(io_.context,target,b,record_bytes)||!equal(a,b,record_bytes))return io_error;
 put(a,8188,commit);
 if(!io_.program(io_.context,target+8188,a+8188,4)||!io_.read(io_.context,target,b,record_bytes)||
    !equal(a,b,record_bytes)||!valid(b,slot))return io_error;
 return ok;
}
void Bank::unpack_model(const uint8_t* record,uint8_t* model){
 copy(model,record+256,model_bytes);for(unsigned i=model_bytes;i<8192;++i)model[i]=255;
}
}
