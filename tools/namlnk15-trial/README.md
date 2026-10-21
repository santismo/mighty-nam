# NAMLNK15 physical trial sources

These are the bounded helpers used for the recorded development-unit restoration and checks. They do not flash firmware, reset the plug, enable headphone output, open host audio streams or change Mac audio settings. They do explicitly mute the plug. Saved presets retain their authorized startup-playback flags, so a later restart can enable plug output.

Compile from the repository root on macOS:

```sh
python3 tools/namlnk15-trial/build.py work/namlnk15-trial
```

Compilation does not run a device test. The builder derives a narrow NU3/4/5 compact-tuner adapter from the production CoreMIDI transport and refuses changed insertion points. The Mac app continues using its production transport.

- `restore --validate PLAN REPORT` validates the seven local model traces and saved records without USB access. `restore --restore PLAN REPORT` requires exact NAMLNK15 and an empty bank, restores seven records, independently reads and recalls them, and checks 15 compact quiet-input readings. It is intentionally specific to the previously verified Fender/Marshall traces and the chosen seven-color plan, not a generic importer. It refuses an occupied bank. Private traces and the user's restore plan are not included here.
- `fx-check REPORT` requires the verified Green Fender capture, temporarily enables Tremolo and Auto Wah, moves and bypasses them, then restores the original FX configuration. It does not write presets.
- `verify-restart PLAN REPORT` reads the seven stored headers and FX records after a manually confirmed restart/button cycle, compares them with the authorized plan, reads Green's live chain and mutes output. It does not write presets. Its `userReportedSevenColorButtonCycle` field records the manual prerequisite, not an automated observation of the button.
- `compact-wire-test FRAMES.json` is offline and checks actual ARM-generated request/reply fixtures plus corruption and bounds rejection.

The local backup uses trace prefixes relative to its directory; run file validation from that directory or resolve the prefixes explicitly. Do not place captures or backup plans in this repository. Keep headphones unplugged and other controllers disconnected for an authorized physical trial. The trial helpers contain no automatic update workflow.

See [physical results](../../evidence/namlnk15/physical-summary.json). Quiet USB tuner timing is not Bluefy cadence or real-note accuracy; successful controls do not measure guitar-to-headphone latency.
