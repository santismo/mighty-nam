/* Exact public MP-3 V1.5.6 diagnostic bridge, NOT standalone firmware.
 * Original code; recovered stock addresses are version-specific dependencies.
 * No NAM, flash, reset, clock programming, or arbitrary memory access command.
 * Stock startup/USB/SAI remain. The entire audio callback writes zero samples.
 * This cannot promise electrical silence during power-up or codec switching.
 */
#include <stdint.h>
#include <stddef.h>

typedef struct {
 uint32_t magic, schema, ready, blocks, bad_buffer, last_rx, last_tx;
 uint32_t snapshot[16];
} Probe;
volatile Probe mpp_probe;
/* Kept for the existing stock-init ordering harness. */
unsigned mpp_hybrid_ready;
/* Version the original code independently of stock package identifiers. */
const uint8_t mpp_probe_identity[8]={'N','A','M','P','B','0','0','2'};

static uint32_t read32(uint32_t address) {
 return *(volatile const uint32_t *)(uintptr_t)address;
}
static void barrier(void) { __asm__ volatile("dmb" ::: "memory"); }
static const uint32_t registers[16] = {
 0xe000ed00u, /* CPUID */
 0xe000ed14u, /* CCR */
 0xe000ed94u, /* MPU CTRL */
 0xe000ef90u, /* ITCMCR */
 0xe000ef94u, /* DTCMCR */
 0x400e4048u, /* IOMUXC GPR18, upper bank configuration */
 0x400e4040u, /* GPR16 */
 0x400e4044u, /* GPR17 */
 0x40cc0000u, /* M7 root CONTROL */
 0x40cc0020u, /* M7 root STATUS0 */
 0x40cc0024u, /* M7 root STATUS1 */
 0x40c84200u, /* ARM PLL CTRL */
 0xe000ed08u, /* VTOR */
 0xe000ed88u, /* CPACR */
 0x40038000u, /* RTWDOG3 CS */
 0x40c10000u  /* RTWDOG4 CS */
};

void mpp_stock_amp_init(void) {
 mpp_hybrid_ready=0;
 mpp_probe.ready=0;
 mpp_probe.magic=0x4d505031u; mpp_probe.schema=1;
 mpp_probe.blocks=0; mpp_probe.bad_buffer=0;
 mpp_probe.last_rx=0; mpp_probe.last_tx=0;
 /* Snapshot is at stock DSP initialization, AFTER stock SystemInit.
  * It is not the state at factory-loader entry and not an atomic bus snapshot.
  */
 for(unsigned i=0;i<16;++i)mpp_probe.snapshot[i]=read32(registers[i]);
 barrier(); mpp_probe.ready=1; mpp_hybrid_ready=1;
}

void mpp_stock_amp_process(const float *left,const float *right,
                           float *out_left,float *out_right) {
 (void)left; (void)right;
 for(unsigned i=0;i<8;++i)out_left[i]=out_right[i]=0;
}

void mpp_probe_audio(const int32_t *rx,int32_t *tx) {
 uint32_t r=(uint32_t)(uintptr_t)rx,t=(uint32_t)(uintptr_t)tx;
 /* Exact paired 128-byte halves selected by the original DMA ISR.
  * Reject unexpected pointers instead of writing into unknown memory.
  */
 if(!((r==0x20016800u && t==0x20016900u) ||
      (r==0x20016880u && t==0x20016980u))) {
  if(mpp_probe.bad_buffer!=UINT32_MAX)++mpp_probe.bad_buffer;
  return;
 }
 /* The original callback does more than DSP: its stock housekeeping tick
  * decrements service timers and advances button-hold timing every 48 samples.
  * Omitting it prevents POWER long presses from reaching their threshold.
  * Preserve that exact service once per accepted eight-frame audio block. */
 ((void (*)(void))(uintptr_t)0x15639u)();
 for(unsigned i=0;i<32;++i)tx[i]=0;
 barrier();
 mpp_probe.last_rx=r; mpp_probe.last_tx=t;
 if(mpp_probe.ready==1 && mpp_probe.blocks!=UINT32_MAX)++mpp_probe.blocks;
}

typedef void (*StockSend)(const uint8_t *,unsigned,unsigned);
typedef void (*StockReply)(unsigned,unsigned,const uint8_t *,unsigned,unsigned);

void mpp_probe_version(const uint8_t *request,unsigned length,unsigned channel) {
 /* Stock byte-ring assembly appends F7 at request[length], then passes the
  * length EXCLUDING that terminator to every downstream handler. */
 if(length!=4 || request[0]!=0xf0 || request[1]!=0x43 || request[2]!=0x58 ||
    request[3]!=0 || request[4]!=0xf7 || channel>1)return;
 uint8_t reply[45]={0};
 reply[0]=0xf0;reply[1]=0x43;reply[2]=0x58;reply[3]=0x10;
 const uint8_t product[8]={'P','L','U','G','P','R','O',0};
 for(unsigned i=0;i<8;++i){reply[4+i]=mpp_probe_identity[i];reply[36+i]=product[i];}
 reply[28]=0x10;reply[44]=0xf7;
 ((StockSend)(uintptr_t)0xae81u)(reply,45,channel);
}

void mpp_probe_query(const uint8_t *request,unsigned length,unsigned channel) {
 /* Only our exact read request is accepted, even if stock dispatch chooses
  * this handler for another direction. No user-supplied address or write.
  */
 if(length!=9 || channel>1 || request[0]!=0xf0 || request[1]!=0x43 ||
    request[2]!=0x58 || request[3]!=0x70 || request[4]!=4 || request[5]!=2 ||
    request[6]!='N' || request[7]!='P' || request[8]>=128 || request[9]!=0xf7)return;
 unsigned page=request[8];uint32_t value=0;uint8_t status=0;
 if(page<23) {
  /* Explicit layout and bounded 32-bit fields; single-field reads only.
   * Different query replies do not form an atomic multi-field snapshot.
   */
  switch(page) {
   case 0:value=mpp_probe.magic;break;
   case 1:value=mpp_probe.schema;break;
   case 2:value=mpp_probe.ready;break;
   case 3:value=mpp_probe.blocks;break;
   case 4:value=mpp_probe.bad_buffer;break;
   case 5:value=mpp_probe.last_rx;break;
   case 6:value=mpp_probe.last_tx;break;
   default:value=mpp_probe.snapshot[page-7];break;
  }
 } else if(page>=32 && page<48)value=read32(registers[page-32]);
 else status=1;
 uint8_t reply[8]={1,(uint8_t)page,status,0,0,0,0,0};
 for(unsigned i=0;i<5;++i)reply[3+i]=(uint8_t)((value>>(7*i))&0x7fu);
 ((StockReply)(uintptr_t)0xa18bu)(4,2,reply,8,channel);
}

_Static_assert(sizeof(Probe)==23*4,"Probe wire word layout changed");
/* Clang may lower local zero initialization to this ARM support routine. */
void __aeabi_memclr4(void *dst,size_t size) {
 volatile uint8_t *p=(volatile uint8_t *)dst;
 for(size_t i=0;i<size;++i)p[i]=0;
}
