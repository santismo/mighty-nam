#include "../target/standalone/prototype.hpp"
#include "standalone_ram_port.hpp"
#include <stdexcept>
#include <iostream>
#include <limits>
using namespace mpp::standalone;
using mpp::standalone::test::RamPort;
static unsigned cases=0;
void require(bool b,const char* what){if(!b)throw std::runtime_error(what);}
struct Fixture {
 Prototype app;DmaMemory memory;RamPort hw;
 float weights[1871]{};
 Config config{0x202c0000,0,8,1000};
 Fixture(){weights[1869]=.25f;weights[1870]=1;for(auto& x:memory.tx)x=123;}
 bool boot(){return app.boot(hw.port(),hw.bus(),config,memory,weights,1871);}
 void silent(){for(auto x:memory.tx)require(x==0,"TX silence lost");}
 void fault(Error e){require(app.status().state==State::Fault&&app.status().error==e,"wrong fault");silent();require(!hw.running&&hw.muted,"failure did not quiesce");require(!app.audio_event({0,0,0}),"fault did not latch");++cases;}
};
int main(){try{
 unsigned boot_calls,reads;
 {Fixture f;require(f.boot(),"cold boot");boot_calls=f.hw.calls;reads=f.hw.read_calls;f.silent();require(f.hw.codec_bytes==63,"codec sequence");
  for(unsigned b=0;b<32;++b){require(f.app.audio_event({b,b%2,1-b%2}),"valid shifted TX phase");f.silent();for(unsigned i=0;i<8;++i)require(f.app.diagnostic_samples()[i]==.25f,"A2 diagnostic compute");}
  require(f.app.status().samples==256&&f.app.status().maximum_ticks==100,"accounting");
  f.app.stop();require(!f.hw.running,"stop");require(f.boot(),"warm restart");require(f.app.status().blocks==0,"warm counters");f.silent();++cases;}
 {Fixture f;f.hw.control=0x20002000;require(f.boot(),"warm PLL");++cases;}
 for(unsigned n=1;n<=boot_calls;++n){Fixture f;f.hw.fail_call=n;require(!f.boot(),"request failure ignored");f.fault(Error::Port);}
 for(unsigned n=1;n<=reads;++n){Fixture f;f.hw.fail_read=n;require(!f.boot(),"read failure ignored");f.fault(Error::Port);}
 for(unsigned n=1;n<=63;++n){Fixture f;f.hw.nack_byte=n;require(!f.boot(),"codec NACK ignored");require(f.hw.codec_starts==f.hw.codec_stops,"unterminated codec transaction");f.fault(Error::Codec);}
 {Fixture f;f.hw.lock_after=0;require(!f.boot(),"PLL never locked");require(f.hw.lock_polls==8,"unbounded PLL wait");f.fault(Error::ClockTimeout);}
 {Fixture f;f.config.input_slot=4;require(!f.boot(),"bad slot");f.fault(Error::Configuration);}
 {Fixture f;f.config.dma_address=0xffffffe0;require(!f.boot(),"address overflow");f.fault(Error::Configuration);}
 {Fixture f;f.config.dma_address=0x202c0004;require(!f.boot(),"unaligned address");f.fault(Error::Configuration);}
 {Fixture f;f.config.deadline_ticks=0;require(!f.boot(),"zero deadline");f.fault(Error::Configuration);}
 {Fixture f;f.weights[1]=std::numeric_limits<float>::quiet_NaN();require(!f.boot(),"NaN model");f.fault(Error::Model);}
 for(Event e: {Event{1,0,0},Event{0,2,0},Event{0,0,2}}){Fixture f;require(f.boot(),"boot");require(!f.app.audio_event(e),"invalid event accepted");f.fault(e.sequence?Error::Sequence:Error::Buffer);}
 {Fixture f;require(f.boot(),"boot");require(f.app.audio_event({0,0,0}),"first block");require(!f.app.audio_event({1,0,1}),"same RX half");f.fault(Error::Buffer);}
 {Fixture f;require(f.boot(),"boot");require(f.app.audio_event({0,0,0}),"first block");require(!f.app.audio_event({1,1,0}),"same TX half");f.fault(Error::Buffer);}
 for(unsigned step:{0u,1000u,0x80000001u}){Fixture f;require(f.boot(),"boot");f.hw.tick_step=step;require(!f.app.audio_event({0,0,0}),"bad timing accepted");f.fault(Error::Timing);}
 for(unsigned n:{1u,2u}){Fixture f;require(f.boot(),"boot");f.hw.fail_tick=n;require(!f.app.audio_event({0,0,0}),"clock failure accepted");f.fault(Error::Port);}
 for(unsigned n:{1u,2u}){Fixture f;require(f.boot(),"boot");f.hw.fail_call=f.hw.calls+n;require(!f.app.audio_event({0,0,0}),"cache port failure accepted");f.fault(Error::Port);}
 {Fixture f;require(f.boot(),"boot");f.hw.tick=0xfffffff0;require(f.app.audio_event({0,0,0}),"timer wrap");require(f.app.status().maximum_ticks==100,"wrap duration");++cases;}
 {Fixture f;require(f.boot(),"boot");f.hw.fail_call=f.hw.calls+1;f.app.stop();require(f.app.status().cleanup_failed,"failed mute not reported");f.silent();++cases;}
 {Fixture f;require(f.boot(),"boot");f.app.stop();for(auto& x:f.memory.tx)x=123;require(f.boot(),"restart after dirty output");f.silent();++cases;}
 {Fixture f;require(f.boot(),"boot");f.hw.fail_stop=1;f.memory.tx[0]=123;f.app.stop();require(f.app.status().cleanup_failed&&f.hw.running,"stop failure hidden");require(f.memory.tx[0]==123,"modified potentially active DMA buffer");require(!f.boot(),"rebound port after failed quiesce");f.hw.fail_stop=0;require(f.boot(),"retry after quiesce recovers");f.silent();++cases;}
 {Fixture f;f.weights[1869]=2;f.weights[1870]=std::numeric_limits<float>::max();require(f.boot(),"finite weights accepted");require(!f.app.audio_event({0,0,0}),"nonfinite computation accepted");f.fault(Error::Nonfinite);}
 std::cout<<"{\"status\":\"PASS_NATIVE_STANDALONE\",\"cases\":"<<cases<<",\"startup_request_failure_positions\":"<<boot_calls<<",\"codec_nack_positions\":63,\"playback\":false,\"device_access\":false}\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
