#include "rt1176_register_model.hpp"
#include "../target/hardware/handoff.hpp"
#include <iostream>
using namespace mpp::hardware;
using namespace mpp::standalone;
using mpp::hardware::test::RegisterModel;
unsigned cases=0;
void require(bool value,const char* what){if(!value)throw std::runtime_error(what);}
struct Fixture {
 RegisterModel registers;DmaMemory memory;Rt1176Backend driver{registers.bus(),{0x202c0000,600000000,2048},memory};Prototype app;
 float weights[1871]{};
 Fixture(){weights[1869]=.25f;weights[1870]=1;for(auto& x:memory.tx)x=99;}
 bool boot(){registers.tick_step=1000000;bool b=app.boot(driver.port(),driver.codec_bus(),{0x202c0000,0,16,100000},memory,weights,1871);registers.tick_step=100;return b;}
 void silent(){for(auto x:memory.tx)require(x==0,"TX nonzero");}
 bool event(unsigned n,unsigned tx){registers.complete(n&1,tx);Event e;return driver.poll_release(e)==Release::Ready&&app.audio_event(e);}
};
int main(){try{
 {Fixture f;require(f.boot(),"cold register-model boot");require(f.registers.codec_bytes.size()==63,"63 bytes on GPIO bus");
  for(unsigned r=0;r<21;++r){require(f.registers.codec_bytes[3*r]==0x20,"codec address");require(f.registers.codec_bytes[3*r+1]==r,"codec reg");require(f.registers.codec_bytes[3*r+2]==mpp::board::stock_codec_registers[r],"codec value");}
  require(f.registers.starts==21&&f.registers.stops==21,"I2C boundaries");require(!f.registers.bad_width,"register widths");
  require(f.registers.get(0x40074040)==0x80000037,"TX request mode");require(f.registers.get(0x4007000c)==0x10001,"DMA ERQ");
  require(f.registers.count_write(0xe000ef70)==20,"initial DMA cache lines");require(f.registers.count_write(0xe000ef68)>=20,"TX/descriptor publication");
  require(!f.registers.count_write(0xe000e100),"no uninstalled IRQ enabled");
  for(unsigned n=0;n<100;++n){require(f.event(n,1-(n&1)),"shifted phase release");f.silent();require(f.app.diagnostic_samples()[0]==.25f,"A2 input path");}
  f.app.stop();require(!f.driver.running(),"stopped");require(f.boot(),"warm boot");require(f.event(0,0),"warm first release");f.silent();++cases;}
 for(unsigned nack=1;nack<=63;++nack){Fixture f;f.registers.nack_byte=nack;require(!f.boot(),"NACK ignored");require(f.app.status().error==Error::Codec,"NACK class");require(!f.driver.running(),"NACK running");f.silent();++cases;}
 for(unsigned mode=0;mode<8;++mode){Fixture f;
  switch(mode){case 0:f.registers.ai_stuck=true;break;case 1:f.registers.ldo_busy=true;break;case 2:f.registers.pll_stuck=true;break;case 3:f.registers.scl_stuck=true;break;case 4:f.registers.sda_stuck=true;break;case 5:f.registers.fail_stop=true;break;case 6:f.registers.put(0xe0001000,1u<<25);break;case 7:f.registers.dma_busy=true;break;}
  require(!f.boot(),"stalled peripheral accepted");require(f.registers.reads<100000,"unbounded stall");++cases;}
 for(uint32_t address:{0x40c84880u,0x40071216u,0x40074040u,0xe000ef68u,0x400e8244u,0x40c60084u}){Fixture f;f.registers.fail_write=address;require(!f.boot(),"bus write failure ignored");++cases;}
 {Fixture f;f.registers.put(0x4007000c,2);require(!f.boot(),"other DMA channel overwritten");++cases;}
 {Fixture f;f.registers.put(0xe000ed14,0);require(f.boot(),"cache disabled boot");require(!f.registers.count_write(0xe000ef70)&&!f.registers.count_write(0xe000ef68),"cache-off maintenance");++cases;}
 {Fixture f;f.registers.put(0x400e4000,0xa5a5ffff);require(f.boot(),"GPR preservation boot");require(f.registers.get(0x400e4000)==0xa5a5ff00,"unrelated GPR fields changed");++cases;}
 {Fixture f;require(f.boot(),"fault fixture boot");f.registers.torn_snapshot=true;f.registers.complete(0,0);Event e;require(f.driver.poll_release(e)==Release::Fault,"torn reload accepted");f.app.stop();++cases;}
 {Fixture f;require(f.boot(),"release boot");Event e;require(f.driver.poll_release(e)==Release::Pending,"spurious event");require(f.event(0,0),"first");f.registers.complete(0,1);require(f.driver.poll_release(e)==Release::Fault,"repeated half accepted");f.app.stop();++cases;}
 {Fixture f;require(f.boot(),"DMA failure boot");f.registers.put(0x4007002c,1);Event e;require(f.driver.poll_release(e)==Release::Fault,"DMA error ignored");f.app.stop();++cases;}
 {Fixture f;require(f.boot(),"quiesce failure boot");f.registers.dma_busy=true;f.memory.tx[0]=123;f.app.stop();require(f.app.status().cleanup_failed&&f.driver.running(),"failed stop hidden");require(f.memory.tx[0]==123,"busy buffer modified");f.registers.dma_busy=false;require(f.boot(),"stop retry");++cases;}
 {Fixture f;require(f.boot(),"clock wrap boot");f.registers.tick=0xffffffd0;require(f.event(0,0),"clock wrap");f.registers.tick_step=0;require(!f.event(1,1),"event stalled timer");++cases;}
 {Fixture f;require(f.boot(),"bounds boot");auto p=f.driver.port();require(!issue(p,Op::PublishTx,0x202c00e0,64),"RX clean accepted");require(!issue(p,Op::AcquireRx,0x202c0004,128),"unaligned invalidate");require(!issue(p,Op::Write32,0x30040000,0),"arbitrary MMIO");++cases;}
 {RegisterModel m;DmaMemory d;Rt1176Backend b(m.bus(),{0x202c0000,600000000,16},d);auto p=b.port();require(issue(p,Op::StopAudio)&&issue(p,Op::PrepareMemory,0x202c0000,640),"delay prep");m.tick_step=0;require(!issue(p,Op::DelayUnits,100),"stalled startup timer");++cases;}
 {RegisterModel m;HandoffSnapshot s{};m.put(0xe000ed94,5);m.put(0x400e4044,0x55aaaa55);require(prepare_core_handoff(m.bus(),{0,0,1},0,s),"handoff");require(s.ccr==0x30000&&s.mpu_ctrl==5&&s.nvic_banks==7,"handoff snapshot");require(m.get(0xe000ed14)==0x30000&&m.get(0xe000ed94)==5&&m.get(0x400e4044)==0x55aaaa55,"handoff destroyed inherited state");require(!m.count_write(0xe000ef50)&&!m.count_write(0xe000ef60),"global invalidate");++cases;}
 for(CoreState c: {CoreState{1,0,1},CoreState{0,1,1},CoreState{0,2,1},CoreState{0,0,0}}){RegisterModel m;HandoffSnapshot s{};require(!prepare_core_handoff(m.bus(),c,0,s)&&m.writes.empty(),"invalid handoff mutated");++cases;}
 {RegisterModel m;HandoffSnapshot s{};require(!prepare_core_handoff(m.bus(),{0,0,1},4,s),"unaligned vectors");++cases;}
 for(uint32_t addr:{0x20240000u,0x2023ffe0u,0x20000000u,0xffffffe0u}){RegisterModel m;DmaMemory d;Rt1176Backend b(m.bus(),{addr,600000000,16},d);auto p=b.port();require(issue(p,Op::StopAudio),"address test stop");require(!issue(p,Op::PrepareMemory,addr,640),"unsafe DMA placement");++cases;}
 {RegisterModel m;DmaMemory d;Rt1176Backend b(m.bus(),{0x202c0000,600000000,0xffffffff},d);require(!issue(b.port(),Op::StopAudio),"unbounded poll config");require(m.reads<10,"poll config caused reads");++cases;}
 std::cout<<"{\"status\":\"PASS_REGISTER_BACKEND\",\"cases\":"<<cases<<",\"codec_nack_positions\":63,\"shifted_phase_blocks\":100,\"device_access\":false,\"playback\":false}\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
