// Offline DaisySP/Soundpipe auto-wah adaptation. Not part of release firmware.
// Copyright (c) 2020 Electrosmith, Corp, Paul Batchelor.
// Adaptation copyright (c) 2026 santismo. MIT; see DAISY-LICENSE.
#pragma once
namespace mighty_wah {
// Approximate 2^x over [0,2.3]; range reduction plus degree-six Taylor.
// Host tests compare against the unmodified upstream powf/cosf core.
inline float exp2(float x) {
 unsigned n=(unsigned)x;float f=(x-n)*.6931471805599453f;
 return (1u<<n)*(1+f*(1+f*(.5f+f*(.1666666667f+f*(.04166666667f+f*(.008333333333f+f*.001388888889f))))));
}
struct State {
 float peak,env,a1,a2,gain,z1[2],z2[2];
 void reset(){peak=env=a1=a2=gain=0;for(unsigned ch=0;ch<2;++ch)z1[ch]=z2[ch]=0;}
 void process(float* x,float sensitivity,float resonance) {
  float level=__builtin_fabsf(x[0]);float other=__builtin_fabsf(x[1]);if(other>level)level=other;
  level*=sensitivity;
  // Upstream 100 ms peak release, 10 ms envelope smoothing at 48 kHz.
  peak=level>peak?level:.9997916884f*peak+.0002083116f*level;
  env=.9979188353f*env+.0020811647f*peak;
  float e=env<1?env:1;
  float power=exp2(2*e),angle=.05890486225f*exp2(2.3f*e);
  float radius=1-angle*power/(16*resonance),square=angle*angle;
  float cosine=1+square*(-.5f+square*(.04166666667f-square*.001388888889f));
  a1=.999f*a1-.002f*radius*cosine;
  a2=.999f*a2+.001f*radius*radius;
  gain=.999f*gain+.0001f*power/resonance;
  for(unsigned ch=0;ch<2;++ch){float z=gain*x[ch]-a1*z1[ch]-a2*z2[ch];x[ch]=z-z1[ch];z2[ch]=z1[ch];z1[ch]=z;}
 }
};
}
