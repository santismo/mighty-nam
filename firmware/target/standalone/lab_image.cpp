#include "prototype.hpp"
#include "../board/startup_memory.hpp"
#include "../../tests/standalone_ram_port.hpp"
#include <stddef.h>
using namespace mpp::standalone;
struct Mailbox {
 uint32_t tag,input_slot,lock_after,initial_control,fail_call,nack_byte,tick_step;
 uint32_t weight_count,sequence,rx_half,tx_half,result;
 float weights[1871];
};
extern "C" {
__attribute__((section(".mailbox"))) Mailbox mpp_vm_mailbox;
__attribute__((section(".dma"))) DmaMemory mpp_vm_dma;
constinit Prototype mpp_vm_app{};
constinit test::RamPort mpp_vm_port{};
uint32_t mpp_data_cookie=0x4d505031;
float mpp_vm_diagnostic[8];
extern unsigned char __data_load[],__data_start[],__data_end[],__bss_start[],__bss_end[],__dma_start[],__dma_end[];
void mpp_runtime_initialize(){
 mpp::board::initialize_data(__data_load,__data_start,unsigned(__data_end-__data_start),__bss_start,unsigned(__bss_end-__bss_start));
 for(auto* p=__dma_start;p!=__dma_end;++p)*p=0;
}
void mpp_board_boot(){
 auto& m=mpp_vm_mailbox;auto& p=mpp_vm_port;
 p.lock_after=m.lock_after;p.control=m.initial_control;p.fail_call=m.fail_call;p.nack_byte=m.nack_byte;p.tick_step=m.tick_step;
 const bool valid=m.tag==0x4d50564d&&mpp_data_cookie==0x4d505031;
 m.result=mpp_vm_app.boot(p.port(),p.bus(),{0x202c0000,m.input_slot,8,1000},mpp_vm_dma,valid?m.weights:nullptr,valid?m.weight_count:0);
}
const Status* mpp_vm_status(){return &mpp_vm_app.status();}
void mpp_vm_audio_irq(){
 auto& m=mpp_vm_mailbox;m.result=mpp_vm_app.audio_event({m.sequence,m.rx_half,m.tx_half});
 for(unsigned i=0;i<8;++i)mpp_vm_diagnostic[i]=mpp_vm_app.diagnostic_samples()[i];
}
void mpp_vm_stop(){mpp_vm_app.stop();}
// Minimal freestanding compiler support; never linked to a NUX/ROM function.
void* memset(void* dest,int value,size_t n){auto* d=static_cast<unsigned char*>(dest);for(size_t i=0;i<n;++i)d[i]=static_cast<unsigned char>(value);return dest;}
void* memcpy(void* dest,const void* src,size_t n){auto* d=static_cast<unsigned char*>(dest);auto* s=static_cast<const unsigned char*>(src);for(size_t i=0;i<n;++i)d[i]=s[i];return dest;}
void __aeabi_memclr(void* d,size_t n){memset(d,0,n);}
void __aeabi_memclr4(void* d,size_t n){memset(d,0,n);}
void __aeabi_memclr8(void* d,size_t n){memset(d,0,n);}
void __aeabi_memcpy(void* d,const void* s,size_t n){memcpy(d,s,n);}
void __aeabi_memcpy4(void* d,const void* s,size_t n){memcpy(d,s,n);}
void __aeabi_memcpy8(void* d,const void* s,size_t n){memcpy(d,s,n);}
}
