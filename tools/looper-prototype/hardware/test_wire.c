/* No CoreMIDI linkage or device enumeration. */
#include <assert.h>
#include <stdio.h>
#include "looper_wire.h"
#include "../../../firmware/tools/probe_wire.h"
static uint8_t query[14];static unsigned received;
static void message(const uint8_t *p,size_t n,void *ctx){
 (void)ctx;unsigned error;uint32_t words[8];assert(loop_reply(p,n,query,&error,words));
 assert(!error && words[0]==0x4c4f5031 && words[7]==0xffffffff);++received;
}
int main(void){
 uint8_t p[55]={0};unsigned error;uint32_t words[8];
 assert(loop_request(query,0,0,123));memcpy(p,query,13);p[9]=64;p[54]=247;
 for(unsigned i=0;i<8;++i){uint32_t value=i==0?0x4c4f5031u:i==7?0xffffffffu:i;for(unsigned j=0;j<5;++j)p[14+i*5+j]=(value>>(j*7))&127;}
 assert(loop_reply(p,55,query,&error,words));
 for(unsigned split=1;split<55;++split){MppSysex s={0};mpp_sysex_feed(&s,p,split,message,NULL);mpp_sysex_feed(&s,p+split,55-split,message,NULL);}
 assert(received==54);
 uint8_t copy[55];
 for(unsigned index=0;index<13;++index){memcpy(copy,p,55);copy[index]^=1;assert(!loop_reply(copy,55,query,&error,words));}
 for(unsigned n=0;n<55;++n)assert(!loop_reply(p,n,query,&error,words));
 memcpy(copy,p,55);copy[18]=16;assert(!loop_reply(copy,55,query,&error,words));
 assert(!loop_request(query,1,0,1)&&!loop_request(query,0,5,1)&&!loop_request(query,1,6,1)&&!loop_request(query,0,0,0));
 assert(loop_request(query,1,5,16383));
 /* Keep all shared parser entry points exercised with bounded bad frames. */
 char version[9];uint32_t page;assert(!mpp_version_reply(p,55,version)&&!mpp_page_reply(p,55,0,&page));
 puts("PASS_OFFLINE_LOOP_WIRE");return 0;
}
