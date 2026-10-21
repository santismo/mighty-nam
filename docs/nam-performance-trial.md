# NAMLNK16 NAM processing trial

NAMLNK16 is installed on the development plug. The user reported official-updater success and a normal restart; exact identity was then confirmed over USB. All seven fresh-backed-up presets were restored and independently read and recalled. Mac 0.3.8+11 is installed locally in Applications, and public phone controller 0.6.3 is live. Both retain support for NAMLNK15.

## Change and limits

The optimized ARM convolution advances a history pointer between taps instead of recalculating the address for each tap. Loads, non-fused arithmetic and accumulation order are retained. Thirteen other firmware objects are identical to 15, including output rendering, timing, presets, tuner and custom effects. The codec startup bytes, vectors and audio IRQ are unchanged. The release kernel matches the separately tested pointer experiment.

This is a processing-headroom trial. It does not shorten the 8-sample protected output path, change the sample rate, reduce the processing block, or change stock bypass/tail behavior. The earlier experiment removed 1,945 simulated instruction events per block (3.79% for NAM only and 3.33% for NAM plus spring reverb). Those are not measured CPU-time or guitar-to-headphone latency reductions. The proposed ADC short-delay filter remains a separate experiment and is absent from this image.

## Offline validation

- Fender and Marshall A2 Lite produced bit-identical output to exact NAMLNK15 for NAM only and NAM plus spring reverb, after 1,350 warm-up blocks and over 384 comparison blocks per case. Output age remained eight samples with no extra queued block.
- Full stock chains, reordering and bypass comparisons matched 15 exactly. All five tested dual-FX combinations, plus the full chain with High / Low Cut, passed 1,350-block runs and RAM guards. The timing-fault mute remains active.
- Seven independent model/effects/FX presets, the stock button branch, failed-write preservation, duplicate-save suppression, cold RAM patterns 0/165/255 and warm restarts passed. Marshall and BE100 reference accuracy passed.
- The compact tuner and bounded Bluetooth replies passed exact ARM tests. Seventeen ARM replies passed the native compact parser, including corruption and nonce rejection (53 checks).
- 70 Flutter tests passed with one optional interop fixture skipped. Static analysis had no errors or warnings and one existing informational print diagnostic. The release app signature and installed bundle contents were verified.
- 78 phone tests passed, covering capture loading and saving on 16, compact tuning, cut EQ and older-firmware behavior. A real browser using simulated Bluetooth displayed seven colors, FX A/B, confirmed eight samples and automatic A2/110 Hz tuning; closing retained mute. Native tests passed 71 FX, 1,603 stock/control and 921 legacy tuner checks.

The packager requires exact-build evidence and unchanged source hashes before creating a local image. Missing kernel evidence, a mismatched controller build, and non-identical comparison PCM were each rejected without producing a firmware file. The package round-trips, preserves stock record headers and setup data, and starts with an empty preset bank. These checks do not establish recovery from arbitrary broken firmware.

## Physical baseline before installation

The user disconnected headphones and the phone controller. A fresh USB read backed up all seven saved headers and extra-FX configurations. They matched the previously verified bank. Both referenced local capture files were checked against the saved checksums and hashes. Personal backup files and models remain outside this repository.

NAMLNK15 was explicitly muted, tested at eight samples, and left with its original live effects, FX A/B and buffer restored. There were no preset writes or output-enable commands. Each case collected 24 whole-audio-IRQ snapshots:

| Case | Minimum cycles | Median cycles | Maximum observed cycles |
| --- | ---: | ---: | ---: |
| NAM only | 90,862 | 92,946.5 | 95,528 |
| NAM plus spring | 90,290 | 92,313 | 95,145 |
| NAM after bypassing spring | 90,957 | 93,137.5 | 94,881 |

These are last-call counters from each snapshot, not per-case lifetime maxima. Input was uncontrolled and quiet; existing effect history was retained. The spring callback may already have been running before the first case. The overlapping distributions cannot prove spring is cheaper or establish a hardware deadline. No host audio streams were opened, and Mac/Teams audio settings were untouched.

## Physical comparison after installation

The same Fender capture, stock effects bytes, FX A/B configuration and eight-sample buffer were verified for both versions. NAMLNK16 completed all three quiet cases without processing/context faults or invalid IRQ snapshots. Original live settings were restored and output was left muted.

| Case | NAMLNK15 median cycles | NAMLNK16 median cycles | Observed reduction |
| --- | ---: | ---: | ---: |
| NAM only | 92,946.5 | 88,677.5 | 4.59% |
| NAM plus spring | 92,313 | 88,592.5 | 4.03% |
| NAM after bypassing spring | 93,137.5 | 88,901 | 4.55% |

Each median uses 24 last-call snapshots. These sequential, quiet-input observations are evidence of reduced processing cost in these runs, not a controlled worst-case benchmark or a guitar-to-headphone latency measurement. The fixed output path is unchanged.

All seven restored records matched the fresh pre-update backup exactly, including all 128 stock bytes, extra FX, model checksums, names, per-color buffers and startup playback flags. Fifteen compact USB tuner reads completed in 112–118 ms with valid 42-byte responses, no pending retries and zero pitch/confidence for quiet input. This does not measure real-note accuracy or Bluefy cadence.

After a POWER-only restart, the user confirmed all seven colors cycled back to Green. An independent USB read then verified every saved record and extra-FX configuration unchanged. Startup output was observed on, establishing standalone playback for this restored bank. The final read showed Green/Fender, eight samples and zero processing, context or IRQ faults; output was explicitly muted for the silent session. See [physical results](../evidence/namlnk16/physical-summary.json) and [counter comparison](../evidence/namlnk16/timing-comparison.json).

## Install and compare

Keep headphones unplugged and other controllers disconnected. The official NUX updater and physical buttons perform installation; none of the trial tools flash or reset the plug. Installing this image clears the onboard bank. After exact NAMLNK16 identity is verified, restore the fresh seven-color plan into the empty bank, verify all model/effects records, and repeat the same silent timing cases. Then verify a manual power cycle and button cycle. Saved startup-playback flags remain enabled, so headphones must stay unplugged during restart checks.

Use `tools/namlnk16-trial/` for bounded restore, timing and restart checks. A new listening or analog round-trip comparison is still required to assess perceived latency. Do not treat successful controls or quiet timing as a listening result.

## Reproduction

Build with the existing NAMLNK15 flags plus `--nam-pointer` using `firmware/tools/build_link_firmware.py`. This requires `--responsive-controls` and `--m7-conv`. Run the preset, FX, cut EQ and responsive ARM suites against the resulting ELF. Run `test_responsive_regression.py` and `test_latency_regression.py` with `--candidate-identity NAMLNK16` against the exact 15 baseline. Run `check_nam_pointer_release.py` against the earlier pointer experiment and 15 build.

`stage_nam_performance_firmware.py STOCK_PACKAGE BUILD_DIR REPORTS OUTPUT_DIR` verifies the exact stock package, build sources and all required reports. It creates `NAMLNK16-nam-performance-test.bin` locally, never accessing USB. Exact hashes and sanitized reports are in `evidence/namlnk16/`; no stock image, generated firmware, model or personal backup is committed.
