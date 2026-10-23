# NAMLNK25 startup, RAM and timing trial

The follow-on [NAMLNK26 layers trial](../layers/README.md) adds phone controls,
merged overdubs, optional 60-second storage and physical button/LED adapters.
This page documents the earlier NAMLNK25 build.

This is a **local diagnostic build**, not a public firmware release or a finished
looper. Nothing in the offline build or tests opens a device or an audio stream.
The ordinary public builder still produces its existing version.

The test image starts the normal saved guitar preset with playback enabled. It
copies the loop code after the stock runtime clear and baseline initialization,
before SAI/DMA starts. It initializes the loop empty; it never starts recording
automatically. No new live-guitar buffer is introduced.

At startup, two address-dependent pattern passes fill and verify the two candidate
loop buffers, **371,316 bytes** total. Cache clean/invalidate precedes readback.
Code-copy checks, eight guard ranges, an incremental idle ownership scan and raw
IRQ cycle counters are reported separately. A detected looper fault disables only
the loop path; it does not change the guitar output enable setting.

The recording format remains 30 seconds of mono 24 kHz IMA ADPCM; live guitar and
the audio callbacks remain 48 kHz/eight frames. This is temporary RAM storage:
power-off loses the loop. Guitar is captured after its effects, before USB/backing
audio and headphone volume. Loop playback goes to the headphone mix; adding the
loop to USB recording is a separate integration step.

Preset recalls use the tested interruptible flash-read path. Saving flash is
allowed while no recording exists and rejected while armed/recording/playing/
paused/stopped. Stop retains the recording; explicit Clear permits saving again.
The existing physical PRESET button still selects presets. **The requested new
POWER/PRESET gestures and app looper UI are not installed by this trial.** Mac **0.5.6** and phone **0.8.5** recognize NAMLNK25 for existing guitar,
wah, preset and model controls. Looper commands remain in the diagnostic client;
these controller updates do not add a looper UI or install firmware.

## Offline reproduction

Use the pinned NAMLNK24 work directory and the research Python environment from
the [parent README](../README.md). First run the parent's `run_continuity.py` to
obtain the licensed full-length numeric fixture and native oracle. No audio is
played. In the commands below, `BASE` contains `generated/` and `build/`, `PAYLOAD`
is the decoded exact public V3.0.5 Original payload, `FIXTURES` is the parent's
`native/` output, and `OUT` is a new local work directory.

```sh
research-python tools/looper-prototype/hardware/build_test.py BASE OUT/build
clang++ -std=c++17 -O2 -ffp-contract=off -dynamiclib \
  tools/looper-prototype/arm_bridge.cpp -o OUT/loop-native.dylib
research-python tools/looper-prototype/hardware/test_startup.py BASE PAYLOAD OUT FIXTURES/models
research-python tools/looper-prototype/hardware/test_audio.py BASE PAYLOAD OUT FIXTURES/models/riffsmith-clean-lite.nam --reference
research-python tools/looper-prototype/hardware/test_audio.py BASE PAYLOAD OUT FIXTURES/models/riffsmith-clean-lite.nam
research-python tools/looper-prototype/hardware/test_continuity.py BASE PAYLOAD FIXTURES OUT
clang -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined \
  tools/looper-prototype/hardware/test_wire.c -o OUT/test-wire
OUT/test-wire
```

`image.py` composes the two pinned ELFs in memory and checks every modified span.
`stage.py` requires passing reports for that exact image and unchanged compiled
sources. It additionally requires the exact **MP3_OR_V3.0.5.bin**, a local preset
bank and its checksum report. It preserves the stock container headers/vector
table and embeds the supplied bank without rewriting it. `test_staging.py` checks
missing, stale and failed reports before invoking the same staging path. These
scripts do not download proprietary firmware or private models, operate an updater,
or publish a resulting binary.

## Later physical test

Build the MIDI-only Mac client (compilation does not connect to the plug):

```sh
clang -std=c11 -O2 -Wall -Wextra -Werror -Wno-unused-function \
  -framework CoreMIDI -framework CoreFoundation \
  tools/looper-prototype/hardware/client.c -o OUT/mighty-loop
```

The client accepts the known USB names `MIGHTY PLUG PRO USB` and `NUX NMP-03`,
requires one paired source/destination, and verifies NAMLNK25 before diagnostics.

Only after a separately authorized installation and normal restart, disconnect
other controllers and run `mighty-loop --status`. It requires the exact NAMLNK25
identity, reads a coherent five-page snapshot, and sends no mute/output, preset,
flash, reset or audio-stream commands. The diagnostic client has no automatic
recording or automatic retries of actions.

| Explicit command | Action |
| --- | --- |
| `--status` | Read RAM/copy/guard results, loop state and raw timing |
| `--arm` | Arm a fresh empty loop; wait for guitar threshold |
| `--finish-or-toggle` | Finish recording, cancel arming, or pause/resume playback |
| `--view` | Switch the internal control mode; no new physical-button/LED mapping |
| `--stop` | Stop and rewind; retain the recording |
| `--clear` | Clear an inactive loop; refuses while playing or recording |

Start with the headphones unplugged for the RAM/timing trial. Check RAM flags and
baseline timing before arming; capture another status during recording, playback
and physical preset changes. No command enables or disables guitar output.
Recording needs actual guitar input; this tool does not inject or play a signal.

## Diagnostic words

Private `NO` version 1: 14-byte requests, 55-byte replies on either existing MIDI
transport. `looper_wire.h` validates sizes, seven-bit encoding, nonce, operation
and page. Commands are acknowledged by a sequence number after application in the
audio IRQ; they do not modify the loop concurrently from foreground code.

| Word(s) | Meaning |
| --- | --- |
| 0–2 | Magic `0x4c4f5031`, schema 1, startup state (2 = complete) |
| 3–4 | Latched fault bits; first failing address |
| 5–7 | RAM bytes checked, startup passes, completed idle sweeps |
| 8–11 | Loop state, recorded 24 kHz samples, stored cursor, played 48 kHz frames |
| 12–14 | Pending command, applied sequence, command result |
| 15–16 | Audio-object bytes, IRQ snapshot sequence |
| 17–20 | Valid/rejected intervals, latest and maximum measured IRQ cycles |
| 21–22 | Minimum/maximum valid IRQ start-to-start cycles |
| 23–25 | Maximum interval for recording, playback and other loop states |
| 26–27 | Cycle-counter reset rejections, observed SAI FIFO/sync error bits |
| 28–31 | Preset read calls/bytes, blocked flash writes, allowed idle flash operations |
| 32–34 | Guard words checked, idle-scan byte offset, copied-code hash |
| 35–36 | Startup CCR and MPU-control register observations |
| 37–39 | Reserved |

Fault bits: 1 code copy, 2 startup RAM readback, 4 guard, 8 idle pattern, 16 codec
data. Loop states: 0 empty, 1 armed, 2 recording, 3 playing, 4 paused, 5 stopped.
Command result: 0 success, 1 invalid, 2 busy/not applicable, 3 disabled by fault.

These tests do **not** establish physical RAM ownership or a hardware deadline.
The CPU model does not emulate Cortex-M7 bus/cache contention, DMA or another
core. Runtime canary reads can miss writes hidden behind a cache; the startup
cache-maintained readback is stronger but still not an ownership proof. Timing
uses raw DWT cycles and rejects disabled/reset intervals; it excludes exception
entry and a small amount of diagnostic bookkeeping. Emulator cycle fixtures and
instruction counts are not measured microseconds or latency. Physical output,
startup duration, long recording, cache/DMA interference and worst-case IRQ margin
remain the purpose of the controlled trial.
