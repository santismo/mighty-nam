# Driver phase investigation after NAMLNK19

This follow-up uses the **84 previously recorded physical snapshots**, the installed build's ELF, and offline ARM/event simulation. There were **no new device commands**, output changes, model/preset writes, firmware builds for installation, or host audio operations. NAMLNK19 and the Mac/phone apps remain unchanged.

## What actually improved?

NAMLNK19 removes unnecessary delay/reverb work after bypass. In the prior physical test, the median audio IRQ cost returned from 84,685.5 cycles with Spring to 73,887.5 after bypass, essentially the 73,921.5 NAM-only level. The protected previous-block output schedule did not change. Thus processing efficiency improved; no reduction in steady input-to-headphone latency has been measured for this change.

NAMLNK17's earlier ADC filter change had a datasheet-predicted saving of about 0.292 ms. Its cached startup settings were verified, but the physical converter identity and analog latency were not measured. It should not be combined with the new CPU percentages as a measured latency total.

The user's report that 8, 16 and 32 all feel good is recorded as subjective feedback. It does not show that the settings are identical or that total latency has fallen.

## The buffer range is small

A new focused test executed the exact NAMLNK19 ARM renderer for 3,360 stereo frames. A single impulse emerged at exactly the expected frame for all three settings, with exact channel values and passing memory guards:

| Selected setting | Added output queue compared with 8 | Added time at 48 kHz |
| --- | ---: | ---: |
| 8 | 0 samples | 0 ms |
| 16 | 8 samples | 0.167 ms |
| 32 | 24 samples | 0.500 ms |

All three still process eight frames per IRQ. These settings **do not buy more DSP processing time**. The separate protected eight-frame handoff, DMA/serial path and converter filtering are excluded from this table. The 21.3 ms startup fade and roughly 200 ms effect-change settling are temporary transitions, not a continuous queue applied to every note.

## Observed driver phase

Re-executing the exact installed-build startup confirms the existing configuration in emulation: four serial words per frame, 16-word DMA bursts, two bursts per interrupt and TX/RX FIFO watermarks of 16. This is not a fresh physical register read.

All 84 recorded captures show the TX source pointing at the half about to be published, two bursts remaining, and the RX destination pointing at the next input half. The TX FIFO contained 30 words at entry and 29 at publication; RX contained 1 then 2. The early CPU publication marker precedes the main current-block NAM/effect processing.

Seventy-seven same-epoch pairs estimate about 166,025.33 raw DWT cycles per audio-interrupt interval. Ratios are internally consistent to less than 0.1 cycle in this data. This assumes no unseen whole counter wraps or untracked resets; it is **not a clock-frequency or millisecond calibration**.

| Chain | Median audio IRQ / observed IRQ period | Largest observed ratio |
| --- | ---: | ---: |
| NAM only | 44.5% | 46.5% |
| NAM + Spring | 51.0% | 52.7% |
| NAM + Digital Delay + Spring | 53.9% | 55.2% |

These are fractions occupied by the measured audio IRQ, not overall CPU load or worst-case capacity. Early publication was within about 3.0% of the interval in these snapshots. Finishing the complete chain within one IRQ period is not sufficient: the hardware can fetch the output half before that period ends.

## A possible route to a shorter handoff

The official [NXP reference manual](https://www.nxp.com/docs/en/reference-manual/IMXRT1170RM.pdf), Rev. 5 sections 58.3.6.1 and 58.5.1.5 (locally retained pages 3476–3477 and 3488), specifies that TX requests service at or below its watermark. NXP's [SAI/eDMA driver](https://github.com/nxp-mcuxpresso/legacy-mcux-sdk/blob/main/drivers/sai/fsl_sai_edma.c) also configures a finite DMA transfer size from FIFO capacity; these are hardware refill rules, distinct from the user-facing 8/16/32 output queue.

Among 256 integer-word phase/entry-delay combinations, one simplified configuration matches the recorded cursor/FIFO pattern. That is a model fit, not unique identification of continuous hardware phase or IRQ entry latency.

The screen uses the largest recorded **whole IRQ duration as a hypothetical completion-time proxy**, rounded up to a serial-word tick. It then compares publishing the current block under different TX watermarks:

| TX watermark | Model first-fetch deadline after modeled IRQ | Continuous cases with proxy cost | With two extra word-times of delay |
| --- | ---: | ---: | ---: |
| 16, current | 14 serial words | 0 / 7 | 0 / 7 |
| 12 | 18 serial words | 6 / 7 | 3 / 7 |
| 8 | 22 serial words | 7 / 7 | 7 / 7 |

With four additional word-times, the watermark-eight candidate fails the Delay+Spring case. This is a useful negative boundary, not sufficient stress coverage. At the exact first-fetch deadline, the conservative model rejects publication and produces mixed old/new sample sequences.

**Lowering the watermark alone does not reduce the modeled steady sample age.** It delays the hardware's fetch while reducing FIFO reserve. That could allow the completed current block to replace the previous protected block. Only that second change removes eight frames, theoretically **0.167 ms at 48 kHz**. In this idealized phase model, serial-label age changes from 95 to 63 words; neither number is a measured guitar-to-headphone delay or a complete channel-path model.

The candidate is not ready to install. The model assumes instantaneous DMA and atomic serial words, omitting bus contention, synchronizers, IRQ preemption, cache/store visibility, channel-slot mapping and converter delays. Whole-IRQ duration is not the missing timestamp at actual end-of-DSP publication. Lower watermarks four and zero were also included as bounds; they reduce reserve further, and zero is not a recommendation.

## Next useful work

The first offline prototype is now tracked separately in
[Current-block DMA prototype](dma-current-prototype.md). The remaining hardware
deadline and analog-measurement requirements below still apply.

1. Build an offline prototype that preserves all eight-frame effect contracts and output guards while testing a later TX fetch plus current-block publication. Keep the present NAMLNK19 as the usable version.
2. Before any hardware trial, test all used chains and transitions with a bus-service/jitter model and exact compiled publication order. Include FIFO underrun and partial-fetch failures. A new diagnostic point after output protection would be needed to measure actual candidate completion, with its overhead accounted for.
3. Measure the real guitar-input-to-headphone path with suitable external input/output equipment. USB status and loopback timing cannot establish that end-to-end figure. This follow-up does not start an audio test.

Four-frame DSP would be a broader stock-effect/driver change and saves only 0.083 ms per stage shortened. Lowering sample rate makes fixed-sample buffers longer and requires model/effect revalidation. Effect-specific algorithmic delay and capture/filter phase response are separate from CPU cost.

For current use, eight remains the smallest supported output queue. There is no need to update the working firmware for this investigation.

## Reproduce offline

```sh
python3 firmware/research/audit_audio_scheduling.py STOCK_PAYLOAD NAMLNK19_ELF STARTUP_REPORT
python3 firmware/research/analyze_driver_phase.py evidence/namlnk19/physical-timing-raw.json STARTUP_REPORT PHASE_REPORT
python3 firmware/research/probe_render_sample_age.py STOCK_PAYLOAD NAMLNK19_ELF PERMITTED_MODEL RENDER_REPORT
```

The phase analysis checks counter/sequence wrap, rejects six invalid interval cases, searches 256 discrete phase combinations, and rejects publication at the first-fetch boundary. It screens 140 chain/watermark/jitter combinations. Exact hashes and numerical evidence are in the [manifest](../evidence/driver-phase19/manifest.json).
