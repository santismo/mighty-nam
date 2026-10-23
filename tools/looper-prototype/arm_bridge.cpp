// MIT (c) 2026 santismo. Test entry points; NOT linked into shipped firmware.
#include "compressed_audio.hpp"
void* operator new(size_t,void* p) noexcept { return p; }
using namespace mighty_loop;
alignas(CompressedAudio) static uint8_t audio_memory[sizeof(CompressedAudio)];
static CompressedAudio* audio=nullptr;
static Controls control;
extern "C" {
void lp_init(uint8_t* memory,unsigned bytes,unsigned rate,unsigned frames) {
    control=Controls{};
    audio=new(audio_memory) CompressedAudio(memory,bytes,rate,frames);
}
void lp_command(unsigned command) {
    if(command==0) { control.power_double();control.preset_tap(); }
    if(command==1)control.preset_tap();
    if(command==2)control.power_single();
    if(command==3)control.power_double();
}
// Load only an already validated host fixture into the emulator component.
void lp_fixture_play(unsigned frames) {
    if(frames>audio->store.capacity)return;
    audio->store.length=frames;control.frames=frames*audio->ratio;
    control.loop=Loop::playing;control.mode=Mode::looper;audio->reset_playback();
}
void lp_fixture_block(unsigned frame) {
    if(frame>=audio->store.length || frame%AdpcmStore::block_samples)return;
    audio->store.cursor=frame;audio->store.decoder={};audio->play_phase=0;
    audio->playback_filter.reset();
}
unsigned lp_state(unsigned key) {
    switch(key) {
        case 0:return audio->store.length;
        case 1:return audio->store.cursor;
        case 2:return control.frames;
        case 3:return unsigned(control.mode);
        case 4:return unsigned(control.loop);
        case 5:return audio->played_frames;
        case 6:return audio->store.failed;
        case 7:return audio->ratio;
        case 8:return sizeof(CompressedAudio);
        case 9:return sizeof(Controls);
    }return 0;
}
void lp_process8(const float* raw,const float* guitar,float* output,unsigned ready) {
    for(unsigned i=0;i<8;++i)audio->frame(control,raw[i],guitar[i],ready,0,0,output[i],output[i+8]);
}
}
