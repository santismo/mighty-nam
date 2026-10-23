#include "store.hpp"
#include <array>
#include <cassert>
#include <cstring>
#include <cstdio>
using namespace mighty_loop;
using S=SettingsStore;
struct Flash {
 std::array<uint8_t,8192> bytes;
 int fail=-1,written=0;unsigned erases=0;
 Flash(){bytes.fill(255);}
 static bool read(void* p,uint32_t at,uint8_t* out,unsigned n){auto& f=*(Flash*)p;assert(at>=S::base&&at+n<=S::base+8192);memcpy(out,f.bytes.data()+at-S::base,n);return true;}
 static bool erase(void* p,uint32_t at){auto& f=*(Flash*)p;assert((at&4095)==0);if(f.fail==0)return false;memset(f.bytes.data()+at-S::base,255,4096);++f.erases;return true;}
 static bool program(void* p,uint32_t at,const uint8_t* src,unsigned n){auto& f=*(Flash*)p;assert(n==256-(at&255));for(unsigned i=0;i<n;++i){if(f.fail>=0&&f.written++>=f.fail)return false;f.bytes[at-S::base+i]&=src[i];}return true;}
 S store(){return {{this,read,erase,program}};}
};
int main(){
 uint8_t a[256],b[256];Flash f;
 assert(f.store().load(a,b)==S::empty);
 // Migrate the exact old buffer-only format without losing its setting.
 auto* v=f.bytes.data();S::put(v,0,0x3142474e);S::put(v,4,1);S::put(v,8,7);S::put(v,12,16);S::put(v,248,S::crc(v,248));S::put(v,252,S::commit);
 const unsigned custom=50|(67<<8)|(60<<16);
 assert(S::valid(v));assert(f.store().save(0,custom,a,b)==0);assert(f.store().load(a,b)==0&&S::word(a,12)==16&&S::loop(a)==custom);
 auto before=f;unsigned cuts=0;
 for(int cut=0;cut<=260;++cut){auto trial=before;trial.fail=cut;trial.written=0;unsigned result=trial.store().save(8,0,a,b);trial.fail=-1;assert(trial.store().load(a,b)==0);assert(S::loop(a)==custom);assert(S::word(a,12)==(result==0?8:16));++cuts;}
 assert(f.store().save(8,0,a,b)==0);assert(f.store().load(a,b)==0&&S::word(a,12)==8&&S::loop(a)==custom);
 auto erases=f.erases;assert(f.store().save(0,custom,a,b)==0&&f.erases==erases);
 for(unsigned x:{0u,11u,61u,0xffffffffu}){if(x)assert(f.store().save(0,x,a,b)==S::invalid);}
 // A committed copy with a damaged CRC must fall back to the other sector.
 unsigned selected=0;assert(f.store().load(a,b,&selected)==0);f.bytes[selected*4096+20]^=1;
 assert(f.store().load(a,b)==0&&S::loop(a)==custom&&S::word(a,12)==16);
 printf("{\"status\":\"PASS_LOOP_SETTINGS_STORE\",\"interrupted_write_cases\":%u,\"legacy_migration\":true,\"buffer_preserved\":true}\n",cuts);
}
