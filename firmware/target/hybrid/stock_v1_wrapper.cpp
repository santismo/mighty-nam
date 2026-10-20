// V1.5.6 candidate integration, exercised ONLY in the offline emulator.
// Addresses are derived from this specific saved stock application.
extern "C" {
extern unsigned mpp_hybrid_enabled, mpp_hybrid_ready;
void mpp_hybrid_reset();
void mpp_hybrid_amp(const float*,const float*,float*,float*);
unsigned mpp_stock_last_control;
void mpp_stock_amp_init() {
  // The existing stock runtime zeros this candidate amp RAM arena before
  // main. Explicit initialization also handles retained/junk state.
  mpp_hybrid_enabled=0;
  mpp_stock_last_control=0xffffffffu;
  mpp_hybrid_reset();
}
void mpp_stock_amp_process(const float* left,const float* right,
                           float* out_left,float* out_right) {
  unsigned preset=*reinterpret_cast<const volatile unsigned*>(0x20005ad0u);
  if (preset<0x20000000u || preset>0x2003ff80u || !mpp_hybrid_ready) {
    for(unsigned i=0;i<8;++i) out_left[i]=out_right[i]=0;
    return;
  }
  unsigned control=*reinterpret_cast<const volatile unsigned char*>(preset+3);
  // Fixed single-model experiment: every enabled AMP type selects the fixture.
  // Reset state on AMP type/bypass changes. Smooth transitions remain future work.
  if(control!=mpp_stock_last_control) {
    mpp_hybrid_reset();
    mpp_stock_last_control=control;
  }
  mpp_hybrid_enabled=(control&0x40u)==0;
  mpp_hybrid_amp(left,right,out_left,out_right);
}
}
