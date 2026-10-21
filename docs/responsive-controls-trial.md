# NAMLNK15 physical trial, Mac 0.3.7 and phone 0.6.2

Mac 0.3.7 is installed locally in Applications. It exposes FX A and FX B with their seven effect choices, controls, bypass, position, live USB application, and independent preset readback. Existing nine-block local chains migrate by inserting two bypassed blocks. The remaining stock block settings and order are retained. This works with NAMLNK13–15; High / Low Cut requires 14–15. Favorites, account credentials and preferences are preserved by the app replacement.

NAMLNK15 is installed on the development plug after the user completed the official updater and a normal restart. Exact identity was confirmed over USB. The public phone controller 0.6.2 recognizes 15 and keeps the previous tuner protocol on older firmware. The following physical results supplement the original offline build evidence; they do not replace it.

## Preset button

Before this update, the user report had only Green occupied (mask 1). The stock button correctly skips empty colors and returns to Green, but the previous hook unnecessarily paused processing and recalled the same capture. The new hook returns without reloading when the requested color is already active. It also avoids copying stock defaults over live edits while a real recall is pending. Rapid queued button requests retain the original listening intent. Multiple occupied colors still cycle; firmware installation alone does not populate empty colors. After this installation, all seven were restored at the user’s request. The user then confirmed that seven button presses cycled through every color and returned to Green. The phone displays a hint when only one color is saved.

## Audio path and latency

Fully bypassed FX A/B now skip their engine-dispatch calls once their bypass fades finish. Enabling either wakes processing. Existing stock bypass and tail behavior remains: initially bypassed effects sleep where already supported; previously used gate, delay and reverb retain their stock callback path to preserve residual tails. No shorter tail policy is claimed.

NAM, listening/output rendering, IRQ timing and profiling object files match the exact NAMLNK14 baseline. All three full-chain/reorder/bypass comparisons produced bit-identical PCM over 1,350 blocks each. Full stock effects plus both custom FX and cut EQ remained finite and passed memory guards. The existing timing fault still mutes output.

The user's report already confirmed 8 samples at 48 kHz, no faults, NAM plus High / Low Cut enabled, and both extra FX bypassed. Eight is the minimum existing output staging and adds no extra queued block. It is **not the total guitar-to-headphone delay**. These tests do not establish a real-time speedup, explain the reported subjective latency, or measure codec/analog delay. An EQ-bypass listening comparison and physical timing remain useful. No sample-rate or output scheduling change is included.

## Phone tuner

With NAMLNK15, the phone requests 1,024 dry samples at 12 kHz (85.33 ms) and the plug calculates bounded YIN pitch in the foreground. The audio interrupt only captures samples, as before. Each result is one 42-byte MIDI reply, containing nonce, generation, frequency, confidence and CRC. Two ordinary requests (start/read) replace paged PCM transfers for each completed reading. A pending capture is polled with a bound, and only one reading runs at a time. Closing or hiding cancels polling; the capture self-stops and output remains muted. There is no host audio or microphone access.

A host sanitizer test passed 117 tone/detuning/phase cases with maximum error 0.327 cents and rejected silence, DC and noise. Exact ARM code detected E2, A2 and E4 to within one cent. Seventeen actual ARM-generated replies decoded in the production JavaScript parser, including pending, stop and muted-only errors. A real browser with simulated Bluetooth displayed A2/110 Hz automatically and recovered its controls on close, with production message pacing. This does not measure the physical chip's calculation time or Bluefy/Bluetooth cadence.

## Validation

- 69 Flutter tests passed; one optional interop fixture test skipped. New coverage includes 770 FX type/position combinations and full Mac save/recall/reconnect flows on 14 and 15.
- 73 phone tests passed, including legacy tuner fallback, compact readings, generation changes, cancellation, muting, buffer readback, TONE3000 capture transfers and persistence.
- Native USB tests cover FX framing and bounds, legacy tuner framing, stock controls, supported identities and output-buffer gates.
- ARM tests pass seven independent model/effects/FX/cut-EQ presets, cold RAM patterns 0/165/255, warm restarts, the actual stock button branch, exact model-reference accuracy, duplicate-save suppression, bounded flash writes and failed-write preservation.
- The candidate preserves stock vectors, setup records and existing audio IRQ bytes. Its container round-trips and only uses audited insertion regions. This is not proof of USB recovery from arbitrary broken firmware.

See `evidence/namlnk15/` for the exact ELF and evidence hashes. No factory image, downloaded capture, saved user bank or private session is committed. The local experimental firmware file contains the user's stock image and is kept outside the repository.

## Physical results after installation

The user chose the latest reported Green settings plus the six other presets from the older verified backup. Seven model/effects records were saved, independently read and recalled. After a POWER-only restart and the user-confirmed seven-color button cycle, all seven stored headers and FX configurations matched again. Green returned with Fender A2 Lite, 8 samples at 48 kHz and no processing or timing faults. Startup playback was observed on before the final explicit mute. Saved startup flags remain enabled, allowing standalone playback.

Green, Orange, Red and Cyan retain 8-sample output staging; Blue and Pink retain 16; Lilac retains 32. These are the restored settings, not a newly imposed buffer policy. All mapped stock effect settings were preserved. The initial pre-save comparison found that the unmapped trailing stock byte 127 was 0 on the new device state versus 7 in the backup. There is no audited control for that byte; the restore retained 0, then verified the normalized full records on save, recall and restart. The original backup was not changed.

A separate muted check enabled Tremolo and Auto Wah together, moved both, bypassed them and restored the exact original FX settings without preset writes. All readbacks matched and no faults were reported.

Fifteen compact tuner readings over physical USB MIDI completed in 113–118 ms, including an intentional 90 ms capture wait, with valid 42-byte replies and no pending retries. Quiet input correctly returned zero frequency/confidence. This verifies the physical compact transport, not real-note pitch accuracy or Bluetooth/Bluefy cadence. Guitar-to-headphone latency remains unmeasured; no listening improvement is claimed from these results.

No host audio streams were opened, Mac/Teams audio settings were unchanged, and no additional firmware flash was performed by the trial tools. The plug was left muted on Green. Personal capture files and the verified seven-color backup remain local. See [sanitized physical evidence](../evidence/namlnk15/physical-summary.json) and [trial sources](../tools/namlnk15-trial/README.md).

## Before installation

Read and back up the latest bank over USB in normal mode before updating: installing this image clears the bank. Restore the saved captures/effects afterward, including each color's startup-output flag. Empty-bank startup remains muted; saved presets can play without a controller when saved with startup output enabled. Keep headphones unplugged during these checks. No firmware was flashed and no Mac or Teams audio settings were changed while preparing this release.

## Reproduction

Build with the existing stock/listening/preset/performance/tuner/FX/cut flags plus `--responsive-controls` (see `firmware/tools/build_link_firmware.py`). Run `test_preset_runtime.py`, `test_fx_firmware.py`, `test_cut_eq_firmware.py`, `test_responsive_firmware.py`, and `test_responsive_regression.py` against that ELF and the exact stock payload. Compile `test_compact_tuner.cpp` with address/undefined-behavior sanitizers. `stage_responsive_firmware.py STOCK_PACKAGE BUILD_DIR REPORTS OUTPUT_DIR` requires all matching evidence and refuses modified/missing reports. It never accesses USB or flashes a device.

A subsequent [offline latency audit](latency-audit.md) compares exact NAMLNK12 and NAMLNK15 output and quantifies the Green cut EQ’s filter phase. No hardware latency improvement is claimed.
