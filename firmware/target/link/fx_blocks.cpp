#include "fx_blocks.hpp"
namespace mpp::fx {
static float absf(float x){return x<0?-x:x;}
static float clamp(float x,float lo,float hi){return x<lo?lo:x>hi?hi:x;}
static float wave(float p){float x=p*2-1;float y=4*x*(1-absf(x));return y+.225f*(y*absf(y)-y);}
bool valid(const uint8_t* p){
 if(!p||p[2]==p[18])return false;
 for(unsigned slot=0;slot<2;++slot){const auto* c=p+16*slot;
  if(c[0]<1||c[0]>7||c[1]>1||c[2]>10||c[3]>24)return false;
  for(unsigned i=4;i<10;++i)if(c[i]>100)return false;
  for(unsigned i=10;i<16;++i)if(c[i])return false;
 }return true;
}
void defaults(uint8_t* p){for(unsigned i=0;i<32;++i)p[i]=0;for(unsigned j=0;j<2;++j){auto* c=p+j*16;c[0]=j+1;c[2]=j+2;c[3]=12;c[4]=100;c[5]=30;c[6]=50;c[8]=50;c[9]=50;}}
void Engine::reset(){
#ifdef MPP_DAISY_WAH
 wah.reset();
#endif
 // No delay-buffer clear inside the IRQ. filled prevents stale reads until
 // samples from the new route have overwritten each required delay position.
 for(auto& channel:allpass)for(auto& value:channel)value=0;
 feedback[0]=feedback[1]=0;phase=pitch_phase=envelope=wet=0;ratio=1;
 write=filled=previous_mode=previous_position=previous_enabled=0;
#ifdef MPP_PITCH_QUALITY_PROTOTYPE
 fine_count=fine_center=fine_anchor=filter_active=0;
#endif
 pitch_window=target_window=1536;yin_sum=0;yin_previous=yin_before=1;yin_lag=1;
}
static float tap(const Engine& e,unsigned ch,float distance){
 const unsigned whole=(unsigned)distance;
 if(whole+1>=e.filled)return 0;
 const float fraction=distance-whole;
 const float a=e.delay[ch][(e.write-whole)&2047],b=e.delay[ch][(e.write-whole-1)&2047];
 return a+(b-a)*fraction;
}
#ifdef MPP_PITCH_QUALITY_PROTOTYPE
// 48 kHz fourth-order Butterworth low-pass, two SOS, +1..+12 semitones.
// Cutoff = .45 * sample_rate / pitch_ratio; Q = .5411961, 1.30656296.
// DF2T coefficients are b0,b1,b2,a1,a2. State reuses the mode-exclusive
// allpass array. Filtering only the wet ring preserves exact dry/zero shift.
static const float pitchFilters[12][10]={
 {6.6523371599e-01f,1.3304674320e+00f,6.6523371599e-01f,1.2532365483e+00f,4.0769831562e-01f,8.0486211913e-01f,1.6097242383e+00f,8.0486211913e-01f,1.5162830744e+00f,7.0316540213e-01f},
 {5.8888740323e-01f,1.1777748065e+00f,5.8888740323e-01f,1.0558242366e+00f,2.9972537631e-01f,7.4083735963e-01f,1.4816747193e+00f,7.4083735963e-01f,1.3282573806e+00f,6.3509205794e-01f},
 {5.2528773854e-01f,1.0505754771e+00f,5.2528773854e-01f,8.8101629941e-01f,2.2013465476e-01f,6.8079250424e-01f,1.3615850085e+00f,6.8079250424e-01f,1.1418299891e+00f,5.8134002790e-01f},
 {4.7136359259e-01f,9.4272718518e-01f,4.7136359259e-01f,7.2417407926e-01f,1.6128029110e-01f,6.2486500101e-01f,1.2497300020e+00f,6.2486500101e-01f,9.6000421730e-01f,5.3945578674e-01f},
 {4.2497206628e-01f,8.4994413257e-01f,4.2497206628e-01f,5.8187644569e-01f,1.1801181945e-01f,5.7299219948e-01f,1.1459843990e+00f,5.7299219948e-01f,7.8454724650e-01f,5.0742155141e-01f},
 {3.8457544560e-01f,7.6915089121e-01f,3.8457544560e-01f,4.5155270728e-01f,8.6749075137e-02f,5.2500692384e-01f,1.0500138477e+00f,5.2500692384e-01f,6.1644158646e-01f,4.8358610891e-01f},
 {3.4904308191e-01f,6.9808616382e-01f,3.4904308191e-01f,3.3123886898e-01f,6.4933458652e-02f,4.8069259826e-01f,9.6138519652e-01f,4.8069259826e-01f,4.5617312254e-01f,4.6659727050e-01f},
 {3.1752563934e-01f,6.3505127868e-01f,3.1752563934e-01f,2.1941223428e-01f,5.0690323076e-02f,4.3981444859e-01f,8.7962889718e-01f,4.3981444859e-01f,3.0391457847e-01f,4.5534321589e-01f},
 {2.8937283241e-01f,5.7874566483e-01f,2.8937283241e-01f,1.1487679638e-01f,4.2614533273e-02f,4.0213666142e-01f,8.0427332284e-01f,4.0213666142e-01f,1.5964239277e-01f,4.4890425290e-01f},
 {2.6407816279e-01f,5.2815632558e-01f,2.6407816279e-01f,1.6682242959e-02f,3.9630408204e-02f,3.6743136682e-01f,7.3486273363e-01f,3.6743136682e-01f,2.3211231353e-02f,4.4651423591e-01f},
 {2.4124090871e-01f,4.8248181742e-01f,2.4124090871e-01f,-7.5934343216e-02f,4.0897978055e-02f,3.3548291716e-01f,6.7096583431e-01f,3.3548291716e-01f,-1.0559848705e-01f,4.4753015568e-01f},
 {2.2053942765e-01f,4.4107885530e-01f,2.2053942765e-01f,-1.6359116609e-01f,4.5748876697e-02f,3.0608951269e-01f,6.1217902538e-01f,3.0608951269e-01f,-2.2705028685e-01f,4.5140833761e-01f}
};
// Share the coarse/fine kernel to stay within the audited copied-code bank.
// Both phases use the same 160 differences; no extra search burst in the IRQ.
__attribute__((noinline)) static float pitchDifference(const Engine& e,unsigned anchor,unsigned lag){
 float difference=0;
 for(unsigned j=0;j<160;++j){
  float d=e.delay[0][(anchor-j*4)&2047]-e.delay[0][(anchor-j*4-lag)&2047];
  difference+=d*d;
 }
 return difference;
}

#endif
void Engine::process(const uint8_t* c,float* l,float* r,unsigned count){
 const unsigned mode=c[0];
 if(mode!=previous_mode||c[2]!=previous_position||(c[1]&&!previous_enabled))reset();
 previous_mode=mode;previous_position=c[2];previous_enabled=c[1];
 if(!c[1]&&wet==0)return;
#ifdef MPP_DAISY_WAH
 if(mode==2){
  const float target=c[1]?c[4]*.01f:0;
  const float sensitivity=.25f+.006375f*c[8]*c[8],resonance=.35f+.013f*c[9];
  for(unsigned i=0;i<count;++i){
   float original[2]={l[i],r[i]},x[2]={l[i],r[i]};
   if(!__builtin_isfinite(x[0])||!__builtin_isfinite(x[1])){reset();l[i]=r[i]=0;continue;}
   wah.process(x,sensitivity,resonance);wet+=clamp(target-wet,-1.f/256,1.f/256);
   for(unsigned ch=0;ch<2;++ch){float y=original[ch]+wet*(x[ch]-original[ch]);
    if(!__builtin_isfinite(y)){reset();y=0;}if(ch)r[i]=y;else l[i]=y;}
  }return;
 }

#endif
#ifdef MPP_PITCH_QUALITY_PROTOTYPE
 if(mode==1){
  // A return from downshift/neutral must not revive a stale filter transient.
  if(c[3]>12&&!filter_active)for(auto& ch:allpass)for(auto& state:ch)state=0;
  filter_active=c[3]>12;
 }
#endif
 static const float ratios[25]={.5f,.529731547f,.561231024f,.594603558f,.629960525f,.667419927f,.707106781f,.749153538f,.793700526f,.840896415f,.890898718f,.943874313f,1,1.05946309f,1.12246205f,1.18920712f,1.25992105f,1.33483985f,1.41421356f,1.49830708f,1.58740105f,1.68179283f,1.78179744f,1.88774863f,2};
 const float target=c[1]?c[4]*.01f:0,depth=c[6]*.01f,rate=(.05f+7.95f*c[5]*.01f)/48000;
 const float fb=c[7]*.007f;
 for(unsigned i=0;i<count;++i){
  float input[2]={l[i],r[i]},out[2]={input[0],input[1]};
  if(!__builtin_isfinite(input[0])||!__builtin_isfinite(input[1])){reset();l[i]=r[i]=0;continue;}
  float a=absf(input[0]),b=absf(input[1]),level=a>b?a:b;
  envelope+=(level-envelope)*(level>envelope?.01f:.0003f);
  phase+=rate;if(phase>=1)phase-=1;
  ratio+=(ratios[c[3]]-ratio)*.01f;
  const float modulation=wave(phase);
#ifdef MPP_PITCH_QUALITY_PROTOTYPE
  for(unsigned ch=0;ch<2;++ch){float z=input[ch];
   if(mode==1&&c[3]>12){const auto* coeff=pitchFilters[c[3]-13];
    for(unsigned stage=0;stage<2;++stage){const auto* a=coeff+5*stage;auto* state=allpass[ch]+2*stage;
     float y=a[0]*z+state[0];state[0]=a[1]*z-a[3]*y+state[1];state[1]=a[2]*z-a[4]*y;z=y;}}
   delay[ch][write]=clamp(z+((mode==4)?feedback[ch]*fb:0),-8,8);}

#else
  for(unsigned ch=0;ch<2;++ch)delay[ch][write]=clamp(input[ch]+((mode==4)?feedback[ch]*fb:0),-8,8);
#endif
  if(filled<delay_size)++filled;
  if(mode==1&&c[3]!=12){
   // Monophonic pitch-synchronous grains. Two small YIN lag checks per
   // eight-frame call bound the IRQ work; no full pitch scan in one callback.
   if(filled>=1472&&(i&3)==0){
#ifdef MPP_PITCH_QUALITY_PROTOTYPE
    // Freeze only the five fine comparisons (20 samples). The oldest
    // reference is under 1400 samples old, safely inside the 2048 ring.
    if(fine_count){
     const unsigned slot=fine_count-1,lag=fine_center+slot-2;
     fine_difference[slot]=pitchDifference(*this,fine_anchor,lag);
     if(++fine_count==6){
      unsigned best=1;for(unsigned k=2;k<4;++k)if(fine_difference[k]<fine_difference[best])best=k;
      float left=fine_difference[best-1],middle=fine_difference[best],right=fine_difference[best+1];
      float denominator=left-2*middle+right;
      float offset=denominator>1e-20f?clamp(.5f*(left-right)/denominator,-1,1):0;
      target_window=clamp(2*(fine_center+best-2+offset),96,1472);fine_count=0;
     }
    }else{

#endif
#ifdef MPP_PITCH_QUALITY_PROTOTYPE
    float difference=pitchDifference(*this,write,yin_lag*4);
#else
    float difference=0;for(unsigned j=0;j<160;++j){float d=delay[0][(write-j*4)&2047]-delay[0][(write-(j+yin_lag)*4)&2047];difference+=d*d;}
#endif
    yin_sum+=difference;float value=yin_sum>1e-12f?difference*yin_lag/yin_sum:1;
    if(yin_lag>12&&yin_previous<.12f&&yin_previous<yin_before&&value>=yin_previous){
     float denominator=yin_before-2*yin_previous+value;
     float offset=denominator>0?clamp(.5f*(yin_before-value)/denominator,-.5f,.5f):0;
#ifdef MPP_PITCH_QUALITY_PROTOTYPE
     fine_center=(unsigned)clamp(4*(yin_lag-1+offset)+.5f,48,736);fine_count=1;fine_anchor=write;yin_lag=1;yin_sum=0;yin_previous=yin_before=1;
#else
     target_window=clamp(8*(yin_lag-1+offset),96,1472);yin_lag=1;yin_sum=0;yin_previous=yin_before=1;
#endif
    }else if(++yin_lag>184){yin_lag=1;yin_sum=0;yin_previous=yin_before=1;}
    else{yin_before=yin_previous;yin_previous=value;}
   }
#ifdef MPP_PITCH_QUALITY_PROTOTYPE
   }
   // The weighted mean read delay is window/2. Compensate its motion so
   // tracking a bend does not itself add an unintended pitch modulation.
   const float window_change=(target_window-pitch_window)*.002f;
   pitch_window+=window_change;
   pitch_phase+=(1-ratio-.5f*window_change)/pitch_window;
#else
   pitch_window+=(target_window-pitch_window)*.002f;
   pitch_phase+=(1-ratio)/pitch_window;
#endif
   if(pitch_phase<0)pitch_phase+=1;if(pitch_phase>=1)pitch_phase-=1;
   float second=pitch_phase+.5f;if(second>=1)second-=1;
   const float w=1-absf(2*pitch_phase-1);
   for(unsigned ch=0;ch<2;++ch)out[ch]=w*tap(*this,ch,16+pitch_window*pitch_phase)+(1-w)*tap(*this,ch,16+pitch_window*second);

#ifndef MPP_DAISY_WAH
  }else if(mode==2){
   // A wider envelope response and resonant, normalized band-pass sweep.
   // Rational compression gives quiet notes useful movement without hard
   // pinning louder attacks at the top of the sweep.
   const float drive=envelope*(.5f+.0062f*c[8]*c[8]);
   const float frequency=180+3420*drive/(1+drive),q=1/(1+.06f*c[9]);
   const float x=frequency*(3.141592654f/48000),g=x/(1-.3333333f*x*x),den=1/(1+g*(g+q));
   for(unsigned ch=0;ch<2;++ch){float v3=input[ch]-allpass[ch][1],v1=(allpass[ch][0]+g*v3)*den,v2=allpass[ch][1]+g*v1;allpass[ch][0]=2*v1-allpass[ch][0];allpass[ch][1]=2*v2-allpass[ch][1];out[ch]=v1*q;}

#endif
  }else if(mode==3||mode==4||mode==7){
   for(unsigned ch=0;ch<2;++ch){float mod=modulation;if(ch&&mode==3){float p=phase+.25f;if(p>=1)p-=1;mod=wave(p);}
    float distance=mode==4?3+(1+mod)*depth*90:mode==3?600+mod*depth*470:350+mod*depth*320;
    out[ch]=tap(*this,ch,distance);feedback[ch]=out[ch];}
  }else if(mode==5){
   const float coefficient=.15f+.7f*(.5f+.5f*modulation)*depth;
   for(unsigned ch=0;ch<2;++ch){float x=input[ch]+feedback[ch]*fb;for(unsigned stage=0;stage<4;++stage){float y=allpass[ch][stage]-coefficient*x;allpass[ch][stage]=x+coefficient*y;x=y;}out[ch]=x;feedback[ch]=clamp(x,-4,4);}
  }else if(mode==6){const float gain=1-depth*(.5f+.5f*modulation);out[0]*=gain;out[1]*=gain;}
  // Delay effects fade in only when the ring contains the whole longest tap.
  const bool ready=(!(mode==1&&c[3]!=12)&&mode!=3&&mode!=4&&mode!=7)||filled>=1600;
  const float wanted=ready?target:0;wet+=clamp(wanted-wet,-1.f/256,1.f/256);
  for(unsigned ch=0;ch<2;++ch){float y=input[ch]+wet*(out[ch]-input[ch]);if(!__builtin_isfinite(y)){reset();y=0;}if(ch)r[i]=y;else l[i]=y;}
  write=(write+1)&2047;
 }
}
}
