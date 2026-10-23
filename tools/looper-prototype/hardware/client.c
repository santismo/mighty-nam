/* MIT (c) 2026 santismo. Explicit MIDI-only diagnostics, never audio/mute/flash. */
#include <CoreMIDI/CoreMIDI.h>
#include <CoreFoundation/CoreFoundation.h>
#include <pthread.h>
#include <stdio.h>
#include <time.h>
#include "../../../firmware/tools/probe_wire.h"
#include "looper_wire.h"

typedef struct {
 pthread_mutex_t lock;MppSysex stream;
 int waiting,received;unsigned error;uint32_t words[8];uint8_t query[14];char version[9];
 unsigned received_packets,received_bytes;
} Client;
static Client client={.lock=PTHREAD_MUTEX_INITIALIZER};
static void message(const uint8_t *p,size_t n,void *context) {
 Client *c=context;
 if(c->waiting==1 && mpp_version_reply(p,n,c->version))c->received=1;
 if(c->waiting==2 && loop_reply(p,n,c->query,&c->error,c->words))c->received=1;
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
 return ok && loop_usb_name(text);
}
static double monotonic_seconds(void) {
 struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);
 return (double)t.tv_sec+(double)t.tv_nsec/1e9;
}
static double last_request_seconds;
static OSStatus last_send_status;
static int request(MIDIPortRef out,MIDIEndpointRef destination,const uint8_t *data,size_t n,int kind) {
 pthread_mutex_lock(&client.lock);client.waiting=kind;client.received=0;if(kind==2)memcpy(client.query,data,14);
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
 unsigned command=0;
 if(argc==2){
  const char *commands[]={"--status","--arm","--finish-or-toggle","--view","--stop","--clear"};
  int found=0;for(unsigned i=0;i<6;++i)if(!strcmp(argv[1],commands[i])){command=i;found=1;}
  if(!found)argc=0;
 }
 if(argc!=2){fputs("Usage: mighty-loop --status | --arm | --finish-or-toggle | --view | --stop | --clear\n",stderr);return 2;}
 MIDIClientRef midi=0;MIDIPortRef in=0,out=0;MIDIEndpointRef source=0,dest=0;int ns=0,nd=0,code=1;
 unsigned sent=0;const char *status="MIDI_SETUP_FAILED";uint32_t values[40]={0},sequence=0;unsigned pages=0,commands_sent=0;
 if(MIDIClientCreate(CFSTR("MPP silent diagnostic"),NULL,NULL,&midi)!=noErr)goto done;
 for(ItemCount i=0;i<MIDIGetNumberOfSources();++i){MIDIEndpointRef e=MIDIGetSource(i);if(matches(e)){source=e;++ns;}}
 for(ItemCount i=0;i<MIDIGetNumberOfDestinations();++i){MIDIEndpointRef e=MIDIGetDestination(i);if(matches(e)){dest=e;++nd;}}
 if(ns!=1 || nd!=1){status="REQUIRE_ONE_MATCHING_PLUG";goto done;}
 MIDIEntityRef se=0,de=0;
 if(MIDIEndpointGetEntity(source,&se)!=noErr || MIDIEndpointGetEntity(dest,&de)!=noErr || !se || se!=de){status="ENDPOINT_PAIR_MISMATCH";goto done;}
 if(MIDIInputPortCreate(midi,CFSTR("MPP replies"),receive,&client,&in)!=noErr ||
    MIDIOutputPortCreate(midi,CFSTR("MPP read requests"),&out)!=noErr || MIDIPortConnectSource(in,source,NULL)!=noErr)goto done;
 const uint8_t identify[]={0xf0,0x43,0x58,0,0xf7};++sent;
 if(!request(out,dest,identify,sizeof(identify),1)){status="IDENTITY_TIMEOUT";goto done;}
 if(strcmp(client.version,"NAMLNK25") && strcmp(client.version,"NAMLNK26")){status="UNRECOGNIZED_IDENTITY_NO_CUSTOM_COMMANDS_SENT";code=1;goto done;}
 if(command){
  uint8_t q[14];if(!loop_request(q,1,command,73)){status="BAD_COMMAND";goto done;}
  ++sent;++commands_sent;
  if(!request(out,dest,q,14,2)){status="COMMAND_TIMEOUT";goto done;}
  if(client.error){status="COMMAND_REJECTED";goto done;}
  sequence=client.words[0];
 }
 for(unsigned pass=0;pass<5;++pass){
  pages=0;
  for(unsigned i=0;i<5;++i){
   uint8_t q[14];if(!loop_request(q,0,i,74+5*pass+i)){status="BAD_REQUEST";goto done;}
   ++sent;if(!request(out,dest,q,14,2)){status="STATUS_TIMEOUT";goto done;}
   if(client.error){status="STATUS_REJECTED";goto done;}
   memcpy(values+8*i,client.words,sizeof client.words);++pages;
  }
  if(!command || (values[12]==0 && values[13]==sequence))break;
 }
 if(values[0]!=0x4c4f5031 || values[1]!=(strcmp(client.version,"NAMLNK26")?1u:2u) || values[2]!=2){status="UNEXPECTED_DIAGNOSTIC_SCHEMA";goto done;}
 if(values[3]){status="LOOPER_RAM_GUARD_FAULT";goto done;}
 if(command && (values[12] || values[13]!=sequence)){status="COMMAND_NOT_APPLIED";goto done;}
 if(command && values[14]){status="COMMAND_NOT_APPLICABLE";goto done;}
 status=command?"LOOPER_COMMAND_APPLIED":"LOOPER_STATUS_READ";code=0;
done:
 if(in && source)MIDIPortDisconnectSource(in,source);
 if(in)MIDIPortDispose(in);
 if(out)MIDIPortDispose(out);
 if(midi)MIDIClientDispose(midi);
 printf("{\"status\":\"%s\",\"version\":\"%s\",\"requests_sent\":%u,\"looper_commands_sent\":%u,\"audio_stream_opened\":false,\"mute_or_output_commands\":0,\"flash_or_reset_sent\":false,\"physical_deadline_proven\":false,\"raw_words\":[",status,client.version,sent,commands_sent);
 for(unsigned i=0;i<pages*8;++i)printf("%s%u",i?",":"",values[i]);puts("]}");return code;
}
