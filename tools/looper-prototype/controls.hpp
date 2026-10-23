// MIT (c) 2026 santismo. Offline control prototype; no GPIO or audio I/O.
#pragma once
#include <stdint.h>

namespace mighty_loop {
enum class Mode : uint8_t { presets, looper };
enum class Loop : uint8_t { empty, armed, recording, playing, paused, stopped };
enum Event : uint32_t {
    select_preset=1, direction_changed=2, view_changed=4, arm=8,
    start_record=16, finish_record=32, play=64, pause=128, stop=256,
    cancel_arm=512, request_shutdown=1024, clear_loop=2048
};
struct Button {
    bool candidate=false, stable=false, released=false, held=false;
    uint32_t changed=0, down=0;
};
struct Controls {
    static constexpr uint32_t debounce_ms=25, double_ms=300;
    static constexpr uint32_t preset_hold_ms=800, power_hold_ms=2000;
    Mode mode=Mode::presets;
    Loop loop=Loop::empty;
    int direction=1;
    uint8_t occupied=7, color=0;
    uint32_t frames=0, capacity=48000, events=0;
    float threshold=.01f; // -40 dBFS starting point, not a calibrated guitar level.
    Button preset{}, power{};
    bool pending_power=false, second_power=false;
    uint32_t first_power_up=0;

    static uint32_t elapsed(uint32_t now,uint32_t then) { return now-then; }
    bool has_loop() const { return frames && loop!=Loop::recording; }
    uint32_t take_events() { auto value=events; events=0; return value; }
    void clear() { frames=0;loop=Loop::empty;events|=clear_loop; }
    // Presentation only. The runtime GPIO/LED adapter must preserve preset color.
    bool preset_led_on(uint32_t now) const {
        return loop!=Loop::armed || (now%500)<250;
    }
    void advance_preset() {
        for(int i=1;i<=7;++i) {
            unsigned next=(int(color)+7+direction*i)%7;
            if(occupied & (1u<<next)) {
                if(next!=color) { color=uint8_t(next); events|=select_preset; }
                return;
            }
        }
    }
    void finish() {
        if(loop!=Loop::recording)return;
        loop=frames ? Loop::playing : Loop::empty;
        events|=finish_record;
        if(frames)events|=play;
    }
    void preset_tap() {
        // A recording always owns PRESET, including one started remotely.
        if(loop==Loop::recording){finish();return;}
        if(mode==Mode::presets) { advance_preset(); return; }
        switch(loop) {
            case Loop::empty: frames=0; loop=Loop::armed; events|=arm; break;
            case Loop::armed: loop=Loop::empty; events|=cancel_arm; break;
            case Loop::recording: finish(); break;
            case Loop::playing: loop=Loop::paused; events|=pause; break;
            case Loop::paused: case Loop::stopped: loop=Loop::playing; events|=play; break;
        }
    }
    void power_single() {
        if(mode==Mode::looper) {
            // Leaving while recording closes the loop; leaving armed cancels it.
            finish();
            if(loop==Loop::armed) { loop=Loop::empty; events|=cancel_arm; }
            mode=Mode::presets; events|=view_changed;
        } else if(has_loop()) { mode=Mode::looper; events|=view_changed; }
        // An isolated POWER tap without a loop does not request a mute.
    }
    void power_double() {
        if(mode==Mode::looper || has_loop() || loop==Loop::recording) {
            if(loop==Loop::recording || loop==Loop::armed)frames=0;
            loop=frames ? Loop::stopped : Loop::empty;
            mode=Mode::presets; events|=stop|view_changed;
        } else { mode=Mode::looper; events|=view_changed; }
    }
    void begin_record(uint32_t pre_frames=0) {
        if(loop!=Loop::armed || !capacity)return;
        loop=Loop::recording; frames=pre_frames<capacity ? pre_frames : capacity;
        events|=start_record;
        if(frames==capacity)finish();
    }
    // The offline audio prototype supplies peak/frame counts. Storage and mixing
    // live outside this button state, so changing a preset cannot reset a loop.
    void audio(float peak,uint32_t count) {
        if(loop==Loop::armed && __builtin_isfinite(peak) && peak>=threshold && count && capacity) {
            begin_record();
        }
        if(loop==Loop::recording) {
            uint32_t room=capacity-frames;
            frames += count<room ? count : room;
            if(frames==capacity)finish();
        }
    }
    void edge(bool is_power,bool pressed,uint32_t now) {
        Button& b=is_power ? power : preset;
        if(pressed) {
            b.down=now; b.held=false;
            if(is_power && pending_power && elapsed(now,first_power_up)<=double_ms) {
                pending_power=false; second_power=true;
            }
        } else if(!b.held) {
            if(!is_power)preset_tap();
            else if(second_power) { second_power=false; power_double(); }
            else { pending_power=true; first_power_up=now; }
        }
    }
    void sample_button(Button& b,bool raw,bool is_power,uint32_t now) {
        if(raw!=b.candidate) { b.candidate=raw; b.changed=now; }
        if(elapsed(now,b.changed)>=debounce_ms) {
            // Ignore buttons held at boot until a clean release. Updater mode
            // is decided earlier by stock startup and is not part of this code.
            if(!b.released) { b.stable=raw; if(!raw)b.released=true; }
            else if(b.stable!=raw) { b.stable=raw; edge(is_power,raw,now); }
        }
        uint32_t hold=is_power ? power_hold_ms : preset_hold_ms;
        if(b.released && b.stable && !b.held && elapsed(now,b.down)>=hold) {
            b.held=true;
            if(is_power) { pending_power=second_power=false; events|=request_shutdown; }
            else if(mode==Mode::presets) { direction=-direction; events|=direction_changed; }
            else clear(); // One press-and-hold; release must not arm a new loop.
        }
    }
    void update(uint32_t now,bool preset_down,bool power_down) {
        sample_button(preset,preset_down,false,now);
        sample_button(power,power_down,true,now);
        if(pending_power && elapsed(now,first_power_up)>double_ms) {
            pending_power=false; power_single();
        }
    }
    // Hardware levels are already debounced by the stock four-sample scanner.
    // Do not discard short taps with a second 25 ms debounce window.
    void update_debounced(uint32_t now,bool preset_down,bool power_down) {
        if(preset_down!=preset.candidate){preset.candidate=preset_down;preset.changed=now-debounce_ms;}
        if(power_down!=power.candidate){power.candidate=power_down;power.changed=now-debounce_ms;}
        update(now,preset_down,power_down);
    }
};
} // namespace mighty_loop
