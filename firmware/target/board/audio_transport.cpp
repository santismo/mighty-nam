#include "audio_transport.hpp"
namespace mpp::board {
const RegisterValue sai_configuration[12]={
 {sai1+0x0c,0x10},{sai1+0x10,0x07000001},{sai1+0x14,0x10000},
 {sai1+0x18,0x31f1b},{sai1+0x1c,0x1f1f1f00},{sai1+0x60,0},
 {sai1+0x8c,0x10},{sai1+0x90,0x47000001},{sai1+0x94,0x10000},
 {sai1+0x98,0x31f1b},{sai1+0x9c,0x1f1f1f00},{sai1+0xe0,0}
};
const uint8_t stock_codec_registers[21]={0x37,0xac,0x1c,0x03,0x22,0x82,0x30,0x30,0x30,0x30,0,0x55,0,0,0x18,0x18,0x18,0x18,4,5,0x0a};
namespace {
bool overlaps(uint32_t a,uint32_t an,uint32_t b,uint32_t bn) {return a<b+bn && b<a+an;}
// Known stock-accessed RAM windows, not proof of bus accessibility or free space.
bool bounded_ram(uint32_t a,uint32_t n) {
 return (a>=0x20000000 && a<=0x20040000-n) || (a>=0x20200000 && a<=0x20300000-n);
}
}
bool make_tcd_ring(Tcd (&out)[4],uint32_t rx,uint32_t tx,uint32_t descriptors) {
 if((rx|tx|descriptors)&31) return false;
 if(!bounded_ram(rx,256)||!bounded_ram(tx,256)||!bounded_ram(descriptors,128)) return false;
 if(overlaps(rx,256,tx,256)||overlaps(rx,256,descriptors,128)||overlaps(tx,256,descriptors,128)) return false;
 for(unsigned i=0;i<2;++i) {
  out[i]={sai_rx,0,0x202,64,0,rx+128*i,4,2,descriptors+32*(1-i),0x12,2};
  out[2+i]={tx+128*i,4,0x202,64,0,sai_tx,0,2,descriptors+64+32*(1-i),0x10,2};
 }
 return true;
}
bool completed_rx_half(uint32_t next,uint32_t descriptors,unsigned& half) {
 if(next==descriptors){half=0;return true;}
 if(descriptors<=0xffffffdf && next==descriptors+32){half=1;return true;}
 return false;
}
void unpack_q31(const int32_t* in,float (&out)[4][8]) {
 for(unsigned f=0;f<frames;++f)for(unsigned c=0;c<slots;++c)out[c][f]=float(in[f*4+c])*0x1p-31f;
}
void pack_q31(const float (&in)[4][8],int32_t* out) {
 for(unsigned f=0;f<frames;++f)for(unsigned c=0;c<slots;++c){
  float x=in[c][f];int32_t value;
  if(!__builtin_isfinite(x)) value=0;
  else if(x>=1.0f)value=INT32_MAX;
  else if(x<=-1.0f)value=INT32_MIN;
  else value=static_cast<int32_t>(x*0x1p31f);
  out[f*4+c]=value;
 }
}
bool AudioBridge::configure(unsigned input_slot,unsigned output_mask,Processor process,void* ctx) {
 if(input_slot>=4||!output_mask||(output_mask&~15u)||!process)return false;
 input_=input_slot;mask_=output_mask;process_=process;context_=ctx;configured_=true;muted_=true;return true;
}
bool AudioBridge::process(const int32_t* rx,int32_t* tx) {
 if(!rx||!tx)return false;
 // Copy input first, allowing the caller to supply the same buffer for both.
 unpack_q31(rx,planar_);
 for(unsigned i=0;i<words;++i)tx[i]=0;
 if(!configured_)return false;
 if(!process_(context_,planar_[input_],mono_,frames))return false;
 if(muted_)return true;
 for(unsigned c=0;c<slots;++c)for(unsigned f=0;f<frames;++f)planar_[c][f]=(mask_&(1u<<c))?mono_[f]:0;
 pack_q31(planar_,tx);return true;
}
}
