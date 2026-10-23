/* MIT (c) 2026 santismo. Bounded diagnostic wire; no device or audio API. */
#ifndef MIGHTY_LOOP_WIRE_H
#define MIGHTY_LOOP_WIRE_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
/* Both known USB names; identity and paired endpoints are checked separately. */
static int loop_usb_name(const char *name) {
 return name && (!strcmp(name,"MIGHTY PLUG PRO USB") || !strcmp(name,"NUX NMP-03"));
}
static int loop_request(uint8_t out[14],unsigned op,unsigned arg,unsigned nonce) {
 if(op>1 || (op==0?arg>4:arg<1||arg>5) || !nonce || nonce>16383)return 0;
 const uint8_t head[]={240,67,88,112,4,2,78,79,1};memcpy(out,head,9);
 out[9]=(uint8_t)op;out[10]=(uint8_t)arg;out[11]=(uint8_t)(nonce&127);out[12]=(uint8_t)(nonce>>7);out[13]=247;return 1;
}
static int loop_reply(const uint8_t *p,size_t n,const uint8_t request[14],unsigned *error,uint32_t words[8]) {
 if(n!=55 || memcmp(p,request,9) || p[9]!=(request[9]|64) || memcmp(p+10,request+10,3) || p[13]>3 || p[54]!=247)return 0;
 for(unsigned i=1;i<54;++i)if(p[i]>=128)return 0;
 for(unsigned i=0;i<8;++i){
  if(p[18+5*i]>15)return 0;
  uint32_t value=0;for(unsigned j=0;j<5;++j)value|=(uint32_t)p[14+5*i+j]<<(7*j);words[i]=value;
 }
 *error=p[13];return 1;
}
#endif
