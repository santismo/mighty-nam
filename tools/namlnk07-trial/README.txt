NAMLNK07 first-boot / restart preflight

This uses the production Mac MIDI transport. It requires an exact NAMLNK07
identity, muted listening state, and empty model slot after a restart. It loads
one locally verified A2 Lite trace, observes 30 seconds, and confirms all 128
preset bytes unchanged. No effect changes, listening-arm command, audio API,
reset, flash or persistent save is present.

Only --validate has been run while preparing NAMLNK07. No NAMLNK07 physical
result exists yet. --run is for after installation and a normal restart.
A muted pass excludes the small armed Q31-rendering cost; follow it with a
controlled low-level physical listening/timing check. Never call it a complete
hardware deadline or acoustic-safety proof.

Compile physical_helpers.swift and restart_reload.swift with the current
Mac plugin NamLinkWire.swift and NamMidi.swift. Usage:
restart-reload --validate|--run TRACE_PREFIX REPORT

The private trace stays under work/ and is excluded from the source export.
