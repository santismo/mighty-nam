# Roadmap

## Next goals

### Standalone looper

Hold PRESET while already powered on to arm a loop; start recording at a guitar-input threshold, retain a short pre-roll so the first note is not clipped, and tap PRESET to finish and start playback. Provide clear LED feedback, stop/resume, and an exit gesture that restores preset selection. Keep the power-on updater gesture intact.

First milestone: audit usable RAM and time a bounded record/playback engine alongside NAM and stock effects. Start with a temporary loop lost at power-off. Maximum loop length, compression, overdubbing, and permanent recording storage are undecided. No looper is implemented in the current release.

### Phone control — iPhone first

Bring capture browsing, favorites, chain editing, and colored preset management to iPhone. Determine which Bluetooth services can carry custom NAM commands and model transfers, and investigate wired MIDI support. Desktop CoreMIDI and shared protocol code are a starting point; they do not establish iPhone compatibility or Bluetooth model transfer.

First milestone: validate discovery, authentication, a bounded status/control exchange, and a model transfer on real iPhone hardware. No release date or App Store delivery is promised.

## Hardware validation before calling onboard presets ready

- Install and identify NAMLNK10, verify empty-bank mute.
- Save multiple distinct captures and effects, check independent readback.
- Power off, close the Mac app, restart and verify standalone recall.
- Exercise all seven button/LED colors, wrap and empty-slot skipping.
- Check timing under heavy effects, repeated switching, USB, and updater return.

## Further development

- Improve CPU headroom and quantify actual end-to-end guitar latency.
- Preserve/export/restore the onboard bank across firmware updates.
- Additional custom effects and an independently bootable firmware backend.
- A guided updater only after its recovery contract is demonstrated.

Roadmap entries describe intent, not existing capability. Contributions should include test evidence and distinguish hardware observations from simulation.
