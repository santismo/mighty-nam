# NAMLNK13 diagnostic helpers

These are the bounded USB helpers used for the initial development-unit trial. They use CoreMIDI only, require exact NAMLNK13 identity, and never open an audio stream, enable output, reset the plug or flash firmware. `NamMidiFx.swift` is the trial copy of the native transport with the NF exchange added; do not compile it alongside the production `NamMidi.swift` (both define `NamMidi`).

From the repository root on macOS:

```sh
mkdir -p work/namlnk13-trial
swiftc -O app/plugins/nam_device/macos/Classes/NamLinkWire.swift \
  tools/namlnk13-trial/NamFxWire.swift \
  tools/namlnk13-trial/NamMidiFx.swift \
  tools/namlnk13-trial/physical_helpers.swift \
  tools/namlnk13-trial/read_fx.swift \
  -o work/namlnk13-trial/read-fx
```

`read-fx REPORT.json` reads identity, status, stock settings and both FX slots. It expects the initial bypassed defaults and an already-muted plug. It fails if those preconditions differ; failure is not proof of faulty firmware.

For the mutating chain trial, replace `read_fx.swift` with `chain_trial.swift` in the compilation above and name the output `chain-trial`. Its arguments are `TRACE_PREFIX REPORT.json`. The prefix must identify a local `.slot`, `.json` and `.requests` trio from the verified 8192-byte A2 Lite packing/transfer workflow; these private capture files are not included here. The helper validates model format, checksums and every transfer frame before touching the plug.

The chain trial requires an empty bank and muted output. It changes live settings, uploads the provided capture, runs short effects/order trials, and saves one new Green preset named Fender A2 Lite with startup output muted. This name refers to the specific capture used in the recorded trial; this is not a general preset manager. It does not back up or restore an older bank. Run only for an explicitly authorized hardware trial, with headphones unplugged and other controllers disconnected. Merely compiling or running the wire check below does not access hardware.

```sh
swiftc -O tools/namlnk13-trial/NamFxWire.swift \
  tools/namlnk13-trial/wire_test.swift -o work/namlnk13-trial/wire-test
work/namlnk13-trial/wire-test tools/namlnk13-trial/fx-wire-golden.json
```

The wire check compares requests against recorded controller frames and rejects malformed requests/replies. The physical summary is in `evidence/namlnk13/physical-summary.json`; these short muted runs do not establish listening quality, calibrated latency/deadlines, or restart/recovery behavior.
