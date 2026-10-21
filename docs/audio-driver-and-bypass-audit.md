# Audio scheduling and bypass research

This investigation follows the NAMLNK18 preparation. The development plug was
not accessed, muted, reset or flashed. NAMLNK17 remains the last physically
verified firmware; the verified NAMLNK18 update file is unchanged. Mac and Teams
audio were untouched. The new tail-sleep ELF is an **offline experiment, not an
update file**, and retains the baseline identity solely for the CPU harness.

## What the driver audit established

Executing the saved startup code confirms four 32-bit serial slots per frame,
16-word DMA bursts and two bursts per eight-frame interrupt. TX and RX FIFO
watermarks are both 16. The existing eight-sample setting removes additional
output staging but retains the protected previous-block handoff.

A separate discrete event model tests six FIFO/burst configurations and seven
startup phase assumptions. It follows NXP's documented TX request condition
(`entries <= watermark`) and RX condition (`entries > watermark`), from
IMXRT1170RM Rev. 5, section 58.3.6.1, pages 3476-3477. See the
[NXP manual](https://www.nxp.com/docs/en/reference-manual/IMXRT1170RM.pdf) and
[NXP SAI DMA driver](https://github.com/nxp-mcuxpresso/legacy-mcux-sdk/blob/main/drivers/sai/fsl_sai_edma.c).

In the synchronous, instantaneous-DMA model, changing FIFO depth alone changes
the refill deadline, not the delay of the serial labels. Publishing the current
DSP result instead of the previous result can remove eight frames (0.167 ms at
48 kHz), **only when publication precedes every TX read**. Longer synthetic DSP
times produce mixed old/new blocks with the current FIFO configuration. This
supports retaining the early protected output that fixed the earlier bitcrushing.

The model's nominal 0.5 ms serial-label age is **not measured input-to-headphone
latency**. Startup phase changes that prediction. Bus arbitration, DMA service
time, serial-slot phase, interrupt entry/preemption and converter filtering are
excluded. A zero TX watermark is only an idealized bound without FIFO reserve
at request time, not a suggested hardware setting. Full results and negative
cases are in [scheduling evidence](../evidence/latency-driver/audio-scheduling.json).

## A compiled bypass prototype

Fresh unused effects already sleep. Previously used delay and reverb continue
processing indefinitely in the release implementation to preserve residual
state. Freezing this state directly can replay old echoes when re-enabled.

The experimental dispatcher instead:

1. Runs the stock bypass transition for 1,198 blocks, stopping two blocks before
   the existing 1,200-block output settling period finishes.
2. Copies dry stereo input while the bypassed delay/reverb sleeps.
3. On re-enable, queues the stock type-change loader, which clears effect history
   and initializes the selected type in the foreground. Existing switching
   settling and output protection remain in place.

This is intentional **hard bypass with reset**, not preserved spillover. It
does not add a new physical mute command. The gate's keepalive policy is unchanged.
The prototype adds 140 linked code bytes and no RAM. It fits the existing
regions, but changes hot-code placement; preserving the verified NAM layout is
an explicit requirement before promotion.

### Isolated reset screen

The actual stock callbacks and loaders were exercised for all five delay types
and six reverb types at two parameter fixtures each: **22 cases**. Each had one
second of input history, 200 ms of bypass and a 250 ms wake observation. A naive
freeze retained old output in the fixtures. Reset produced silence after the
existing settling window in all cases. Analog Delay had a brief post-reset
transient before that window ended; it must not be exposed by shortening the
settling period. The loaders clear 256 KiB, so their real foreground cost still
requires measurement.

This screen drives policy from Python while executing the actual stock ARM DSP
and loaders; it is distinct from the compiled dispatcher test below. Results:
[reset screen](../evidence/latency-driver/tail-reset.json).

### Full IRQ and chain test

The compiled prototype executes the actual IRQ, NAM, stock DSP, foreground
loaders and output protection. It passed delay/reverb bypass, type changes while
asleep, re-enable with different types and repeated rapid switching. Memory
guards, DMA-half guards, finite output and fault checks passed. The initial
enabled Digital Delay + Spring chain matched baseline PCM exactly over 2,400
frames per channel.

| Settled chain/history | Baseline instruction events / 8 IRQs | Prototype | Reduction |
| --- | ---: | ---: | ---: |
| NAM + Spring after bypassing used delay | 471,306 | 451,426 | 4.22% |
| NAM only after bypassing used delay and reverb | 471,259 | 394,847 | 16.21% |
| NAM only after rapid switching | 466,996 | 394,927 | 15.43% |

These are emulator instruction events, **not measured cycles, CPU-load
percentages or headphone latency**. The prototype adds a small instruction cost
with both effects enabled. The compiled fixtures cover Digital Delay/Spring and
waking Pan Delay/Damp; all-type compiled-chain coverage remains to be done.
Results: [compiled test](../evidence/latency-driver/compiled-tail-sleep.json).

## Capture response checks

An independent host reference processed three captures at three input levels,
subtracting a matched zero-input run to remove bias. Four known-delay fixtures
checked the response analysis. In the Fender capture, the first response above
the chosen relative -60 dB threshold was at sample 1-2, while the largest
excursion was at sample 21 (0.438 ms at 48 kHz). Thus this probe did not find a
long initial silent interval in that capture. Marshall and BE100 responded at
sample zero under the same threshold criterion.

Peak time and energy centroid describe nonlinear, level-dependent response
shape; they are not uniform buffering delay or a perceptual latency measurement.
No captures were edited. Results: [capture response](../evidence/latency-driver/capture-response.json).

## Next engineering step

The bypass prototype is promising for processing headroom. Before it becomes
installable, preserve NAM hot-code/table placement and test all effect types in
the compiled dispatcher, saved presets, cold/warm startup, live-control races and
fault cases. Then measure real IRQ and foreground load costs with the same
capture and effects. Do not promise a latency improvement from instruction counts.

For a shorter audio handoff, first add a read-only diagnostic snapshot at IRQ
entry and output publication: DWT counter/reset epoch, RX/TX DMA cursor and
iteration count, FIFO read/write pointers and error flags. Record coherent
samples without changing clocks or stopping audio. Their actual phase and worst
publication margin determine whether a different handoff is feasible. An
electrical input/output measurement is still needed for total latency; software
counters and USB timing cannot substitute for it.

No extra flash is necessary to use the currently installed plug. NAMLNK18's
global buffer work remains separate from these research results.

## Reproduction

Use the private, exact stock payload, prepared NAMLNK18 ELF, permitted captures
and existing host-reference library. These tools use local files and virtual
peripheral memory only; no stock firmware, captures, backups or generated ELF is
committed here.

```sh
python3 firmware/research/audit_audio_scheduling.py STOCK ELF SCHEDULING_REPORT
python3 firmware/research/probe_tail_reset.py STOCK ELF MODEL RESET_REPORT
python3 firmware/research/experiment_tail_sleep.py NEW_EXPERIMENT_DIRECTORY
python3 firmware/research/test_tail_sleep.py STOCK ELF EXPERIMENT_ELF MODEL CHAIN_REPORT
python3 firmware/research/probe_capture_response.py REFERENCE_LIBRARY RESPONSE_REPORT MODEL1 MODEL2 MODEL3
```

Source and input hashes, scope and limits are recorded in
[the evidence manifest](../evidence/latency-driver/manifest.json).
