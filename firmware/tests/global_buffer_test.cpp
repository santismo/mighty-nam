#include "../target/link/global_buffer.hpp"
#include <array>
#include <vector>
#include <algorithm>
#include <cassert>
#include <cstdio>
using namespace mpp;
struct Flash {
 std::vector<uint8_t> memory=std::vector<uint8_t>(settings::end-presets::base+4096,0x5a);
 int cut=-1,writes=0,reads=0,fail_read=-1;unsigned torn=0;
 Flash(){std::fill(memory.begin()+settings::base-presets::base,memory.begin()+settings::end-presets::base,255);}
 bool tick(){++writes;return cut<0||cut-->0;}
 static bool rd(void* c,uint32_t a,uint8_t* b,unsigned n){auto& f=*(Flash*)c;assert(a>=settings::base&&a+n<=settings::end&&n==256);if(f.reads++==f.fail_read)return false;std::copy_n(f.memory.data()+a-presets::base,n,b);return true;}
 static bool erase(void* c,uint32_t a){auto& f=*(Flash*)c;assert(a>=settings::base&&a+4096<=settings::end&&a%4096==0);bool ok=f.tick();std::fill_n(f.memory.data()+a-presets::base,ok?4096:f.torn,255);return ok;}
 static bool pg(void* c,uint32_t a,const uint8_t* b,unsigned n){auto& f=*(Flash*)c;assert(a>=settings::base&&a+n<=settings::end&&n==256-(a&255));bool ok=f.tick();for(unsigned i=0;i<(ok?n:std::min(n,f.torn));++i){assert((f.memory[a-presets::base+i]&b[i])==b[i]);f.memory[a-presets::base+i]&=b[i];}return ok;}
 presets::IO io(){return{this,rd,erase,pg};}
 void guards(){for(unsigned i=0;i<memory.size();++i)if(i<settings::base-presets::base||i>=settings::end-presets::base)assert(memory[i]==0x5a);}
};
int main(){
 std::array<uint8_t,256>a{},b{};Flash f;settings::BufferStore store(f.io());unsigned cases=0;
 assert(store.load(a.data(),b.data())==presets::empty);
 for(unsigned value:{8u,16u,32u,8u}){
  assert(store.save(value,a.data(),b.data())==presets::ok);int writes=f.writes;
  assert(store.save(value,a.data(),b.data())==presets::ok&&writes==f.writes);
  settings::BufferStore reboot(f.io());assert(reboot.load(a.data(),b.data())==presets::ok&&presets::word(a.data(),12)==value);f.guards();++cases;
 }
 auto baseline=f.memory;
 for(unsigned cut=0;cut<=3;++cut)for(unsigned torn:{0u,1u,3u,4u,127u,256u}){
  Flash broken;broken.memory=baseline;broken.cut=cut;broken.torn=torn;settings::BufferStore writer(broken.io());auto result=writer.save(16,a.data(),b.data());assert(result==presets::ok||result==presets::io_error);
  broken.cut=-1;settings::BufferStore reboot(broken.io());assert(reboot.load(a.data(),b.data())==presets::ok);assert(presets::word(a.data(),12)==8||presets::word(a.data(),12)==16);broken.guards();++cases;
 }
 for(int failed=0;failed<4;++failed){Flash broken;broken.memory=baseline;broken.fail_read=failed;settings::BufferStore writer(broken.io());assert(writer.save(32,a.data(),b.data())==presets::io_error);if(failed<2)assert(broken.writes==0);broken.fail_read=-1;assert(writer.load(a.data(),b.data())==presets::ok);assert(presets::word(a.data(),12)==8||presets::word(a.data(),12)==32);broken.guards();++cases;}
 for(unsigned bad:{0u,4u,9u,128u,0xffffffffu}){int writes=f.writes;assert(store.save(bad,a.data(),b.data())==presets::invalid&&f.writes==writes);++cases;}
 assert(store.save(16,a.data(),b.data())==presets::ok);unsigned selected;assert(store.load(a.data(),b.data(),&selected)==presets::ok);f.memory[settings::base-presets::base+selected*4096+12]^=1;assert(store.load(a.data(),b.data())==presets::ok&&presets::word(a.data(),12)==8);++cases;
 std::printf("PASS %u global-storage cases: persistence, duplicate no-op, torn writes, read errors, corruption, invalid values and unchanged preset/code guards\n",cases);
}
