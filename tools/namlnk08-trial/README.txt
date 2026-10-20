NAMLNK08 physical trial helpers — prepared, not run on hardware

Compile with the current production NamLinkWire.swift and NamMidi.swift.
prepare_fender --validate|--run TRACE_PREFIX REPORT
listen_fender --inspect|--listen|--mute REPORT

--validate checks only local private Fender trace files. It does not connect.
--run refuses every identity except NAMLNK08, requires default mute and an
empty model slot after a normal restart, prepares NAM enabled / all stock
blocks bypassed, loads the verified Fender full amp+cab A2 Lite and observes
30 seconds while muted. All controls are volatile; original and prepared
128-byte preset snapshots are recorded. No reset, flash or preset save.
The current NAMLNK07 plug is intentionally not accepted.

The listening helper requires that exact Fender CRC/generation and NAM-only
preset. Use --listen only after the user's low-headphone-volume preparation.
It leaves output enabled after the observation; mute explicitly on poor sound.
Both helpers use CoreMIDI only. No host audio, Mac volume or Teams changes.
Private model data remain outside the source export.
