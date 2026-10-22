#include "nam_controls.hpp"
namespace mpp::tone {
static const float gains[97]={0x1.0270ac3f8a9fap-4f,0x1.11c0f06d80170p-4f,0x1.21f97ef20893cp-4f,0x1.33281b6744ae1p-4f,0x1.455b5a30b035cp-4f,0x1.58a2acda3500bp-4f,0x1.6d0e6f32e6ea2p-4f,0x1.82aff52e87a2fp-4f,0x1.999999999999ap-4f,0x1.b1decdac7bf4dp-4f,0x1.cb94298ac6d25p-4f,0x1.e6cf7dbce77c0p-4f,0x1.01d3f2d9684d0p-3f,0x1.111aedafb9a9dp-3f,0x1.2149a5fed24dap-3f,0x1.326dd708071b0p-3f,0x1.44960c576b375p-3f,0x1.57d1ae1b6242bp-3f,0x1.6c310e3769f3fp-3f,0x1.81c5761d32f80p-3f,0x1.98a13577c93c0p-3f,0x1.b0d7b1b53e057p-3f,0x1.ca7d767c030d5p-3f,0x1.e5a84719edcd2p-3f,0x1.0137987dd704cp-2f,0x1.10754f9e31838p-2f,0x1.209a37aef4450p-2f,0x1.31b4039db843fp-2f,0x1.43d136248490fp-2f,0x1.57012e19e480dp-2f,0x1.6b54337bc3b65p-2f,0x1.80db8540212cfp-2f,0x1.97a967f7524b2p-2f,0x1.afd1354c40d50p-2f,0x1.c9676c6fcaf21p-2f,0x1.e481c37d34012p-2f,0x1.009b9cf334252p-1f,0x1.0fd015fbdabe0p-1f,0x1.1feb33c1c381ep-1f,0x1.30faa0e3d83f5p-1f,0x1.430cd74f6d478p-1f,0x1.56312c88e01cdp-1f,0x1.6a77deae8ab8ap-1f,0x1.7ff2224115d9ap-1f,0x1.96b230bcdc434p-1f,0x1.aecb5810c240dp-1f,0x1.c8520affa0a4bp-1f,0x1.e35bf27a298b9p-1f,0x1.0000000000000p+0f,0x1.0f2b408bcd790p+0f,0x1.1f3c99f6bc436p+0f,0x1.3041ae9610ad9p+0f,0x1.4248ef8fc2604p+0f,0x1.5561a91ba8144p+0f,0x1.699c0f7e86e10p+0f,0x1.7f094cca08e1cp+0f,0x1.95bb8f6d46053p+0f,0x1.adc619a23ad36p+0f,0x1.c73d51c54470ep+0f,0x1.e236d3a47fb60p+0f,0x1.fec982d5bb8afp+0f,0x1.0e86cf1146c37p+1f,0x1.1e8e6a0d81e85p+1f,0x1.2f892c7034a03p+1f,0x1.41857e9d4cc5fp+1f,0x1.5492a385bde46p+1f,0x1.68c0c59ab1564p+1f,0x1.7e2104852654fp+1f,0x1.94c583ada5b53p+1f,0x1.acc179a05da10p+1f,0x1.c629405ab4a3fp+1f,0x1.e112669029781p+1f,0x1.fd93c1f526ddfp+1f,0x1.0de2c14fa8852p+2f,0x1.1de0a3c5ded75p+2f,0x1.2ed11a2e4080cp+2f,0x1.40c28430012e6p+2f,0x1.53c41b7ad16d8p+2f,0x1.67e600b234626p+2f,0x1.7d39491cce4f2p+2f,0x1.93d00d2348997p+2f,0x1.abbd77ab1823fp+2f,0x1.c515d65a2d66cp+2f,0x1.dfeeaad15b500p+2f,0x1.fc5ebcec13542p+2f,0x1.0d3f170a79688p+3f,0x1.1d3346dfc466ep+3f,0x1.2e19778c59f73p+3f,0x1.4000000000000p+3f,0x1.52f610aec0d73p+3f,0x1.670bc0746b545p+3f,0x1.7c521a3b94d8ep+3f,0x1.92db2b73b2f86p+3f,0x1.aaba136292195p+3f,0x1.c403135e28992p+3f,0x1.decb9ffc8b1a4p+3f,0x1.fb2a734897866p+3f};
void defaults(uint8_t* p){p[0]=48;p[1]=p[2]=p[3]=12;p[4]=100;p[5]=48;}
bool valid(const uint8_t* p){return p[0]<=96&&p[1]<=24&&p[2]<=24&&p[3]<=24&&p[4]<=100&&p[5]<=96;}
void decode(const uint8_t* preset,uint8_t* p){if(preset[33]==78&&preset[34]==1&&valid(preset+27))for(unsigned i=0;i<6;++i)p[i]=preset[27+i];else defaults(p);}
void Engine::reset(){low=high=0;ready=false;}
const float* Engine::prepare(const float* dry,const uint8_t* p){
 float target[6]={gains[p[0]],gains[2*p[1]+24],gains[2*p[2]+24],gains[2*p[3]+24],float(p[4])*.01f,gains[p[5]]};
 for(unsigned j=0;j<6;++j){if(!ready)gain[j]=target[j];else{gain[j]+=(target[j]-gain[j])*.0625f;if(__builtin_fabsf(target[j]-gain[j])<.00001f)gain[j]=target[j];}}
 ready=true;
 if(gain[0]==1)return dry;
 for(unsigned i=0;i<8;++i)input[i]=dry[i]*gain[0];return input;
}
void Engine::finish(const float* dryL,const float* dryR,float* l,float* r){
 const float a=1-gain[4],b=gain[4],o=gain[5];
 const bool flat=gain[1]==1&&gain[2]==1&&gain[3]==1;
 for(unsigned i=0;i<8;++i){float x=l[i];
  // 150 Hz / 3 kHz parallel crossovers at the hardware's fixed 48 kHz.
  low+=.01944344385f*(x-low);high+=.3247680933f*(x-high);
  if(!flat)x+=(gain[1]-1)*low+(gain[2]-1)*(high-low)+(gain[3]-1)*(x-high);
  if(b==1&&o==1){l[i]=x;r[i]=x;}else{l[i]=(a*dryL[i]+b*x)*o;r[i]=(a*dryR[i]+b*x)*o;}
 }
}
}
