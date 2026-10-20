#include "prototype.hpp"
namespace mpp::standalone {
bool Prototype::cleanup(){
 // Quiesce before touching buffers; a physical backend must honor this ordering.
 bool muted=issue(port_,Op::HoldOutputs);
 bool stopped=issue(port_,Op::StopAudio);
 if(stopped&&dma_)for(auto &x:dma_->tx)x=0;
 bool published=!dma_ready_||(stopped&&issue(port_,Op::PublishTx,config_.dma_address+256,256));
 return muted&&stopped&&published;
}
bool Prototype::fail(Error e){
 status_.state=State::Fault;status_.error=e;
 status_.cleanup_failed=!cleanup();return false;
}
void Prototype::stop(){
 if(!cleanup()){status_.state=State::Fault;status_.error=Error::Port;status_.cleanup_failed=1;}
 else status_.state=State::Reset;
}
bool Prototype::boot(Port p,board::I2cBus bus,Config cfg,DmaMemory& memory,const float* weights,unsigned count){
 // A live instance must be stopped before rebinding its port or buffers.
 if(status_.state==State::RunningSilent||status_.state==State::Starting||status_.cleanup_failed){if(!cleanup())return fail(Error::Port);}
 port_=p;config_=cfg;dma_=&memory;status_={State::Starting,Error::None,0,0,0,0,0};last_rx_=last_tx_=0;
 have_event_=false;dma_ready_=false;
 for(auto& x:input_)x=0;for(auto& x:output_)x=0;
 if(!port_.request||!port_.read32||!port_.ticks)return fail(Error::Port);
 if(!issue(port_,Op::HoldOutputs)||!issue(port_,Op::StopAudio))return fail(Error::Port);
 for(auto& x:memory.tx)x=0;for(auto& x:memory.rx)x=0;
 if(cfg.input_slot>=4||!cfg.deadline_ticks||cfg.deadline_ticks>=0x80000000
    ||!cfg.pll_poll_limit||cfg.pll_poll_limit>65536
    ||cfg.dma_address>0xfffffd7f
    ||!board::make_tcd_ring(memory.descriptors,cfg.dma_address,cfg.dma_address+256,cfg.dma_address+512))return fail(Error::Configuration);
 dma_ready_=true;
 if(!issue(port_,Op::PrepareMemory,cfg.dma_address,sizeof(DmaMemory))
    ||!issue(port_,Op::PreparePins)||!issue(port_,Op::CodecReset,0))return fail(Error::Port);
 auto clock=configure_audio_clock(port_,cfg.pll_poll_limit);
 if(clock!=ClockResult::Ready)return fail(clock==ClockResult::LockTimeout?Error::ClockTimeout:Error::Port);
 if(!issue(port_,Op::DelayUnits,400000)||!issue(port_,Op::CodecReset,1)
    ||!issue(port_,Op::DelayUnits,400000))return fail(Error::Port);
 if(!board::codec_replay_stock_config(bus))return fail(Error::Codec);
 for(auto r:board::sai_configuration)if(!issue(port_,Op::Write32,r.address,r.value))return fail(Error::Port);
 if(!model_.load(weights,count))return fail(Error::Model);
 // Both TX halves remain permanently zero in this diagnostic prototype.
 if(!issue(port_,Op::PublishTx,cfg.dma_address+256,256)
    ||!issue(port_,Op::InstallDma,cfg.dma_address+512,4))return fail(Error::Port);
 status_.state=State::RunningSilent;
 if(!issue(port_,Op::StartAudio))return fail(Error::Port);
 return true;
}
bool Prototype::audio_event(Event event){
 if(status_.state!=State::RunningSilent)return false;
 if(event.sequence!=status_.expected_sequence)return fail(Error::Sequence);
 if(event.rx_half>1||event.tx_writable_half>1
    ||(have_event_&&(event.rx_half==last_rx_||event.tx_writable_half==last_tx_)))return fail(Error::Buffer);
 uint32_t start=0,end=0;
 if(!port_.ticks(port_.context,&start)
    ||!issue(port_,Op::AcquireRx,config_.dma_address+128*event.rx_half,128))return fail(Error::Port);
 const int32_t* rx=dma_->rx+32*event.rx_half;
 for(unsigned i=0;i<8;++i)input_[i]=float(rx[4*i+config_.input_slot])*0x1p-31f;
 model_.process(input_,output_,8);
 for(float x:output_)if(!__builtin_isfinite(x))return fail(Error::Nonfinite);
 for(unsigned i=0;i<32;++i)dma_->tx[event.tx_writable_half*32+i]=0;
 if(!issue(port_,Op::PublishTx,config_.dma_address+256+128*event.tx_writable_half,128)
    ||!port_.ticks(port_.context,&end))return fail(Error::Port);
 const uint32_t duration=end-start;
 if(!duration||duration>=config_.deadline_ticks)return fail(Error::Timing);
 if(duration>status_.maximum_ticks)status_.maximum_ticks=duration;
 if(status_.blocks!=UINT32_MAX)++status_.blocks;
 status_.samples=status_.samples>UINT32_MAX-8?UINT32_MAX:status_.samples+8;
 ++status_.expected_sequence;have_event_=true;
 last_rx_=event.rx_half;last_tx_=event.tx_writable_half;return true;
}
}
