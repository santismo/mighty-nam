#include "global_buffer.hpp"
#include "model_receiver.hpp"
namespace mpp::settings {
using namespace presets;
static bool equal(const uint8_t* a,const uint8_t* b){for(unsigned i=0;i<bytes;++i)if(a[i]!=b[i])return false;return true;}
bool BufferStore::valid(const uint8_t* p){
 if(word(p,0)!=0x3142474e||word(p,4)!=1||!word(p,8)||
    !(word(p,12)==8||word(p,12)==16||word(p,12)==32)||
    word(p,248)!=link::crc32(p,248)||word(p,252)!=commit)return false;
 for(unsigned i=16;i<248;++i)if(p[i]!=255)return false;
 return true;
}
Result BufferStore::load(uint8_t* a,uint8_t* b,unsigned* selected){
 if(!a||!b||a==b)return invalid;
 if(!io_.read(io_.context,base,a,bytes)||!io_.read(io_.context,base+4096,b,bytes))return io_error;
 bool va=valid(a),vb=valid(b);if(!va&&!vb)return empty;
 unsigned which=(!va||(vb&&word(b,8)>word(a,8)))?1:0;
 if(which)for(unsigned i=0;i<bytes;++i)a[i]=b[i];
 if(selected)*selected=which;return ok;
}
Result BufferStore::save(unsigned samples,uint8_t* a,uint8_t* b){
 if(!(samples==8||samples==16||samples==32))return invalid;
 unsigned selected=1;auto result=load(a,b,&selected);
 if(result!=ok&&result!=empty)return result;
 uint32_t generation=result==ok?word(a,8):0;
 if(result==ok&&word(a,12)==samples)return ok;
 if(generation==0xffffffff)return exhausted;
 for(unsigned i=0;i<bytes;++i)a[i]=255;
 put(a,0,0x3142474e);put(a,4,1);put(a,8,generation+1);put(a,12,samples);put(a,248,link::crc32(a,248));
 uint32_t target=base+(selected^1)*4096;
 if(!io_.erase(io_.context,target)||!io_.program(io_.context,target,a,bytes)||
    !io_.read(io_.context,target,b,bytes)||!equal(a,b))return io_error;
 put(a,252,commit);
 if(!io_.program(io_.context,target+252,a+252,4)||!io_.read(io_.context,target,b,bytes)||
    !equal(a,b)||!valid(b))return io_error;
 return ok;
}
}
