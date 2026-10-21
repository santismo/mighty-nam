# NAMLNK19: bypass sleep and driver timing trial

NAMLNK19 is prepared for an experimental physical test, **not installed**. The last physically verified build remains NAMLNK17. No USB/Bluetooth commands, mute commands, audio streams or updater actions were used while preparing this release. NAMLNK18's previously staged container remains unchanged.

- Firmware: `NAMLNK19-bypass-timing-test.bin`
- SHA-256: `40e12512141730bdfbdd1c64c9b38d5c99032fa2546db5fed832b8912b8cc732`
- ELF SHA-256: `4c058e7d985897a3ef84f78881a98f0fff0aa9ee3d930347d158a3f0421ebbb0`
- Mac compatibility: 0.3.11+14. Phone compatibility: 0.6.6.
- Includes NAMLNK18's persistent global 8/16/32 setting and playback-preserving successful edits. Eight remains the default and minimum. Saved presets with playback enabled resume after power-on; no new startup or controller auto-mute policy is introduced. Existing fault guards and effect-switch settling remain.

## What changed

Used stock delay and reverb blocks now sleep after 1,198 bypass blocks (about 200 ms at 48 kHz). On re-enable, the compiled hook requests the original foreground loader to clear and initialize the selected algorithm during the established switch-settling interval. This is hard bypass: old tails are discarded, not frozen for later playback. The used noise gate keeps its previous policy because its envelope/stereo behavior needs a separate audit.

The one-shot driver capture records observations at the IRQ wrapper before the stock handler and immediately after output rendering. It is disabled at boot, never continuously polls hardware, never changes clock/FIFO/DMA configuration, and never sends a listen/mute/reset/flash command. A small disabled-call branch remains in the two hook sites. All NAM hot-code and table addresses/bytes match NAMLNK16/18 exactly.

## Offline verification

All tests bind to the exact ELF hash above:

- 22 compiled full-IRQ cases: all five delays and six reverbs, each at ordinary and long settings. Sleeping blocks had zero dispatch calls; real foreground history clears were observed; silent wake stayed below 1e-6 normalized output after settling. New input remained audible in the numerical output.
- Active delay/reverb PCM matched NAMLNK18 over 2,400 frames/channel. Type changes while asleep, wake into other algorithms and rapid switching passed.
- Full stock chain with real NAM, five dual-custom-FX combinations and High/Low Cut passed. Two real captures matched the reference NAM core at the tested boundary with zero recorded error. This is numerical validation, not real-time capacity proof.
- Cold starts with RAM filled 0/0xa5/0xff, warm restarts, seven independent presets, stock button branches, global buffer persistence, failed writes and fault guards passed.
- Both Fender and Marshall fixtures retained exact PCM and eight-sample protected-output age in NAM-only and NAM-plus-spring chains. There is no new output queue.
- Diagnostic protocol passed both channels, invalid commands, pending-request protection, reset/disabled-counter/torn-DMA decoder cases, incomplete-render handling and cold/warm reset-to-off checks. Active instrumented publication matched the previous protected block exactly. No diagnostic MMIO writes occurred.
- Controller: 98 phone tests, 78 Mac tests (one optional interop fixture skipped), 1,667 native stock-wire checks, 85 FX checks, 921 tuner checks, and 17 actual ARM compact replies decoded in JavaScript. The simulated browser showed both FX blocks, seven colors, 8→16→8 global changes across a color switch, saving without losing playback intent and an A2 tuner reading.

The instruction-count fixtures used 4.17% fewer IRQ instruction events after bypassing a used delay with NAM/spring remaining, and 16.16% fewer after bypassing both used tails. Both active algorithms gained about 0.077% instruction overhead in that fixture. These are emulator instruction events, **not measured CPU cycles, deadlines, or analog latency**. A fresh minimal chain whose other blocks have never run already skipped them and should not be expected to get the same saving.

## Timing capture protocol and interpretation

Use only with NAMLNK19 and no other controller issuing diagnostic commands. Normal status requests never arm tracing.

- `F0 43 58 70 04 02 4E 44 7F F7` (ND127) explicitly arms one capture. Pending captures cannot be overwritten. ND126 cancels diagnostic state only.
- Status page NP118: high byte `D1`, 16-bit generation in bits 8–23, state in low byte: 0 idle, 1 armed, 2 entry only, 3 complete, 4 no output publication observed.
- ND0…ND5 selects one of six read windows. NP119…NP126 reads its eight words, for 48 words total. These reads never arm tracing. Incomplete captures return error 2; NP127 is unsupported. Verify the same complete header before and after reading all windows.
- Each 24-word phase contains DWT epoch/control/cycle brackets, DMA RX/TX next descriptor and address/CITER observations before and after, SAI FIFO pointer/status words, IRQ sequence and published TX half. The aligned TCD+0x14 word contains DOFF low/CITER high.
- `firmware/research/decode_driver_timing.py` identifies counter resets/disabled counters, observed DMA motion and FIFO errors. The capture is a sequence of reads, **not atomic**: unobserved wrap/ABA races remain possible. FIFO pointers are not hardware timestamps.
- The publication marker is after CPU rendering returns; it is not proof that DMA has consumed, or even observed, every store. Counter spans include diagnostic overhead and cold-cache effects. They are not calibrated milliseconds. Repeat captures and compare phases before proposing a different output schedule.

The optional Mac collector builds with:

```sh
clang -Wall -Wextra -Werror -Wno-deprecated-declarations firmware/tools/mpp_driver_client.c -framework CoreMIDI -framework CoreFoundation -o mpp_driver_client
```

**Do not run until the physical test is requested.** Its sole operation is `--capture`. It requires exactly one matching MIDI endpoint pair and an NAMLNK19 identity, arms once, reads a bounded snapshot, and prints JSON. It has no generic packet sender and no listen, mute, preset-save or firmware-update operation. Feed the result to `decode_driver_timing.py` for interpretation. It was compiled, not connected to the plug during preparation.

## Next physical test

1. In normal mode, take a fresh seven-color backup while leaving output intent unchanged. This build's update still clears the onboard bank and global setting sectors; restore is required. Don't use an old backup without checking for newer edits.
2. Only after explicit update readiness, install the exact named container through the stock updater. Do not reset/power off during the update.
3. Restart normally, restore the seven colors with the chosen global buffer (normally eight), then verify power-off storage and button cycling.
4. Compare matched fresh and used-then-bypassed minimal chains. Take explicit driver snapshots while checking faults and output. Measure the analog input-to-headphone path if equipment becomes available.

No shorter handoff, four-frame processing, FIFO-watermark change or sample-rate change is included. The candidate's USB recovery and real-time headroom remain physically unverified. Existing stock recovery depends on reaching the stock updater; no full bootloader backup exists.

## What could reduce latency next?

Faster NAM and effects free compute margin and can prevent overload. They do not automatically shorten a fixed pipeline. The measurements above are intended to decide whether the protected eight-sample handoff can be shortened safely; eliminating that entire stage could remove 8/48000 seconds, about 0.167 ms, but its deadline protection previously prevented bitcrushing. Four samples would save only 0.083 ms per shortened stage and requires changing the stock eight-frame processing contract.

Reducing sample rate works against fixed-sample buffer latency: eight samples at 32 kHz take 0.250 ms instead of 0.167 ms at 48 kHz. These captures are validated at 48 kHz; resampling introduces its own work and phase response. Effect-specific delay, especially pitch shifting, and capture/EQ phase response are separate from the buffer. A lower-delay effect algorithm may help where generic CPU optimization cannot.

See [exact evidence](../evidence/namlnk19/manifest.json) and [the preceding driver audit](audio-driver-and-bypass-audit.md).
