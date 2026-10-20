#include "rt1176_backend.hpp"
namespace mpp::hardware {
using standalone::Op;
namespace {
constexpr uint32_t sai=0x40404000,dma=0x40070000,mux=0x40074000;
constexpr uint32_t gpio7=0x40c5c000,gpio8=0x40c60000,gpio11=0x40c6c000;
constexpr uint32_t sda=1u<<14,scl=1u<<13,ai=0x40c84000;
constexpr uint32_t ccr=0xe000ed14,dc_clean=0xe000ef68,dc_inval=0xe000ef5c,dc_both=0xe000ef70;
constexpr uint32_t tcd(unsigned ch){return dma+0x1000+32*ch;}
}
bool Rt1176Backend::read(uint32_t a,uint32_t& v,unsigned w){return bus_.read&&bus_.read(bus_.context,w,a,&v);}
bool Rt1176Backend::write(uint32_t a,uint32_t v,unsigned w){return bus_.write&&bus_.write(bus_.context,w,a,v);}
bool Rt1176Backend::barrier(){return bus_.barrier&&bus_.barrier(bus_.context);}
bool Rt1176Backend::modify(uint32_t a,uint32_t clear,uint32_t set){uint32_t v;return read(a,v)&&write(a,(v&~clear)|set);}
bool Rt1176Backend::wait(uint32_t a,uint32_t mask,uint32_t value,unsigned width){
 if(!cfg_.poll_limit||cfg_.poll_limit>16000000)return false;
 for(uint32_t n=0;n<cfg_.poll_limit;++n){uint32_t v;if(!read(a,v,width))return false;if((v&mask)==value)return true;}return false;
}
standalone::Port Rt1176Backend::port(){return {this,
 [](void* p,standalone::Request r){return static_cast<Rt1176Backend*>(p)->request(r);},
 [](void* p,uint32_t a,uint32_t* v){return v&&a==ai+0x300&&static_cast<Rt1176Backend*>(p)->read(a,*v);},
 [](void* p,uint32_t* v){return v&&static_cast<Rt1176Backend*>(p)->ticks(*v);}};}
board::I2cBus Rt1176Backend::codec_bus(){return {this,
 [](void* p){auto& b=*static_cast<Rt1176Backend*>(p);bool ok=b.i2c_start();b.i2c_fault_|=!ok;return ok;},
 [](void* p,uint8_t v){auto& b=*static_cast<Rt1176Backend*>(p);bool ok=b.i2c_byte(v);b.i2c_fault_|=!ok;return ok;},
 [](void* p){auto& b=*static_cast<Rt1176Backend*>(p);b.i2c_fault_|=!b.i2c_stop();},
 [](void* p){return static_cast<Rt1176Backend*>(p)->bus_healthy();}};}
bool Rt1176Backend::ticks(uint32_t& v){uint32_t c;return read(0xe0001000,c)&&(c&1)&&!(c&(1u<<25))&&read(0xe0001004,v);}
bool Rt1176Backend::delay_us(uint32_t us){
 if(!cfg_.poll_limit||cfg_.poll_limit>16000000||!cfg_.cpu_hz||cfg_.cpu_hz%1000000||cfg_.cpu_hz>1000000000)return false;
 const uint64_t required=uint64_t(us)*(cfg_.cpu_hz/1000000);
 if(required>=0x80000000u)return false;
 if(!required)return true;
 uint32_t begin,now;if(!ticks(begin))return false;
 for(uint32_t n=0;n<cfg_.poll_limit;++n){if(!ticks(now))return false;if(uint32_t(now-begin)>=required)return true;}return false;
}
bool Rt1176Backend::cache(uint32_t address,uint32_t bytes,uint32_t operation){
 if(!bytes||((address|bytes)&31)||address<cfg_.dma_address||bytes>640||address-cfg_.dma_address>640-bytes)return false;
 uint32_t value;if(!barrier()||!read(ccr,value))return false;
 if(value&0x10000)for(uint32_t n=0;n<bytes;n+=32)if(!write(operation,address+n))return false;
 return barrier();
}
bool Rt1176Backend::hold(){
 // Reproduce stock's low GPIO7 controls plus codec reset. Their analog function
 // and pop behavior are not electrically verified; software TX is always zero.
 return write(0x40cc6620,1)&&write(0x40cc6660,1)&&barrier()
  &&write(gpio7+0x88,0x8800)&&write(gpio8+0x88,1)
  &&modify(gpio7+4,0,0x8800)&&modify(gpio8+4,0,1)
  &&write(0x400e803c,0xa)&&write(0x400e804c,0xa)&&write(0x400e8090,0xa)
  &&write(0x400e8280,0xe)&&write(0x400e8290,0xe)&&write(0x400e82d4,0xe)&&barrier();
}
bool Rt1176Backend::stop(){
 stopped_=false;installed_=false;configured_sai_=0;sai_reset_=false;
 // Gate on before touching registers. IRQ0 is shared by DMA0/DMA16, both ours.
 if(!write(0x40cc62c0,1)||!write(0x40cc6f60,1)||!barrier()
  ||!write(0xe000e180,1)||!write(mux,0)||!write(mux+64,0)
  ||!write(dma+0x1a,0,1)||!write(dma+0x1a,16,1)
  ||!write(sai+8,0)||!write(sai+0x88,0)||!barrier())return false;
 if(!wait(tcd(0)+28,0x40,0,2)||!wait(tcd(16)+28,0x40,0,2)
  ||!wait(sai+8,0x80010001,0)||!wait(sai+0x88,0x80010001,0))return false;
 if(!write(dma+0x1f,0,1)||!write(dma+0x1f,16,1)||!write(0xe000e280,1)||!barrier())return false;
 stopped_=true;running_=false;return true;
}
bool Rt1176Backend::prepare(){
 prepared_=false;pins_=false;have_release_=false;sequence_=0;
 // Dedicated 32-byte lines in OCRAM only. Actual ownership and MPU attributes
 // must be proven by the eventual loader/linker contract.
 if(!stopped_||!cfg_.poll_limit||cfg_.poll_limit>16000000||!cfg_.cpu_hz||cfg_.cpu_hz%1000000||cfg_.cpu_hz>1000000000
  ||(cfg_.dma_address&31)||cfg_.dma_address<0x20200000||cfg_.dma_address>0x20300000-640)return false;
 // NXP RM 10.5.1: retain the ROM's documented 48-KiB work area for later
 // recovery work. Excluding it does not establish a callable ROM entry.
 if(cfg_.dma_address<0x2024c000&&cfg_.dma_address+640>0x20240000)return false;
#if defined(__arm__)
 if(reinterpret_cast<uintptr_t>(&memory_)!=cfg_.dma_address)return false;
#endif
 if(!modify(0xe000edfc,0,0x1000000)||!modify(0xe0001000,0,1)||!barrier())return false;
 uint32_t tick;if(!ticks(tick)||!cache(cfg_.dma_address,640,dc_both))return false;
 prepared_=true;return true;
}
bool Rt1176Backend::pins(){
 if(!stopped_||!prepared_)return false;
 // GPIO_DISP_B2_12/13: SCL/SDA. Release direction before pinmux; never drive high.
 if(!modify(gpio11+4,sda|scl,0)||!write(gpio11+0x88,sda|scl)
  ||!write(0x400e8244,0xa)||!write(0x400e8248,0xa)
  ||!write(0x400e8488,0xe)||!write(0x400e848c,0xe))return false;
 // GPIO_AD_17/20/21/22/23 are SAI1. SD_B2_05..11 are FlexSPI: untouched.
 constexpr uint32_t muxes[]={0x400e8150,0x400e815c,0x400e8160,0x400e8164,0x400e8168};
 constexpr uint32_t pads[]={0x400e8394,0x400e83a0,0x400e83a4,0x400e83a8,0x400e83ac};
 constexpr uint32_t daisies[]={0x400e866c,0x400e8674,0x400e867c,0x400e8680};
 for(auto a:muxes)if(!write(a,0x10))return false;
 for(auto a:pads)if(!write(a,2))return false;
 for(auto a:daisies)if(!write(a,0))return false;
 if(!barrier())return false;pins_=true;i2c_fault_=false;return true;
}
bool Rt1176Backend::analog(bool ldo,bool reading,uint32_t reg,uint32_t& value){
 if(!prepared_||reg>255)return false;
 if(ldo&&!wait(ai+0x500,0x40000000,0))return false;
 uint32_t ctrl=ai+(ldo?0x820:0x880),old;
 if(!read(ctrl,old))return false;
 uint32_t next=(old&~0x100ffu)|reg|(reading?0x10000:0);
 if(!write(ctrl,next)||(!reading&&!write(ctrl+0x10,value)))return false;
 if(ldo){
  if(!read(ai+0x500,old)||!write(ai+0x500,old^0x10000)
    ||!barrier()||!wait(ai+0x500,0x40000000,0))return false;
 }else{
  if(!write(ctrl,next^0x100)||!barrier()||!wait(ctrl,0x200,(old^0x200)&0x200))return false;
 }
 if(reading)return read(ctrl+0x20,value);
 return modify(ctrl,0x10000,0);
}
bool Rt1176Backend::audio_ldo(){
 // Saved V1 uses 0x105 and a 1-us wait. This prototype deliberately reproduces
 // that observed sequence; newer NXP SDK uses a different limiter sequence.
 uint32_t v=0;if(!analog(true,true,0,v))return false;
 if(v!=0x105){v=0x105;if(!analog(true,false,0,v)||!delay_us(1))return false;}
 return modify(ai+0x570,0,0x10);
}
bool Rt1176Backend::gpio_line(uint32_t mask,bool release){
 if(release)return modify(gpio11+4,mask,0);
 return write(gpio11+0x88,mask)&&modify(gpio11+4,0,mask);
}
bool Rt1176Backend::scl_high(){return gpio_line(scl,true)&&wait(gpio11+8,scl,scl)&&delay_us(5);}
bool Rt1176Backend::i2c_start(){
 if(!pins_||i2c_fault_||!gpio_line(sda,true)||!scl_high())return false;
 uint32_t v;return read(gpio11+8,v)&&(v&sda)&&gpio_line(sda,false)&&delay_us(5)&&gpio_line(scl,false);
}
bool Rt1176Backend::i2c_byte(uint8_t byte){
 if(!pins_||i2c_fault_)return false;
 for(unsigned i=0;i<8;++i){if(!gpio_line(sda,(byte&0x80)!=0)||!delay_us(5)||!scl_high()||!gpio_line(scl,false))return false;byte<<=1;}
 uint32_t v;
 bool ok= gpio_line(sda,true)&&delay_us(5)&&scl_high()&&read(gpio11+8,v);
 bool ack=ok&&!(v&sda);
 return gpio_line(scl,false)&&ack;
}
bool Rt1176Backend::i2c_stop(){
 return gpio_line(scl,false)&&gpio_line(sda,false)&&delay_us(5)&&scl_high()
  &&gpio_line(sda,true)&&delay_us(5)&&wait(gpio11+8,scl|sda,scl|sda);
}
bool Rt1176Backend::install(){
 if(!stopped_||!prepared_||!pins_||configured_sai_!=0xfff||i2c_fault_)return false;
 uint32_t erq;if(!read(dma+0xc,erq)||erq)return false;
 // Do not change global DMA policy while another channel owns the engine.
 for(unsigned ch=0;ch<32;++ch){uint32_t csr;if(!read(tcd(ch)+28,csr,2)||(csr&0x40))return false;}
 board::Tcd expected[4];if(!board::make_tcd_ring(expected,cfg_.dma_address,cfg_.dma_address+256,cfg_.dma_address+512))return false;
 auto* a=reinterpret_cast<const uint8_t*>(expected);auto* b=reinterpret_cast<const uint8_t*>(memory_.descriptors);
 for(unsigned i=0;i<128;++i)if(a[i]!=b[i])return false;
 if(!cache(cfg_.dma_address+512,128,dc_clean)||!write(dma,0x4c0))return false;
 for(unsigned i=0;i<2;++i){const auto& d=memory_.descriptors[i*2];uint32_t t=tcd(i?16:0);
  if(!write(t+28,0,2)||!write(t,d.saddr)||!write(t+4,uint16_t(d.soff),2)||!write(t+6,d.attr,2)
   ||!write(t+8,d.nbytes)||!write(t+12,uint32_t(d.slast))||!write(t+16,d.daddr)
   ||!write(t+20,uint16_t(d.doff),2)||!write(t+22,d.citer,2)||!write(t+24,d.next)
   ||!write(t+30,d.biter,2)||!write(t+28,d.csr,2))return false;
  unsigned channel=i?16:0;
  if(!write(dma+0x1e,channel,1)||!write(dma+0x1c,channel,1)||!write(dma+0x1f,channel,1))return false;
 }
 // Source IDs 54/55. SDK enum bit8 is a mux-instance tag, not SOURCE data.
 // Use normal request mode: no unexplained stock TRIG bit on channel 16.
 if(!write(mux,54)||!write(mux+64,55)||!write(sai+8,0x2000000)||!write(sai+8,0)
  ||!write(sai+0x88,0x2000000)||!write(sai+0x88,0)||!barrier())return false;
 installed_=true;return true;
}
bool Rt1176Backend::start(){
 if(!stopped_||!installed_||!prepared_||!pins_||i2c_fault_)return false;
 for(auto x:memory_.tx)if(x)return false;
 uint32_t clock;if(!read(ai+0x300,clock)||(clock&0x20006000)!=0x20002000)return false;
 // An interrupted start can leave channels active. Keep that possibility
 // visible until a successful stop confirms quiescence.
 stopped_=false;running_=true;
 if(!cache(cfg_.dma_address+256,256,dc_clean)||!write(mux,0x80000036)||!write(mux+64,0x80000037)
  ||!write(dma+0x1b,0,1)||!write(dma+0x1b,16,1)||!barrier()
  ||!write(sai+8,0x80010001)||!write(sai+0x88,0x80010001)||!barrier())return false;
 // Poll DMA INT; a physical exception-vector integration is not yet supplied.
 stopped_=false;running_=true;return true;
}
bool Rt1176Backend::request(standalone::Request r){
 switch(r.op){
 case Op::HoldOutputs:return hold();
 case Op::StopAudio:return stop();
 case Op::PrepareMemory:return r.a==cfg_.dma_address&&r.b==640&&prepare();
 case Op::PreparePins:return pins();
 case Op::AudioLdo:return audio_ldo();
 case Op::AnalogWrite:return analog(false,false,r.a,r.b);
 case Op::AnalogModify:{if(r.d>=32)return false;uint32_t v;if(!analog(false,true,r.a,v))return false;v=(v&~r.c)|((r.b<<r.d)&r.c);return analog(false,false,r.a,v);}
 case Op::DelayUnits:return delay_us(r.a);
 case Op::CodecReset:return pins_&&r.a<2&&write(gpio8+(r.a?0x84:0x88),1);
 case Op::InstallDma:return r.a==cfg_.dma_address+512&&r.b==4&&install();
 case Op::PublishTx:return prepared_&&r.a>=cfg_.dma_address+256&&r.a<cfg_.dma_address+512&&r.b<=cfg_.dma_address+512-r.a&&cache(r.a,r.b,dc_clean);
 case Op::AcquireRx:return running_&&r.a>=cfg_.dma_address&&r.a<cfg_.dma_address+256&&r.b<=cfg_.dma_address+256-r.a&&cache(r.a,r.b,dc_inval);
 case Op::StartAudio:return start();
 case Op::Write32:
  if(!stopped_||!prepared_)return false;
  if(r.a==ai+0x300)return write(r.a,r.b);
  if(r.a==0x40cc2000)return r.b==0x40f&&write(r.a,r.b);
  if(r.a==0x40cc6f60)return r.b==1&&write(r.a,r.b);
  if(r.a==0x400e4000)return r.b==0x100&&modify(r.a,0x1ff,0x100); // preserve unrelated GPR0 fields
  for(unsigned i=0;i<12;++i)if(r.a==board::sai_configuration[i].address&&r.b==board::sai_configuration[i].value){
   if(!sai_reset_){if(!write(sai+8,0x1000000)||!write(sai+8,0)||!write(sai+0x88,0x1000000)||!write(sai+0x88,0))return false;sai_reset_=true;}
   if(!write(r.a,r.b))return false;configured_sai_|=1u<<i;return true;
  }
  return false;
 }return false;
}
Release Rt1176Backend::poll_release(standalone::Event& out){
 if(!running_)return Release::Fault;
 uint32_t interrupt,error;if(!read(dma+0x24,interrupt)||!read(dma+0x2c,error)||(error&0x10001))return Release::Fault;
 if(!(interrupt&1))return Release::Pending;
 // Two equal snapshots avoid using a descriptor during scatter/gather reload.
 // They cannot count missed full-ring wraps: hardware IRQ/timing verification
 // remains required before this diagnostic polling path can be a real audio loop.
 uint32_t rx,tx,rx2,tx2;
 if(!read(tcd(0)+24,rx)||!read(tcd(16)+24,tx)||!barrier()||!read(tcd(0)+24,rx2)||!read(tcd(16)+24,tx2)
  ||rx!=rx2||tx!=tx2)return Release::Fault;
 unsigned rh,th;
 if(!board::completed_rx_half(rx,cfg_.dma_address+512,rh)||!board::completed_rx_half(tx,cfg_.dma_address+576,th)
  ||(have_release_&&(rh==last_rx_||th==last_tx_)))return Release::Fault;
 if(!write(dma+0x1f,0,1)||!barrier()||!read(tcd(0)+24,rx2)||!read(tcd(16)+24,tx2)||rx!=rx2||tx!=tx2)return Release::Fault;
 out={sequence_++,rh,th};last_rx_=rh;last_tx_=th;have_release_=true;return Release::Ready;
}
}
