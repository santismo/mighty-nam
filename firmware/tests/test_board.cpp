#include "../target/board/audio_transport.hpp"
#include "../target/board/codec_control.hpp"
#include "../target/board/startup_memory.hpp"
#include "../target/audio_module.hpp"
#include <array>
#include <vector>
#include <stdexcept>
#include <iostream>
#include <cstring>
#include <limits>
#include <cmath>
#include <chrono>
using namespace mpp::board;
void check(bool b,const char* m){if(!b)throw std::runtime_error(m);}
bool gain(void*,const float* i,float* o,unsigned n){for(unsigned k=0;k<n;++k)o[k]=i[k]*2;return true;}
bool model(void*,const float* i,float* o,unsigned n){return mpp_audio_process(i,o,n);}
bool fail(void*,const float*,float*,unsigned){return false;}
struct Bus {std::vector<int> bytes;unsigned starts=0,stops=0;int nack=-1;};
bool start(void* p){++static_cast<Bus*>(p)->starts;return true;}
void stop(void* p){++static_cast<Bus*>(p)->stops;}
bool write(void* p,uint8_t v){auto& b=*static_cast<Bus*>(p);b.bytes.push_back(v);return int(b.bytes.size())!=b.nack;}
int main(){try{
 Tcd t[4]{};check(make_tcd_ring(t,0x20016800,0x20016900,0x20016aa0),"stock ring build");
 // Golden descriptors independently recovered by ARM emulation of stock 0x11bfe.
 const Tcd golden[4]={
 {0x404040a0,0,0x202,64,0,0x20016800,4,2,0x20016ac0,0x12,2},
 {0x404040a0,0,0x202,64,0,0x20016880,4,2,0x20016aa0,0x12,2},
 {0x20016900,4,0x202,64,0,0x40404020,0,2,0x20016b00,0x10,2},
 {0x20016980,4,0x202,64,0,0x40404020,0,2,0x20016ae0,0x10,2}};
 check(std::memcmp(t,golden,sizeof(t))==0,"TCD mismatch with stock emulation");
 check(!make_tcd_ring(t,0x20016804,0x20016900,0x20016aa0),"unaligned DMA accepted");
 check(!make_tcd_ring(t,0x20016800,0x20016880,0x20016aa0),"overlap accepted");
 check(!make_tcd_ring(t,0x40000000,0x20016900,0x20016aa0),"peripheral RAM accepted");
 check(!make_tcd_ring(t,0xffffffe0,0x20016900,0x20016aa0),"overflow accepted");
 unsigned half=99;check(completed_rx_half(0x20016aa0,0x20016aa0,half)&&half==0,"RX half A");
 check(completed_rx_half(0x20016ac0,0x20016aa0,half)&&half==1,"RX half B");
 check(!completed_rx_half(0x20016ae0,0x20016aa0,half),"invalid RX next pointer");
 // Simulate each transfer count, ensuring one major loop represents 8*4 words.
 for(unsigned k=0;k<4;++k)check(golden[k].nbytes*golden[k].citer==128,"DMA block size");
 int32_t rx[32],tx[32];for(unsigned f=0;f<8;++f)for(unsigned c=0;c<4;++c)rx[4*f+c]=int32_t((c+1)*0x10000000);
 float channels[4][8];unpack_q31(rx,channels);pack_q31(channels,tx);check(std::memcmp(rx,tx,sizeof(rx))==0,"slot roundtrip");
 channels[0][0]=2;channels[1][0]=-2;channels[2][0]=std::numeric_limits<float>::infinity();channels[3][0]=std::numeric_limits<float>::quiet_NaN();pack_q31(channels,tx);
 check(tx[0]==INT32_MAX&&tx[1]==INT32_MIN&&tx[2]==0&&tx[3]==0,"saturation/nonfinite");
 AudioBridge bridge;check(!bridge.process(rx,tx),"uninitialized processing");for(auto x:tx)check(x==0,"uninitialized output not zero");
 check(bridge.configure(1,5,gain,nullptr),"bridge configure");check(bridge.process(rx,tx),"muted process");for(auto x:tx)check(x==0,"default output not muted");
 bridge.set_muted(false);check(bridge.process(rx,tx),"routed process");
 for(unsigned f=0;f<8;++f)check(tx[4*f]==0x40000000&&tx[4*f+1]==0&&tx[4*f+2]==0x40000000&&tx[4*f+3]==0,"route isolation");
 check(!bridge.configure(4,1,gain,nullptr),"bad input slot");check(!bridge.configure(0,16,gain,nullptr),"bad output slots");
 check(bridge.configure(0,3,fail,nullptr),"failure config");bridge.set_muted(false);check(!bridge.process(rx,tx),"failed callback accepted");for(auto x:tx)check(x==0,"failed callback output not zero");
 check(mpp_audio_initialize(),"NAM init");check(bridge.configure(0,3,model,nullptr),"NAM route");
 auto begin=std::chrono::steady_clock::now();
 for(unsigned b=0;b<6000;++b){check(bridge.process(rx,tx),"8-frame NAM transport");for(auto x:tx)check(x==0,"NAM mute leak");}
 std::cout<<"Mac-only compute seconds for 1 s audio in eight-frame NAM callbacks: "<<std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count()<<"\n";
 Bus bus;I2cBus port{&bus,start,write,stop};check(codec_replay_stock_config(port),"codec replay");check(bus.starts==21&&bus.stops==21&&bus.bytes.size()==63,"codec transfer count");
 for(unsigned i=0;i<21;++i)check(bus.bytes[3*i]==0x20&&bus.bytes[3*i+1]==int(i)&&bus.bytes[3*i+2]==stock_codec_registers[i],"codec wire transaction");
 for(int n:{1,2,3,10}){Bus bad;bad.nack=n;I2cBus p{&bad,start,write,stop};check(!codec_replay_stock_config(p),"NACK ignored");check(bad.starts==bad.stops&&int(bad.bytes.size())==n,"NACK did not stop transaction");}
 unsigned char source[4]={1,2,3,4},data[6]={9,9,9,9,9,9},zero[6]={7,7,7,7,7,7};initialize_data(source,data+1,4,zero+1,4);
 check(data[0]==9&&data[5]==9&&zero[0]==7&&zero[5]==7,"startup bounds");for(int i=1;i<5;++i)check(data[i]==i&&zero[i]==0,"startup data initialization");
 std::cout<<"PASS: stock TCD equivalence, DMA boundaries, 4-slot Q31, muted/error routing, 6000 eight-frame NAM blocks, codec ACK/NACK, startup data initialization. All RAM/mocks only.\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
