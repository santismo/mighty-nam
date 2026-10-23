# NAMLNK26 looper layers trial

A local development candidate following the NAMLNK25 hardware trial. The owner
confirmed that a recorded loop kept its sound and continued through Green,
Orange and Red preset changes. That result does not establish the new overdub,
60-second mode or physical gestures on NAMLNK26; those require a new hardware test.
The public builder remains NAMLNK23 r2. No stock-derived image or personal capture
is published with these sources.

## Controls

Phone controller **0.8.6 → Looper** provides Arm, Finish/Pause/Play, Overdub/Finish
layer, Stop, Clear, threshold (−60 to −12 dBFS), loop level (0–100%), length and
hardware control mode. Opening or closing the panel does not stop the loop or
change guitar output. Preset colors remain selectable while looping or layering.
Mac **0.5.7** recognizes NAMLNK26 for existing guitar, model, effects and preset
controls; the new looper panel is on the phone controller.

- Double-tap POWER to enter looper mode when empty. PRESET arms threshold recording;
  playing guitar starts it, and another PRESET tap closes the loop and plays it.
- PRESET then pauses/resumes. Hold PRESET for about 0.8 seconds in looper mode to
  clear; releasing after a hold does not arm another recording.
- POWER once leaves looper mode so PRESET changes guitar presets. With a retained
  loop, POWER once returns to looper mode. Double POWER stops playback and exits;
  it retains the recording until Clear or power-off.
- Hold PRESET in preset mode to reverse preset direction. POWER hold retains the
  stock shutdown behavior. Stock volume buttons and bootloader entry are retained.
- The selected preset LED flashes at 2 Hz while armed. Recording/playback keep
  the preset color. These button/LED adapters have compiled offline coverage,
  not a physical gesture test yet.

Overdub is an explicit phone action. Play the existing loop, tap **Overdub**, choose
any saved preset, and play the new layer. **Finish layer** returns to playback.
Pause/Stop end the layer; they do not erase it. Layers are merged into mono ADPCM,
with no separate track editing or undo. Repeated encoding and clipping can degrade
layer quality; leave headroom. Loop level affects playback only, not the recorded
layer. Bluetooth music, USB backing and the loop itself are not recorded again.

## Duration and storage

| Choice | Stored loop | RAM | Live guitar |
| --- | --- | --- | --- |
| Default 30 seconds | Mono, 24 kHz IMA ADPCM | 371,316 bytes | 48 kHz / 8-frame callback |
| Optional 60 seconds | Mono, 12 kHz IMA ADPCM | Same | Same |

The 60-second option reduces loop bandwidth with two cascaded antialiasing stages;
it is a duration/quality tradeoff, not a higher-capacity RAM claim. Choose length
before arming. Clear before changing it. Settings and the recording are volatile;
power-off returns to an empty 30-second loop, −40 dB threshold, 50% loop level.
Loop playback currently goes to headphones, not the USB recording feed.

The two audited storage regions are unchanged. A transactional ADPCM block keeps
132 bytes of original data plus a 132-byte replacement. Playback consumes the
original while the replacement is encoded; the next loop pass hears the layer.
A partial block completes in bounded slices after Pause/Stop. Capture filters
are skipped during ordinary playback; inactive looping does not add a guitar
buffer. Code/state stay in the prior 16 KiB / 8 KiB reserved windows. Flash saves
remain blocked while armed or while a loop exists; Clear permits saving again.

## Offline checks and reproduction

Use the exact baseline and fixture setup in [hardware/README.md](../hardware/README.md).
All tests operate on numerical buffers or CPU emulation, with no audio stream,
USB device, mute command or updater access.

```sh
research-python tools/looper-prototype/layers/build_next.py BASE OUT/build
clang++ -std=c++17 -O2 -ffp-contract=off -dynamiclib \
  tools/looper-prototype/layers/native_bridge.cpp -o OUT/loop-native.dylib
research-python tools/looper-prototype/hardware/test_startup.py BASE PAYLOAD OUT FIXTURES/models
research-python tools/looper-prototype/hardware/test_audio.py BASE PAYLOAD OUT MODEL --reference
research-python tools/looper-prototype/hardware/test_audio.py BASE PAYLOAD OUT MODEL
research-python tools/looper-prototype/layers/test_arm.py BASE PAYLOAD OUT MODEL
research-python tools/looper-prototype/layers/test_buttons.py BASE PAYLOAD OUT MODEL
research-python tools/looper-prototype/layers/test_continuity.py BASE PAYLOAD FIXTURES OUT
research-python tools/looper-prototype/layers/run_native.py FIXTURES/models OUT/offline
```

The native duration test covers 30/60-second record, overdub and playback passes:
1,620,000 eight-frame callbacks and 52 A2 Lite model changes. The partial-block
oracle covers 3,484 cases. Compiled ARM checks cover command acceptance/application,
settings, guards, output publication, warm/cold startup, stock scanner/LED paths,
and cooperative IRQ preemption during actual preset recall. Instruction counts
and synthetic cycle fixtures are **not** physical M7 deadline measurements.
Packaging requires matching hashes and all startup/audio/continuity/layer/button
gates; malformed or stale evidence is rejected before a container is created.

Before using layers on hardware, verify RAM guards, worst-case whole IRQ timing,
60-second sound quality, preset transitions and real POWER/PRESET gestures. Building and packaging never contact the plug; installation is a separate manual step.

## Protocol extension

NO version 1 remains length/nonce/argument validated; NAMLNK25 retains its original
commands. NAMLNK26 adds compact status (`op 0, arg 5`), transport arguments 6–10
(overdub, play, pause, enter looper, leave to presets), threshold (`op 2`), level
(`op 3`) and 30/60-second selection (`op 4`). Acceptance returns a sequence number.
The audio IRQ applies the operation; controllers poll until that sequence is
applied with no pending command. A lost mutation acknowledgement is not retried
automatically. Invalid requests cannot reach stock commands or flash operations.
