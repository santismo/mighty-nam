# NAMLNK13 experimental trial

NAMLNK13 adds two independent movable FX slots to the existing nine-block chain. FX A and FX B each offer Pitch (−12…+12 semitones), Auto Wah, Chorus, Flanger, Phaser, Tremolo and Vibrato. Both can run together. They default to bypassed, after gate/compression in the default stock order. The original stock modulation block remains.

Use [controller 0.4.0](https://santismo.github.io/nam-plug-controller/?v=0.4.0) in Bluefy for the two FX editors. Tap the symbol for bypass, the block name for controls below, and the arrows to move it. Changes apply live; Save to plug persists the pair with the active color's capture, effects and buffer. The Mac 0.3.5+8 compatibility update supports NAMLNK13 USB capture loading and existing controls; its chain editor still displays the nine stock blocks.

## Scope and limits

This is an offline-tested hardware trial. Actual NAMLNK13 real-time processing, iPhone Bluetooth transport, recovery entry and listening quality remain unverified. Pitch uses a basic monophonic, pitch-synchronous granular shifter with incremental pitch tracking. Steady synthetic guitar-range pitch checks do not establish chord or transient quality. Delay-based effects add algorithm delay beyond the output buffer. The 8/16/32 setting still changes only output staging.

The firmware remains a hybrid using locally obtained NUX startup, drivers and stock effects. This repository's license does not relicense those proprietary components or third-party captures. Do not commit or distribute the combined firmware image here.

Installation clears the onboard bank. Before an update, read and verify a fresh seven-preset backup in normal mode, retain the current firmware restore file, install with the official updater, and restore/read back the bank. Existing preset records are accepted with both new slots bypassed. Once FX data exists, backup/restore tooling must explicitly retain its extra configuration; legacy header-only exports do not describe these new slots. No full bootloader backup exists.

## Implementation

Each slot owns a 2048-frame stereo delay ring and independent filter state. Bypass settles to a bit-exact pass-through. Wet changes are smoothed. Reordering/type changes reset small state without clearing delay rings in the audio interrupt. A fill count prevents stale reads.

The 32-byte FX configuration consists of two 16-byte slots: mode (1…7 in the order above), enabled (0/1), absolute position (0…10), semitones+12 (0…24), mix, rate, depth, feedback, sensitivity, resonance (0…100), and six reserved zeros. Slot positions must differ. Stock order stays nine bytes; FX positions insert two blocks between stock dispatcher boundaries.

The current 8192-byte preset record retains its header and packed NAM data. Offset 7808 stores `FX13` as the little-endian word `0x33315846`; offset 7812 stores the 32-byte config. The existing record CRC covers this extension. FF padding denotes legacy defaults. Dual-copy save/commit behavior and the stock preset-button hook remain.

New bounded `NF` requests read the live pair, read a saved pair, or replace the live pair. A write includes the expected active color and model CRC; it does not write flash. Existing `NS` Save includes the live FX configuration. Requests and responses carry a nonce; the controller independently reads settings back.

Bluetooth long replies use `NR` envelopes: generation, page index/count, total body length and up to 40 seven-bit payload bytes. The first page is pushed; each next page requires an explicit pull. Maximum envelope length is 56 MIDI bytes. USB retains the original complete NS/NU frames. The controller checks order/generation/size and then the original nonce/CRC. It never automatically retries a save after a lost acknowledgement. This avoids the observed NAMLNK12 truncated 326-byte Bluetooth reply without assuming an unproven cause in the stock serializer.

## Build and checks

Add `--fx-blocks` to the existing NAMLNK12 build flags (`--performance --tuner` are required). The new linker file uses the same audited retired-RAM extent, splitting state below `0x20310000` and copied code from there through `0x20314000`. The combined image still requires exact stock V1.5.6 and preserves vectors/IRQ body.

The test entry points are `research/test_fx_blocks.cpp`, `test_fx_pitch_range.cpp`, `check_fx_pitch.py`, `test_fx_firmware.py`, `test_fx_regression.py`, and the existing `test_preset_runtime.py`. Host DSP executables write synthetic float samples to files for FFT analysis; they never play them. Compile the host checks with address/undefined-behavior sanitizers. Firmware tests use Unicorn with stock flash-driver semantics modeled at their boundaries; they do not emulate physical peripheral timing.

`tools/stage_fx_firmware.py` accepts the stock package, build directory, report directory and output directory. It checks exact ELF-bound runtime/FX/PCM/controller reports, source-bound pitch evidence, stock-image identity, memory allowlists, vector/IRQ preservation and container round-tripping. It writes a local experimental candidate only. Reports in `evidence/namlnk13/` describe the recorded build and do not validate modified source.
