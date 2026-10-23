// MIT (c) 2026 santismo. Foreground-only settings storage using the audited bank I/O.
#include "store.hpp"
using namespace mighty_loop;
extern "C" {
bool mpp_loop_read(void*,uint32_t,uint8_t*,unsigned);
bool mpp_loop_erase(void*,uint32_t);
bool mpp_loop_program(void*,uint32_t,const uint8_t*,unsigned);
unsigned mpp_loop_state(unsigned),mpp_loop_apply(unsigned);
void mpp_bank_pause(),mpp_bank_resume(unsigned);
extern volatile unsigned mpp_listen_enabled;
volatile bool mpp_loop_saving;
}
namespace {
uint8_t a[256],b[256];
unsigned saved;
SettingsStore store(){return {{nullptr,mpp_loop_read,mpp_loop_erase,mpp_loop_program}};}
}
extern "C" {
// ABI-compatible replacements for the baseline's own BufferStore methods.
unsigned mpp_loop_store_load(SettingsStore* self,uint8_t* first,uint8_t* second,unsigned* which){return self->load(first,second,which);}
unsigned mpp_loop_store_buffer(SettingsStore* self,unsigned samples,uint8_t* first,uint8_t* second){return self->save(samples,0,first,second);}
void mpp_loop_settings_boot(){
 if(store().load(a,b)==SettingsStore::ok){
  unsigned value=SettingsStore::loop(a);
  mpp_loop_apply((2<<8)|(value&255));mpp_loop_apply((3<<8)|((value>>8)&255));mpp_loop_apply((4<<8)|((value>>16)&255));
  if(SettingsStore::word(a,4)==2)saved=value;
 }
}
unsigned mpp_loop_settings_saved(){return saved && saved==(mpp_loop_state(10)&0xffffff);}
unsigned mpp_loop_settings_save(){
 // Caller rejects pending controls and any retained/armed/recording loop.
 mpp_loop_saving=true;__asm__ volatile("dmb":::"memory");
 unsigned value=mpp_loop_state(10)&0xffffff,listening=mpp_listen_enabled;
 mpp_bank_pause();unsigned result=store().save(0,value,a,b);mpp_bank_resume(listening);
 if(!result)saved=value;
 __asm__ volatile("dmb":::"memory");mpp_loop_saving=false;return result?3:0;
}
}
