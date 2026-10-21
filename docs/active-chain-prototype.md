# Active-only signal chain — offline prototype

`NAMACP01` replaces the fixed eleven-stage audio dispatcher with a cached list
of active nodes. With only NAM and reverb enabled, that list contains two effect
processors. Removed effects receive no audio callback, no bypass-buffer copy and
no per-node routing work during steady playback. This is a firmware change, not
just a display filter.

The effects remain available as a compiled library, with their existing static
state allocations. Adding an effect inserts it into the execution list; removing
it takes it out. This does not yet support multiple instances of every stock
effect. The nine existing stock categories and two custom FX slots remain the
available inventory. Necessary input/output conversion, volume, protection,
tuner and driver work still exist outside the effect graph.

## Compatibility and behavior

- Existing enabled bits and order encode graph membership. Preset storage does
  not need a new format. The firmware rebuilds the graph at an audio boundary
  when that membership or order changes.
- A NAM + reverb preset has two nodes; an empty graph with a valid loaded preset passes dry audio through the existing
  volume and output protections.
- Both independent custom FX slots participate at their chosen positions. All
  seven custom FX modes retain their original processors.
- Invalid topology is rejected before the stock routing manager indexes its
  descriptors. It produces zero graph output rather than running a stale plan.
- Used delay/reverb state is reset when those effects are added again. Removing
  an effect is a hard removal, not a request for continuing reverb/delay tails.
- Original stock transition gain placement is retained while a routing fade is
  active. At unity, those gain loops do not execute. Existing control settling
  remains; custom FX membership/position changes also settle before playback.

This experiment preserves the installed NAMLNK19 driver, 48 kHz rate,
eight-frame processing block and previous-block output handoff. Its 8/16/32
control has the same meaning as before. It does **not** include the separate
current-block DMA experiment. In the recorded emulator trace, NAM + spring used
53,259 instructions versus 56,435 for NAMLNK19 (5.63% fewer), with identical
tested settled output. Fewer executed instructions are not a physical
latency measurement; the input-to-output schedule can stay the same despite a
lower processing cost.

## Offline validation

The native planner test covers 450,560 combinations under AddressSanitizer and
UndefinedBehaviorSanitizer: every stock membership mask, both custom FX enable
states, every distinct pair of FX positions, and forward/reverse stock orders.
It also checks the original routing-fade positions and rejects invalid input.

The compiled ARM test executes the actual NAM and stock effects, observes real
callback entries, compares the settled output with NAMLNK19, checks an independent
NAM reference, and exercises removal, insertion, reordering, all seven custom FX
modes, an empty chain, invalid topology, restart and a saved two-block preset.
Its stock callback writes are permitted only inside the explicit 128-byte audio
scratch; all other reclaimed-RAM guards remain enabled.

The recorded validation is split into completed DSP/transition checks and a
separate corrected storage check against the same ELF. The first combined test
fixture omitted the deferred foreground bank service before saving; its log is
preserved with the evidence. The maintained runner initializes that service
correctly. No firmware change was needed for that test setup correction.

Results and exact ELF identity are recorded in
[the evidence](../evidence/active-chain-prototype/arm.json). Instruction counts
come from the emulator and must not be interpreted as Cortex-M7 cycles. Tests
use a bounded set of settings and a privately held permitted A2 Lite capture.
They do not establish every possible effect combination, physical timing,
click-free transitions or headphone sound quality.

The image builder requires `allow_active_prototype=True`; normal packaging
rejects this identity. No updater file is produced. The code and RAM stay inside
the previously audited allocations. Optional per-effect profiling and one-shot
DMA snapshots are omitted to make room; whole-IRQ timing remains. Pages 118–123
report graph telemetry under a prototype-specific marker, not the old snapshot
format.

## Controllers and next physical trial

The intended interface is **Add effect / Remove**, backed by this active graph.
Phone and Mac release UIs must not label an operation as true graph removal on
older firmware that still uses the fixed dispatcher. No controller or Mac app
release advertises this prototype yet.

Before enabling it in a release: measure whole-IRQ time on the plug, verify
startup and saved preset changes, check removal/re-add behavior with real
headphone listening at a controlled level, and verify capability/readback in
both controllers. Then expose the compact chain in those controllers. Neither
this experiment nor the DMA experiment has been flashed by the offline runner.
