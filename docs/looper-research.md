# Standalone looper research

Status: **30-second compressed recording/playback tested offline with A2 Lite at eight frames; no hardware looper is released**.
The prototype uses caller-owned memory. No physical RAM allocation or button hooks are assigned. See the [compressed prototype and RAM audit](#compressed-30-second-prototype) below.

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

This is **candidate space, not proven free RAM**: hardware DMA is modeled, loader coverage is bounded, and untested combinations can still own it. Even if reclaimed, it holds only 0.299 s of 48 kHz mono PCM16, or 1.195 s of 4-bit mono ADPCM before codec overhead. It cannot by itself support a useful multi-second loop. The larger audit below supersedes this narrow probe; interrupt-friendly preset loads remain unresolved. No program-flash recording is enabled.

The new reports are [audio-v2.json](../evidence/looper-prototype/audio-v2.json), [controls-v2.json](../evidence/looper-prototype/controls-v2.json) and [memory-v2.json](../evidence/looper-prototype/memory-v2.json). Run `test_audio.cpp` with the same sanitizer flags as `test.cpp`; `scripts/probe_looper_memory.py` runs the bounded ARM memory audit. No audio device is opened.

## Compressed 30-second prototype

The original MIT implementation in [`compressed_audio.hpp`](../tools/looper-prototype/compressed_audio.hpp) uses 4-bit IMA ADPCM: 256 encoded samples and a four-byte predictor/index header per block. This is an internal storage format, not a WAV or RTP file. Codec behavior is checked against CPython's independent `audioop` implementation. The [IMA/DVI description in RFC 3551](https://www.rfc-editor.org/rfc/rfc3551.html#section-4.5.1) is a specification reference; no third-party codec source is bundled.

| Thirty-second mono loop | Encoded recording | Recording plus ARM audio/control objects |
| --- | ---: | ---: |
| 48 kHz ADPCM | 742,500 bytes | 743,272 bytes |
| 24 kHz ADPCM | 371,316 bytes | 372,088 bytes |

These totals exclude code, stack, alignment, command queues and any DMA buffers. Live guitar/NAM stays at **48 kHz, eight frames** for both formats. Only the recorded loop is reduced to 24 kHz. Its capture and reconstruction filters have 62 frames of combined group delay at 48 kHz (about 1.29 ms); they do not queue the live guitar path. The 63-tap filters attenuate frequencies above 12 kHz by at least 75 dB in the offline response test. A lower loop sample rate trades recorded bandwidth/quality for capacity; it is not a change to guitar or converter latency.

The recorder waits for raw guitar to cross the threshold, retains up to 64 stored-rate samples before the trigger, records processed guitar, then loops independently of the active preset. The mixer adds loop playback after live guitar processing. Backing audio is excluded from recording. Pause retains the cursor and decoder/filter state; stop rewinds while retaining the recording. Capacity closes the loop automatically. Buffers and state have fixed bounds and no heap allocation in the component.

### Tests completed

- ASan/UBSan: both full 30-second formats recorded through the actual portable A2 Lite implementation, followed by 60 seconds of playback. Three licensed public captures are reloaded 17 times across recording/playback. Eight-frame callbacks, 200 ms guitar-only settling intervals, independent sequential playback checks, immutable recording hashes, capacity limits, tiny buffers, pre-roll, malformed headers, nonfinite input, backing exclusion and pause/resume/stop pass.
- Independent codec validation: all encoded bytes match CPython on 131,071 stress samples and both full-duration recordings. The synthetic guitar-like NAM fixture measures 42.76 dB signal-to-error ratio at 48 kHz and 28.02 dB at 24 kHz against each format's PCM input. These are **fixture results, not listening-quality claims**. Arbitrary loop endpoints can still click; wrap smoothing and overdubbing are not implemented.
- Bounded ARM execution: 5,622 loop callbacks match the native output exactly, including first/last blocks of a full 720,000-sample recording, wrap, pause/resume and four real stock preset recalls. The firmware executes actual NAM and stock spring reverb. Loop state/storage survive those recalls in **artificial emulator RAM**. The loop is called separately after the stock IRQ; this is not a firmware audio hook or proof that playback continues during a blocked IRQ.

The ARM component uses 712 bytes of audio state plus 60 bytes of controls, excluding storage, stack and the test bridge pointer. Executed instruction counts are included in the report to identify work, not to assert real-time performance. The emulator does not model M7 cycles, cache misses or peripheral contention. A physical deadline measurement is still required, particularly on the threshold callback that encodes pre-roll.

### Expanded RAM audit

The audit uses the exact NAMLNK24 ELF (`13e14ec6…26e65d`) and V3.0.5-derived payload, 66 stock type-loader cases, representative spring/delay/full chains, public model transfers and four actual preset recalls. Runtime CPU reads/writes are observed in 256-byte pages:

| Observed region, end exclusive | Pages touched, rounded bytes | Largest unobserved span within that region |
| --- | ---: | ---: |
| `0x20200000..0x20240000` — M4 RAM alias / stock DSP | 249,088 | 7,936 |
| `0x20240000..0x202c0000` — OCRAM1 | 376,832 | 147,456 |
| `0x202c0000..0x202e4000` — below custom arena | 0 | 147,456 |
| `0x20314000..0x20340000` — beyond copied code | 0 | 180,224 |

The two adjacent middle spans could form a **294,912-byte investigation range**, still smaller than a 24 kHz recording. Combining that range with part of the upper span would fit the arithmetic budget, but would require segmented storage or a verified memory-layout change. **Unobserved means unobserved, not available.** Stock literal references include `0x2031b000`; their reachable uses need resolution. Cold startup clears `0x202e4000..0x2031c000`. DMA, USB/Bluetooth concurrency, long-running effects, other cores, MPU/cache settings and configured RAM aliases are not fully covered. DTCM/ITCM and configuration-dependent ECC/FlexRAM banks are not counted as additional free storage. [NXP's memory-allocation note](https://www.nxp.com/docs/en/application-note/AN13106.pdf) explains why nominal chip capacity alone is insufficient.

The audited custom-state area has only **644 bytes spare**. Its largest existing objects are the 84,024-byte NAM state, 33,120-byte FX engines, 16,404-byte receiver and three 8,192-byte preset/model scratch buffers. They have active owners; this prototype does not reuse them or disable effects. Even the loop's small control/audio objects need a separately justified allocation. The emulator component's code also needs a real linker placement; its artificial addresses are deliberately unsuitable for installation.

Every observed recall performs **two 8,192-byte flash reads with interrupts masked**. The emulator substitutes those peripheral transfers and cannot measure their duration. Separating the loop's state from NAM prevents reset damage, but does not make a masked audio interrupt run. Continuous hardware playback needs a verified interrupt-friendly read path, preload strategy or bounded scheduling design; flash writes/erases while looping need their own policy.

### Before a hardware trial

1. Prove ownership and initialization of enough RAM, including bus masters and cache policy; implement any required segmented allocator.
2. Keep the loop mixer/clock alive through guitar resets and preset reads; verify deadlines for recording, playback, threshold pre-roll and all supported effect combinations at eight frames.
3. Integrate debounced physical gestures, a bounded command mailbox, output placement and LED/controller feedback. Add loop-clear behavior and evaluate seam/quality handling.

The original and compressed prototypes remain outside the firmware build, public builder, Mac app and phone controller. No update file was produced, no physical device was accessed and no audio device was opened. Reproduction commands are in the [prototype README](../tools/looper-prototype/README.md); sanitized reports are in [evidence/looper-prototype](../evidence/looper-prototype/).
