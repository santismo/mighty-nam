#include "../tools/probe_wire.h"
#include <assert.h>
#include <stdio.h>
static unsigned seen;
static uint8_t captured[128];static size_t captured_n;
static void receive(const uint8_t *p,size_t n,void *context) {
 (void)context;++seen;captured_n=n;memcpy(captured,p,n);
}
int main(void) {
 uint8_t version[45]={0xf0,0x43,0x58,0x10};memcpy(version+4,"20220720",8);memcpy(version+36,"PLUGPRO\0",8);version[44]=0xf7;
 char name[9]={0};assert(mpp_version_reply(version,45,name) && !strcmp(name,"20220720"));
 for(unsigned split=0;split<=45;++split) {
  MppSysex p={0};seen=0;mpp_sysex_feed(&p,version,split,receive,NULL);mpp_sysex_feed(&p,version+split,45-split,receive,NULL);
  assert(seen==1 && captured_n==45 && !memcmp(captured,version,45));
 }
 MppSysex p={0};seen=0;
 for(unsigned i=0;i<45;++i){uint8_t realtime=0xf8;mpp_sysex_feed(&p,&realtime,1,receive,NULL);mpp_sysex_feed(&p,version+i,1,receive,NULL);}
 assert(seen==1 && captured_n==45);
 uint8_t huge[256]={0};huge[0]=0xf0;huge[255]=0xf7;seen=0;mpp_sysex_feed(&p,huge,256,receive,NULL);assert(seen==0);
 mpp_sysex_feed(&p,version,45,receive,NULL);assert(seen==1);
 uint8_t page[15]={0xf0,0x43,0x58,0x70,4,2,1,32,0,0,0,0,0,0,0xf7};
 uint32_t numbers[]={0,1,127,128,0x80000000u,0xffffffffu,0x4d505031u};uint32_t value=0;
 for(unsigned j=0;j<sizeof(numbers)/sizeof(numbers[0]);++j) {
  for(unsigned i=0;i<5;++i)page[9+i]=(uint8_t)((numbers[j]>>(7*i))&127);
  assert(mpp_page_reply(page,15,32,&value) && value==numbers[j]);
 }
 for(unsigned i=0;i<15;++i) {
  if(i>=9 && i<=13)continue;
  uint8_t keep=page[i];page[i]^=1;assert(!mpp_page_reply(page,15,32,&value));page[i]=keep;
 }
 page[13]=16;assert(!mpp_page_reply(page,15,32,&value));page[13]=0;
 for(unsigned i=9;i<14;++i){page[i]=128;assert(!mpp_page_reply(page,15,32,&value));page[i]=0;}
 for(unsigned n=0;n<45;++n)assert(!mpp_version_reply(version,n,name));
 for(unsigned n=0;n<15;++n)assert(!mpp_page_reply(page,n,32,&value));
 version[4]='"';assert(!mpp_version_reply(version,45,name));
 puts("{\"status\":\"PASS_PROBE_WIRE\",\"split_boundaries\":46,\"audio_or_device_access\":false}");
}
