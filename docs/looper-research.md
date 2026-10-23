# Standalone looper research

Status: **button/transport model tested offline; no hardware looper is released**.
The current prototype has no sample storage, audio mixer or physical button hooks.

## Requested controls

| Context | Gesture | Result |
| --- | --- | --- |
| Normal preset controls, no loop | Double-tap POWER | Enter looper controls |
| Looper controls, empty | Tap PRESET | Arm threshold recording |
| Armed | Play above threshold | Start recording |
| Recording | Tap PRESET | Close the loop and repeat it |
| Loop exists | Tap POWER once | Switch between preset and looper controls; preserve playback/pause state |
| Normal preset controls | Tap PRESET | Change guitar preset while the loop keeps its state |
| Looper controls, playing | Tap PRESET | Pause the loop |
| Looper controls, paused or stopped | Tap PRESET | Resume the loop |
| Looper controls or loop exists | Double-tap POWER | Stop the loop and exit looper controls |
| Normal preset controls | Hold PRESET | Reverse preset-cycling direction; release does not change preset |
| Any runtime mode | Hold POWER | Request normal shutdown |

The model retains a stopped recording so it can be resumed by returning with one
POWER tap. Choosing how to replace/clear that recording is still an integration
step; overdubbing and permanent loop storage are not implemented. If POWER is
single-tapped during recording, the prototype closes the loop and returns to preset
controls. Leaving while armed cancels arming. Tapping PRESET while armed also cancels.

Provisional timings: 25 ms debounce, 300 ms double-tap window, 800 ms PRESET hold and
2 seconds POWER hold. A single POWER action waits for the double-tap window; this
delay concerns the controls, not the live guitar signal. The first tap must not
invoke the stock mute action. A standalone POWER tap with no loop is a no-op in
this model. Buttons held at boot are ignored until released; stock startup's
PRESET+POWER updater gesture remains outside the runtime model.

[controls.hpp](../tools/looper-prototype/controls.hpp) uses 60 host bytes without
allocation. The sanitizer-enabled tests exercise the full record/play/change-preset/
return/pause/resume/stop sequence, 1,792 occupied-color/direction cases, contact
bounce, long holds, time-counter wrap, boot-held buttons, threshold rejection and
recording-capacity boundaries. See [evidence](../evidence/looper-prototype/).

```sh
clang++ -std=c++17 -O1 -fsanitize=address,undefined -Wall -Wextra -Werror \
  tools/looper-prototype/test.cpp -o /tmp/mighty-loop-controls
/tmp/mighty-loop-controls
```

## Firmware integration findings

A bounded inspection of the exact V3.0.5 Original payload identifies the stock
button action dispatcher at `0xa05e`, called through the runtime wrapper at `0xa19a`.
The forward preset-selection span at `0xa102..0xa144` uses the occupied-color mask,
updates the selected slot and publishes it on both controller paths. Its behavior
is exercised by the existing emulated preset tests. The flag-handling span around
`0xa17e..0xa196` toggles the runtime mute field; a new POWER recognizer must consume
that action before its first tap changes playback. Raw pin polarity, hold timing,
shutdown interaction and LED feedback still need exact hook-level verification.
These are code observations, not proof that the new gestures work on the plug.

Record processed guitar **before** Bluetooth/USB backing playback and headphone
volume, then mix loop playback **after** the current live-guitar effects. This lets
a new preset change the live guitar without reprocessing the recorded sound.

However, current preset recall calls `mpp_bank_pause`, resets output state and loads
a capture with interrupts masked during flash reads. Some graph changes also use
1,200 eight-frame settling callbacks (200 ms). A looper cannot simply share that
pause/reset path: its playback clock and mixer must survive guitar-graph reloads,
and flash access must be bounded or made interrupt-friendly. Saving/erasing flash
while looping needs a separate policy and test; offline button tests do not solve it.

## Memory budget

The wah prototype leaves only **644 bytes** in the currently audited custom-state
window. Nominal [RT1170 RAM capacity](https://www.nxp.com/products/i.MX-RT1170) is not
free RAM: stock DSP, DMA, USB/Bluetooth and presets already own regions. No large
loop buffer is yet proven safe, and no external memory is assumed.

At 48 kHz, mono PCM16 requires 96,000 bytes/second:

| Dedicated buffer | PCM16 mono | PCM16 stereo | 4-bit mono ADPCM, before block overhead |
| --- | ---: | ---: | ---: |
| 256 KiB | 2.73 s | 1.37 s | 10.92 s |
| 512 KiB | 5.46 s | 2.73 s | 21.85 s |
| 1 MiB | 10.92 s | 5.46 s | 43.69 s |

These are arithmetic examples, **not available recording durations**. Thirty seconds
of uncompressed mono PCM16 alone needs 2.88 MB. A practical longer loop may need a
verified reclaimed region plus compression, or other storage; streaming recordings
to program flash is not assumed safe. Compression quality, pre-roll for the first
attack, seam smoothing, pause/resume cursor behavior and overdub headroom remain
for the audio prototype after the ownership audit.
