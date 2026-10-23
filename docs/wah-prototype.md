# DaisySP auto-wah prototype

Status: **NAMLNK24 candidate built and checked offline; not flashed or released in the public builder**.

The prototype adapts the MIT-licensed [DaisySP AutoWah](https://github.com/daisyaudio/DaisySP/tree/2c72eaf9eac5fc0dca1919d65d606da907832618/Source/Effects),
with its Soundpipe lineage and license retained in
[tools/auto-wah-prototype](../tools/auto-wah-prototype/). The canonical firmware implementation is enabled with `MPP_DAISY_WAH` and replaces FX mode 2 in the NAMLNK24 candidate. Builder 0.3.1 continues to make NAMLNK23 r2 with its existing wah.

The design follows a guitar envelope through a resonant wah filter. Stereo channels
share the envelope but retain separate filter state. Sensitivity, resonance and
wet/dry controls remain in the existing FX slots. At 100% mix, the settled path is
fully wet. The implementation uses bounded polynomial approximations instead of
per-sample general-purpose powers/cosines. It adds 36 bytes of filter state per
FX instance and no block buffering or lookahead. Filter phase response still exists;
this is not a claim of zero analog latency.

## Checks completed

- 60 synthetic plucked-guitar cases compared against the pinned upstream DaisySP
  implementation at its corresponding sensitivity and nominal resonance. Maximum
  absolute sample error: **0.0005951**. Sensitivity extremes, finite recovery,
  linked stereo, zero mix and bypass are also covered.
- The other six FX modes produce sample-exact native results against the current
  firmware implementation, including pitch. The prototype compiles only the FX
  translation unit with `-Os` to fit; NAM kernels retain production optimization.
- Three public RiffSmith A2 Lite captures execute in the ARM emulator at **8 samples,
  48 kHz**, with wah before NAM, wah after NAM plus stock Spring, and two wah blocks
  plus Spring. Model-boundary output matches the independent reference within the
  required 0.00002 tolerance. Bypassed guitar output matches the baseline exactly.
- Those 12 prototype cases and three baseline cases total **21,810 callbacks**.
  Representative whole-callback instruction maxima are about 49,773 for bypass,
  51,556 for one pre-NAM wah and 60,662 for dual wah with Spring. These are **instruction
  counts, not CPU cycles or a real-time guarantee**.

[NAMLNK24 evidence](../evidence/namlnk24/) records the exact candidate ELF, host tests and compiled ARM tests. [Earlier prototype evidence](../evidence/wah-prototype/) remains scoped to its original build. Synthetic stress inputs can exceed normal audio scale before the existing
output limiter; tests cover stability, not automatic loudness matching. Listening,
resonance tuning and sustained physical deadlines are pending.

The linked code uses 19,520 of 20,480 bytes in the copied code region. Custom BSS ends
at `0x2030ed7c`, leaving 644 bytes before copied code. This is enough for this filter's
small state, not a useful loop recording buffer.

## Reproduce without hardware

Requires the repository's ARM toolchain/Unicorn environment and NumPy for native
comparisons. Use an independently built NAM reference library as in the firmware
research setup, and extract the public starter models with `build_starter_presets.py`.

```sh
python tools/auto-wah-prototype/build.py WORK_DIRECTORY
python tools/auto-wah-prototype/test_host.py WORK_DIRECTORY
python tools/auto-wah-prototype/test_arm.py WORK_DIRECTORY STOCK_PAYLOAD \
  BLUETOOTH_BASELINE_ELF STARTER_MODEL_DIRECTORY NAM_REFERENCE_LIBRARY arm.json
```

The build script edits only its generated research copy. It produces an ELF for
emulation, not a NUX update container, and marks its metadata research-only.

## Retained NUX Touch Wah

NUX lists Touch Wah among the V3 additions on the [official Mighty Plug Pro page](https://nuxaudio.com/product/mightyplugpro/). The supplied V3.0.5 Original file already contains its DSP. NAMLNK24 exposes it as **Drive → Touch Wah** (type 14), separately from **FX A/B → Auto Wah**. It is retained proprietary NUX code from the user's input firmware, not a new MIT-licensed implementation or copied into this source repository.

Type, Wow, Sense, Direction and Level are available in Mac 0.5.5 and phone controller 0.8.4. Earlier firmware remains limited to its supported Drive types. The ARM tests cover four wah types, both directions, NAM + Spring at eight frames, saving/recalling/cold startup and sample-exact bypass. The controller tests exercise live edits and preset storage/readback with type 14.

Build an offline candidate with `firmware/tools/build_public_v3.py WORK --bluetooth-audio --daisy-wah`. `stage_public_v3.py` additionally requires matching wah and Touch Wah reports before producing a local update container. Missing or stale reports must reject staging. The public builder recipe and its default captures are unchanged. No looper audio or new button behavior is compiled into this candidate.
