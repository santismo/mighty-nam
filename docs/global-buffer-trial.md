# Global buffer and NAM placement trial — NAMLNK18

NAMLNK18 is an offline-tested candidate, not installed on the development plug. NAMLNK17 remains the last physically tested version. This development session made no USB, Bluetooth, audio-device, mute, reset or flashing calls to the physical plug. Mac/Teams audio was untouched.

## What changes

- One persistent **8 / 16 / 32-sample output buffer** for the whole plug. Setting 8 once applies to all seven colors, button recalls and subsequent power-ons. A new installation defaults to 8. No preset save is needed to persist this control.
- Two separately committed settings sectors in the audited retired amp region. Changing the buffer never rewrites captures, effect presets or copied executable code. CRC/readback and a final commit marker allow recovery of the previous setting after interrupted writes. Duplicate settings do not write flash.
- Controller 0.6.5 and Mac 0.3.10 show global scope only on verified NAMLNK18. Older firmware keeps its existing per-preset behavior. Ordinary successful buffer changes, capture uploads and preset saves resume output if it was previously enabled; previously muted output stays muted. Writes/transfer may briefly interrupt sound while settling. Explicit mute, tuner mute and processing-fault protection remain.
- Restore the exact NAMLNK16 linked NAM process code and hot-table addresses while retaining NAMLNK17's converter startup setting. This removes a memory-placement variable from the next hardware comparison; it is **not evidence of a measured latency or CPU improvement**.

## Offline results

See [evidence](../evidence/namlnk18/). Actual ARM code with bounded modeled peripherals passed global setting persistence, all seven button recalls, cold/warm reinitialization, failed writes, invalid commands and output-state checks. Host storage tests include ASan/UBSan and interrupted commits. Reference NAM accuracy, full stock/custom effects, High / Low Cut, tuner packets, saved presets and existing fault protection passed.

With Fender and Marshall fixtures, NAM-only and NAM-plus-spring output is bit-identical to NAMLNK17. Protected output age remains one eight-sample block (0.167 ms); there is no additional output queue at 8. This excludes DMA, converters, analog circuitry and model/filter phase response, so it is not total guitar-to-headphone latency.

A separate callback audit shows no unused bypassed effect callbacks and no idle custom-FX callbacks in a freshly loaded NAM-plus-spring chain. After gate/delay/reverb have been used, their callbacks remain active when bypassed, following the established tail policy. Earlier tail experiments showed that arbitrary sleep can revive old delay audio. A future optimization needs per-type history draining/reset and click-free wake, rather than a blanket timeout. Four-frame processing also remains a separate audio-driver/DSP project; stock callbacks write eight samples.

## Installation and next comparison

Local-only file: `NAMLNK18-global-buffer-test.bin`. The checked packager preserves stock vectors, audio IRQ, update container and allowed patch regions. Stock firmware, generated images, captures and private backups are not committed to GitHub.

Installation still clears the seven-preset bank and settings. Obtain a fresh backup when the user is ready for an update, normalize the restore plan's effective buffer to 8 for every color, then restore and verify all seven captures/effect records. Do not reuse old per-color 16/32 values as global writes. The user can keep playing the installed version until then.

After installation, verify global 8 survives a normal restart and all colors; compare matched NAM-only and NAM-plus-spring timing against the immediate 17 baseline, using the same model/effects and a calibrated end-to-end measurement where available. Physical timing, storage endurance and listening on NAMLNK18 remain unverified. Existing stock recovery access is not a guarantee for every experimental build.
