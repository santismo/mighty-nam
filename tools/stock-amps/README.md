# NAMLNK30 Amp block

Original overlay and local relocation tools, MIT © 2026 santismo. No complete
NUX image, generated stock assembly or private capture is included here.

The controller offers **Add block → Amp**, displays the selected model under
its Amp tile, and keeps NAM as a separate block. Internally Amp uses one of the
two custom FX slots. Only one stock amp is available at a time; the other slot
can run Pitch, Auto Wah or modulation. All 29 models in the original V3.0.5
catalog are supported, with each model's own Tone/Cut/Presence/Bright controls.
Cabinet/IR remains a separate block. NAM A2 Lite, the existing looper, presets,
USB audio routing and Bluetooth music routing are retained from NAMLNK29.

## Implementation and memory

The legacy stock coefficient loader is never called in the hybrid: it would
overwrite NAM. Read-only coefficients stay in the supplied stock flash image.
One resource overlapping the NAM preset/code region is copied locally to a
previously zero-filled flash extent. One selected stock wrapper is relocated
into a 2 KiB RAM slot, verified after copying and followed by data-cache clean
and instruction-cache invalidation before it can run. A failed copy leaves
that amp path dry. Amp scratch remains in its original 4 KiB region. Mutable
tone coefficients have their own 68-byte area.

| Allocation | Address range, end exclusive |
| --- | --- |
| NAM state, unchanged from 29 | `0x202e4020..0x2030ed7c` |
| Existing bank code | `0x2030f000..0x20313c40` |
| Existing looper code | `0x20314020..0x20317c70` |
| Existing looper state | `0x20318020..0x203190b4` |
| Amp state | `0x20319c00..0x20319c24` |
| Amp tone coefficients | `0x20319d00..0x20319d44` |
| Amp overlay code | `0x2031a020..0x2031a518` |
| Selected relocated wrapper | `0x2031a800..0x2031afe0` maximum |
| Original amp scratch | `0x2031b000..0x2031c000` |

The recording arenas, eight-frame DSP quantum and 8/16/32 output-buffer choices
are unchanged. No new audio queue is introduced. Master 0 now reaches digital
zero after its existing smoothing; nonzero gains match version 29.

A read-only NP status request, page 126, reports `0x5354011d` for all 29 amps.
Ordinary NAMLNK29 returns unsupported; the earlier five-amp extension reports
`0x53540105`. Both controllers respect these capabilities. NF mode 8 stores
`[8, enabled, position, model, mix, gain, master, p3, p4, p5, p6, 0,0,0,0,0]`.
Models are 1–29; their parameter maps are in the controller catalogs. A second
mode-8 block is rejected even if bypassed. Existing NF modes 1–7 are unchanged.

## Reproduce locally

For the end-user path, use the [browser builder](../../docs/looper-builder.html).
It requires the exact `MP3_OR_V3.0.5.bin`; it needs no compiler. It includes the
three licensed RiffSmith starters, with 29/28/23 also selectable.

For development, first reproduce the frozen NAMLNK24 baseline and NAMLNK29
looper ELF following [the looper instructions](../looper-prototype/takes/README.md).
Use Python with Unicorn 2.1.4, Capstone, pyelftools, numpy and ziglang 0.13,
and Apple clang. Set these to absolute **local paths outside the repository**:

```sh
export MIGHTY_NAM_STOCK_WORK=/path/to/stock-amp-work
export MIGHTY_NAM_BASELINE=/path/to/namlnk24-baseline
export MIGHTY_NAM_LOOP29=/path/to/namlnk29-work
export MIGHTY_NAM_STOCK_PAYLOAD=/path/to/MP3_OR_V3.0.5.payload
export MIGHTY_NAM_STOCK_FILE=/path/to/MP3_OR_V3.0.5.bin
export MIGHTY_NAM_TEST_BANK=/path/to/licensed-starter-bank.bin
export MIGHTY_NAM_REFERENCE=/path/to/liba2-reference-order.dylib
python tools/stock-amps/audit_writes.py
python tools/stock-amps/relocate.py
python tools/stock-amps/build.py
python tools/stock-amps/test_stock_unit.py
python tools/stock-amps/test_fallback.py
python tools/stock-amps/test_levels.py
python tools/stock-amps/test_loop.py
python tools/stock-amps/test_persistence.py
python tools/stock-amps/test_starters.py
python tools/stock-amps/export.py
MIGHTY_NAM_RECIPE=looper node --test scripts/test_firmware_builder.cjs
```

The source exporter is a maintainer tool: it updates the public recipe, uses the
archived licensed starter bank and stages the combined result **locally only**.
Run the listed tests before packaging. The browser validates the original input,
allowed copy/patch ranges, source fragments, before/after checksums and final
whole-image checksum. Original instructions/literals are represented by input
copy descriptions; only new relocation instructions and original overlay code
are embedded in the recipe. Never publish generated wrappers or staged images.

## Evidence and limits

See [the release evidence](../../evidence/namlnk30). All 29 amp algorithms match
an independently executed original-stock reference in 87 amp/knob cases, with
1,024 synthetic frames each. Protected NAM model and recording arenas remain
unchanged in that comparison. Whole-chain checks cover NAM, stock amp, existing
FX, reverb, recorded-loop continuity and preset recall. A saved Amp setting
survives emulated restart. Public starter checks cover startup playback, color
cycling and three NAM reference comparisons.

These are functional CPU tests with modeled peripherals, not Cortex-M7 cycle
measurements. Flash-backed coefficients may have different processing cost on
hardware. Exact NAMLNK30 hardware listening, cache behavior, combined-effect
headroom and physical restart tests remain pending. No analog latency improvement
or recovery guarantee is claimed.

Unicorn 2.1.4 changes execution when a memory-read observer covers the dynamically
copied wrapper; even a no-op observer reproduces it (`observer_wrapper.py`). The
integration harness omits only that observer, retaining the other code/NAM guards,
loop canaries and exact DSP comparisons. This is a limitation of the dynamic
ownership test, not evidence of physical RAM ownership.
