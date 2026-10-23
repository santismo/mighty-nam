# Standalone looper research

Status: **button model and PCM audio transport tested offline; no hardware looper is released**.
The audio prototype uses caller-owned host memory. No device RAM address or physical button hooks are assigned.

## Requested controls

| Context | Gesture | Result |
| --- | --- | --- |
| Normal preset controls, no loop | Double-tap POWER | Enter looper controls |
| Looper controls, empty | Tap PRESET | Arm threshold recording |
| Armed | Play above threshold | Start recording |
| Recording | Tap PRESET | Close the loop and repeat it |
| Loop exists | Tap POWER once | Switch between preset and looper controls; preserve playback/pause state |
| Normal preset controls | Tap PRESET | Change guitar preset while the loop keeps its state |
| Looper controls, playing | Tap PRESET | Pause the loop |
| Looper controls, paused or stopped | Tap PRESET | Resume the loop |
| Looper controls or loop exists | Double-tap POWER | Stop the loop and exit looper controls |
| Normal preset controls | Hold PRESET | Reverse preset-cycling direction; release does not change preset |
| Any runtime mode | Hold POWER | Request normal shutdown |

The model retains a stopped recording so it can be resumed by returning with one
POWER tap. Choosing how to replace/clear that recording is still an integration
step; overdubbing and permanent loop storage are not implemented. If POWER is
single-tapped during recording, the prototype closes the loop and returns to preset
controls. Leaving while armed cancels arming. Tapping PRESET while armed also cancels.

Provisional timings: 25 ms debounce, 300 ms double-tap window, 800 ms PRESET hold and
2 seconds POWER hold. A single POWER action waits for the double-tap window; this
delay concerns the controls, not the live guitar signal. The first tap must not
invoke the stock mute action. A standalone POWER tap with no loop is a no-op in
this model. Buttons held at boot are ignored until released; stock startup's
PRESET+POWER updater gesture remains outside the runtime model.

[controls.hpp](../tools/looper-prototype/controls.hpp) uses 60 host bytes without
allocation. The sanitizer-enabled tests exercise the full record/play/change-preset/
return/pause/resume/stop sequence, 1,792 occupied-color/direction cases, contact
bounce, long holds, time-counter wrap, boot-held buttons, threshold rejection and
recording-capacity boundaries. See [evidence](../evidence/looper-prototype/).

```sh
clang++ -std=c++17 -O1 -fsanitize=address,undefined -Wall -Wextra -Werror \
  tools/looper-prototype/test.cpp -o /tmp/mighty-loop-controls
/tmp/mighty-loop-controls
```

## Firmware integration findings

A bounded inspection of the exact V3.0.5 Original payload identifies the stock
button action dispatcher at `0xa05e`, called through the runtime wrapper at `0xa19a`.
The forward preset-selection span at `0xa102..0xa144` uses the occupied-color mask,
updates the selected slot and publishes it on both controller paths. Its behavior
is exercised by the existing emulated preset tests. The flag-handling span around
`0xa17e..0xa196` toggles the runtime mute field; a new POWER recognizer must consume
that action before its first tap changes playback. Raw pin polarity, hold timing,
shutdown interaction and LED feedback still need exact hook-level verification.
These are code observations, not proof that the new gestures work on the plug.

Record processed guitar **before** Bluetooth/USB backing playback and headphone
volume, then mix loop playback **after** the current live-guitar effects. This lets
a new preset change the live guitar without reprocessing the recorded sound.

However, current preset recall calls `mpp_bank_pause`, resets output state and loads
a capture with interrupts masked during flash reads. Some graph changes also use
1,200 eight-frame settling callbacks (200 ms). A looper cannot simply share that
pause/reset path: its playback clock and mixer must survive guitar-graph reloads,
and flash access must be bounded or made interrupt-friendly. Saving/erasing flash
while looping needs a separate policy and test; offline button tests do not solve it.

## Memory budget

The wah prototype leaves only **644 bytes** in the currently audited custom-state
window. Nominal [RT1170 RAM capacity](https://www.nxp.com/products/i.MX-RT1170) is not
free RAM: stock DSP, DMA, USB/Bluetooth and presets already own regions. No large
loop buffer is yet proven safe, and no external memory is assumed.

At 48 kHz, mono PCM16 requires 96,000 bytes/second:

| Dedicated buffer | PCM16 mono | PCM16 stereo | 4-bit mono ADPCM, before block overhead |
| --- | ---: | ---: | ---: |
| 256 KiB | 2.73 s | 1.37 s | 10.92 s |
| 512 KiB | 5.46 s | 2.73 s | 21.85 s |
| 1 MiB | 10.92 s | 5.46 s | 43.69 s |

These are arithmetic examples, **not available recording durations**. Thirty seconds
of uncompressed mono PCM16 alone needs 2.88 MB. A practical longer loop may need a
verified reclaimed region plus compression, or other storage; streaming recordings
to program flash is not assumed safe. Compression quality and overdub headroom remain open. The second host prototype below exercises pre-roll, a basic edge fade and pause/resume; hardware ownership remains unproven.

## PCM transport and preset changes (second prototype)

`tools/looper-prototype/audio.hpp` now records mono PCM16 post-effects guitar, independently of the live guitar graph. A 64-frame pre-roll retains the attack before the threshold crossing. Backing music and loop playback are excluded from recording. Playback is mixed after live guitar processing, so changing a preset does not reprocess the recording. Pause retains the cursor; stop returns it to the beginning while retaining the recording. An optional short edge fade preserves the recorded period.

ASan/UBSan tests pass at 8, 16 and 32 frames: 504,000 playback frames across 21 simulated preset reloads, each including 200 ms with the guitar path unavailable. They also cover threshold waiting, capacity truncation, tiny/zero buffers, nonfinite input, headroom, pre-roll order, pause/resume and stereo backing exclusion. Audio state is 168 bytes on the host, plus caller-supplied PCM storage; controls use 60 bytes. This is an architectural test, not actual ARM preset switching or a guarantee of uninterrupted hardware playback. A blocked DMA interrupt still stops the audio clock regardless of this separation.

## Bounded tail-RAM probe

The NAMLNK24 emulator probe marks `0x20314000..0x2031b000` (28,672 bytes) beyond copied code. The sentinel survives 66 stock type-loader cases, a rendered full chain, and save/recall. No CPU reads or writes were observed there during those tested runtime phases. Cold startup clears it from PC `0x35e6`, with LR `0x22659`; a looper must not promise power-off persistence from RAM.

This is **candidate space, not proven free RAM**: hardware DMA is modeled, loader coverage is bounded, and untested combinations can still own it. Even if reclaimed, it holds only 0.299 s of 48 kHz mono PCM16, or 1.195 s of 4-bit mono ADPCM before codec overhead. It cannot by itself support a useful multi-second loop. Next work is a larger RAM-ownership audit, compression quality/budget testing, and interrupt-friendly preset loads. No program-flash recording is enabled.

The new reports are [audio-v2.json](../evidence/looper-prototype/audio-v2.json), [controls-v2.json](../evidence/looper-prototype/controls-v2.json) and [memory-v2.json](../evidence/looper-prototype/memory-v2.json). Run `test_audio.cpp` with the same sanitizer flags as `test.cpp`; `scripts/probe_looper_memory.py` runs the bounded ARM memory audit. No audio device is opened.
