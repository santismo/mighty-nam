/* Dedicated A2 input reader. It rejects NAMPB002 and stock firmware.
 * Completion of reads does not imply completion of all 180000 input batches.
 * Page 17 is phase: 0 waiting, 1 running, 2 completed, 3 model/output fault, 4 timing/half/configuration fault.
 * DWT statistics are raw, uncalibrated spans, not deadline proof. */
/* Silent Mac USB-MIDI probe. No audio framework, note messages, reset, flash,
 * preset writes or generic packet sender. Queries our extension ONLY after
 * the standard firmware reply explicitly identifies NAMA2I01.
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
int main(int argc,char **argv) {
 if(argc!=2 || strcmp(argv[1],"--inspect")){fputs("Usage: mpp_probe_client --inspect\n",stderr);return 2;}
 MIDIClientRef midi=0;MIDIPortRef in=0,out=0;MIDIEndpointRef source=0,dest=0;int ns=0,nd=0,code=1;
 unsigned sent=0;const char *status="MIDI_SETUP_FAILED";uint32_t values[62]={0};unsigned pages=0;
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
 if(strcmp(client.version,"NAMA2I01")){status="UNRECOGNIZED_IDENTITY_NO_CUSTOM_COMMANDS_SENT";code=0;goto done;}
 for(unsigned i=0;i<62;++i) {
  unsigned page=i;
  const uint8_t query[]={0xf0,0x43,0x58,0x70,4,2,'N','P',(uint8_t)page,0xf7};++sent;
  if(!request(out,dest,query,sizeof(query),2,page)){status="DIAGNOSTIC_REPLY_TIMEOUT";goto done;}
  pthread_mutex_lock(&client.lock);values[pages++]=client.value;pthread_mutex_unlock(&client.lock);
 }
 if(values[0]!=0x4d504232u || values[1]!=3 || values[2]!=1){status="DIAGNOSTIC_STATE_INVALID";goto done;}
 status="DIAGNOSTIC_READ_COMPLETE";code=0;
done:
 if(in && source)MIDIPortDisconnectSource(in,source);
 if(in)MIDIPortDispose(in);
 if(out)MIDIPortDispose(out);
 if(midi)MIDIClientDispose(midi);
 printf("{\"status\":\"%s\",\"version\":\"%s\",\"requests_sent\":%u,\"diagnostic_pages_read\":%u,\"received_packets\":%u,\"received_bytes\":%u,\"last_send_status\":%d,\"last_request_seconds\":%.6f,\"audio_stream_opened\":false,\"flash_or_reset_sent\":false,\"words\":[",status,client.version,sent,pages,client.received_packets,client.received_bytes,(int)last_send_status,last_request_seconds);
 for(unsigned i=0;i<pages;++i)printf("%s%u",i?",":"",values[i]);puts("]}");return code;
}
