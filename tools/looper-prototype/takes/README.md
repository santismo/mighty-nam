# NAMLNK29 independent-lane preview

Source-only, offline-tested development by santismo. The local image retains the user's exact NUX MP3_OR_V3.0.5.bin and private preset bank; complete images are not distributed by this directory. No test script here accesses hardware or an audio device.

## Behavior

The base loop stays unchanged. Up to three separate mono ADPCM lanes can be added. An overdub can span multiple complete passes. Selecting an existing lane adds notes to that lane, with a pre-edit copy for one-level undo/redo. Starting another edit replaces the previous undo history. Per-lane volume/mute affect playback, and delete removes one overdub lane. Recordings remain in RAM only.

A new lane is zeroed incrementally; editing a lane copies its previous compressed bytes incrementally. Recording begins only once preparation completes at a codec block boundary. Undo/redo swaps at a block boundary. No full-loop copy runs with interrupts masked. The live guitar path remains 48 kHz/eight frames and gains no added buffering.

## RAM and capacity

The existing pool is unchanged: 270,336 bytes at 0x202a0020 plus 100,980 at 0x2031c020, totaling 371,316 bytes (2,813 ADPCM blocks). Each 256-sample block occupies 132 bytes. A lane reserves the base length rounded up to a block. One additional region is needed to undo an edit to an existing lane.

| Retained audio plus editable undo | Maximum base at 24 kHz | Maximum base at 12 kHz |
| --- | ---: | ---: |
| Base + one lane + undo | 9.995 s | 19.989 s |
| Base + two lanes + undo | 7.499 s | 14.997 s |
| Base + three lanes + undo | 5.995 s | 11.989 s |

A full 30/60-second base can play, but cannot add an independent lane. The controller reads capacity from the firmware. This version does not claim unlimited tracks or use unverified external RAM. Code uses 15,440 bytes of the existing 16,320-byte overlay code range; BSS uses 4,244 of 8,128 bytes. Physical timing still requires a device trial.

## Seven saved presets

The stock low-level page-program entry does not reset FlexSPI AHB buffers, unlike the stock multi-page wrapper. The overlay now performs a bounded controller software reset after each successful page program, including the commit word, before readback. A split backing-store/AHB emulator reproduces the old slot-four I/O error and verifies all seven saves, restart/cycling and failed-write preservation. Hardware confirmation remains pending.

## Protocol

Existing NO v1 framing and 55-byte replies are unchanged. NAMLNK29 adds status page 7 and the following commands. Older identities must not receive these additions.

- Operation 1: 11 undo, 12 redo, 13 start new lane, 14 finish recording.
- Operations 6–9: track 0–3 volume, argument 0–100.
- Operation 10: mute, argument `track * 2 + muted`.
- Operation 11: delete overdub lane 1–3.
- Operation 12: record into existing lane 1–3.

Page 7 returns eight words: presence/mute/recording/undone/preparing/pending/can-edit flags; packed 7-bit levels; two pairs of 16-bit peaks; available new lanes; undo/redo lane; generation; base sample length. Track 0 is the base. Commands use the existing bounded audio-IRQ mailbox; transport acceptance alone is not a successful edit.

## Offline verification

`run_native.py` runs ASan/UBSan storage, gesture, codec-quality, lane-boundary and full-duration NAM/model-switching tests. `test_arm.py` executes the compiled lane commands with NAM and spring reverb. `test_presets.py` models stale AHB reads. `test_continuity.py` interleaves actual ARM IRQ processing with preset loading and compares recorded bytes/playback to the native oracle. Startup, media/USB and saved-setting regressions use the existing hardware/settings test runners.

The staging tool requires matching source/ELF hashes and all gates before creating a private test container. These tests do not prove Cortex-M7 cycle deadlines, electrical button behavior or physical RAM/DMA ownership.

The synthetic `test_vm_read_hook.py` demonstrates a Unicorn 2.1.4 conditional load/store instrumentation bug. Continuity tests retain per-IRQ boundary canaries, immutable-code checks and exact byte/sample comparisons, but omit live-data memory hooks that change instruction execution. Native ASan/UBSan tests cover lane accesses; this continuity run is not a dynamic ownership audit. The RAM ranges are unchanged from the previous allocation.

The current candidate passed 49 native lane-boundary cases, 2,700,000 eight-frame callbacks with 86 NAM changes, and 14,837 compiled ARM callbacks with 2,363 interleaved IRQs. Loop samples and encoded overdubs matched the native oracle exactly across preset recalls. These are functional checks, not measured hardware cycle budgets.
