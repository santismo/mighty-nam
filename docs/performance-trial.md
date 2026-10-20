# NAMLNK11 performance trial

This trial is prepared offline, not installed or measured on hardware. The development app is 0.3.3; the installed local app remains 0.3.2. The repository is private and GitHub Pages is disabled.

## Changes

NAM preparation now reads an in-range address for each 32-byte cache line containing its next eight frames' working set. All preparation call sites remain in place. It preserves the model state and active processing math. Across the tested old/new ARM executions, preparation uses at least 83.59% fewer model-memory reads and 67.36% fewer instruction events. These percentages do not describe active NAM, the whole chain, or elapsed hardware time.

An opt-in profiler selects one effect stage per block. It is off at boot. Existing effect dispatch and bypass policy remain in place for unselected stages. The selected path executes the same policy and callback, records raw DWT cycles, and rejects disabled/reset/ambiguous counter spans. Measurements add overhead and exclude surrounding routing fades and interrupt release latency. See the [wire contract](../spec/performance-v1.json).

The existing 48 kHz rate, eight-frame processing, 8/16/32 output staging, prior-block output schedule, output protection, seven-preset bank and stock tail behavior remain unchanged. Used gate, delay and reverb blocks are not force-suspended. Further suspension work needs evidence about residual audio and state on wake-up.

## Validation

- 24 old/new cache-coverage cases preserve model state, including wrapped histories.
- 33 actual-stock-chain comparisons preserve PCM with each stage selected while enabled, bypassed and resumed.
- 138 synthetic-counter cases cover ABI, wrap, reset, disabled counters, saturation and bounded snapshot retries.
- Seven stored presets, stock button wrap, cold/warm restarts and two captures through the stock chain pass in the ARM harness. Same-input NAM error is zero for the tested samples.
- NAMLNK10 rebuilds identically. The receiver, codec, output, whole-IRQ recorder and preset-storage object files match the original build.
- 53 distinct app tests pass, plus one optional skipped interop test; 1,565 native wire checks pass. Mac release compilation and signature checks pass.

These are offline checks, not physical clock, cache, storage, audio-deadline or recovery proof. Evidence is under [evidence/namlnk11](../evidence/namlnk11).

## Local build and packaging

Use the existing firmware build command with all NAMLNK10 options and add `--performance`. The resulting identity is NAMLNK11. The additional research entry points are `test_performance_prime.py`, `test_effect_profiler.py`, `test_effect_profiler_math.py` and `check_performance_placement.py`; each accepts explicit paths and has `--help`. Existing `test_preset_runtime.py` and `test_preset_native_wire.py` accept both preset firmware versions.

`tools/stage_performance_firmware.py` requires the exact user-provided stock package, final ELF and matching reports for preparation, profiling, counters, runtime, placement, controller and preset wire. It validates image changes and record boundaries before creating a local update file. Failed or mismatched evidence does not create an image. No stock or combined firmware is included in this repository.

## Hardware trial sequence

1. Reconnect in normal mode with headphones unplugged. Read the current seven preset headers and verify a matching local capture for each stored SHA. Preserve unsaved app edits separately. Earlier plans are not a current backup.
2. Install the prepared 0.3.3 app and use the official updater for the checked NAMLNK11 image. **The firmware update clears the onboard preset bank.** Restore from the verified local copies afterward.
3. Begin muted, verify model identity and faults, then measure one stage at a time alongside whole-IRQ timing on the same presets. Include switching and re-enabling cases. Disable the profiler afterward.
4. Compare actual timing before deciding whether to change tail suspension, active NAM kernels or driver buffering. Measure guitar-to-headphone latency separately.

No full bootloader backup exists; stock recovery still depends on reaching the loader. NAMLNK11 recovery has not been demonstrated. Current packaging does not constitute an instruction to flash before the backup check.
