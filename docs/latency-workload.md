# Minimal-chain latency and processing investigation

The user's earlier report that 8 samples felt good followed the NAMLNK12 installation. This investigation also includes NAMLNK10, which the user recalled as a possible good baseline. It found a useful NAM processing optimization and a separate converter-delay option, but has not established the cause of the reported slower feel. Everything here ran offline without USB or host audio access. NAMLNK15 remains the installed release.

## Did an older optimization disappear?

The active `A2Lite::process` code is byte-identical in the retained NAMLNK10, NAMLNK12 and NAMLNK15 objects. Its model RAM location is also unchanged. The later cache-line preparation improvement remains present; it prepares state during bypass or loading and does not change active NAM arithmetic. Output rendering and IRQ-timing objects are identical across these builds.

The new NAMLNK10-versus-15 comparison used the same Fender capture, 8-sample setting and two chains: NAM alone and NAM with Spring reverb. After 1,350 startup/settling blocks, all 384 comparison blocks per case had identical output. Both versions publish the previous protected eight-sample block with no additional output queue. The [earlier NAMLNK12 comparison](latency-audit.md) also passed. These results exclude an added software sample delay in the tested fixtures, not a physical transmit-deadline problem, capture-dependent behavior or converter delay.

## Bypassed effects can retain work

The offline profiler executed the actual ARM audio interrupt and counted emulator instruction events and stock effect callbacks. It observed eight blocks per case after settling. These counts are **not Cortex-M7 cycles, a CPU-load percentage, a worst-case bound or headphone latency**; cache, bus and interrupt timing are not modeled.

| Chain and history | NAMLNK10 mean events/block | NAMLNK15 mean events/block | NAM pointer experiment |
| --- | ---: | ---: | ---: |
| Fresh NAM only | 51,143.5 | 51,275.5 | 49,330.5 |
| NAM + Spring | 58,219.125 | 58,351.125 | 56,406.125 |
| Gate + NAM + delay + Spring | 61,902.375 | 62,034.375 | 60,089.375 |
| NAM + Spring after bypassing used gate/delay | 61,925.625 | 62,057.625 | 60,112.625 |
| NAM only after bypassing used gate/delay/reverb | 61,926.25 | 62,058.25 | 60,113.25 |

Fresh bypassed compressor, drive, EQ, modulation and cabinet callbacks were skipped. NAMLNK15's idle FX A/B dispatch shortcut was also effective. However, previously enabled gate, delay and reverb retain their callbacks indefinitely through `mpp_bypass_hold == 65535`. That policy preserves stock residual/tail state and was already present in NAMLNK10.

In this sequence, returning to NAM + Spring after using gate/delay leaves about 6.35% more instruction events than the fresh chain. Returning to NAM alone leaves about 21.03% more. The new features add only 132 events per observed interrupt relative to NAMLNK10. All five histories have equal corresponding output hashes across versions and the pointer experiment.

This is a worthwhile workload target, but callback work does not automatically add sample latency when the deadline is met. No tail policy was changed. Suspending used effects requires checking decay, feedback, wake/reset behavior and switching artifacts; simply clearing the hold flag would not establish correctness.

## Tested NAM optimization

The experiment advances a pointer through each convolution history ring instead of recalculating its address for every tap. It preserves weight order, floating-point operations and non-fused accumulation. The active function grows by 12 bytes and fits its existing region; model RAM and the output publication order stay unchanged.

It removes 1,945 emulator instruction events per observed block: **3.79% for NAM alone and 3.33% for NAM + Spring**. Separate Fender and Marshall comparisons produced identical output for both chains, with memory guards intact and no simulated processing faults. Each comparison used 1,350 warmup blocks and 384 measured blocks per version and case. This is evidence for less instruction work, not a measured hardware speedup or latency reduction.

`experiment_a2_pointer_taps.py` builds from an isolated source copy. Production DSP source is unchanged. Its ELF retains the baseline identity solely for the CPU harness, is marked `OFFLINE_EXPERIMENT_NOT_INSTALLABLE`, and has no release identity or flash container. It is **not an update file**. Full release checks, real CPU timing and transmit-deadline validation remain required before promotion.

## Converter option without changing sample rate

Offline stock startup writes `0x00` to ADC-filter register `0x0A` and `0x0A` to DAC-filter register `0x14`. Interpreted as AK4619 settings, these select normal sharp ADC filtering and already-short-delay sharp DAC filtering. AKM specifies ADC delay of 22 sample periods versus 8 in short-delay sharp mode at 48 kHz: a nominal reduction of **0.292 ms**. Both have the same specified passband, but phase differs; short mode has up to 2.6 sample periods of group-delay variation over 0–20 kHz. See the [AKM datasheet, pages 13, 15, 48, 52, 64 and 66](https://www.mouser.com/datasheet/2/1431/ak4619vn_en_datasheet-3010069.pdf).

An isolated VM experiment changes `0x0A` to `0x22`, setting AD1SD and AD2SD. All other 20 codec writes, SAI configuration and DMA descriptors match stock. Codec identification is inferred; this is not physical register readback. No analog response, switching behavior or actual saved latency has been measured. The startup-memory override is a research probe, not an integrated boot patch.

## Next validation

1. Promote the NAM pointer optimization into a separately identified test build after the broader DSP, restart and storage checks. Measure real whole-chain time and transmit-deadline margin with the same capture and NAM + Spring settings. Fewer instructions alone should not be presented as lower latency.
2. Validate the converter option separately, keeping 48 kHz and the eight-sample pipeline. Confirm the setting, startup behavior, frequency response and actual input-to-headphone delay before combining changes.
3. Develop bounded tail suspension as a separate change. Test a fresh minimal chain and a minimal chain reached after using heavy effects, including re-enable behavior. Keep spillover behavior explicit.

Actual input-to-output measurement is still needed to explain the reported feel. An eight-sample interval is 0.167 ms at 48 kHz; reducing it to four would save 0.083 ms for each buffering stage actually halved. Lowering the sample rate lengthens a fixed-size block and also changes model/effect assumptions. Neither should be advertised as a quick fix. The [cut-EQ phase finding](latency-audit.md) remains a separate comparison, not the assumed explanation.

## Reproduction and evidence

Run from the repository root with the retained exact builds, locally supplied stock payload and permitted captures:

```sh
python3 firmware/research/test_latency_regression.py STOCK_PAYLOAD BUILD10 BUILD15 FENDER_NAM REPORT_JSON --baseline-identity NAMLNK10
python3 firmware/research/profile_minimal_chain.py STOCK_PAYLOAD BUILD15/nam-link-offline.elf FENDER_NAM PROFILE_JSON
python3 firmware/research/experiment_a2_pointer_taps.py NEW_EXPERIMENT_DIRECTORY
python3 firmware/research/test_latency_regression.py STOCK_PAYLOAD BUILD15 NEW_EXPERIMENT_DIRECTORY FENDER_NAM REPORT_JSON --baseline-identity NAMLNK15
python3 firmware/research/test_latency_regression.py STOCK_PAYLOAD BUILD15 NEW_EXPERIMENT_DIRECTORY MARSHALL_NAM REPORT_JSON --baseline-identity NAMLNK15
python3 firmware/research/probe_stock_audio.py STOCK_PAYLOAD STOCK_CODEC_JSON
python3 firmware/research/probe_stock_audio.py STOCK_PAYLOAD EXPERIMENT_CODEC_JSON --adc-short-delay
```

The experiment directory's parent must exist. Repeat the workload profiler with BUILD10 and the experiment ELF for the table. Dependencies match the existing ARM harness. [Evidence and source hashes](../evidence/latency-history/summary.json) identify the exact comparisons. Captures, stock payloads and compiled firmware are not distributed.
