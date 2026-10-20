#include "../hardware/handoff.hpp"
#include "../link/model_receiver.hpp"
#include <stddef.h>
#ifdef MPP_STARTUP_CONTROL
#include "../hardware/startup_clock.hpp"
#endif
using namespace mpp;
// Actual objects, not guessed sizes. Reserve both to catch integration growth.
extern "C" {
constinit standalone::Prototype mpp_diag_app{};
constinit link::ModelReceiver mpp_diag_receiver{};
__attribute__((section(".dma"))) standalone::DmaMemory mpp_diag_dma;
uint32_t mpp_diag_data_cookie=0x4d505044;
struct Diagnostic {
 uint32_t magic,version,stage,blockers,cookie,app_bytes,receiver_bytes,dma_bytes;
 hardware::HandoffSnapshot core;
 uint32_t watchdog1,watchdog2,watchdog3,watchdog4;
};
volatile Diagnostic mpp_diag_status;
#ifdef MPP_STARTUP_CONTROL
hardware::ClockReport mpp_diag_clock;
uint32_t mpp_diag_read_clock(uint32_t reference_hz){
 return static_cast<uint32_t>(hardware::inspect_startup_clock(hardware::direct_mmio_bus(),reference_hz,mpp_diag_clock));
}
#endif
void mpp_diag_main(){
 // This path only initializes C state, normalizes core interrupt state and
 // records registers. All linked audio/transport code remains uncalled.
 auto bus=hardware::direct_mmio_bus();
 hardware::HandoffSnapshot snapshot{};
 bool ok=hardware::prepare_core_handoff(bus,hardware::direct_core_state(),0,snapshot);
 mpp_diag_status.magic=0x4d504447;
 mpp_diag_status.version=1;
 mpp_diag_status.stage=ok?2:3;
 // Bits: loader contract, RAM ownership, clock, watchdog, DMA/USB quiescence,
 // electrical mute, physical recovery, hardware timing. All are unresolved.
 mpp_diag_status.blockers=0xff;
 mpp_diag_status.cookie=mpp_diag_data_cookie;
 mpp_diag_status.app_bytes=sizeof(mpp_diag_app);
 mpp_diag_status.receiver_bytes=sizeof(mpp_diag_receiver);
 mpp_diag_status.dma_bytes=sizeof(mpp_diag_dma);
 mpp_diag_status.core.old_vtor=snapshot.old_vtor;
 mpp_diag_status.core.ccr=snapshot.ccr;
 mpp_diag_status.core.mpu_ctrl=snapshot.mpu_ctrl;
 mpp_diag_status.core.itcm_ctrl=snapshot.itcm_ctrl;
 mpp_diag_status.core.dtcm_ctrl=snapshot.dtcm_ctrl;
 mpp_diag_status.core.flexram_gpr17=snapshot.flexram_gpr17;
 mpp_diag_status.core.root_m7=snapshot.root_m7;
 mpp_diag_status.core.nvic_banks=snapshot.nvic_banks;
 // Readbacks are observations only, never claims of watchdog ownership.
 uint32_t value=0;
 bus.read(bus.context,2,0x40030000,&value);mpp_diag_status.watchdog1=value;
 bus.read(bus.context,2,0x40034000,&value);mpp_diag_status.watchdog2=value;
 bus.read(bus.context,4,0x40038000,&value);mpp_diag_status.watchdog3=value;
 bus.read(bus.context,4,0x40c10000,&value);mpp_diag_status.watchdog4=value;
#ifdef MPP_STARTUP_CONTROL
 mpp_diag_status.version=2;
 mpp_diag_read_clock(0); // Board reference is not established by this image.
#endif
}
// Compiler support for a self-contained freestanding link. No ROM calls.
void* memset(void* dst,int v,size_t n){auto* d=static_cast<unsigned char*>(dst);for(size_t i=0;i<n;++i)d[i]=static_cast<unsigned char>(v);return dst;}
void* memcpy(void* dst,const void* src,size_t n){auto* d=static_cast<unsigned char*>(dst);auto* s=static_cast<const unsigned char*>(src);for(size_t i=0;i<n;++i)d[i]=s[i];return dst;}
void __aeabi_memclr(void* d,size_t n){memset(d,0,n);}
void __aeabi_memclr4(void* d,size_t n){memset(d,0,n);}
void __aeabi_memclr8(void* d,size_t n){memset(d,0,n);}
void __aeabi_memcpy(void* d,const void* s,size_t n){memcpy(d,s,n);}
void __aeabi_memcpy4(void* d,const void* s,size_t n){memcpy(d,s,n);}
void __aeabi_memcpy8(void* d,const void* s,size_t n){memcpy(d,s,n);}
}
