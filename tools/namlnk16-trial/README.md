# NAMLNK16 physical trial tools

These bounded development tools use the production USB MIDI transport. They do not flash firmware, reset the plug, enable headphone output, open host audio streams or change system audio. Physical tests explicitly mute the plug. Saved presets can still play after restart when their startup flags are enabled.

Compile on macOS from the repository root:

```sh
python3 tools/namlnk16-trial/build.py work/namlnk16-trial
```

Compilation does not access a device. The compact-tuner adapter checks exact production insertion points and the NAMLNK16 identity.

- `restore --validate PLAN REPORT` checks the seven private records and Fender/Marshall capture traces without USB access. `restore --restore PLAN REPORT` requires exact NAMLNK16 and an empty bank, restores and independently reads all records, recalls seven colors, checks compact quiet tuner transport, and leaves Green muted. This importer is specific to the verified development-unit backup: all seven saved records must have startup playback enabled. It refuses an occupied bank. It is not a generic preset converter.
- `timing NAMLNK15|NAMLNK16 REPORT` reads the active capture and chain, explicitly mutes output, sets eight samples, bypasses FX A/B, and gathers 24 whole-IRQ snapshots for NAM only, NAM plus spring, and NAM after bypassing spring. It then restores the original 128 stock bytes, FX A/B and buffer and stays muted. No presets are saved. Input and effect history are uncontrolled; the report does not prove a deadline or measure acoustic latency. Run it on the same capture and with headphones unplugged and other controllers disconnected.
- `verify-restart PLAN REPORT` is a readback check after a manually confirmed power and seven-color button cycle. It requires NAMLNK16, verifies the saved records against the plan and mutes output. Its user-reported button-cycle field is a prerequisite, not an automated button observation.
- `compact-wire-test FRAMES.json` runs entirely offline against actual ARM-generated compact-tuner request/reply pairs and verifies corruption/nonce rejection.
- `python3 compare_timing.py BASELINE15.json CANDIDATE16.json REPORT.json` compares the recorded last-call counters after requiring matching capture, effects and eight-sample settings. It reports observed cycle changes without claiming acoustic latency or worst-case deadline coverage.

Keep models, trace files and restore plans outside the repository. Resolve relative trace prefixes before validation. See [trial evidence and limitations](../../docs/nam-performance-trial.md).
