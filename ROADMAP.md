# Roadmap

## Next task — TONE3000 on the phone controller

Bring TONE3000 sign-in, capture browsing and favorites, compatible A2 Lite selection, and verified model transfer to the GitHub Pages controller used in Bluefy. Selecting a capture should make it the active NAM model after a successful transfer; saving it into a colored onboard preset remains explicit. Investigate browser authentication and bounded Bluetooth transfer before promising direct-to-plug loading. Requested as the next feature after the High / Low Cut EQ addition; not implemented in NAMLNK14.

## Further goals

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

## High / Low Cut EQ — prepared for NAMLNK14

The user explicitly moved this ahead of TONE3000. The EQ addition passed offline release checks and is packaged for a physical trial; see [trial notes](docs/high-low-cut-trial.md). Physical installation and listening tests remain separate. TONE3000 on the phone controller remains the next requested feature after this addition.
