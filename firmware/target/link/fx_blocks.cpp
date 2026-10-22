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
 // No delay-buffer clear inside the IRQ. filled prevents stale reads until
 // samples from the new route have overwritten each required delay position.
 for(auto& channel:allpass)for(auto& value:channel)value=0;
 feedback[0]=feedback[1]=0;phase=pitch_phase=envelope=wet=0;ratio=1;
 write=filled=previous_mode=previous_position=previous_enabled=0;
 pitch_window=target_window=1536;yin_sum=0;yin_previous=yin_before=1;yin_lag=1;
}
static float tap(const Engine& e,unsigned ch,float distance){
 const unsigned whole=(unsigned)distance;
 if(whole+1>=e.filled)return 0;
 const float fraction=distance-whole;
 const float a=e.delay[ch][(e.write-whole)&2047],b=e.delay[ch][(e.write-whole-1)&2047];
 return a+(b-a)*fraction;
}
void Engine::process(const uint8_t* c,float* l,float* r,unsigned count){
 const unsigned mode=c[0];
 if(mode!=previous_mode||c[2]!=previous_position||(c[1]&&!previous_enabled))reset();
 previous_mode=mode;previous_position=c[2];previous_enabled=c[1];
 if(!c[1]&&wet==0)return;
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
  for(unsigned ch=0;ch<2;++ch)delay[ch][write]=clamp(input[ch]+((mode==4)?feedback[ch]*fb:0),-8,8);
  if(filled<delay_size)++filled;
  if(mode==1&&c[3]!=12){
   // Monophonic pitch-synchronous grains. Two small YIN lag checks per
   // eight-frame call bound the IRQ work; no full pitch scan in one callback.
   if(filled>=1472&&(i&3)==0){
    float difference=0;for(unsigned j=0;j<160;++j){float d=delay[0][(write-j*4)&2047]-delay[0][(write-(j+yin_lag)*4)&2047];difference+=d*d;}
    yin_sum+=difference;float value=yin_sum>1e-12f?difference*yin_lag/yin_sum:1;
    if(yin_lag>12&&yin_previous<.12f&&yin_previous<yin_before&&value>=yin_previous){
     float denominator=yin_before-2*yin_previous+value;
     float offset=denominator>0?clamp(.5f*(yin_before-value)/denominator,-.5f,.5f):0;
     target_window=clamp(8*(yin_lag-1+offset),96,1472);yin_lag=1;yin_sum=0;yin_previous=yin_before=1;
    }else if(++yin_lag>184){yin_lag=1;yin_sum=0;yin_previous=yin_before=1;}
    else{yin_before=yin_previous;yin_previous=value;}
   }
   pitch_window+=(target_window-pitch_window)*.002f;
   pitch_phase+=(1-ratio)/pitch_window;
   if(pitch_phase<0)pitch_phase+=1;if(pitch_phase>=1)pitch_phase-=1;
   float second=pitch_phase+.5f;if(second>=1)second-=1;
   const float w=1-absf(2*pitch_phase-1);
   for(unsigned ch=0;ch<2;++ch)out[ch]=w*tap(*this,ch,16+pitch_window*pitch_phase)+(1-w)*tap(*this,ch,16+pitch_window*second);
  }else if(mode==2){
   // A wider envelope response and resonant, normalized band-pass sweep.
   // Rational compression gives quiet notes useful movement without hard
   // pinning louder attacks at the top of the sweep.
   const float drive=envelope*(.5f+.0062f*c[8]*c[8]);
   const float frequency=180+3420*drive/(1+drive),q=1/(1+.06f*c[9]);
   const float x=frequency*(3.141592654f/48000),g=x/(1-.3333333f*x*x),den=1/(1+g*(g+q));
   for(unsigned ch=0;ch<2;++ch){float v3=input[ch]-allpass[ch][1],v1=(allpass[ch][0]+g*v3)*den,v2=allpass[ch][1]+g*v1;allpass[ch][0]=2*v1-allpass[ch][0];allpass[ch][1]=2*v2-allpass[ch][1];out[ch]=v1*q;}
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
