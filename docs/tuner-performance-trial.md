# NAMLNK12 tuner and performance trial

The Mac controller 0.3.4 is installed on the development Mac. NAMLNK12 is prepared and offline-tested; physical installation and validation are pending. The repository remains private and GitHub Pages remains disabled. No new release installer is published; the local Applications app and ZIP contain 0.3.4.

## Using the tuner

Connect by USB in normal mode and open **Tuner** in the app header. This requires NAMLNK12. The app mutes the plug, reads short dry-guitar snapshots over USB MIDI, and displays the nearest note, octave, cents and a flat/sharp needle. Play one sustained note at a time. Reference A can be set from 430 to 450 Hz; the default is 440 Hz.

Closing the tuner stops collection and leaves the plug muted. Use **Listen on plug** to resume. The tuner opens no Mac microphone, input or playback stream and does not change Mac or Teams audio settings. Saved captures, effects and presets are unchanged by tuning.

Capture is off at startup. Each explicit start records at most 2,048 signed samples at 12 kHz, from dry guitar input before effects. A completed capture is frozen until the next start. Playback stays at 48 kHz with eight-frame processing. The native and Dart parsers check lengths, checksums, nonce, generation and sample count. See the [wire contract](../spec/tuner-v1.json).

## Performance work included

NAMLNK12 includes the NAMLNK11 cache-preparation and opt-in per-effect profiler changes. Preparation covers the same cache lines with at least 83.59% fewer model-memory reads and 67.36% fewer instruction events in simulation. Those figures describe bypass/settling preparation only, not active NAM, total CPU use, physical speedup or headphone latency.

The profiler defaults off. The existing output schedule, 48 kHz rate, 8/16/32 output-staging choices, model math, preset storage and stock gate/delay/reverb tail policy are retained. Hardware measurements are still needed before further latency or effect-suspension changes.

## Validation

- Full final Mac suite: 60 tests pass, one optional interop test skipped; scoped analysis clean; release build and signature verified.
- 1,573 native controller checks, 921 tuner wire checks, nine CoreMIDI packet allocation cases under AddressSanitizer, and 1,039 bounded capture checks under sanitizers.
- 84 synthetic pitch cases, including bass/guitar frequencies, detuning, harmonics, noise and decay, meet a two-cent bound. Silence, DC and noise are rejected. This does not establish accuracy on real pickups or distorted/polyphonic notes.
- Exact firmware ARM execution captures all 2,048 dry samples correctly, accepts both USB channels, enforces muted-only start, freezes completed pages, resets cleanly, rejects invalid/interrupt-context requests and works without a loaded model. PCM is identical over 1,024 full-chain blocks with capture on and off.
- Seven-preset save/recall, cold/warm restart, stock button branch, two-model reference accuracy, placement, 24 cache-preparation cases, 33 profiler PCM comparisons and 138 counter/ABI cases pass against the same final ELF.
- NAMLNK10 rebuilds identically; output and storage objects, stock vectors and IRQ body are preserved. Incomplete or mismatched evidence is rejected by the packaging tool.

Reports are in [evidence/namlnk12](../evidence/namlnk12). These are offline checks; physical tuner accuracy, timing and recovery for NAMLNK12 remain unverified.

## Build and hardware trial

Add both `--performance --tuner` to the complete NAMLNK10 build options. `stage_tuner_firmware.py` requires the exact user-supplied stock package, final ELF and matching performance, preset, controller and tuner reports. It creates the combined image locally; this repository does not distribute it.

Before installation, read the latest seven preset headers, verify matching local model bytes by CRC and SHA, and preserve all effects, order, names, buffers and unsaved Mac edits. **Installing the image clears the onboard bank.** Original backup headers retain their generations; newly restored records start at generation 1. Restore only from verified files after checking exact NAMLNK12 identity and muting the plug.

The `tools/namlnk12-trial` helper can validate a private restore plan without connecting, then restore empty slots with complete effect readback before each save. It refuses capture/header mismatches, existing different records and unverified effect state. Personal plans and captures stay local.

Use the official NUX updater with headphones unplugged. Wait for explicit completion before power cycling. Confirm firmware identity, restore/recall all seven slots, test a quiet tuner capture, collect timing, and verify a normal restart and button cycle. The bootloader has not been fully backed up; stock recovery still depends on a reachable loader.
