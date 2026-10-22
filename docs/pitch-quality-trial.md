# NAMLNK22: pitch quality trial

2026-10-22. **Ready for a hardware trial; not flashed.** This candidate promotes
the improved pitch DSP from [NAMPIT01](pitch-quality-prototype.md), retaining
NAMLNK21's USB audio repair, NAM controls, recording gain, Auto Wah and active
chain. The Mac app is **0.5.1 (20)**; the public phone controller is **0.8.1**.
Neither controller update installs firmware.

## Local candidate and presets

File: `NAMLNK22-pitch-quality-test.bin` (14,439,215 bytes).

SHA-256: `e8e50d55ef3eda951722cf66eb0a4ec29bfbede21ffb5e79238bde5e6ec70855`.

At the user's request, this local candidate embeds **the seven presets saved
in the Mac app**, including the edited Green, Orange and Red slots, their
captures, effects, order, FX A/B, NAM controls and levels. Four distinct cached
A2 Lite captures are used. Orange retains its enabled Pitch block. Preset names
are preserved exactly, even where a name does not describe the selected capture.
Installing this image writes those Mac versions into the seven onboard colors.
It starts on Green, with playback enabled and a global eight-sample output
buffer. The library does not persist the plug's current global buffer value.

The export uses the app's production library and control-plan parsers. Actual
compiled firmware saves the exported settings in an emulator; cold startup and
nonadjacent recalls verify each slot. An independent check decodes the final
updater file and verifies both record copies, capture hashes and effects against
the export. The original Mac library remains unchanged. No device preset backup
or device access was performed. Library exports, captures, banks, stock firmware
and the locally assembled updater file are excluded from this repository.

## DSP and validation

Pitch now uses finer period estimation, compensation during changing pitch,
and anti-alias filtering before upward shifts. Its DSP source is identical to
the measured NAMPIT01 prototype. It remains monophonic; this is not a claim of
polyphonic tracking or lower physical latency. There is no new queued block or
DMA/clock change. The previous DMA deadline experiment is not included.

- [Compiled pitch comparison](../evidence/namlnk22/pitch.json): three traces
  per variant, 1,024 calls each; outputs match the native implementation exactly.
  Octave-up requires about 9.2% more per-effect instruction events. These are
  emulator events, not physical CPU cycles or whole-chain percentages.
- [Combined-chain regression](../evidence/namlnk22/chain.json): 2,501 callbacks
  with both pitch blocks, NAM and Spring, opposite octave settings and neutral
  shifts. NAM reference error is zero; bypassed pitch blocks execute no FX
  processing callbacks.
- [USB/NAM regression](../evidence/namlnk22/arm.json): 1,652 callbacks, stereo
  PCM routing, NG/NV on both transports, seven saved control sets, cold/warm
  startup and stock preset-button dispatch. Peripheral completion is modeled.
- [Final preset verification](../evidence/namlnk22/package-check.json): all
  seven packaged colors match the Mac export; both copies validate.
- Mac suite: 101 passing cases plus the explicit local-export test. Native
  stock wire checks: 1,697. Phone suite: 118 passing cases plus two additional
  complete model-transfer cases for NAMLNK21/22. Fixtures exercise controllers
  without connecting to the physical plug.

Copied code has 228 bytes remaining and state RAM has 780 bytes remaining in
the existing audited regions. Build, storage and source-hash checks pass.
Synthetic spectral and vibrato results are recorded in the
[prototype evidence](../evidence/nampit01/quality.json); they are not listening
scores or measurements of this device's analog latency.

## Controllers and next hardware checks

The universal Mac app is installed in Applications without launching it. Its
stable development signature and bundle identity are preserved; the installer
passes disk-image verification but is not notarized. The public
[phone controller](https://santismo.github.io/mighty-nam-controller/?v=0.8.1)
recognizes NAMLNK22, including both FX blocks, NAM controls, recording gain,
direct color selection and global buffering. Unknown firmware remains gated.

After a separately authorized update, check the seven colors after power-off,
physical processing deadlines with pitch and USB audio active, and octave-up/
down listening with single notes, bends and attacks. Logic duplex audio remains
a physical verification item. No plug mute, host audio stream, system audio
setting or Teams setting was touched while preparing this build.
