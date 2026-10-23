// MIT (c) 2026 santismo. Emulator research overlay, never an updater image.
#include "compressed_audio.hpp"
#include "layout.hpp"
void* operator new(size_t,void* p) noexcept { return p; }
using namespace mighty_loop;
extern "C" {
struct LinkStatus { uint32_t magic,schema,ready,callbacks,faults,model_crc,
    generation,runs,timer_max,running,context_rejections,last_output_bits; };
extern volatile LinkStatus mpp_link;
void mpp_listen_reset();
}
namespace {
alignas(CompressedAudio) uint8_t object[sizeof(CompressedAudio)];
CompressedAudio* audio;
Controls control;
float recorded_raw[8],recorded_guitar[8],bus[8];
bool guitar_ready=false;
float headphone_gain=0;
unsigned reads=0,read_bytes=0,blocked_writes=0;
// Volatile AHB loads avoid the IP-command FIFO and its IRQ-masked transaction.
// No flash programming/erase is allowed while a loop exists. Flash bus stalls,
// cache policy and exception entry latency still require physical verification.
bool bank_bounds(uint32_t address,unsigned n) {
    return n && ((address>=0x30384000 && address<0x303a0000 && n<=0x303a0000-address) ||
        (address>=0x303a4000 && address<0x303a6000 && n<=0x303a6000-address));
}
}
extern "C" {
void mpp_loop_init() {
    control=Controls{};
    audio=new(object) CompressedAudio(reinterpret_cast<uint8_t*>(layout::first),layout::first_bytes,
                                     reinterpret_cast<uint8_t*>(layout::second),layout::second_bytes);
    guitar_ready=false;headphone_gain=0;reads=read_bytes=blocked_writes=0;
    for(unsigned i=0;i<8;++i)recorded_raw[i]=recorded_guitar[i]=bus[i]=0;
}
unsigned mpp_loop_state(unsigned key) {
    switch(key) {
        case 0:return audio->store.length;
        case 1:return audio->store.cursor;
        case 2:return audio->played_frames;
        case 3:return unsigned(control.loop);
        case 4:return reads;
        case 5:return read_bytes;
        case 6:return blocked_writes;
        case 7:return sizeof(CompressedAudio);
        case 8:return audio->store.failed;
    }return 0;
}
void mpp_loop_command(unsigned cmd) {
    if(cmd==0){control.power_double();control.preset_tap();}
    if(cmd==1)control.preset_tap();
    if(cmd==2)control.power_single();
    if(cmd==3)control.power_double();
}
// Test fixture only: the harness separately validates/preloads the recording.
void mpp_loop_fixture(unsigned samples) {
    if(samples>720000)return;
    audio->store.length=samples;control.frames=samples*2;
    control.loop=Loop::playing;control.mode=Mode::presets;audio->reset_playback();
    headphone_gain=*reinterpret_cast<volatile float*>(0x200006f8);
}
void mpp_loop_fixture_block(unsigned frame) {
    if(frame>=audio->store.length || frame%256)return;
    audio->store.cursor=frame;audio->store.decoder={};audio->play_phase=0;audio->playback_filter.reset();
}
void mpp_loop_capture(const int32_t* rx,const float* left,const float* right,unsigned ready) {
    for(unsigned i=0;i<8;++i) {
        recorded_raw[i]=float(rx[4*i+3])*0x1p-31f;
        recorded_guitar[i]=(left[i]+right[i])*.5f;
    }
    guitar_ready=ready;
}
void mpp_loop_tick() {
    if(!audio)return;
    for(unsigned i=0;i<8;++i) {
        float l=0,r=0;
        bool playback=control.loop==Loop::playing;
        audio->frame(control,recorded_raw[i],playback?0:recorded_guitar[i],
                     playback?false:guitar_ready,0,0,l,r);
        bus[i]=playback?l:0;
    }
    guitar_ready=false;
}
void mpp_loop_render(int32_t* tx) {
    if(!audio || audio->store.failed || mpp_link.faults)return;
    // Read the same volume lookup/target used by V3 stock 0x653c. Maintain a
    // separate smoother so guitar suspension does not freeze headphone volume.
    auto* settings=*reinterpret_cast<volatile uint8_t**>(0x20014970);
    const uintptr_t address=reinterpret_cast<uintptr_t>(settings);
    if(address<0x20000000 || address>0x2003ffe0)return;
    unsigned volume=settings[0x16];if(volume>100)volume=50;
    auto* levels=reinterpret_cast<volatile float*>(0x200006f8);
    float target=settings[0x10]?0:levels[4+volume]*levels[105];
    if(!__builtin_isfinite(target) || target<0 || target>16)target=0;
    constexpr float smoothing=.999f; // loop-only 20.8 ms time constant
    for(unsigned i=0;i<8;++i) {
        headphone_gain=target*(1-smoothing)+headphone_gain*smoothing;
        float add=bus[i]*headphone_gain*0x1p28f;
        for(unsigned ch=0;ch<2;++ch) {
            float value=float(tx[4*i+ch])+add;
            value=__builtin_isfinite(value)?value:0;
            if(value>0x1.cp30f)value=0x1.cp30f;
            if(value<-0x1.cp30f)value=-0x1.cp30f;
            tx[4*i+ch]=tx[4*i+ch+2]=int32_t(value);
        }
    }
}
bool mpp_loop_read(void*,uint32_t address,uint8_t* destination,unsigned n) {
    if(!bank_bounds(address,n)||!destination)return false;
    auto* source=reinterpret_cast<const volatile uint8_t*>(address);
    // Interrupts remain enabled through copying, CRC validation and model load.
    for(unsigned i=0;i<n;++i)destination[i]=source[i];
    ++reads;read_bytes+=n;return true;
}
void mpp_loop_bank_pause() {
    mpp_link.running=0;__asm__ volatile("dmb":::"memory");
    mpp_listen_reset();guitar_ready=false;
    // Do not clear either DMA half: the next IRQ publishes the loop normally.
}
// Research overlay deliberately rejects all flash mutation. It is tested on
// an emulated bank seeded before installation; there is no hardware writer.
bool mpp_loop_no_erase(void*,uint32_t) { ++blocked_writes;return false; }
bool mpp_loop_no_program(void*,uint32_t,const uint8_t*,unsigned) { ++blocked_writes;return false; }
}
