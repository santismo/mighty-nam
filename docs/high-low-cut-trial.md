# NAMLNK14 — High / Low Cut EQ

Choose **Equalizer → High / Low Cut** in phone controller 0.5.0 or Mac app 0.3.6 while connected to NAMLNK14. Low Cut spans 20 Hz–1 kHz and High Cut spans 1–20 kHz. Each has an Off position; use either alone or both together. Both start Off when choosing this effect. The main Enabled / Bypassed button controls the whole block, and it retains its existing movable position.

Changes apply live. Save to plug keeps the cutoffs, bypass state and EQ position with that color's capture, other effects, FX A/B and buffer. Older saved chains gain neutral defaults in the Mac library. Earlier firmware does not expose or accept the new option from these controllers. NAMLNK14 also accepts the existing stock EQ type 3; it does not reinterpret it as the custom filter.

The new DSP uses two stereo 12 dB/oct Butterworth filters. There is no extra block buffer. Smoothing limits abrupt control changes; this is not a measured latency improvement. The 48 kHz sample rate and 8/16/32 output settings remain unchanged.

## Validation and installation

Host checks cover cutoff response, attenuation, both filters together, rapid switching, independent Off, stereo and in-place buffers, exact settled bypass and nonfinite input, with address/undefined-behavior sanitizers. ARM emulation runs the exact candidate through real MIDI control dispatch, both cuts at 1 kHz, all seven saved slots, cold/warm restarts and stock EQ fallback. The existing NAM accuracy, FX A/B, paged Bluetooth, full-chain PCM and timing-fault tests are retained. See `evidence/namlnk14/` for recorded results and their limits.

Mac 0.3.6+9 is installed in Applications and phone controller 0.5.0 is deployed with verified live assets. The local candidate is `NAMLNK14-high-low-cut-test.bin`, SHA-256 `58a76236d2fc09cc396505815763c40b7fa1bcfbbc9401de1a57244799963e95`.

NAMLNK14 was installed on the development plug on 2026-10-21; USB identity and empty-bank muted startup were verified after the user reported a normal restart. A bounded muted trial passed six cut pairs, EQ types 1/2/3/4, move/bypass transitions, and NAM plus stock effects and Pitch/Auto Wah with both cuts. A fresh Green Fender A2 Lite preset was saved, independently read, changed and recalled; all 128 effect bytes matched. It remains muted, with Low Cut about 77 Hz, High Cut about 8.07 kHz and buffer 8. See [physical summary](../evidence/namlnk14/physical-summary.json).

No processing fault was reported (maximum NAM timer 127; maximum raw IRQ counter 129,958 cycles). These counters do not establish calibrated deadlines. Real-guitar listening, phone controls on NAMLNK14, post-save power-off persistence and USB recovery remain unverified on this build. The installer clears the onboard bank: take a fresh backup before installing if you want to keep the current presets. The earlier backup waiver applied to the NAMLNK13 trial; do not assume it authorizes losing later edits. The combined image is built locally from the exact user-supplied NUX V1.5.6 package and is not distributed in this repository. The official updater performs installation.

`firmware/tools/build_link_firmware.py` adds `--cut-eq` to the NAMLNK13 flags. `firmware/tools/stage_cut_eq_firmware.py` accepts the stock package, build directory, report directory and output directory, and requires exact-build evidence before creating the local candidate. Neither command accesses USB or plays audio.
