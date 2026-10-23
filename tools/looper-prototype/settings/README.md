# NAMLNK28 looper settings and gestures

This overlay extends the frozen NAMLNK27 implementation. It uses the same
48 kHz live path, eight-frame callbacks and audited compressed-loop storage.
The exact combined release is an offline-tested preview; hardware timing and
the new gestures still need a device trial. Nothing here flashes a device.

## Behavior

Threshold, loop level and duration apply live. New defaults are −50 dB, 100%
level and 30 seconds. Lower levels remain available. **Save looper settings**
on phone 0.9.0 or Mac 0.6.0 explicitly stores these three values globally.
Clear the retained loop before saving. The audio loop is never persisted.
Unsaved changes do not become saved when the global buffer is changed.

The NO protocol adds operation 5, argument 1. It is supported only by NAMLNK28.
Compact status page 6 keeps the NAMLNK27 meter and sets bit 24 of its settings
word when current values match stored settings. Bits 25–31 are reserved.
Saving returns busy while armed, recording or retaining a loop. Flash failure
is reported without marking settings saved. Controllers verify readback.

The existing two global-settings sectors at `0x303a4000..0x303a6000` now hold a
version-2, CRC-checked, commit-last record. The version-1 buffer-only format is
readable. Buffer changes preserve saved looper values; loop-settings saves
preserve the buffer. Each write targets the other sector and verifies it before
committing. Original preset-bank bytes are untouched by settings saves.

## Buttons

| Context | PRESET tap | PRESET hold, 800 ms |
| --- | --- | --- |
| Presets | Next occupied color | Previous occupied color once |
| Looper | Arm/cancel/finish/pause/resume | Toggle overdub on retained loop |

In Looper, tap PRESET, then press again within 300 ms and hold 800 ms to clear.
Release after a hold does not trigger another action. Double POWER enters with
no loop, otherwise stops and exits. Single POWER switches preset/loop controls
when a loop exists. Stock POWER hold and volume buttons remain unchanged.
The physical preset LED flashes while armed. Phone arming puts the buttons in
Looper mode. [User guide](https://santismo.github.io/mighty-nam/guide.html#gestures).

## Offline verification

- Native sanitized tests: 261 interrupted settings writes, migration, saved vs
  unsaved restart behavior, gesture timing and wraparound, merged-overdub quality.
- 1,620,000 eight-frame callbacks across 30/60-second loops and 52 NAM changes.
- Compiled ARM tests: actual button dispatcher, startup, USB/BLE save commands,
  preserved output state, preset-bank isolation, overdub continuity across recalls.
- Inactive-loop guitar, USB recording and stereo Bluetooth paths remain sample
  exact against the baseline in the tested cases.

[Reports](../../../evidence/looper-settings28) contain no device measurements.
The public builder variant uses only the three licensed RiffSmith presets.
Its recipe exports own linked sections and generated hooks, never stock bytes
or private captures. Users supply exact `MP3_OR_V3.0.5.bin` locally.

`build_next.py BASELINE OUTPUT` builds the overlay from the exact audited
NAMLNK24 baseline. `run_native.py MODELS OUTPUT/offline` runs the numeric tests.
Run `test_settings_arm.py`, `test_buttons.py`, `test_arm.py`, `test_continuity.py`
and the shared startup/audio harnesses before `hardware/stage.py` will stage an
image. That gate binds reports to source and ELF hashes. Keep stock inputs and
generated images outside this repository.

`scripts/package_looper_builder.py` additionally checks the licensed starter bank
and exports the public recipe. `scripts/package_looper_download.py` packages only
the browser builder, original changes, licensed starters and notices.
