# Latency investigation after NAMLNK15

Follow-up: [NAMLNK10 comparison, bypass-history workload and NAM/converter experiments](latency-workload.md). The EQ comparison below is one hypothesis, not an established explanation of the reported feel.

The exact NAMLNK12 and installed NAMLNK15 builds produced bit-identical output in the offline comparison with the same Fender A2 Lite capture, 8-sample setting and two matched presets: NAM alone and NAM with stock Spring reverb. This rules out an added software sample delay in those tested cases. It does not establish physical headphone latency or rule out a hardware deadline problem.

Each of the four runs executed 1,350 actual settling/fade blocks followed by 384 comparison blocks (3,072 frames). Every compared callback rendered the previous protected eight-sample block, then processed and protected the current block. Additional output staging was zero. The NAM engine, output renderer and IRQ-timing object files are byte-identical across the two builds; the original stock audio IRQ body is preserved. Timing in the emulator is synthetic, so these are sample-order results, not CPU or converter measurements.

## What the buffer setting means

The working pipeline deliberately publishes the previous protected block before running the next NAM block. This has been retained since the NAMLNK08 correction that resolved bitcrushed playback. Moving output publication after NAM again is not justified without checking the physical transmit deadline.

At 48 kHz, eight samples span 0.167 ms. The 8 setting adds no further queue; 16 adds eight samples and 32 adds 24. Lowering sample rate makes a fixed-size block longer. A four-frame implementation would require coordinated driver and fixed-size DSP changes, and would reduce one eight-frame buffering stage by only 0.083 ms. It would not prove that the reported delayed feel is solved. No buffer, sample-rate or device setting was changed during this investigation.

## Low Cut comparison

The latest reported Green has Low Cut 35 (about 76.65 Hz) and High Cut 70 (about 8.07 kHz). An offline impulse test of the actual float filter, checked against an independent bilinear Butterworth response, gives:

| Frequency | Low + High Cut group delay | High Cut only group delay |
| --- | ---: | ---: |
| Low E, 82.4 Hz | 2.735 ms | 0.025 ms |
| A, 110 Hz | 1.739 ms | 0.025 ms |
| High E, 329.6 Hz | 0.192 ms | 0.025 ms |
| 1 kHz | 0.043 ms | 0.026 ms |

These numbers describe frequency-dependent phase/group delay, **not a uniform delay imposed on every sample**. Every filter configuration responds at sample zero; neither filter queues a block. Cutting bass also changes its level. The result makes Low Cut a useful listening comparison but does not establish that it explains the user's perceived delay. Both cuts Off produce exact unity with zero group delay in this test. Address and undefined-behavior sanitizer checks passed.

## Next physical comparison

Use the same Green Fender capture, 8-sample setting and a low headphone volume. Temporarily turn only Low Cut to Off, retaining High Cut and the other bypass states. Do not save during the comparison. Alternate with the original Low Cut value 35. If the delayed feel remains with NAM alone, compare bypassed NAM at the same level before changing the driver. Actual end-to-end measurement must include the input/output converters and transmit scheduling; a software impulse response cannot replace that measurement.

No preset writes, USB access, firmware packaging, flashing or host audio occurred. The plug's current mute state and saved bank were not changed. No lower-latency firmware is being claimed or offered from this audit.

## Reproduction

Run from the repository root with the exact locally retained builds, user-supplied stock payload and licensed model:

```sh
python3 firmware/research/test_latency_regression.py STOCK_PAYLOAD BUILD12 BUILD15 MODEL_NAM REPORT_JSON
clang++ -O2 -std=c++17 -Wall -Wextra -Werror -ffp-contract=off -fsanitize=address,undefined firmware/research/test_cut_eq_sample_delay.cpp firmware/target/link/cut_eq.cpp -o CUT_PHASE_TEST
```

Run the resulting `CUT_PHASE_TEST` executable to emit its JSON report. Python dependencies match the existing ARM harness. Exact input/build hashes are recorded in [comparison evidence](../evidence/latency-audit/regression.json); [filter evidence](../evidence/latency-audit/cut-phase.json) includes source hashes. Captures and stock firmware are not distributed.
