# mighty-nam roadmap

Updated 23 October 2026. Research entries are not released capabilities.

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

NAMLNK25 recorded and played a 30-second loop on the development plug; the owner
confirmed continuous playback with its original sound through three preset colors.
The [NAMLNK26 layers trial](tools/looper-prototype/layers/README.md) adds merged
layers across preset changes, phone transport/threshold/level, optional 60 seconds
at 12 kHz, armed LED blinking, hold-PRESET clear, direction reversal and POWER
mode gestures. New features have offline coverage; physical deadlines, gesture
behavior, 60-second fidelity and overdub listening remain the next trial.
The public builder does not yet include the looper. Recording is RAM-only, with
no undo or storage after power-off; playback currently feeds headphones only.

## Controller and longer-term work

- Physical iPhone transfer/reconnect and tuner cadence checks.
- Preserve the official capture picker, creator/license metadata and local favorites.
- Keep A2 Lite at 48 kHz; full A2 is unsupported.
- Further pitch/wah tuning, processing headroom and measured latency improvements.
- Dependable preset export/restore across updates.
- Independent startup/audio drivers and an updater with a demonstrated recovery contract.
- Ongoing third-party notices, service terms and distribution review. Do not publish
  complete stock-containing firmware images or private captures.
