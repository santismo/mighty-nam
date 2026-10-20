/* Bounded parser shared by the Mac client and its offline tests. */
#ifndef MPP_PROBE_WIRE_H
#define MPP_PROBE_WIRE_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef struct { uint8_t bytes[128];size_t count;int active; } MppSysex;
typedef void (*MppMessage)(const uint8_t *,size_t,void *);
static void mpp_sysex_feed(MppSysex *p,const uint8_t *data,size_t n,MppMessage fn,void *ctx) {
 for(size_t i=0;i<n;++i) {
  uint8_t b=data[i];
  if(b>=0xf8)continue; /* MIDI real-time bytes may interrupt SysEx. */
  if(b==0xf0){p->active=1;p->count=0;}
  else if(!p->active)continue;
  else if(b>=0x80 && b!=0xf7){p->active=0;p->count=0;continue;}
  if(p->count>=sizeof(p->bytes)){p->active=0;p->count=0;continue;}
  p->bytes[p->count++]=b;
  if(b==0xf7){p->active=0;fn(p->bytes,p->count,ctx);p->count=0;}
 }
}
static int mpp_version_reply(const uint8_t *p,size_t n,char out[9]) {
 if(n!=45 || memcmp(p,"\xf0\x43\x58\x10",4) || p[44]!=0xf7 || memcmp(p+36,"PLUGPRO\0",8))return 0;
 for(size_t i=1;i<44;++i)if(p[i]>=128)return 0;
 for(size_t i=0;i<8;++i) {
  uint8_t c=p[4+i];
  if(!((c>='0'&&c<='9')||(c>='A'&&c<='Z')))return 0;
  out[i]=(char)c;
 }
 out[8]=0;return 1;
}
static int mpp_page_reply(const uint8_t *p,size_t n,unsigned page,uint32_t *value) {
 static const uint8_t head[]={0xf0,0x43,0x58,0x70,4,2,1};
 if(n!=15 || memcmp(p,head,7) || p[7]!=page || p[8]!=0 || p[14]!=0xf7)return 0;
 for(size_t i=1;i<14;++i)if(p[i]>=128)return 0;
 if(p[13]>15)return 0;
 uint32_t v=0;for(unsigned i=0;i<5;++i)v|=(uint32_t)p[9+i]<<(7*i);
 *value=v;return 1;
}
#endif
