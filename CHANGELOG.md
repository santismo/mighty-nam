# Changelog

## NAMLNK18 / Mac 0.3.10 / phone 0.6.5 — prepared global-buffer trial

Persist one output-buffer choice for every color, defaulting to 8 samples. Ordinary successful edits preserve playback intent, and captures/effects are not rewritten when the global buffer changes. Restore exact NAMLNK16 NAM hot-code and constant-table placement while retaining the 17 converter setting. Firmware, controller and simulated-browser checks passed; this version has not been flashed or physically timed. See [trial notes](docs/global-buffer-trial.md).

## NAMLNK14 / Mac 0.3.6 / phone controller 0.5.0 — High / Low Cut

Add stereo 12 dB/oct High / Low Cut as a movable EQ choice, with independently disabled filters and logarithmic cutoff controls. Retain stock EQ choices, two FX slots, presets and output buffering. The new choice requires verified NAMLNK14; older firmware remains supported. Mac chain-library migration preserves existing settings. Installed on the development plug: bounded muted USB cut controls, movement/bypass, full-chain processing and a fresh preset save/read/recall passed. Listening and post-save power-off checks remain. See [EQ trial notes](docs/high-low-cut-trial.md).

## NAMLNK13 / Mac 0.3.5 / phone controller 0.4.1 — experimental trial

Two independent movable FX slots, each with Pitch, Auto Wah, Chorus, Flanger, Phaser, Tremolo and Vibrato. Both persist with the seven onboard presets. Bluetooth preset/tuner replies are pulled in short numbered pages. Controller 0.4.1 exposes live controls and a second Enabled / Bypassed toggle below the chain; Mac 0.3.5 adds USB compatibility. NAMLNK13 is installed on the development plug. Bounded muted USB tests passed; one fresh Green Fender A2 Lite preset was saved and recalled. Bluefy status and current FX reads are confirmed by the user log. Listening quality, calibrated timing, phone save/tuner, power-cycle persistence and recovery on this build remain unverified. See [trial notes](docs/dual-fx-trial.md).

## 0.3.4 / NAMLNK12 — tuner and performance trial

- Add a USB MIDI chromatic tuner with reference A adjustment, note/cents display, muted input capture and explicit listening resume. No host audio streams.
- Include NAMLNK11 preparation and profiler changes; retain output scheduling, model math and the seven-color bank.
- Pass 60 Mac tests plus firmware, parser, pitch and restart checks. App and firmware installed locally. Seven presets restored/verified with no faults; quiet tuner transport passed. Real-guitar tuner accuracy and restart checks remain.
- Back up all seven current presets and matching captures before installation; the update clears the onboard bank.
- Restore stock amp metadata, patch level and tempo from verified backups before checking all 128 effect bytes and saving.
- Keep repository private and Pages disabled; the older hosted installer is unchanged.

## 0.3.3 / NAMLNK11 — prepared performance trial

- Add NAMLNK11 controller compatibility while retaining earlier versions.
- Reduce duplicate reads during NAM bypass/settling preparation, covering the same cache lines without changing model state or active processing math.
- Add a default-off, single-stage profiler with bounded USB commands, coherent snapshots and counter validity checks.
- Preserve the existing output path, 48 kHz rate, buffer options, seven presets and stock delay/reverb/gate tail policy.
- Offline checks pass; physical timing and latency gains remain unmeasured. The trial is not installed. Installation clears the onboard bank and requires a fresh verified preset/capture backup.
- Repository remains private; Pages remains disabled. No new hosted release asset is published.

## 0.3.2 — onboard listening

- Enable Listen for a verified saved onboard capture even when its model is absent from the Mac library; retain model identity and fault checks. Installed locally and confirmed working by the user.

## 0.3.1 — CoreMIDI packet storage

- Preserve replies longer than the fixed 256-byte Swift tuple by reading CoreMIDI's original packet allocation. Seven NAMLNK10 presets were physically saved and verified after restart and button cycling.

## 0.3.0-preview.1 — public project preview

- Publish Mac controller 0.3, firmware source/research, protocols, retained upstream licenses, and offline validation evidence.
- Add a Mac disk-image installer, user guide, developer guide, and GitHub Pages site.
- Seven colored onboard presets and 8/16/32-sample output staging are implemented in NAMLNK10 but await physical validation.
- NAMLNK08 remains the last firmware with observed live guitar listening on the development unit.
- Next goals: a standalone threshold-triggered looper and iPhone control.

The preview release does not distribute NUX stock or combined firmware images, private captures, or a ready iPhone app.
