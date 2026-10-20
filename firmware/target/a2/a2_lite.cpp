// Fixed C3 implementation, checked against NAM Core v0.5.2.
// Topology and weight order follow NAM/wavenet/a2_fast.cpp (MIT, Steve Atkinson
// and contributors). See A2-PROVENANCE.json and upstream license in this folder.
#include "a2_lite.hpp"
namespace mpp {
namespace {
constexpr unsigned kernels[23]={6,6,6,6,6,6,6,6,6,6,6,6,6,6,15,15,6,6,6,6,6,6,6};
constexpr unsigned dilations[23]={1,3,7,17,41,101,239,1,3,7,17,41,101,239,1,13,1,3,7,17,41,101,239};
constexpr unsigned history_size(){unsigned n=0;for(unsigned i=0;i<23;++i)n+=3*((kernels[i]-1)*dilations[i]+1);return n;}
static_assert(history_size()==A2Lite::history_floats);
}
#ifdef MPP_COMPACT_INIT
__attribute__((minsize))
#endif
bool A2Lite::load(const float* w,unsigned n){
 ready_=0;
 if(!w||n!=weight_count)return false;
 for(unsigned i=0;i<n;++i)if(!__builtin_isfinite(w[i]))return false;
 // Pack once at model load: consecutive weights serve the nine scalar MACs
 // for one tap. The on-flash/export format remains [out][in][tap].
 for(unsigned i=0;i<3;++i)weights_[i]=w[i];
 unsigned wi=3;
 for(unsigned layer=0;layer<layer_count;++layer){
  const unsigned k=kernels[layer];
  for(unsigned tap=0;tap<k;++tap)for(unsigned c=0;c<3;++c)for(unsigned r=0;r<3;++r)
   weights_[wi+tap*9+c*3+r]=w[wi+(r*3+c)*k+tap];
  wi+=9*k;
  for(unsigned i=0;i<18;++i)weights_[wi+i]=w[wi+i];
  wi+=18;
 }
 for(unsigned tap=0;tap<16;++tap)for(unsigned c=0;c<3;++c)weights_[wi+tap*3+c]=w[wi+c*16+tap];
 weights_[wi+48]=w[wi+48];weights_[wi+49]=w[wi+49];
 ready_=1;reset();return true;
}
#ifdef MPP_COMPACT_INIT
__attribute__((minsize))
#endif
void A2Lite::reset(){
 for(auto &v:history_)v=0;for(auto &v:head_)v=0;
 for(auto &v:pos_)v=0;head_pos_=0;
}
#ifdef MPP_PRIME_STATE
// Read the upcoming eight-frame working set without advancing DSP state.
// During bypass these reads stay inside the same timed audio callback; after
// model upload they run while the engine is stopped, before it is published.
__attribute__((minsize,noinline)) void A2Lite::prime_working_set() const {
 if(!ready_)return;
 const volatile float* weights=weights_;
 const volatile float* history=history_;
 const volatile float* head=head_;
 for(unsigned i=0;i<3;++i)(void)weights[i];
 unsigned wi=3,hi=0;
 for(unsigned layer=0;layer<23;++layer){
  const unsigned k=kernels[layer],d=dilations[layer],length=(k-1)*d+1;
  unsigned p=pos_[layer];
  for(unsigned frame=0;frame<8;++frame){
   unsigned col=p+1==length?0:p+1;
   for(unsigned tap=0;tap<k;++tap){
    for(unsigned c=0;c<3;++c)(void)history[hi+3*col+c];
    col+=d;if(col>=length)col-=length;
   }
   p=p+1==length?0:p+1;
  }
  for(unsigned i=0;i<9*k+18;++i)(void)weights[wi+i];
  wi+=9*k+18;hi+=3*length;
 }
 for(unsigned i=0;i<50;++i)(void)weights[wi+i];
 for(unsigned i=0;i<48;++i)(void)head[i];
}
#endif
void A2Lite::process(const float* input,float* output,unsigned frames){
 if(!ready_){for(unsigned t=0;t<frames;++t)output[t]=0;return;}
 for(unsigned t=0;t<frames;++t){
  const float x=input[t];float lin[3]={weights_[0]*x,weights_[1]*x,weights_[2]*x},sum[3]={0,0,0};
  unsigned wi=3,hi=0;
  for(unsigned layer=0;layer<23;++layer){
   const unsigned k=kernels[layer],d=dilations[layer],length=(k-1)*d+1,p=pos_[layer];
   float* ring=history_+hi;
   for(unsigned c=0;c<3;++c)ring[3*p+c]=lin[c];
#ifdef MPP_REFERENCE_ORDER
   // Core's generic Conv1D accumulates each tap's three-channel dot product,
   // then adds the bias. Keep those rounding boundaries in the chain build.
   float z[3]={0,0,0};
#else
   float z[3]={weights_[wi+9*k],weights_[wi+9*k+1],weights_[wi+9*k+2]};
#endif
   // Oldest tap first. For the minimal ring, the oldest column is p+1.
   // Advance one dilation per tap instead of recomputing a backward offset.
   unsigned col=p+1==length?0:p+1;
   const float* w=weights_+wi;
#if defined(MPP_M7_CONV) && defined(__arm__)
   // Contiguous packed weights allow one VLDMI rather than nine VLDRs.
   // VMLA is deliberately non-fused: preserve Core's rounded dot products.
   unsigned taps=k;
   float z0=0,z1=0,z2=0;
   __asm__ volatile(
    "1:\n"
    "add r12, %[col], %[col], lsl #1\n"
    "add r12, %[ring], r12, lsl #2\n"
    "vldmia r12, {s12-s14}\n"
    "vldmia %[weights]!, {s3-s11}\n"
    "vmul.f32 s15, s3, s12\n"
    "vmul.f32 s16, s4, s12\n"
    "vmul.f32 s17, s5, s12\n"
    "vmla.f32 s15, s6, s13\n"
    "vmla.f32 s16, s7, s13\n"
    "vmla.f32 s17, s8, s13\n"
    "vmla.f32 s15, s9, s14\n"
    "vmla.f32 s16, s10, s14\n"
    "vmla.f32 s17, s11, s14\n"
    "vadd.f32 %[z0], %[z0], s15\n"
    "vadd.f32 %[z1], %[z1], s16\n"
    "vadd.f32 %[z2], %[z2], s17\n"
    "add %[col], %[col], %[d]\n"
    "cmp %[col], %[length]\n"
    "it hs\n"
    "subhs %[col], %[col], %[length]\n"
    "subs %[taps], %[taps], #1\n"
    "bne 1b\n"
    : [col] "+&r"(col),[weights] "+&r"(w),[taps] "+&r"(taps),
      [z0] "+&t"(z0),[z1] "+&t"(z1),[z2] "+&t"(z2)
    : [ring] "r"(ring),[d] "r"(d),[length] "r"(length)
    : "r12","s3","s4","s5","s6","s7","s8","s9","s10","s11",
      "s12","s13","s14","s15","s16","s17","cc","memory");
   z[0]=z0;z[1]=z1;z[2]=z2;
#else
#ifdef MPP_REFERENCE_ORDER
   // Two taps per iteration keep the hot convolution fast while preserving
   // room in the retained code window and a smaller stack frame.
#pragma clang loop unroll_count(2)
#endif
   for(unsigned tap=0;tap<k;++tap){
    const float a=ring[3*col],b=ring[3*col+1],c=ring[3*col+2];
#ifdef MPP_REFERENCE_ORDER
    z[0]+=(w[0]*a+w[3]*b)+w[6]*c;
    z[1]+=(w[1]*a+w[4]*b)+w[7]*c;
    z[2]+=(w[2]*a+w[5]*b)+w[8]*c;
#else
    // Preserve the earlier model-only build's arithmetic.
    z[0]+=w[0]*a;z[1]+=w[1]*a;z[2]+=w[2]*a;
    z[0]+=w[3]*b;z[1]+=w[4]*b;z[2]+=w[5]*b;
    z[0]+=w[6]*c;z[1]+=w[7]*c;z[2]+=w[8]*c;
#endif
    w+=9;col+=d;if(col>=length)col-=length;
   }
#endif
   wi+=9*k;
#ifdef MPP_REFERENCE_ORDER
   for(unsigned c=0;c<3;++c)z[c]+=weights_[wi+c];
#endif
   wi+=3;
   for(unsigned c=0;c<3;++c){z[c]+=weights_[wi+c]*x;if(z[c]<0)z[c]*=.01f;sum[c]+=z[c];}
   wi+=3;
#if defined(MPP_M7_DENSE) && defined(__arm__)
   float l0=lin[0],l1=lin[1],l2=lin[2];
   const float* projection=weights_+wi;
   __asm__ volatile(
    "vldmia %[weights], {s3-s14}\n"
    "vmul.f32 s15, s3, %[z0]\n"
    "vmul.f32 s16, s6, %[z0]\n"
    "vmul.f32 s17, s9, %[z0]\n"
    "vmla.f32 s15, s4, %[z1]\n"
    "vmla.f32 s16, s7, %[z1]\n"
    "vmla.f32 s17, s10, %[z1]\n"
    "vmla.f32 s15, s5, %[z2]\n"
    "vmla.f32 s16, s8, %[z2]\n"
    "vmla.f32 s17, s11, %[z2]\n"
    "vadd.f32 s15, s15, s12\n"
    "vadd.f32 s16, s16, s13\n"
    "vadd.f32 s17, s17, s14\n"
    "vadd.f32 %[l0], %[l0], s15\n"
    "vadd.f32 %[l1], %[l1], s16\n"
    "vadd.f32 %[l2], %[l2], s17\n"
    :[l0]"+&t"(l0),[l1]"+&t"(l1),[l2]"+&t"(l2)
    :[weights]"r"(projection),[z0]"t"(z[0]),[z1]"t"(z[1]),[z2]"t"(z[2])
    :"s3","s4","s5","s6","s7","s8","s9","s10","s11","s12","s13","s14",
     "s15","s16","s17","memory");
   lin[0]=l0;lin[1]=l1;lin[2]=l2;
#else
#ifdef MPP_REFERENCE_ORDER
   // Keep the three output rows compact; tap MACs remain explicitly unrolled.
#pragma clang loop unroll(disable)
#endif
   for(unsigned r=0;r<3;++r){
#ifdef MPP_REFERENCE_ORDER
    float y=(weights_[wi+r*3]*z[0]+weights_[wi+r*3+1]*z[1])+weights_[wi+r*3+2]*z[2];
    y+=weights_[wi+9+r];
#else
    float y=weights_[wi+9+r];for(unsigned c=0;c<3;++c)y+=weights_[wi+r*3+c]*z[c];
#endif
    lin[r]+=y;
   }
#endif
   wi+=12;hi+=3*length;pos_[layer]=p+1==length?0:p+1;
  }
  for(unsigned c=0;c<3;++c)head_[head_pos_*3+c]=sum[c];
#ifdef MPP_REFERENCE_ORDER
  float y=0;
#if defined(MPP_M7_DENSE) && defined(__arm__)
  const float* head_weights=weights_+wi;
  unsigned col=(head_pos_+1)&15,taps=16;
  __asm__ volatile(
   "1: add r12, %[col], %[col], lsl #1\n"
   "add r12, %[head], r12, lsl #2\n"
   "vldmia r12, {s3-s5}\n"
   "vldmia %[weights]!, {s6-s8}\n"
   "vmul.f32 s9, s3, s6\n"
   "vmla.f32 s9, s4, s7\n"
   "vmla.f32 s9, s5, s8\n"
   "vadd.f32 %[y], %[y], s9\n"
   "add %[col], %[col], #1\n"
   "and %[col], %[col], #15\n"
   "subs %[taps], %[taps], #1\n"
   "bne 1b\n"
   :[y]"+&t"(y),[weights]"+&r"(head_weights),[col]"+&r"(col),[taps]"+&r"(taps)
   :[head]"r"(head_)
   :"r12","s3","s4","s5","s6","s7","s8","s9","cc","memory");
#else
  for(unsigned tap=0;tap<16;++tap){
   unsigned col=(head_pos_+1+tap)&15;
   y+=(weights_[wi+tap*3]*head_[col*3]+weights_[wi+tap*3+1]*head_[col*3+1])+weights_[wi+tap*3+2]*head_[col*3+2];
  }
#endif
  y+=weights_[wi+48];
#else
  float y=weights_[wi+48];
  for(unsigned tap=0;tap<16;++tap){unsigned col=(head_pos_+1+tap)&15;for(unsigned c=0;c<3;++c)y+=weights_[wi+tap*3+c]*head_[col*3+c];}
#endif
  output[t]=y*weights_[wi+49];head_pos_=(head_pos_+1)&15;
 }
}
}
