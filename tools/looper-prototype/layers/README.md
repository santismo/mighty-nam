# NAMLNK27 looper refinements

The owner tested NAMLNK26 recording/playback from the phone, but reported scratchy
second layers in 30-second mode and missed physical PRESET finishes after phone
arming. NAMLNK27 addresses both paths and adds live input metering. Offline checks
pass; the new candidate still needs a physical button and listening trial.
The public builder remains NAMLNK23 r2. No stock-derived image or personal capture
is published with these sources. A personal local image can retain a separately
validated three-preset bank.

## Changes from NAMLNK26

The overwritten ADPCM encoder now carries its state between adjacent blocks
instead of restarting from each quiet original block. A quiet-first-layer / louder
second-layer numerical comparison improves SNR from 16.98 to 42.92 dB, with
block-start RMS error falling from 2108.16 to 27.70 integer sample units. Recording
uses 12 dB of internal storage headroom and compensates on playback. This is
synthetic evidence, not a claim that every overdub will be artifact-free.

The stock scanner already debounces physical buttons. The new adapter avoids a
second 25 ms filter that could discard a short tap. A 12 ms regression fails on
the prior image and passes on this one. An active recording also takes priority
when PRESET is released, including after changing control mode. Hold-to-clear and
stock volume/shutdown remain covered. These cases may explain the reported missed
press; the user's exact hardware gesture remains to be checked.

## Controls

Phone controller **0.8.8 → Looper** provides Arm, Finish/Pause/Play, Overdub/Finish
layer, Stop, Clear, threshold (−60 to −12 dBFS), loop level (0–100%), length and
hardware control mode. Opening or closing the panel does not stop the loop or
change guitar output. Preset colors remain selectable while looping or layering.
Mac **0.5.8 → Looper** provides the same transport/settings. Close its panel to
select another preset; closing does not stop or mute the loop. Both controllers
show the recent raw guitar peak directly on the threshold slider on NAMLNK27.
Controller 0.8.8 keeps meter polling visually steady and displays the current
physical button mode plus Forward/Reverse preset order. The mode button names
the mode it will switch to.
The white marker selects the threshold; the bar is blue below it and green when
it is reached. The meter remains visible before arming and uses a short peak
decay so plucked notes are readable. Older firmware cannot supply this reading.

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

Overdub is an explicit controller action. Play the existing loop, tap **Overdub**, choose
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
and numerical overdub-quality gates; malformed or stale evidence is rejected before a container is created.

Before using layers on hardware, verify RAM guards, worst-case whole IRQ timing,
60-second sound quality, preset transitions and real POWER/PRESET gestures. Building and packaging never contact the plug; installation is a separate manual step.

## Protocol extension

NAMLNK27 adds read-only compact status `op 0, arg 6`. Word 5 packs the command
error in bits 0–7 and a raw input peak (0–65535) in bits 8–23. Bits 24–31 must
be zero. Schema 3 identifies this layout; `arg 5` retains its old layout.
The peak is updated by the existing audio callback, with no extra audio buffer.
Controllers poll this compact packet about every 125 ms plus transport time
while visible; closing/backgrounding stops polling without affecting playback.


NO version 1 remains length/nonce/argument validated; NAMLNK25 retains its original
commands. NAMLNK26 adds compact status (`op 0, arg 5`), transport arguments 6–10
(overdub, play, pause, enter looper, leave to presets), threshold (`op 2`), level
(`op 3`) and 30/60-second selection (`op 4`). Acceptance returns a sequence number.
The audio IRQ applies the operation; controllers poll until that sequence is
applied with no pending command. A lost mutation acknowledgement is not retried
automatically. Invalid requests cannot reach stock commands or flash operations.
