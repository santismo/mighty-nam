# mighty-nam roadmap

Updated 22 October 2026. Roadmap entries describe work still needed, not promised capability.

## Next hardware trial

- Install NAMLNK22 only when requested. Its local image includes the owner's seven Mac-saved presets; no factory capture bank is distributed.
- Verify pitch/octave listening and sustained deadlines with both FX blocks, NAM, reverb and active USB audio. Test attacks, bends, neutral shifts and bypass transitions.
- Verify Logic Pro stereo input/output, recording gain and host-return isolation at 48 kHz. The repair passes offline PCM checks; physical duplex remains pending.
- Confirm seven colors, captures and effect settings survive power-off on this exact build.
- Measure actual analog guitar-to-headphone latency. Instruction counts and output-buffer values are not that measurement. The DMA deadline prototype is still excluded.

## Phone and Mac follow-up

Phone control, TONE3000 browsing, A2 Lite transfer, live edits, tuner and seven-color saving are implemented. Continue physical iPhone transfer/reconnect and tuner cadence checks. Keep the official picker open while auditioning captures and preserve creator/license metadata. Full A2 is not supported. A native iPhone app is not currently planned for the immediate milestone.

## Standalone looper

Hold PRESET while powered on to arm, start recording at an input threshold, then tap to finish and repeat. Preserve the updater's power-on gesture. Audit memory and CPU budget first, then implement temporary loops with pre-roll, LED feedback and a clear exit. Duration, overdubbing and permanent storage are undecided; no looper is implemented yet.

## Longer term

- More processing headroom and measured latency improvements without losing USB recording.
- A dependable preset export/restore path across firmware updates.
- Further pitch and Auto Wah quality work based on physical listening.
- Independent startup/audio drivers and an updater with a demonstrated recovery contract.
- Distribution review: third-party notices/source availability, TONE3000 design requirements and any permission needed for wider product release. Do not distribute stock firmware or creator captures in installers.
