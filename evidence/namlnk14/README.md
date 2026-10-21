# NAMLNK14 recorded checks

These records bind to ELF `8f63f2a9191ca0f6d8e06d211515d38f1760cf728ba35e4e141005b16589523d` and local candidate `58a76236d2fc09cc396505815763c40b7fa1bcfbbc9401de1a57244799963e95`. The original offline records predate installation. Subsequent physical records (`physical-first-boot.json`, `physical-cut-trial.json`, `physical-summary.json`) verify NAMLNK14 identity, muted control tests and one fresh preset save/read/recall. Listening quality, post-save power-off persistence, Bluetooth and calibrated real-time timing remain unverified.

- Host cut filters: ten cutoff-response checks, combined response, independent Off, switching, stereo/in-place, finite output and exact settled bypass; address/undefined-behavior sanitizers enabled.
- Exact ARM build: real stock MIDI control ingress, both cuts at 1 kHz, seven distinct saved cut configurations, duplicate-write protection, PRESET recall, cold/warm restarts, RAM guards and stock EQ types 1/2/3.
- Full-chain regression: unchanged NAMLNK13 reference rebuilt identically; 4,050 bypassed-FX blocks remain bit-identical. NAM with stock effects and five dual-FX combinations runs 1,350 blocks per combination. An additional 1,350-block run includes both cuts. Timing-fault mute remains covered; emulation time is not hardware timing.
- Two licensed local A2 Lite models match the independent reference through 1,300 blocks each. The captures are not redistributed.
- Existing FX/paged transport checks pass. `pitch.json` is reused prior evidence for unchanged, hash-checked FX source, not a newly run pitch experiment.
- 49 web tests; simulated NAMLNK12/13/14 browser flows at five widths. New cut controls, live writes and explicit save/recall are covered. Live controller 0.5.0 assets match the tested source.
- 63 distinct Mac tests passed across the initial suite and one targeted retest after correcting the expected catalog size; one optional interop test skipped. 1,586 native wire checks, clean scoped analysis and signed release validation. Mac 0.3.6+9 installed without launch; no host audio or Teams changes.
- Container round-trip, unchanged setup/record headers and stock vector/IRQ bounds pass. Packaging rejects mismatched controller evidence without writing an image.

The combined image stays local. Installing it clears the onboard bank; obtain a current preset/capture backup before updating if retaining those settings is desired. The recorded NAMLNK14 hardware checks are bounded single-unit observations. See [trial notes](../../docs/high-low-cut-trial.md).
