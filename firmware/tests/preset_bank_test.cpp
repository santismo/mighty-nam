#include "../target/link/preset_bank.hpp"
#include "../target/link/model_receiver.hpp"
#include <array>
#include <vector>
#include <cassert>
#include <cstdio>
#include <algorithm>
using namespace mpp::presets;
struct Flash {
 std::vector<uint8_t> data=std::vector<uint8_t>(end-base,255);
 int remaining=-1, writes=0; bool fail_read=false; unsigned torn=0;
 bool tick(){++writes;return remaining<0||remaining-->0;}
 static bool rd(void* c,uint32_t a,uint8_t* b,unsigned n){auto& f=*(Flash*)c;assert(a>=base&&a+n<=end);if(f.fail_read)return false;std::copy_n(f.data.data()+a-base,n,b);return true;}
 static bool erase(void* c,uint32_t a){auto& f=*(Flash*)c;assert(a>=base&&a+4096<=end&&a%4096==0);bool ok=f.tick();unsigned n=ok?4096:f.torn;std::fill_n(f.data.data()+a-base,n,255);return ok;}
 static bool pg(void* c,uint32_t a,const uint8_t* p,unsigned n){auto& f=*(Flash*)c;assert(a>=base&&a+n<=end&&n&&n<=256&&a/256==(a+n-1)/256);bool ok=f.tick();unsigned size=ok?n:std::min(n,f.torn);for(unsigned i=0;i<size;++i){assert((f.data[a-base+i]&p[i])==p[i]);f.data[a-base+i]&=p[i];}return ok;}
 IO io(){return {this,rd,erase,pg};}
};
int main(){
 std::array<uint8_t,8192> model{},a{},b{},restored{};
 model.fill(255);std::fill_n(model.begin(),7516,0);
 for(auto pair: {std::array<unsigned,2>{0,0x3241504d},{4,1},{8,48000},{12,1871},{16,7484},{24,1}})put(model.data(),pair[0],pair[1]);
 put(model.data(),20,mpp::link::crc32(model.data()+32,7484));
 std::array<uint8_t,128> fx{};for(unsigned i=1;i<=9;++i){fx[i]=1;fx[89+i]=i;}
 std::array<uint8_t,32> sha{};std::array<uint8_t,64> name{};name[0]='A';
 Flash f;Bank bank(f.io());unsigned cases=0;
 for(unsigned slot=0;slot<7;++slot){
  name[0]='A'+slot;sha[0]=slot;
  assert(bank.read(slot,a.data(),b.data())==empty);
  assert(bank.save(slot,model.data(),fx.data(),sha.data(),name.data(),1,8,a.data(),b.data())==ok);
  unsigned writes=f.writes;
  assert(bank.save(slot,model.data(),fx.data(),sha.data(),name.data(),1,8,a.data(),b.data())==ok&&f.writes==int(writes));
  Bank restarted(f.io());assert(restarted.read(slot,a.data(),b.data())==ok&&word(a.data(),12)==1&&a[64]=='A'+slot);
  Bank::unpack_model(a.data(),restored.data());assert(restored==model);cases+=4;
 }
 const auto baseline=f.data;name[0]='Z';
 // Every erase/program boundary, with partial programming/erase as well as
 // failure before the operation. A reboot may select old or complete new,
 // never a mixture; unrelated colors are byte-for-byte unchanged.
 for(unsigned cut=0;cut<36;++cut)for(unsigned torn: {0u,1u,3u,4u,127u,256u}){
  Flash broken;broken.data=baseline;broken.remaining=cut;broken.torn=torn;Bank writer(broken.io());
  auto result=writer.save(3,model.data(),fx.data(),sha.data(),name.data(),1,16,a.data(),b.data());
  assert(result==ok||result==io_error);broken.remaining=-1;broken.torn=0;
  Bank reboot(broken.io());assert(reboot.read(3,a.data(),b.data())==ok);
  assert((a[64]=='D'&&word(a.data(),12)==1&&word(a.data(),24)==8)||(a[64]=='Z'&&word(a.data(),12)==2&&word(a.data(),24)==16));
  for(unsigned i=0;i<broken.data.size();++i)if(i/16384!=3)assert(broken.data[i]==baseline[i]);++cases;
 }
 f.data=baseline;assert(bank.save(2,model.data(),fx.data(),sha.data(),name.data(),1,32,a.data(),b.data())==ok);
 f.data[2*16384+8192+500]^=1;
 assert(bank.read(2,a.data(),b.data())==ok&&word(a.data(),12)==1);++cases;
 f.fail_read=true;unsigned writes=f.writes;
 assert(bank.save(2,model.data(),fx.data(),sha.data(),name.data(),1,8,a.data(),b.data())==io_error&&f.writes==int(writes));f.fail_read=false;++cases;
 for(unsigned slot: {7u,255u,0xffffffffu}){assert(bank.save(slot,model.data(),fx.data(),sha.data(),name.data(),1,8,a.data(),b.data())==invalid);++cases;}
 writes=f.writes;fx[90]=fx[91];assert(bank.save(0,model.data(),fx.data(),sha.data(),name.data(),1,8,a.data(),b.data())==invalid);fx[90]=1;
 model[8191]=0;assert(bank.save(0,model.data(),fx.data(),sha.data(),name.data(),1,8,a.data(),b.data())==invalid);model[8191]=255;
 name.fill('a');assert(bank.save(0,model.data(),fx.data(),sha.data(),name.data(),1,8,a.data(),b.data())==invalid);
 assert(f.writes==int(writes));cases+=3;
 std::printf("PASS %u bank cases: seven colors, exact model/effects, duplicate saves, corruption and interrupted writes; no hardware/audio\n",cases);
}
