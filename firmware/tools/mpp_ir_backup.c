/* Fixed, read-only Mac MIDI backup. No audio API, flash/reset, arbitrary
 * message CLI, preset SET or out-of-range IR request. stdout is JSONL.
 * IR GET changes the stock scratch buffer/cache, but not persistent storage.
 */
#include <CoreMIDI/CoreMIDI.h>
#include <CoreFoundation/CoreFoundation.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <assert.h>

typedef struct { uint8_t bytes[512]; size_t count; int active; } Stream;
typedef struct {
 pthread_mutex_t lock; Stream stream; uint8_t reply[512]; size_t reply_len;
 int waiting,received,kind; unsigned slot,offset; char version[9];
} Client;
static Client client={.lock=PTHREAD_MUTEX_INITIALIZER};
static unsigned sent=0;
static int decode(const uint8_t *in,size_t n,uint8_t *out,size_t capacity) {
 if(n%3 || capacity<n/3*2)return 0;
 for(size_t i=0;i<n;i+=3) {
  if(in[i]>3 || in[i+1]>127 || in[i+2]>127)return 0;
  unsigned value=((unsigned)in[i]<<14)|((unsigned)in[i+1]<<7)|in[i+2];
  out[i/3*2]=(uint8_t)(value>>8);out[i/3*2+1]=(uint8_t)value;
 }
 return 1;
}
static void encode(const uint8_t *in,size_t n,uint8_t *out) {
 assert(!(n%2));
 for(size_t i=0;i<n;i+=2){unsigned v=((unsigned)in[i]<<8)|in[i+1];out[i/2*3]=v>>14;out[i/2*3+1]=(v>>7)&127;out[i/2*3+2]=v&127;}
}
static unsigned le16(const uint8_t *p){return p[0]|((unsigned)p[1]<<8);}
static int valid_reply(const uint8_t *p,size_t n,int kind,unsigned slot,unsigned offset) {
 if(n<7 || p[0]!=0xf0 || p[n-1]!=0xf7)return 0;
 for(size_t i=1;i<n-1;++i)if(p[i]>=128)return 0;
 if(kind==0) {
  if(n!=45 || memcmp(p,"\xf0\x43\x58\x10",4) || memcmp(p+36,"PLUGPRO\0",8))return 0;
  for(size_t i=4;i<12;++i)if(p[i]<'0'||p[i]>'9')return 0;
  return 1;
 }
 if(memcmp(p,"\xf0\x43\x58\x70",4) || p[5]!=2)return 0;
 if(kind==9){uint8_t raw[36];return n==62 && p[4]==9 && p[6]==slot && decode(p+7,54,raw,36);}
 if(kind==16){uint8_t raw[132];return n==205 && p[4]==16 && decode(p+6,198,raw,132) && le16(raw)==slot && le16(raw+2)==offset;}
 if(kind==11)return n==136 && p[4]==11 && p[6]==slot;
 if(kind==12)return n==136 && p[4]==12 && p[6]<7;
 if(kind==20)return n==29 && p[4]==20;
 return 0;
}
static size_t make_request(uint8_t *q,int kind,unsigned slot,unsigned offset) {
 if(kind==0){memcpy(q,"\xf0\x43\x58\x00\xf7",5);return 5;}
 if((kind==9 && slot<54)||(kind==11 && slot<7)) {
  const uint8_t h[]={0xf0,0x43,0x58,0x70,(uint8_t)kind,2,(uint8_t)slot,0xf7};memcpy(q,h,8);return 8;
 }
 if(kind==12||kind==20){const uint8_t h[]={0xf0,0x43,0x58,0x70,(uint8_t)kind,2,0xf7};memcpy(q,h,7);return 7;}
 if(kind==16 && slot<54 && offset<=2016 && !(offset%32)) {
  /* Exact editor shape: GET direction 0, encoded slot/offset, 2 zero padding bytes. */
  const uint8_t h[]={0xf0,0x43,0x58,0x70,16,0};memcpy(q,h,6);
  uint8_t raw[]={slot&255,slot>>8,offset&255,offset>>8};encode(raw,4,q+6);q[12]=q[13]=0;q[14]=0xf7;return 15;
 }
 return 0;
}
static void feed(Client *c,const uint8_t *data,size_t n) {
 Stream *s=&c->stream;
 for(size_t i=0;i<n;++i) {
  uint8_t b=data[i];if(b>=0xf8)continue;
  if(b==0xf0){s->active=1;s->count=0;}
  else if(!s->active)continue;
  else if(b>=0x80 && b!=0xf7){s->active=0;s->count=0;continue;}
  if(s->count>=sizeof(s->bytes)){s->active=0;s->count=0;continue;}
  s->bytes[s->count++]=b;
  if(b==0xf7){
   s->active=0;
   if(c->waiting && !c->received && valid_reply(s->bytes,s->count,c->kind,c->slot,c->offset)){
    memcpy(c->reply,s->bytes,s->count);c->reply_len=s->count;c->received=1;
   }
   s->count=0;
  }
 }
}
static void receive(const MIDIPacketList *list,void *context,void *source) {
 (void)source;Client *c=context;pthread_mutex_lock(&c->lock);
 const MIDIPacket *p=&list->packet[0];
 for(UInt32 i=0;i<list->numPackets;++i){feed(c,p->data,p->length);p=MIDIPacketNext(p);}
 pthread_mutex_unlock(&c->lock);
}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void hex(const uint8_t *p,size_t n){for(size_t i=0;i<n;++i)printf("%02x",p[i]);}
static int request(MIDIPortRef port,MIDIEndpointRef dest,int kind,unsigned slot,unsigned offset,const char *phase,int pass) {
 uint8_t q[32];size_t n=make_request(q,kind,slot,offset);if(!n)return 0;
 pthread_mutex_lock(&client.lock);client.kind=kind;client.slot=slot;client.offset=offset;
 client.waiting=1;client.received=0;client.reply_len=0;memset(&client.stream,0,sizeof(client.stream));pthread_mutex_unlock(&client.lock);
 MIDIPacketList list;MIDIPacket *p=MIDIPacketListInit(&list);
 if(!MIDIPacketListAdd(&list,sizeof(list),p,0,n,q))return 0;
 ++sent;OSStatus error=MIDISend(port,dest,&list);double deadline=now()+1.5;int received=0;
 while(!error && now()<deadline && !received) {
  CFRunLoopRunInMode(kCFRunLoopDefaultMode,0.005,false);
  struct timespec pause={0,1000000};nanosleep(&pause,NULL);
  pthread_mutex_lock(&client.lock);received=client.received;pthread_mutex_unlock(&client.lock);
 }
 pthread_mutex_lock(&client.lock);client.waiting=0;
 printf("{\"phase\":\"%s\",\"pass\":%d,\"kind\":%d,\"slot\":%u,\"offset\":%u,\"request_hex\":\"",phase,pass,kind,slot,offset);hex(q,n);
 printf("\",\"matched\":%s,\"reply_hex\":\"",received?"true":"false");hex(client.reply,client.reply_len);puts("\"}");fflush(stdout);
 if(received && kind==0){memcpy(client.version,client.reply+4,8);client.version[8]=0;}
 pthread_mutex_unlock(&client.lock);
 struct timespec pace={0,5000000};nanosleep(&pace,NULL);
 return received && !error;
}
static int matches(MIDIEndpointRef e) {
 CFStringRef name=NULL;char text[256]={0};
 if(MIDIObjectGetStringProperty(e,kMIDIPropertyDisplayName,&name)!=noErr||!name)return 0;
 int ok=CFStringGetCString(name,text,sizeof(text),kCFStringEncodingUTF8);CFRelease(name);
 return ok && !strcmp(text,"MIGHTY PLUG PRO USB");
}
static int snapshot(MIDIPortRef port,MIDIEndpointRef dest,const char *phase) {
 for(unsigned s=0;s<7;++s)if(!request(port,dest,11,s,0,phase,-1))return 0;
 return request(port,dest,12,0,0,phase,-1)&&request(port,dest,20,0,0,phase,-1);
}
static int self_test(void) {
 uint8_t q[32],raw[132],encoded[198],decoded[132],reply[205];unsigned count=0;
 const uint8_t settings[]={0xf0,0x43,0x58,0x70,0x14,2,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0x32,0x32,1,0x32,0x7f,0x32,0,0xf7};
 /* Captured 20220720 settings replies are 29 bytes (22-byte payload). */
 uint8_t settings29[29]={0xf0,0x43,0x58,0x70,0x14,2};settings29[28]=0xf7;
 assert(valid_reply(settings29,sizeof(settings29),20,0,0));
 assert(!valid_reply(settings,sizeof(settings),20,0,0));
 for(unsigned s=0;s<54;++s)for(unsigned o=0;o<=2016;o+=32){assert(make_request(q,16,s,o)==15);assert(decode(q+6,6,decoded,sizeof(decoded)));assert(le16(decoded)==s&&le16(decoded+2)==o);++count;}
 for(unsigned s=54;s<=65535;++s)assert(!make_request(q,16,s,0));
 for(unsigned o=0;o<=65535;++o)if(o>2016||o%32)assert(!make_request(q,16,0,o));
 for(unsigned k=0;k<128;++k)if(k!=0&&k!=9&&k!=11&&k!=12&&k!=16&&k!=20)assert(!make_request(q,k,0,0));
 for(unsigned i=0;i<132;++i)raw[i]=(uint8_t)(i*137);raw[0]=53;raw[1]=0;raw[2]=0xe0;raw[3]=7;
 encode(raw,132,encoded);assert(decode(encoded,198,decoded,132)&&!memcmp(raw,decoded,132));
 memcpy(reply,"\xf0\x43\x58\x70\x10\x02",6);memcpy(reply+6,encoded,198);reply[204]=0xf7;
 assert(valid_reply(reply,205,16,53,2016));assert(!valid_reply(reply,205,16,52,2016));assert(!valid_reply(reply,204,16,53,2016));
 for(size_t split=0;split<=205;++split){Client c={.waiting=1,.kind=16,.slot=53,.offset=2016};feed(&c,reply,split);uint8_t rt=0xf8;feed(&c,&rt,1);feed(&c,reply+split,205-split);assert(c.received&&c.reply_len==205);}
 for(size_t i=6;i<204;i+=3){uint8_t save=reply[i];reply[i]=4;assert(!valid_reply(reply,205,16,53,2016));reply[i]=save;}
 Client c={.waiting=1,.kind=16,.slot=53,.offset=2016};uint8_t junk[600]={0xf0};feed(&c,junk,600);feed(&c,reply,205);assert(c.received);
 printf("{\"self_test\":\"PASS\",\"valid_ir_requests_checked\":%u,\"fragment_splits\":206,\"device_access\":false}\n",count);return 0;
}
int main(int argc,char **argv) {
 if(argc==2&&!strcmp(argv[1],"--self-test"))return self_test();
 int backup=argc==2&&!strcmp(argv[1],"--backup");
 if(!backup && !(argc==2&&!strcmp(argv[1],"--catalog"))){fputs("Usage: mpp_ir_backup --catalog | --backup | --self-test\n",stderr);return 2;}
 MIDIClientRef midi=0;MIDIPortRef in=0,out=0;MIDIEndpointRef source=0,dest=0;int ns=0,nd=0,code=1;const char *status="MIDI_SETUP_FAILED";
 if(MIDIClientCreate(CFSTR("MPP cabinet backup, no audio"),NULL,NULL,&midi)!=noErr)goto done;
 for(ItemCount i=0;i<MIDIGetNumberOfSources();++i){MIDIEndpointRef e=MIDIGetSource(i);if(matches(e)){source=e;++ns;}}
 for(ItemCount i=0;i<MIDIGetNumberOfDestinations();++i){MIDIEndpointRef e=MIDIGetDestination(i);if(matches(e)){dest=e;++nd;}}
 if(ns!=1||nd!=1){status="REQUIRE_ONE_MATCHING_PLUG";goto done;}
 MIDIEntityRef se=0,de=0;
 if(MIDIEndpointGetEntity(source,&se)!=noErr||MIDIEndpointGetEntity(dest,&de)!=noErr||!se||se!=de){status="ENDPOINT_PAIR_MISMATCH";goto done;}
 if(MIDIInputPortCreate(midi,CFSTR("IR replies"),receive,&client,&in)!=noErr||MIDIOutputPortCreate(midi,CFSTR("IR GET only"),&out)!=noErr||MIDIPortConnectSource(in,source,NULL)!=noErr)goto done;
 status="IDENTITY_TIMEOUT";if(!request(out,dest,0,0,0,"identity",-1))goto done;
 status="UNEXPECTED_FIRMWARE";if(strcmp(client.version,"20220720"))goto done;
 status="CATALOG_TIMEOUT";
 for(unsigned slot=0;slot<54;++slot)if(!request(out,dest,9,slot,0,"catalog",-1))goto done;
 if(!backup){status="CATALOG_COMPLETE";code=0;goto done;}
 status="SNAPSHOT_TIMEOUT";if(!snapshot(out,dest,"settings_before"))goto done;
 status="IR_READ_TIMEOUT";
 /* Prime with another valid slot so first pass of slot 0 reloads its buffer. */
 if(!request(out,dest,16,53,0,"prime",-1))goto done;
 for(int pass=0;pass<2;++pass)for(unsigned slot=0;slot<54;++slot) {
  for(unsigned offset=0;offset<=2016;offset+=32)if(!request(out,dest,16,slot,offset,"ir",pass))goto done;
  fprintf(stderr,"Backup pass %d: slot %u/54 saved\n",pass+1,slot+1);fflush(stderr);
 }
 status="SNAPSHOT_TIMEOUT";if(!snapshot(out,dest,"settings_after"))goto done;
 for(unsigned slot=0;slot<54;++slot)if(!request(out,dest,9,slot,0,"catalog_after",-1))goto done;
 status="IDENTITY_TIMEOUT";if(!request(out,dest,0,0,0,"identity_after",-1))goto done;
 status="BACKUP_CAPTURE_COMPLETE";code=0;
done:
 if(in&&source)MIDIPortDisconnectSource(in,source);if(in)MIDIPortDispose(in);if(out)MIDIPortDispose(out);if(midi)MIDIClientDispose(midi);
 printf("{\"status\":\"%s\",\"requests_sent\":%u,\"audio_stream_opened\":false,\"flash_reset_or_set_sent\":false}\n",status,sent);
 return code;
}
