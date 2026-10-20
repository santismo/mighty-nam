NAMLNK10 physical preset checks — development tool

Compile with the current app NamMidi.swift and NamLinkWire.swift plus both
Swift files in this directory. No Mac audio API is used.

--validate checks local plan/model inputs without touching the plug.
--save-empty writes the requested empty onboard slots, recalls each, checks
readback, and tests an unchanged save. It never overwrites an occupied slot.
--verify reads and recalls occupied slots without any save or model upload.
An optional expectedHeader in each plan binds the complete256-byte metadata
from a previous run, including all128 effect bytes, for post-restart comparison.

This is the focused development-unit test for the previously checked Fender
and Marshall captures, not a general user importer. Private capture weights
and personal plan inputs are not included. Each plan identifies a zero-based
slot, name, validated local model trace prefix,8/16/32 output buffer, bounded
stock controls and nine-block order. The helper validates model frames first.

Physical use requires the plug in normal USB mode with headphones unplugged.
Saved presets have boot-play enabled; the helper explicitly mutes the plug
before changing/recalling them. A user must perform and report any power cycle
or physical button steps; the script cannot do or prove those steps itself.
The evidence summary combines those reports with exact pre/post metadata and
model/status checks. Generic raw run flags refer only to script actions.

Initial0.3.0 Mac receive code truncated variable-size CoreMIDI replies. Use
0.3.1 sources. The firmware itself was not replaced during the successful
save/recall/restart trial. See evidence/10-physical-persistence-summary.json.
