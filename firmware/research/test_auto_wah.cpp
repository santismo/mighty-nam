#include "fx_blocks.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>

// A fixed level on the other channel isolates the shared envelope from the
// small swept sine. This measures the actual filter response, not its formula.
static float response(float hz, float level, unsigned sensitivity, unsigned resonance) {
 static mpp::fx::Engine engine;
 engine.reset(); uint8_t config[32]; mpp::fx::defaults(config);
 config[0]=2; config[1]=1; config[4]=100;
 config[8]=sensitivity; config[9]=resonance;
 double energy=0;
 for(unsigned n=0;n<24000;n+=8) {
  float left[8],right[8];
  for(unsigned i=0;i<8;i++){left[i]=.001f*std::sin(6.283185307f*hz*(n+i)/48000);right[i]=level;}
  engine.process(config,left,right,8);
  for(float value:left){assert(std::isfinite(value));if(n>=12000)energy+=value*value;}
 }
 return std::sqrt(energy/12000)*1414.213562f;
}
static float peak(float level,unsigned sensitivity,unsigned resonance) {
 float best=0,frequency=0;
 for(unsigned hz=100;hz<=3700;hz+=25){float gain=response(hz,level,sensitivity,resonance);if(gain>best){best=gain;frequency=hz;}}
 assert(best>.8f && best<1.1f);return frequency;
}
int main(){
 const float soft=peak(.01f,50,50),loud=peak(.15f,50,50);
 const float sensitive=peak(.01f,100,50),lowSense=peak(.01f,0,50);
 assert(soft>300 && soft<900 && loud>2000 && loud>soft*2);
 assert(sensitive>soft*1.5f && lowSense<300);
 // More resonance must narrow the response without boosting its peak.
 const float broad=response(loud*.7f,.15f,50,0),focused=response(loud*.7f,.15f,50,100);
 assert(focused<broad*.5f);
 std::printf("{\"status\":\"PASS_AUTO_WAH_RESPONSE\",\"soft_peak_hz\":%.0f,\"loud_peak_hz\":%.0f,\"high_sensitivity_peak_hz\":%.0f,\"off_peak_broad\":%.5f,\"off_peak_resonant\":%.5f,\"audio_playback\":false}\n",soft,loud,sensitive,broad,focused);
}
