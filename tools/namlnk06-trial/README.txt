NAMLNK06 controlled silent test runner

Prepared for a later authorized physical test. It has NOT been run against
the plug. Files-only validation passed. The controller transport is shared
with the Mac app: plugins/nam_device/macos/Classes/NamLinkWire.swift and
NamMidi.swift. Build those two files with physical_helpers.swift and
physical_chain.swift using swiftc; no audio frameworks are used by the test.

--validate FIRST_TRACE SECOND_TRACE REPORT validates the two private transfer
traces without enumerating MIDI devices or sending any messages. Each prefix
requires .slot, .json and .requests files. Captures are not distributed here.

--run is a separate, explicit physical-device action. Do not use it until the
user authorizes the trial and NAMLNK06 is successfully installed/restarted.
It requires exact NAMLNK06 identity, clean timing snapshots, advancing IRQ
counts, the existing <150-tick DSP guard, acknowledged model transfers and
verified volatile controls. It restores all 128 original preset bytes after
its test or an ordinary failure while the plug remains responsive.

The first trial uses the plug's existing effect types and settings, then
reorders and toggles NAM and swaps two A2 Lite models. The heavier settings
are tested offline; they are NOT part of this initial hardware script.
Raw IRQ cycles are recorded without converting to microseconds or claiming
a complete hardware deadline. Hardware exception/release latency and some
measurement-wrapper work remain outside the timestamps.

No firmware writer, reset command, preset-save command, host audio stream or
Mac/Teams audio-setting change is implemented. The firmware still supplies
zero output. Models remain RAM-only and disappear after a restart.
