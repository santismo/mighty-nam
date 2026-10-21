# NAMLNK14 USB trial helpers

These bounded CoreMIDI helpers do not open audio streams, enable headphone output, change Mac audio settings, reset the plug or flash firmware. The mutating cut trial requires an exact NAMLNK14 identity, muted output and an empty preset bank before loading a validated local A2 Lite transfer trace. It refuses to overwrite an occupied bank. It leaves one newly saved Green preset, named Fender A2 Lite, with only NAM and High / Low Cut enabled, Low Cut 35 (about 77 Hz), High Cut 70 (about 8.07 kHz), buffer 8 and startup output muted. It does not restore old presets.

Compile from the repository root on macOS:

```sh
mkdir -p work/namlnk14-trial
swiftc -O app/plugins/nam_device/macos/Classes/NamLinkWire.swift   tools/namlnk14-trial/NamFxWire.swift   tools/namlnk14-trial/NamMidiFx.swift   tools/namlnk14-trial/physical_helpers.swift   tools/namlnk14-trial/cut_trial.swift   -o work/namlnk14-trial/cut-trial
```

`cut-trial TRACE_PREFIX REPORT.json` validates the local `.slot`, `.json` and `.requests` trio before device access. The trace used for this recorded trial is the licensed Fender Super Reverb 1965 A2 Lite capture; private capture files are not distributed. The preset name is specific to that trace, not a general library importer. Run only as an authorized physical trial with other controllers disconnected.

The trial checks independent Off, both cuts, extreme cut values, all four EQ types, move/bypass transitions, NAM plus stock effects and Pitch/Auto Wah, and independent save/read/recall of all 128 effect bytes. Failure attempts to leave output muted and custom FX bypassed. Controls change temporarily during the trial. It does not establish listening quality, real-guitar response, calibrated deadlines, Bluetooth behavior or power-off persistence.

`inspect.swift` can instead be compiled with the production `NamLinkWire.swift` and `NamMidi.swift` to perform identity/status reads only. `NamMidiFx.swift` is a trial transport based on the production NAMLNK14 transport with bounded NF commands; do not compile both NamMidi classes together.
