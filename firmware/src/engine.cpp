#include "mpp/engine.hpp"
extern "C" { float sinf(float); float cosf(float); float tanhf(float); float expf(float); float powf(float,float); }
namespace mpp {
namespace {
constexpr float tau=6.283185307179586f;
bool finite(float x) { return __builtin_isfinite(x); }
float clip(float x) { return x>1 ? 1 : x < -1 ? -1 : x; }
float wrap(float x) { while(x>=1) x-=1; while(x<0) x+=1; return x; }
float read(const float* ring, unsigned size, unsigned pos, float delay) {
  float p=float(pos)-delay; while(p<0) p+=float(size);
  unsigned a=unsigned(p)%size; float f=p-unsigned(p);
  return ring[a]*(1-f)+ring[(a+1)%size]*f;
}
float sigmoid(float x) { return 1.0f/(1.0f+expf(-x)); }
}
const EffectExtension* Chain::extension(unsigned id) const {
  for(unsigned i=0;i<extension_count_;++i) if(extensions_[i].id==id) return &extensions_[i];
  return nullptr;
}
bool Chain::register_effect(const EffectExtension& e) {
  if(count_ || extension_count_==4 || e.id<64 || e.id>127 || !e.process || extension(e.id)) return false;
  for(unsigned i=0;i<3;++i) if(!finite(e.minimum[i])||!finite(e.maximum[i])||e.minimum[i]>e.maximum[i]) return false;
  extensions_[extension_count_++]=e;return true;
}
bool Chain::configure(const Stage* stages, unsigned n) {
  if(n>max_stages || (n && !stages)) return false;
  unsigned seen=0;
  for(unsigned i=0;i<n;++i) {
    const auto s=stages[i]; unsigned k=unsigned(s.kind);
    if(!finite(s.a)||!finite(s.b)||!finite(s.c)) return false;
    if(k>unsigned(Kind::reverb)) {
      const auto* e=extension(k);if(!e) return false;
      float values[3]={s.a,s.b,s.c};
      for(unsigned j=0;j<3;++j) if(values[j]<e->minimum[j]||values[j]>e->maximum[j]) return false;
      for(unsigned j=0;j<i;++j) if(unsigned(stages[j].kind)==k) return false;
      continue;
    }
    // One stateful instance of each effect; multiple gain/drive stages are OK.
    if(k>=unsigned(Kind::nam) && (seen&(1u<<k))) return false;
    seen|=1u<<k;
    switch(s.kind) {
    case Kind::gain: if(s.a<0||s.a>16) return false; break;
    case Kind::drive: case Kind::distortion: if(s.a<1||s.a>100||s.b<0||s.b>1) return false; break;
    case Kind::tremolo: case Kind::chorus: if(s.a<0.1f||s.a>20||s.b<0||s.b>1) return false; break;
    case Kind::pitch: if(s.a < -12||s.a>12||s.b<0||s.b>1) return false; break;
    case Kind::delay: if(s.a<1||s.a>900||s.b<0||s.b>0.95f||s.c<0||s.c>1) return false; break;
    case Kind::reverb: if(s.a<0||s.a>0.9f||s.b<0||s.b>1) return false; break;
    default: break;
    }
  }
  count_=n; for(unsigned i=0;i<n;++i) stages_[i]=stages[i]; reset(); return true;
}
void Chain::reset() {
  for(auto &x:delay_) x=0; for(auto &x:chorus_) x=0; for(auto &x:pitch_) x=0;
  for(auto &r:comb_) for(auto &x:r) x=0;
  for(auto &p:comb_pos_) p=0;
  delay_pos_=chorus_pos_=pitch_pos_=rejected_=0; trem_phase_=chorus_phase_=pitch_phase_=0;
  for(unsigned i=0;i<extension_count_;++i) if(extensions_[i].reset) extensions_[i].reset(extensions_[i].context);
}
bool Chain::process(const float* in, float* out, unsigned n) {
  if(n>max_block || (n && (!in||!out))) return false;
  // Fail before altering state if a requested model is missing.
  for(unsigned i=0;i<count_;++i) if(stages_[i].enabled&&stages_[i].kind==Kind::nam&&!model_) return false;
  for(unsigned i=0;i<n;++i) { float x=in[i]; if(!finite(x)) {x=0; ++rejected_;} scratch_[0][i]=x; }
  unsigned bank=0;
  for(unsigned st=0;st<count_;++st) {
    auto s=stages_[st]; float* src=scratch_[bank]; float* dst=scratch_[bank^1];
    if(!s.enabled) continue;
    if(s.kind==Kind::nam) model_(context_,src,dst,n);
    else if(const auto* e=extension(unsigned(s.kind))) e->process(e->context,s,src,dst,n);
    else for(unsigned i=0;i<n;++i) {
      float x=src[i], y=x;
      switch(s.kind) {
      case Kind::gain: y=x*s.a; break;
      case Kind::drive: y=(1-s.b)*x+s.b*tanhf(s.a*x); break;
      case Kind::distortion: y=(1-s.b)*x+s.b*clip(s.a*x); break;
      case Kind::tremolo: y=x*(1-s.b*(0.5f+0.5f*sinf(tau*trem_phase_))); trem_phase_=wrap(trem_phase_+s.a/sample_rate); break;
      case Kind::chorus: {
        chorus_[chorus_pos_]=x;
        float wet=read(chorus_,2048,chorus_pos_,576+240*sinf(tau*chorus_phase_));
        y=x*(1-s.b)+wet*s.b; chorus_pos_=(chorus_pos_+1)%2048;
        chorus_phase_=wrap(chorus_phase_+s.a/sample_rate); break;
      }
      case Kind::pitch: {
        if(s.a==0) break;
        pitch_[pitch_pos_]=x;
        float p2=wrap(pitch_phase_+0.5f), w=0.5f-0.5f*cosf(tau*pitch_phase_);
        float wet=w*read(pitch_,4096,pitch_pos_,32+2048*pitch_phase_)+(1-w)*read(pitch_,4096,pitch_pos_,32+2048*p2);
        y=x*(1-s.b)+wet*s.b; pitch_pos_=(pitch_pos_+1)%4096;
        pitch_phase_=wrap(pitch_phase_+(1-powf(2,s.a/12))/2048); break;
      }
      case Kind::delay: {
        unsigned d=unsigned(s.a*48+0.5f); float wet=delay_[(delay_pos_+48000-d)%48000];
        delay_[delay_pos_]=x+wet*s.b; delay_pos_=(delay_pos_+1)%48000;
        y=x*(1-s.c)+wet*s.c; break;
      }
      case Kind::reverb: {
        constexpr unsigned lengths[4]={1557,1617,1491,1422}; float wet=0;
        for(unsigned j=0;j<4;++j) { float v=comb_[j][comb_pos_[j]]; wet+=v*0.25f;
          comb_[j][comb_pos_[j]]=x+s.a*v; comb_pos_[j]=(comb_pos_[j]+1)%lengths[j]; }
        y=x*(1-s.b)+wet*s.b; break;
      }
      default: break;
      }
      dst[i]=y;
    }
    for(unsigned i=0;i<n;++i) if(!finite(dst[i])) { dst[i]=0; ++rejected_; }
    bank^=1;
  }
  for(unsigned i=0;i<n;++i) out[i]=scratch_[bank][i];
  return true;
}
bool Lstm::load(unsigned hidden,const float* weights,unsigned count) {
  if(hidden<1||hidden>16||!weights||count!=4*hidden*(hidden+1)+7*hidden+1) return false;
  for(unsigned i=0;i<count;++i) if(!finite(weights[i])) return false;
  h_=hidden; for(unsigned i=0;i<count;++i) weights_[i]=weights[i]; reset(); return true;
}
void Lstm::reset() {
  unsigned offset=4*h_*(h_+1)+4*h_;
  for(unsigned i=0;i<h_;++i) {hidden_[i]=weights_[offset+i]; cell_[i]=weights_[offset+h_+i];}
}
void Lstm::process(const float* in,float* out,unsigned n) {
  if(!h_) {for(unsigned t=0;t<n;++t) out[t]=0; return;}
  const unsigned bias=4*h_*(h_+1), head=bias+6*h_;
  for(unsigned t=0;t<n;++t) {
    float gates[64];
    for(unsigned r=0;r<4*h_;++r) {
      unsigned w=r*(h_+1); float sum=weights_[bias+r]+weights_[w]*in[t];
      for(unsigned c=0;c<h_;++c) sum+=weights_[w+c+1]*hidden_[c]; gates[r]=sum;
    }
    for(unsigned i=0;i<h_;++i) cell_[i]=sigmoid(gates[h_+i])*cell_[i]+sigmoid(gates[i])*tanhf(gates[2*h_+i]);
    float y=weights_[head+h_];
    for(unsigned i=0;i<h_;++i) {hidden_[i]=sigmoid(gates[3*h_+i])*tanhf(cell_[i]); y+=weights_[head+i]*hidden_[i];}
    out[t]=y;
  }
}
}
