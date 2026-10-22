# NAMLNK21: USB audio and NAM controls

NAMLNK21 is staged for testing, **not installed**. It restores the missing stock USB PCM exchange in the replacement audio callback and adds NAM input/output gain, bass, middle, treble and wet/dry mix. Mac 0.4.3 (18) and phone controller 0.7.3 expose these controls only on the matching firmware. Both capture detail browsers keep their view open after loading a capture. Mac Explore TONE3000 goes directly to the official site-style picker, which returns to the selected tone’s model details. Those details remain open after loading; Browse TONE3000 there can pick another tone without nesting more dialogs.

## Audio routing

The old callback did not call the stock PCM exchange at `0xccec`, which prevented Logic input and playback despite USB enumeration. The new callback services the existing stereo rings, stock recording gain/limiter (`0x1488c`), and playback gain/limiter (`0x14914`). An initialization guard avoids touching the USB class before its state pointer is ready.

The recording tap contains processed guitar, before headphone master volume. USB host playback is mixed into the headphone path after that tap, so it is not fed back into the recording stream. Both directions use the stock PCM layout and scaling. No descriptor, endpoint, clock, vector table, IRQ/DMA schedule or sample-rate change is included. The existing 8/16/32 output-buffer choices remain global. The uninstalled DMA deadline prototype is not included.

The implementation adds processing work but no new queued block. It does **not** establish a measured latency improvement or physical real-time safety margin. Real USB endpoint completion and Logic duplex audio must be checked after installation.

## NAM controls

| Control | Range | Stored byte | Neutral |
| --- | --- | --- | --- |
| Input gain | −24 to +24 dB, 0.5 dB steps | 27 | 48 |
| Bass | −12 to +12 dB | 28 | 12 |
| Middle | −12 to +12 dB | 29 | 12 |
| Treble | −12 to +12 dB | 30 | 12 |
| Mix | 0 to 100% | 31 | 100 |
| Output gain | −24 to +24 dB, 0.5 dB steps | 32 | 48 |

Retired AMP bytes 33/34 carry marker/version `78,1`; older presets without that marker decode to neutral controls. The order is input gain → NAM → broad tone controls → wet/dry blend → output gain. Dry audio is taken before NAM input gain and retains both channels. Tone bands use complementary first-order 150 Hz/3 kHz crossovers at 48 kHz; these are not an exact copy of the TONE3000 plugin EQ curves. Gains smooth between blocks. Neutral controls match the reference NAM output exactly in the compiled callback regression.

NG requests use `f0 43 58 70 04 02 4e 47 01`, get/set operations 0/1, an active-color selector and a nonzero 14-bit nonce. Writes include the expected model CRC and six bounded values. Replies echo the operation, selector and nonce, then error, active color and the six confirmed values. USB MIDI and BLE use the same bounded handler. Stale model/color writes are rejected. Controllers confirm readback; changes apply live and persist only with **Save to plug**. Moving a gain or tone control does not invoke the legacy 200 ms effect-settling window. Bypassing NAM removes its processing callback, including these controls, while retaining its tile and parameters. Remove is a separate UI action. Change block chooses an available engine at the same position and retains bypass state. The visible bypassed-tile list is stored locally in each controller, separately from firmware enable bits; it does not consume DSP time or add a queued block.

## Placement and staged image

The linked state occupies `0x202e4020..0x2030eca4`; copied code occupies `0x2030f000..0x20313894`, inside the previously audited retired-AMP RAM extent ending at `0x20314000`. Its flash source is `0x303a6000`, following global settings. The seven-color preset bank stays at `0x30384000..0x303a0000`. The build and stage tools check exact stock/source hashes and placement before producing a local file.

The private local candidate is `NAMLNK21-usb-audio-nam-controls-test.bin`, SHA-256 `f815628c96aca85221931089ff738c1100e01b7344b557219aafda9e430a0763`. It preloads all seven colors with the locally held **Fender Super Reverb 1965 – Edge of Breakup – A2** capture (its A2 Lite component, TONE3000 tone 88775) + Spring chain, neutral NAM controls, master volume 37, global buffer 8 and playback enabled after power-on. **Installing it replaces the current onboard presets.** No backup was requested or made. Stock binaries and capture weights are not committed or distributed by this repository.

## Validation and remaining hardware checks

[Offline evidence](../evidence/usb-nam21/arm.json) executes 1,652 compiled callbacks, the actual stock USB PCM rings and conversion routines, stereo class gain/mute behavior, recording without host-return loopback, NG read/write on both transports, rejected stale/invalid requests, seven independent saved control sets, warm/cold startup, and the stock preset-button branch. NAM+Spring neutral output has zero peak error against the independent C++ reference. Flash completion, USB endpoint completion and USB frame progression are modeled. Host DSP tests also pass address/undefined-behavior sanitizers and rapid parameter switching.

App/widget and controller protocol tests cover live writes, readback, save/recall, older-firmware compatibility, and capture selection without closing the browser. Browser checks use a simulated BLE device and a silent local fixture; they are not evidence of a physical phone transfer. No physical device access or host audio stream was used during this work. Nothing was flashed or auto-muted, and system/Teams audio was untouched.

After the user authorizes installation, verify normal startup, duplex Logic audio at 48 kHz, sustained callback timing with USB active, live NAM controls, preset persistence and headphone listening. Until those checks pass, describe USB audio as an offline-tested firmware repair, not confirmed working in Logic.
