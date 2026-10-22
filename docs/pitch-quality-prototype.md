# Pitch/octave quality prototype — NAMPIT01

2026-10-22. This is an **offline research build**, not an installable release.
Nothing was sent to the plug. Its playback state, the Mac audio configuration,
and Teams were untouched. No audio was played, presets backed up, or flash
container produced. The staged NAMLNK21 file remains unchanged.

## Changes

The existing monophonic dual-delay pitch shifter now has three opt-in changes:

- Refine the detected pitch period at one-sample lag intervals. The coarse
  detector previously compared four-sample intervals; small period errors
  caused the two overlapping reads to interfere, especially on bright notes.
  Five fine comparisons share one frozen reference, spread over 20 samples.
  Each eight-frame call still performs at most two 160-term difference sums.
- Compensate the changing read-window length. With the triangular crossfade,
  the weighted mean delay is half the window. Subtracting half its change from
  phase advancement reduces unintended modulation while tracking vibrato.
- Filter the wet input before upward shifting to reduce folded high-frequency
  content. Two Butterworth biquads use a cutoff of `0.45 * 48000 / pitch_ratio`.
  Returning from neutral/downshift clears stale filter state. The dry path is
  unfiltered; the other six effect algorithms are unchanged.

The delay ring remains 2,048 samples per channel and processing remains eight
frames at 48 kHz. This does **not** establish lower hardware latency: there is
no new audio queue, but filtering has frequency-dependent delay, and pitch
shifting retains its existing variable read delay. This remains a monophonic
effect; good chord tracking is not claimed.

## Results and limits

[Quality results](../evidence/nampit01/quality.json) compare the default DSP with
the prototype compiled from the same source, with fused arithmetic disabled.

| Offline measure | Default | Prototype |
| --- | ---: | ---: |
| Worst nonharmonic energy across 84 steady synthetic cases | −8.16 dB | −35.44 dB |
| Median nonharmonic energy | −54.83 dB | −55.41 dB |
| Median vibrato error across 12 cases | 2.30 cents RMS | 1.03 cents RMS |
| Worst vibrato error | 22.16 cents RMS | 10.48 cents RMS |

Steady cases cover seven fundamentals from 65.4 to 880 Hz, six shifts from
−12 to +12 semitones, and gentle/bright harmonic spectra. The energy measure
excludes ±8 Hz bands around expected harmonics; it is **not THD+N or a listening
score**. Sixty-three of 84 cases improve. The largest regression is from
−61.48 to −58.42 dB on the gentle 880 Hz/+2 case. Eight of 12 vibrato cases
improve; the largest RMS regression is 0.49 cents. Vibrato metrics allow delay
alignment within the existing ring, so they do not measure physical latency.

The [137 pitch-range checks](../evidence/nampit01/pitch-range.json) pass with a
maximum frequency error of 0.847 cents. This includes all 25 semitone settings
and eight additional notes with/without harmonics. Address/undefined-behavior
sanitizers pass the effect range, resets, NaN handling and switching tests.
Additional checks cover note attacks, bends, bypass, zero mix, stereo isolation,
rapid type/shift changes, and returning to octave-up after silence. These are
boundedness and correctness checks, not proof of click-free transitions.

Native tests verify that non-pitch modes remain sample-identical. Rebuilding
without the prototype flag reproduces the staged NAMLNK21 ELF byte-for-byte:
`a08029df182d9f509b4dc965f1ef294e713a5e590e76c410326ce7b4240587fa`.

The [compiled ARM checks](../evidence/nampit01/arm.json) compare complete DSP
output against the native version and count instruction events for three
traces. These counts **are not M7 cycles**: cache, bus, interrupt contention,
and physical deadlines remain unverified. Upward filtering costs additional
processing, so the sound improvement must still be checked against the real
device's timing budget before promotion to a release.

| Trace | Default mean instruction events / call | Prototype mean | Prototype maximum |
| --- | ---: | ---: | ---: |
| 110 Hz, octave down | 5,834.6 | 5,796.1 | 5,861 |
| 110 Hz, octave up | 5,836.3 | 6,373.6 | 6,439 |
| 880 Hz, octave up | 5,832.9 | 6,368.7 | 6,412 |

All three traces match the native output exactly across 1,024 calls each;
the last 256 calls of each trace are profiled. The roughly 9.2% increase for
octave-up is a per-effect instruction count, not a whole-chain CPU percentage.

The audited copied-code region has 228 bytes remaining; state RAM has 780
bytes remaining. This uses 1,380 more code bytes and 72 more state bytes than
the default build, without moving either region. The kernel is shared between
coarse and fine analysis to fit; the original duplicated prototype did not fit
and was rejected by the linker.

[USB/NAM regression](../evidence/nampit01/usb-regression.json) executes 1,652
compiled callbacks plus the existing controls, seven-preset persistence and
cold/warm restart checks in the emulator. Neutral NAM output matches its
independent reference exactly. USB endpoint/enumeration behavior is modeled;
this is not a physical Logic or Bluetooth test.

## Reproduction

From the repository root, with clang++, numpy, and the existing firmware Python
dependencies installed:

```sh
python firmware/research/test_pitch_quality.py build/pitch-host
python firmware/tools/build_link_firmware.py build/pitch-arm \
  --stock-chain --m7-conv --fast-bypass --m7-dense --prime-state \
  --irq-timing --listening --early-output --output-buffer --preset-bank \
  --performance --tuner --fx-blocks --cut-eq --responsive-controls \
  --nam-pointer --adc-short-delay --global-buffer --driver-timing \
  --active-chain --usb-nam-controls --pitch-quality-prototype
python firmware/research/test_pitch_quality_arm.py STOCK_PAYLOAD \
  NAMLNK21_ELF build/pitch-arm/nam-link-offline.elf \
  build/pitch-host build/pitch-arm/arm.json
python firmware/research/test_usb_nam.py STOCK_PAYLOAD \
  build/pitch-arm/nam-link-offline.elf LOCAL_A2_LITE_MODEL \
  A2_REFERENCE_LIBRARY build/pitch-arm/usb.json --pitch-prototype
```

Stock firmware and capture files remain local, excluded from the repository.
The prototype has a distinct identity, `NAMPIT01`. Ordinary image construction
rejects it; emulator construction requires `allow_pitch_prototype=True`. The
NAMLNK21 staging tool still requires `NAMLNK21`, preventing accidental packaging
of this experiment. No controller release or app update is needed for these
offline tests; compatibility with a future installable identity must be added
when this work is promoted.

The next gate is physical processing-budget measurement and an audition of
single notes, bends, attacks, and octave-up/down. Until then, this is evidence
of an offline improvement, not a declaration that the reported sound is fixed.

## Research context

The [MathWorks dual-delay explanation](https://www.mathworks.com/help/audio/ug/delay-based-pitch-shifter.html)
and [DAFx 2007 non-fluctuating time scaling paper](https://dafx.labri.fr/main/papers/p007.pdf)
provided background on overlap interference and phase alignment. TONE3000's
locally available pitch-shift design was also reviewed; its implementation was
not copied. Fixed long-window analysis and a separate splice prototype were
rejected in this investigation after worse tracking results. The selected
implementation retains this project's existing delay engine and bounded work.
