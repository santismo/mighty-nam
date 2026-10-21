/* NAMLNK19 opt-in one-shot driver snapshot collector. No audio framework, note messages, reset, flash,
 * preset writes, mute commands or generic packet sender. ND127 explicitly arms
 * one read-only snapshot. This collector never changes output intent. Queries our extension ONLY after
 * the standard firmware reply explicitly identifies NAMLNK19.
 */
#include <CoreMIDI/CoreMIDI.h>
#include <CoreFoundation/CoreFoundation.h>
#include <pthread.h>
#include <stdio.h>
#include <time.h>
#include "probe_wire.h"

typedef struct {
 pthread_mutex_t lock;MppSysex stream;
 int waiting,received;unsigned page;uint32_t value;char version[9];
 unsigned received_packets,received_bytes;
} Client;
static Client client={.lock=PTHREAD_MUTEX_INITIALIZER};
static void message(const uint8_t *p,size_t n,void *context) {
 Client *c=context;
 if(c->waiting==1 && mpp_version_reply(p,n,c->version))c->received=1;
 if(c->waiting==2 && mpp_page_reply(p,n,c->page,&c->value))c->received=1;
}
static void receive(const MIDIPacketList *list,void *context,void *source) {
 (void)source;Client *c=context;pthread_mutex_lock(&c->lock);
 const MIDIPacket *p=&list->packet[0];
 for(UInt32 i=0;i<list->numPackets;++i){++c->received_packets;c->received_bytes+=p->length;mpp_sysex_feed(&c->stream,p->data,p->length,message,c);p=MIDIPacketNext(p);}
 pthread_mutex_unlock(&c->lock);
}
static int matches(MIDIEndpointRef endpoint) {
 CFStringRef name=NULL;char text[256]={0};
 if(MIDIObjectGetStringProperty(endpoint,kMIDIPropertyDisplayName,&name)!=noErr || !name)return 0;
 int ok=CFStringGetCString(name,text,sizeof(text),kCFStringEncodingUTF8);CFRelease(name);
 return ok && !strcmp(text,"MIGHTY PLUG PRO USB");
}
static double monotonic_seconds(void) {
 struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);
 return (double)t.tv_sec+(double)t.tv_nsec/1e9;
}
static double last_request_seconds;
static OSStatus last_send_status;
static int request(MIDIPortRef out,MIDIEndpointRef destination,const uint8_t *data,size_t n,int kind,unsigned page) {
 pthread_mutex_lock(&client.lock);client.waiting=kind;client.page=page;client.received=0;
 client.stream.active=0;client.stream.count=0;pthread_mutex_unlock(&client.lock);
 MIDIPacketList list;MIDIPacket *p=MIDIPacketListInit(&list);
 if(!MIDIPacketListAdd(&list,sizeof(list),p,0,n,data))return 0;
 last_send_status=MIDISend(out,destination,&list);
 const double start=monotonic_seconds(),deadline=start+3.0;
 int received=0;
 while(last_send_status==noErr && !received && monotonic_seconds()<deadline) {
  CFRunLoopRunInMode(kCFRunLoopDefaultMode,0.005,false);
  const struct timespec pause={0,1000000};nanosleep(&pause,NULL);
  pthread_mutex_lock(&client.lock);received=client.received;pthread_mutex_unlock(&client.lock);
 }
 last_request_seconds=monotonic_seconds()-start;
 pthread_mutex_lock(&client.lock);client.waiting=0;pthread_mutex_unlock(&client.lock);
 return received;
}
static int action(MIDIPortRef out,MIDIEndpointRef destination,uint8_t value) {
 const uint8_t data[]={0xf0,0x43,0x58,0x70,4,2,'N','D',value,0xf7};
 MIDIPacketList list;MIDIPacket *p=MIDIPacketListInit(&list);
 return MIDIPacketListAdd(&list,sizeof(list),p,0,sizeof(data),data) && MIDISend(out,destination,&list)==noErr;
}
static int page(MIDIPortRef out,MIDIEndpointRef dest,unsigned value) {
 const uint8_t data[]={0xf0,0x43,0x58,0x70,4,2,'N','P',(uint8_t)value,0xf7};
 return request(out,dest,data,sizeof(data),2,value);
}
int main(int argc,char **argv) {
 if(argc!=2 || strcmp(argv[1],"--capture")){fputs("Usage: mpp_driver_client --capture\n",stderr);return 2;}
 MIDIClientRef midi=0;MIDIPortRef in=0,out=0;MIDIEndpointRef source=0,dest=0;int ns=0,nd=0,code=1;
 unsigned sent=0;const char *status="MIDI_SETUP_FAILED";uint32_t values[48]={0},header=0;unsigned pages=0;
 if(MIDIClientCreate(CFSTR("MPP silent diagnostic"),NULL,NULL,&midi)!=noErr)goto done;
 for(ItemCount i=0;i<MIDIGetNumberOfSources();++i){MIDIEndpointRef e=MIDIGetSource(i);if(matches(e)){source=e;++ns;}}
 for(ItemCount i=0;i<MIDIGetNumberOfDestinations();++i){MIDIEndpointRef e=MIDIGetDestination(i);if(matches(e)){dest=e;++nd;}}
 if(ns!=1 || nd!=1){status="REQUIRE_ONE_MATCHING_PLUG";goto done;}
 MIDIEntityRef se=0,de=0;
 if(MIDIEndpointGetEntity(source,&se)!=noErr || MIDIEndpointGetEntity(dest,&de)!=noErr || !se || se!=de){status="ENDPOINT_PAIR_MISMATCH";goto done;}
 if(MIDIInputPortCreate(midi,CFSTR("MPP replies"),receive,&client,&in)!=noErr ||
    MIDIOutputPortCreate(midi,CFSTR("MPP read requests"),&out)!=noErr || MIDIPortConnectSource(in,source,NULL)!=noErr)goto done;
 const uint8_t identify[]={0xf0,0x43,0x58,0,0xf7};++sent;
 if(!request(out,dest,identify,sizeof(identify),1,0)){status="IDENTITY_TIMEOUT";goto done;}
 if(strcmp(client.version,"NAMLNK19")){status="UNRECOGNIZED_IDENTITY_NO_CUSTOM_COMMANDS_SENT";code=1;goto done;}
 ++sent;if(!page(out,dest,118)){status="STATUS_TIMEOUT";goto done;}
 header=client.value;
 if((header>>24)!=0xd1 || (header&255)==1 || (header&255)==2){status="DIAGNOSTIC_BUSY_OR_INVALID";goto done;}
 ++sent;if(!action(out,dest,127)){status="ARM_SEND_FAILED";goto done;}
 for(unsigned attempt=0;attempt<10;++attempt){
  ++sent;if(!page(out,dest,118)){status="CAPTURE_TIMEOUT";goto done;}
  if((client.value&255)==3)break;
  CFRunLoopRunInMode(kCFRunLoopDefaultMode,0.01,false);
 }
 if((client.value>>24)!=0xd1 || (client.value&255)!=3 || ((client.value>>8)&65535)!=(((header>>8)+1)&65535)){status="CAPTURE_INCOMPLETE_OR_RACED";goto done;}
 header=client.value;
 for(unsigned window=0;window<6;++window){
  ++sent;if(!action(out,dest,(uint8_t)window)){status="WINDOW_SEND_FAILED";goto done;}
  for(unsigned i=119;i<=126;++i){
   ++sent;if(!page(out,dest,i)){status="SNAPSHOT_PAGE_TIMEOUT";goto done;}
   values[pages++]=client.value;
  }
 }
 ++sent;if(!page(out,dest,118)||client.value!=header){status="SNAPSHOT_GENERATION_CHANGED";goto done;}
 status="DIAGNOSTIC_READ_COMPLETE";code=0;
done:
 if(in && source)MIDIPortDisconnectSource(in,source);
 if(in)MIDIPortDispose(in);
 if(out)MIDIPortDispose(out);
 if(midi)MIDIClientDispose(midi);
 printf("{\"status\":\"%s\",\"version\":\"%s\",\"requests_sent\":%u,\"diagnostic_pages_read\":%u,\"received_packets\":%u,\"received_bytes\":%u,\"last_send_status\":%d,\"last_request_seconds\":%.6f,\"audio_stream_opened\":false,\"flash_or_reset_sent\":false,\"words\":[",status,client.version,sent,pages,client.received_packets,client.received_bytes,(int)last_send_status,last_request_seconds);
 for(unsigned i=0;i<pages;++i)printf("%s%u",i?",":"",values[i]);puts("]}");return code;
}
