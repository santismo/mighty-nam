// MIT (c) 2026 santismo. Fixed-pool independent ADPCM lanes and one edit undo.
#pragma once
#include "../layers/overdub_store.hpp"
namespace mighty_loop {
struct TakeStore : AdpcmStore {
    static constexpr unsigned tracks=4;
    struct Track {
        OverdubStore audio{nullptr,0,0};
        unsigned region=0,level=100,peak=0;
        float gain=1.f;
        bool present=false,muted=false;
    } take[tracks],backup{};
    unsigned recording=0,preparing=0,copy_position=0,undo_lane=0,undo_kind=0;
    unsigned generation=0,commits=0,swap_pending=0;
    bool undone=false,dirty=false;
    using AdpcmStore::AdpcmStore;
    unsigned blocks() const {return unsigned(required(length)/block_bytes);}
    unsigned slots() const {
        unsigned n=blocks();if(!n)return 0;
        unsigned count=unsigned(bytes/block_bytes)/n;
        return count<5?count:5; // Base + three lanes + one temporary undo copy.
    }
    bool used(unsigned region,bool history=true) const {
        if(!region)return true;
        for(unsigned i=1;i<tracks;++i)if(take[i].region==region &&
            (take[i].present || preparing==i || (history&&undone&&undo_kind==1&&undo_lane==i)))return true;
        return history && backup.region==region;
    }
    unsigned free_region(bool history=true) const {
        for(unsigned i=1;i<slots();++i)if(!used(i,history))return i;return 0;
    }
    unsigned free_takes() const {
        unsigned n=0,logical=0;
        for(unsigned i=1;i<slots();++i)if(!used(i,false))++n;
        for(unsigned i=1;i<tracks;++i)if(!take[i].present && i!=preparing)++logical;
        return n<logical?n:logical;
    }
    void discard_history() {
        if(undone && undo_kind==1)take[undo_lane]=Track{};
        backup=Track{};undo_lane=undo_kind=0;undone=false;
    }
    Track view(unsigned region) {
        Track t{};t.region=region;unsigned offset=region*blocks(),count=blocks();
        auto* p=block(offset*block_samples);
        if(offset<first_blocks && offset+count>first_blocks)
            t.audio=OverdubStore(p,(first_blocks-offset)*block_bytes,second,(offset+count-first_blocks)*block_bytes,length);
        else t.audio=OverdubStore(p,count*block_bytes,length);
        t.audio.length=length;return t;
    }
    void clear() {
        AdpcmStore::clear();for(auto& t:take)t=Track{};backup=Track{};
        recording=preparing=copy_position=undo_lane=undo_kind=commits=swap_pending=0;
        undone=dirty=false;++generation;
    }
    bool append(int16_t sample) {
        bool ok=AdpcmStore::append(sample);if(ok)take[0].present=true;return ok;
    }
    bool begin_take(unsigned lane=0) {
        if(!length || failed || recording || preparing || swap_pending)return false;
        if(lane>=tracks || (lane && !take[lane].present))return false;
        unsigned region=free_region(false);if(!region)return false;
        if(!lane){
            for(unsigned i=1;i<tracks;++i)if(!take[i].present){lane=i;break;}
            if(!lane)return false;
            discard_history();take[lane]=view(region);undo_kind=1;
        }else {discard_history();backup=view(region);undo_kind=2;}
        undo_lane=lane;preparing=lane;copy_position=0;++generation;return true;
    }
    void finish_take() {
        if(preparing){
            if(undo_kind==1)take[preparing]=Track{};
            preparing=0;discard_history();++generation;
        }
        if(recording){recording=0;++commits;++generation;}
    }
    bool undo() {
        if(preparing){finish_take();return true;}
        if(!undo_kind || undone || swap_pending)return false;
        finish_take();swap_pending=1;return true;
    }
    bool redo() {
        if(!undo_kind || !undone || recording || preparing || swap_pending)return false;
        swap_pending=2;return true;
    }
    bool erase_take(unsigned i) {
        if(!i || i>=tracks || (!take[i].present && preparing!=i))return false;
        if(recording==i)recording=0;
        if(preparing==i)preparing=0;
        if(undo_lane==i){discard_history();swap_pending=0;}
        take[i]=Track{};++generation;return true;
    }
    bool level(unsigned i,unsigned v) {
        if(i>=tracks || v>100 || !take[i].present)return false;take[i].level=v;return true;
    }
    bool mute(unsigned i,bool v) {
        if(i>=tracks || !take[i].present)return false;take[i].muted=v;return true;
    }
    void apply_swap(unsigned now) {
        if(!swap_pending || now%block_samples)return;
        auto& t=take[undo_lane];
        if(undo_kind==1)t.present=swap_pending==2;
        else {
            unsigned level=t.level;bool muted=t.muted;float gain=t.gain;
            Track temp=t;t=backup;backup=temp;
            t.level=level;t.muted=muted;t.gain=gain;t.present=true;
        }
        t.audio.rewind_ready();t.audio.cursor=now;t.audio.cached=false;t.audio.dirty=false;
        undone=swap_pending==1;swap_pending=0;++generation;
    }
    void maintenance(unsigned budget) {
        if(!preparing || dirty)return;
        auto& t=take[preparing];unsigned bytes_to_copy=blocks()*block_bytes;
        // Bounded copies while audio keeps running. No allocation or interrupt
        // masking. A redo buffer is retained only until the next edit begins.
        for(unsigned i=0;i<budget && copy_position<bytes_to_copy;++i,++copy_position){
            unsigned b=copy_position/block_bytes,offset=copy_position%block_bytes;
            auto* dst=(undo_kind==1?t.audio:backup.audio).block(b*block_samples);
            dst[offset]=undo_kind==1?0:t.audio.block(b*block_samples)[offset];
        }
        unsigned now=cursor==length?0:cursor;
        if(copy_position==bytes_to_copy && !(now%block_samples)){
            t.present=true;t.audio.rewind_ready();t.audio.cursor=now;
            recording=preparing;preparing=0;++generation;
        }
    }
    bool rewind_ready() {
        finish_take();for(auto& t:take)if(t.audio.dirty)return false;
        AdpcmStore::rewind();for(auto& t:take)t.audio.rewind_ready();
        apply_swap(0);return true;
    }
    void drain(unsigned budget) {
        dirty=false;for(unsigned i=1;i<tracks;++i){take[i].audio.drain(budget);dirty|=take[i].audio.dirty;}
        if(swap_pending && !dirty){AdpcmStore::rewind();for(auto& t:take)t.audio.rewind_ready();apply_swap(0);}
    }
    void decay() {for(auto& t:take)t.peak=t.peak*255/256;}
    int32_t mix(unsigned i,int16_t sample) {
        auto& t=take[i];float target=t.muted?0.f:float(t.level)*.01f;
        t.gain+=(target-t.gain)*.002f;int32_t value=int32_t(float(sample)*t.gain);
        unsigned peak=unsigned(value<0?-value:value);if(peak>t.peak)t.peak=peak;return value;
    }
    int32_t next_layer(int16_t addition,bool enabled) {
        if(failed || !length)return 0;
        if(!enabled && (recording || preparing))finish_take();
        maintenance(16);
        if(cursor>=length)AdpcmStore::rewind();unsigned now=cursor;
        apply_swap(now);int32_t result=mix(0,AdpcmStore::next());dirty=false;
        for(unsigned i=1;i<tracks;++i){auto& t=take[i];
            if(!t.present && !(undone&&undo_kind==1&&undo_lane==i))continue;
            if(i==preparing && undo_kind==1)continue;
            if(!now && t.audio.cursor!=0)t.audio.rewind_ready();
            if(t.audio.cursor!=now){failed=true;return 0;}
            int16_t sample=t.audio.next_layer(i==recording?addition:0,i==recording&&enabled);
            if(t.present)result+=mix(i,sample);else t.peak=0;
            dirty|=t.audio.dirty;failed|=t.audio.failed;
        }
        return result;
    }
    unsigned commit_count() const {unsigned n=commits;for(const auto& t:take)n+=t.audio.commits;return n;}
    void status(uint32_t* out) const {
        unsigned flags=0,levels=0;
        for(unsigned i=0;i<tracks;++i){const auto& t=take[i];
            flags|=unsigned(t.present)<<i;flags|=unsigned(t.muted)<<(4+i);levels|=t.level<<(7*i);
        }
        if(recording)flags|=1u<<(8+recording);
        if(undone && undo_kind==1)flags|=1u<<(12+undo_lane);
        if(preparing)flags|=preparing<<16;
        if(swap_pending)flags|=1u<<18;
        if(free_region(false))flags|=1u<<19;
        out[0]=flags;out[1]=levels;out[2]=take[0].peak|(take[1].peak<<16);out[3]=take[2].peak|(take[3].peak<<16);
        out[4]=free_takes();out[5]=(undo_kind&&!undone?undo_lane:0)|(undone?undo_lane<<8:0);
        out[6]=generation;out[7]=length;
    }
};
}
