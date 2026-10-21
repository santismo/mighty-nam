# Current-block DMA prototype (offline only)

NAMDMP01 explores removing NAMLNK19's protected previous-block stage. It is a
separate experiment, not NAMLNK20 or an installable update. No device commands,
host audio, flashing, physical mute changes, or Teams changes are part of this
work. NAMLNK19 remains the usable installed version.

## What changes

The prototype renders the **current** stereo block after the stock chain, NAM,
master-volume smoothing, output protection, and the existing GPT timing check.
A DSB follows the renderer before the optional publication snapshot. The
previous-block renderer remains the default when the experiment flag is absent.

An explicitly opted-in, in-memory research image also changes the exact stock
instruction at `0x11aa0` from `movs r2,#16` to `movs r2,#8`. Executing stock
startup confirms that this changes only TX TCR1 at `0x4040400c`. RX stays at 16,
and the four DMA descriptors remain byte-identical: 64-byte minor transfers,
two transfers per eight-frame audio interrupt. Clocks, sample rate, codec
settings and interrupt routing retain the NAMLNK19 configuration.

The later TX request is intended to let the newly processed half finish before
the hardware fetches it. Lowering the watermark alone does not remove a block.
The combination could remove **eight frames, or 0.1667 ms at 48 kHz**, assuming
the handoff succeeds. It does not remove converter or effect-specific delay.

The 8/16/32 control still adds 0/8/24 frames of output queue. Processing contracts
remain eight frames. Increasing that queue does not grant more processing time.

## Validation and its limits

Completed evidence: [manifest](../evidence/dma-current-prototype/manifest.json),
[compiled ARM tests](../evidence/dma-current-prototype/arm.json),
[diagnostic tests](../evidence/dma-current-prototype/driver.json), and
[bus-model results](../evidence/dma-current-prototype/bus-model.json).

All 22 paired audio cases passed, covering more than 71,000 emulated audio
blocks including settling and fault cases. Four injected processing faults
prevented publication, and three RAM-fill patterns passed restart/reload.
The bus sweep found 197 working and 27 unsafe modeled timing combinations out
of 224. These are scenario counts, not a probability of reliability. Separate
negative controls detected all five deliberately unsafe boundary conditions.

The exact ARM comparison uses the established Fender and Marshall A2 Lite
fixtures, the actual stock chain and the installed NAMLNK19 ELF as its reference. It
checks identical protected float streams and identical settled integer PCM
shifted earlier by one block, at all three buffer settings. It exercises NAM,
Spring, Delay+Spring, used-tail bypass/wake, all stock blocks, two custom FX,
High/Low Cut and reordered chains. Real settling and fade execute in the harness.

Startup is checked from three dirty-RAM patterns and on repeated setup. A
separate diagnostic test checks both protocol channels, captures after current
publication, default-off behavior, bounded snapshots and warm restarts. Invalid
GPT configuration, zero/excessive processing time and nonfinite output must
prevent the renderer from being called. These are emulated faults: they do not
mute or otherwise contact the physical plug.

The bus model uses the actual compiled output-store order and explicitly varied
service delays, store spans and IRQ delays. Historical NAMLNK19 whole-IRQ durations
provide hypothetical completion times for seven recorded chain states. Those
are **not measurements of the new publication point**. CPU instruction indices
give ordering evidence only; they are not converted into M7 cycles.

The idealized serial-label ages of 95 and 63 words reproduce the earlier phase model
and differ by eight frames. Neither is measured guitar-to-headphone latency.
The model intentionally detects late publication, coincident fetch/write,
TX starvation, RX overflow and CPU overload. The test suite passes only if these
unsafe cases are detected. It does not mean the firmware would recover safely
from them on hardware.

The current-block prototype is **not ready to flash**. Its existing GPT guard
does not establish TX ownership or the earlier DMA fetch deadline. The final
render and DSB occur after that guard; the whole-IRQ diagnostic encloses them.
A partially fetched half can still contain gaps or inconsistent data. The new
publication snapshot provides an observation point, not a deadline interlock.

## Before a physical trial

Establish an appropriate deadline/ownership policy and a bounded fallback for
late blocks. Verify current-block publication margin, both DMA halves, startup
phase, heavy chains, effect transitions, bus contention and store visibility.
The lower watermark also leaves less FIFO reserve during delayed bus service.
Passing a lightweight chain does not establish the heavier chains' deadlines.

A separate, explicit hardware trial would then need to measure the candidate's
actual phase and completion margin. End-to-end latency still needs suitable
external analog measurement; this offline work cannot establish that number.

At the fitted phase with a one-word publication span, all seven historical
chain-time proxies pass without extra IRQ delay and with two additional word
times. All seven fail with eight additional word times in the instantaneous
service model. The finite-service variants differ because a delayed DMA fetch
also changes the available publication margin. A separate phase sweep passes
only offsets 0 through 5 out of 0 through 15 under its nominal inputs.
These boundaries are precisely why neither the FIFO setting nor the historical
processing times alone prove a safe handoff.

## Reproduce

Use [the offline runner](../tools/dma-current-prototype/README.md). Its inputs
are a privately held, hash-checked stock payload and permitted captures. It
builds the experiment as ELF only, never an updater container. The default image
builder rejects `NAMDMP01`; research tests must explicitly opt in. Existing
release packagers remain closed to this identity.

The NAMLNK19 rebuild must retain ELF SHA-256
`4c058e7d985897a3ef84f78881a98f0fff0aa9ee3d930347d158a3f0421ebbb0`.
The experiment uses the same audited section extents and unchanged DSP objects.
Only the audio callback grows, by eight bytes; subsequent low-code helpers and
their branch thunks relocate within the existing allocation.

See also [the preceding phase investigation](driver-phase-investigation.md).
