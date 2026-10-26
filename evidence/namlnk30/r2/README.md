# NAMLNK30 revision 2

Offline tests of the corrected overlay, with modeled peripherals. The initial
revision's evidence remains in the parent directory; it is not relabeled here.

- The real receive assembler accepts fragmented Amp capability requests on both
  transport selectors, with and without the SysEx terminator counted in length.
- Separate modeled NOR storage and CPU cache reproduce stale readback failure.
  Invalidation allows all seven saves, random recall and normal restart.
- Failed writes preserve the previous committed record and report diagnostics.
- All seven seeded colors pass the compiled preset-button cycle and startup.
- All 29 amp models match the original DSP reference across 87 knob cases.
- The builder matches its independently staged output. Archived 29/28/23 outputs
  remain byte-for-byte unchanged. No device or host audio is accessed.

The cache model is a regression fixture, not evidence that cache coherency
caused the physical device's I/O failure. Hardware save/restart verification is
pending. No new latency measurement is claimed.
