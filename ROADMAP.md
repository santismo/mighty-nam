# mighty-nam roadmap

Updated 22 October 2026. Research entries are not released capabilities.

## Current baseline

Public local builder 0.3.1 creates NAMLNK23 r2 from the exact NUX
MP3_OR_V3.0.5.bin, with three licensed RiffSmith starter presets. The owner confirmed
Bluetooth playback on the personal r2 build. Mac 0.5.4 and phone 0.8.3 remain compatible.
See [Bluetooth evidence and limits](docs/bluetooth-audio.md).

## Next hardware trial

- Evaluate the [DaisySP wah prototype](docs/wah-prototype.md), after explicit installation authorization.
  Native reference, compiled NAM/wah/Spring and pitch regressions are offline checks.
- Measure sustained deadlines with both FX blocks, NAM, reverb and active USB audio.
- Verify Logic stereo input/output, recording gain and host-return isolation at 48 kHz.
- Verify public starter-bank startup, playback and power-off persistence on hardware.
- Measure analog guitar-to-headphone latency. Instruction counts and output-buffer values
  are not that measurement. DMA deadline experiments remain excluded.

## Standalone looper and buttons

The [offline control model](docs/looper-research.md) implements the requested gestures:
double POWER to enter; PRESET to arm threshold recording, finish, pause and resume;
single POWER to switch between loop and preset controls without stopping playback;
double POWER to stop and exit. Holding PRESET reverses normal preset cycling.

Next establish safe loop memory, protect playback across preset reloads, verify button
hooks and preserve long-POWER shutdown and the startup updater gesture. Duration,
compression, replacement/clear controls, overdubbing and persistence remain undecided.
No recorder, playback mixer or looper firmware is released.

## Controller and longer-term work

- Physical iPhone transfer/reconnect and tuner cadence checks.
- Preserve the official capture picker, creator/license metadata and local favorites.
- Keep A2 Lite at 48 kHz; full A2 is unsupported.
- Further pitch/wah tuning, processing headroom and measured latency improvements.
- Dependable preset export/restore across updates.
- Independent startup/audio drivers and an updater with a demonstrated recovery contract.
- Ongoing third-party notices, service terms and distribution review. Do not publish
  complete stock-containing firmware images or private captures.
