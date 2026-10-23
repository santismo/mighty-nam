// MIT (c) 2026 santismo. Offline next-version prototype, no device access.
#pragma once
#include "../ima_adpcm.hpp"
namespace mighty_loop {
// One transactional ADPCM block. Playback consumes the original block while
// the replacement is encoded. A partially overdubbed block is completed with
// its original suffix before commit. No whole-loop copy or allocation occurs.
// A completed block is still read from the original during the current pass;
// on the following pass its replacement is heard. This avoids decoding a new
// suffix with the old predictor, including pause/stop in the middle of a block.
struct OverdubStore : AdpcmStore {
    using AdpcmStore::AdpcmStore;
    uint8_t original[block_bytes]{}, replacement[block_bytes]{};
    uint32_t begin=0,end=0,position=0,commits=0;
    Ima writer{}, tail{};
    bool cached=false, dirty=false;
    void clear() { AdpcmStore::clear();cached=dirty=false;commits=0; }
    bool rewind_ready() {
        if(dirty)return false;
        AdpcmStore::rewind();cached=false;return true;
    }
    unsigned code(const uint8_t* p,uint32_t frame) const {
        unsigned i=frame%block_samples,v=p[4+i/2];return i&1?v&15:v>>4;
    }
    __attribute__((noinline)) void write(int16_t sample) {
        unsigned i=position%block_samples,n=writer.encode(sample);
        auto& packed=replacement[4+i/2];
        packed=uint8_t(i&1?(packed&240)|n:(packed&15)|(n<<4));
        ++position;
        if(position==end) {
            auto* target=block(begin);
            for(unsigned j=0;j<block_bytes;++j)target[j]=replacement[j];
            dirty=false;++commits;
        }
    }
    // Used while paused/stopped, with an explicit small per-frame budget.
    __attribute__((noinline)) void drain(unsigned budget) {
        while(dirty && budget--)write(tail.decode(code(original,position)));
    }
    __attribute__((noinline)) int16_t next_layer(int16_t addition,bool overdub) {
        if(failed || !length)return 0;
        if(cursor>=length) {
            // Sequential playback finishes the final partial block itself.
            if(dirty){failed=true;return 0;}
            AdpcmStore::rewind();cached=false;
        }
        if(cached && (cursor<begin || cursor>=end)) {
            if(dirty){failed=true;return 0;}
            cached=false;
        }
        auto* source=cached?original:block(cursor);
        if(!(cursor%block_samples)) {
            if(source[2]>88 || source[3]){failed=true;return 0;}
            unsigned v=unsigned(source[0])|(unsigned(source[1])<<8);
            decoder.predictor=v>=32768?int(v)-65536:int(v);decoder.index=source[2];
        }
        if(overdub && addition && !cached) {
            begin=cursor-(cursor%block_samples);end=begin+block_samples;
            if(end>length)end=length;
            auto* base=block(begin);
            for(unsigned j=0;j<block_bytes;++j)original[j]=replacement[j]=base[j];
            position=cursor;writer=tail=decoder;cached=dirty=true;source=original;
        }
        int16_t sample=decoder.decode(code(source,cursor));
        if(dirty && position==cursor) {
            tail=decoder;
            int mixed=int(sample)+(overdub?int(addition):0);
            if(mixed>32767)mixed=32767;if(mixed<-32768)mixed=-32768;
            write(int16_t(mixed));
        }
        ++cursor;return sample;
    }
};
}
