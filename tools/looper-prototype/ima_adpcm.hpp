// MIT (c) 2026 santismo. Original offline IMA ADPCM implementation.
#pragma once
#include <stdint.h>
#include <stddef.h>

namespace mighty_loop {
struct Ima {
    int predictor=0, index=0;
    static constexpr int steps[89]={
        7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,
        66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,
        408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,
        1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,
        6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,
        20350,22385,24623,27086,29794,32767};
    static constexpr int change[8]={-1,-1,-1,-1,2,4,6,8};
    int16_t decode(unsigned nibble) {
        nibble &= 15;
        const int step=steps[index];
        int diff=step>>3;
        if(nibble&4)diff+=step;
        if(nibble&2)diff+=step>>1;
        if(nibble&1)diff+=step>>2;
        predictor+=(nibble&8)?-diff:diff;
        if(predictor>32767)predictor=32767;
        if(predictor<-32768)predictor=-32768;
        index+=change[nibble&7];
        if(index<0)index=0;
        if(index>88)index=88;
        return int16_t(predictor);
    }
    unsigned encode(int16_t sample) {
        int diff=int(sample)-predictor;
        unsigned nibble=diff<0?8:0;
        if(diff<0)diff=-diff;
        int step=steps[index];
        if(diff>=step){nibble|=4;diff-=step;}
        step>>=1;
        if(diff>=step){nibble|=2;diff-=step;}
        step>>=1;
        if(diff>=step)nibble|=1;
        decode(nibble);
        return nibble;
    }
};

// Internal format, not a WAV or RTP file. Each block begins with the state
// BEFORE its first sample: little-endian predictor, index, zero reserved byte.
// All 256 samples are coded, high nibble first; final length is held separately.
// Caller-owned, fixed capacity. Nothing here allocates or accesses a device.
struct AdpcmStore {
    static constexpr uint32_t block_samples=256, block_bytes=132;
    static constexpr uint32_t maximum_frames=48000*30;
    uint8_t* memory;
    size_t bytes;
    uint32_t capacity, length=0, cursor=0;
    Ima encoder{}, decoder{};
    bool failed=false;
    static constexpr size_t required(uint32_t frames) {
        return ((size_t(frames)+block_samples-1)/block_samples)*block_bytes;
    }
    AdpcmStore(uint8_t* p,size_t n,uint32_t frames):memory(p),bytes(n),
        capacity(p && frames<=maximum_frames && n>=required(frames)?frames:0) {}
    void clear() { length=cursor=0;encoder={};decoder={};failed=false; }
    void rewind() { cursor=0;decoder={}; }
    bool append(int16_t sample) {
        if(failed || length>=capacity)return false;
        const uint32_t within=length%block_samples;
        const size_t base=size_t(length/block_samples)*block_bytes;
        if(!within) {
            const uint16_t p=uint16_t(encoder.predictor);
            memory[base]=uint8_t(p);memory[base+1]=uint8_t(p>>8);
            memory[base+2]=uint8_t(encoder.index);memory[base+3]=0;
        }
        const unsigned nibble=encoder.encode(sample);
        uint8_t& packed=memory[base+4+within/2];
        if(within&1)packed=uint8_t(packed|nibble);
        else packed=uint8_t(nibble<<4);
        ++length;return true;
    }
    int16_t next() {
        if(failed || !length)return 0;
        if(cursor>=length)rewind();
        const uint32_t within=cursor%block_samples;
        const size_t base=size_t(cursor/block_samples)*block_bytes;
        if(!within) {
            if(memory[base+2]>88 || memory[base+3]) { failed=true;return 0; }
            const unsigned p=unsigned(memory[base])|(unsigned(memory[base+1])<<8);
            decoder.predictor=p>=32768?int(p)-65536:int(p);
            decoder.index=memory[base+2];
        }
        unsigned packed=memory[base+4+within/2];
        ++cursor;
        return decoder.decode((within&1)?packed&15:packed>>4);
    }
};
} // namespace mighty_loop
