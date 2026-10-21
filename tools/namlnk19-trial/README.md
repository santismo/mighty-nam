# NAMLNK19 physical checks

These bounded Mac tools reproduce the recorded test. They do not flash firmware, open a host audio stream or send explicit mute commands. Run only for an authorized physical test with headphones unplugged, the plug in normal mode, and other controllers disconnected. They are not a background monitor.

`python3 tools/namlnk19-trial/build.py OUT` compiles tools only. Keep `timing` and `mpp_driver_client` together. The recorded local trial used the same sources except that the timing collector originally had a task-local relative path; the portable version locates it beside its executable.

- `OUT/inspect REPORT`: read identity/status only.
- `OUT/restore --validate PLAN REPORT`: validate private model traces and seven-color restore plan without MIDI access. For NAMLNK19 normalize every planned buffer and header word at offset 24 to the selected global value, eight in this trial; retain the original backup separately.
- `OUT/restore --restore PLAN REPORT`: requires exact NAMLNK19 and an empty bank. Restores the seven private records, validates every stock/extra-FX field, then enables Green playback. Model transfer, save and recall still have their existing temporary settling. Stops on a failed check without sending mute. There was no fresh backup before this installation; the recorded test used the checked bank preserved for NAMLNK17.
- `OUT/timing NAMLNK19 REPORT`: requires a healthy loaded capture and output enabled. Measures seven minimal-chain/bypass/wake states, with 24 IRQ snapshots and 12 driver captures each. Restores original volatile stock effects, extra FX and buffer. No preset save or explicit output command. Keep the requested buffer at eight to avoid unnecessary settings writes.
- `OUT/global PLAN REPORT`: switches global 16 then 8, recalls every saved color at each value and checks playback remains on. Writes the global settings sectors, not preset records or firmware. Finishes on Green/eight.
- `OUT/verify-restart PLAN REPORT`: read-only verification after the user confirms a POWER-only restart and seven physical button presses returned to Green. Verifies every saved header and FX record, startup output and global eight. Do not run it as evidence of physical button use without that user report.
- `OUT/driver-header --header`: read-only check that the diagnostics are idle with generation zero after restart. Does not arm tracing.
- `OUT/mpp_driver_client --capture`: explicitly arm and read one diagnostic; decode offline with `firmware/research/decode_driver_timing.py`.

Restore plans, captures and raw backup records stay private local inputs and are not distributed. Results are in `evidence/namlnk19/physical-summary.json` and the adjacent raw timing observations. Sequential register snapshots and raw cycle counts do not establish analog latency or worst-case deadlines. No diagnostic changes CPU clocks, DMA descriptors or FIFO settings.
