// MIT (c) 2026 santismo. Numeric-only storage/session assertions, ASan/UBSan.
#include "session.hpp"
#include "../layout.hpp"
#include <cassert>
#include <vector>
#include <cmath>
#include <cstdio>
#include <cstring>
using namespace mighty_loop;
static int16_t signal(unsigned i,unsigned k=1){return int16_t(1200*std::sin(i*.061*k)+700*std::sin(i*.027));}
int main(){
 unsigned cases=0;
 for(unsigned length:{1u,17u,255u,256u,257u,509u,1023u,1801u})
 for(unsigned start=0;start<length;start+=length/7+1){
  unsigned bytes=unsigned(AdpcmStore::required(length));
  std::vector<uint8_t> pool(bytes*5+64,0xa5),ref(bytes);
  TakeStore s(pool.data()+32,bytes*5,length);AdpcmStore base(ref.data(),bytes,length);
  for(unsigned i=0;i<length;++i){assert(s.append(signal(i)));assert(base.append(signal(i)));}
  auto original=std::vector<uint8_t>(pool.begin()+32,pool.begin()+32+bytes);
  for(unsigned i=0;i<start;++i)s.next_layer(0,false);
  assert(s.begin_take());while(s.preparing){s.next_layer(0,true);assert(!s.failed);}
  unsigned first=s.recording;
  // Multiple complete passes and a partial pass belong to ONE undoable take.
  for(unsigned i=0;i<length*3+length/3;++i){s.next_layer(signal(i,2),true);assert(!s.failed);}
  s.finish_take();assert(s.take[first].audio.length==length && s.recording==0);
  for(unsigned i=0;i<length*2;++i){s.next_layer(0,false);assert(!s.failed);}
  assert(!memcmp(pool.data()+32,original.data(),bytes));
  std::vector<uint8_t> firstCopy(s.take[first].audio.memory,s.take[first].audio.memory+bytes);
  assert(s.begin_take());while(s.preparing)s.next_layer(0,true);unsigned second=s.recording;
  for(unsigned i=0;i<length/2+1;++i)s.next_layer(signal(i,3),true);
  s.finish_take();for(unsigned i=0;i<length*2;++i)s.next_layer(0,false);
  assert(!memcmp(s.take[first].audio.memory,firstCopy.data(),bytes));
  assert(s.undo());while(s.swap_pending)s.next_layer(0,false);assert(!s.take[second].present);
  for(unsigned i=0;i<length*2+11;++i)s.next_layer(0,false);
  assert(s.redo());while(s.swap_pending)s.next_layer(0,false);assert(s.take[second].present);
  for(unsigned i=0;i<length*2;++i)s.next_layer(0,false);
  assert(s.begin_take(first));while(s.preparing){s.next_layer(0,true);assert(!s.failed);}
  for(unsigned i=0;i<length*2+length/2;++i)s.next_layer(signal(i,4),true);
  s.finish_take();for(unsigned i=0;i<length;++i)s.next_layer(0,false);
  assert(s.undo());while(s.swap_pending)s.next_layer(0,false);
  assert(!memcmp(s.take[first].audio.memory,firstCopy.data(),bytes));
  assert(s.redo());while(s.swap_pending)s.next_layer(0,false);
  assert(s.undo());while(s.swap_pending)s.next_layer(0,false);
  assert(!memcmp(s.take[first].audio.memory,firstCopy.data(),bytes));
  assert(s.mute(first,true) && s.level(second,23));
  assert(s.erase_take(second));assert(s.erase_take(first));
  // Undo both completed takes returns bit-exact original encoded base audio.
  while(!s.rewind_ready())s.drain(4);base.rewind();
  for(unsigned i=0;i<length*2;++i)assert(s.next_layer(0,false)==base.next());
  assert(!s.failed && !memcmp(pool.data()+32,original.data(),bytes));
  assert(!s.redo());
  while(!s.rewind_ready())s.drain(4);
  for(unsigned i=0;i<length*2;++i){s.next_layer(0,false);assert(!s.failed);}
  for(unsigned i=0;i<32;++i)assert(pool[i]==0xa5 && pool[pool.size()-1-i]==0xa5);
  ++cases;
 }
 // Actual two-window layout and maximum recording: no room for an undo copy.
 std::vector<uint8_t> a(layout::first_bytes+64,0x65),b(layout::second_bytes+64,0xa9);
 TakeStore full(a.data()+32,layout::first_bytes,b.data()+32,layout::second_bytes,720000);
 for(unsigned i=0;i<720000;++i)assert(full.append(signal(i)));
 assert(!full.begin_take() && full.free_takes()==0 && full.length==720000);
 for(unsigned i=0;i<720000;++i)full.next_layer(0,false);
 assert(!full.failed);
 // Cross-window take and delete/reuse. Each half is guarded.
 full.clear();for(unsigned i=0;i<200000;++i)assert(full.append(signal(i)));
 for(unsigned j=0;j<2;++j){assert(full.begin_take());while(full.preparing)full.next_layer(0,true);for(unsigned i=0;i<400000;++i)full.next_layer(signal(i,2),true);full.finish_take();}
 assert(!full.begin_take());assert(full.erase_take(1));assert(full.begin_take());while(full.preparing)full.next_layer(0,true);
 for(unsigned i=0;i<210000;++i)full.next_layer(signal(i,3),true);full.finish_take();
 assert(!full.failed);
 for(unsigned i=0;i<32;++i)assert(a[i]==0x65&&a[a.size()-1-i]==0x65&&b[i]==0xa9&&b[b.size()-1-i]==0xa9);
 printf("{\"status\":\"PASS_INDEPENDENT_TAKES\",\"boundary_cases\":%u,\"storage_bytes\":%u,\"multi_pass_undo\":true,\"base_unchanged\":true,\"cross_window\":true,\"full_capacity_rejected\":true}\n",cases,layout::first_bytes+layout::second_bytes);
}
