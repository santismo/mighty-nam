# NAMLNK17 converter latency trial

NAMLNK17 is an offline-tested candidate, not installed or physically verified. NAMLNK16 remains the last verified installed firmware. Mac 0.3.9+12 and phone controller 0.6.4 recognize both versions. The trial changes the ADC filter only at startup and adds cached readback diagnostics. It retains the 48 kHz, eight-frame processing path, seven saved presets, existing effects, tuner and NAMLNK16 NAM optimization.

## Expected benefit and limits

The stock codec setup matches AK4619 registers; this is an inference, not a physical part-ID read. The [AKM-authored datasheet](https://www.mouser.com/datasheet/2/1431/ak4619vn_en_datasheet-3010069.pdf), pages 13 and 15, specifies 22 samples of ADC group delay for the normal sharp filter and 8 for the short-delay sharp filter at 48 kHz. The predicted difference is 14/48000 seconds, approximately **0.292 ms**. The short-delay filter has different phase behavior, with up to 2.6 samples of group-delay variation over 0–20 kHz. This is not a measured guitar-to-headphone reduction or a promise about perceived feel.

The stock DAC filter already selects short-delay sharp. It stays unchanged. Lowering sample rate would lengthen each fixed eight-frame period and require validating model/effect behavior at the new rate; no sample-rate switch is included.

## Isolated startup change

The exact V1.5.6 call at `0x116fa` is redirected to a small routine in the existing low application-code region. It runs before copied bank code is available. Only the expected device address, register-table pointer, register index and one-byte write can change register `0x0a` from `0x00` to `0x22`. The other 20 writes, codec reset GPIO, audio pins, SAI and DMA setup remain identical in the startup simulation.

The stock read/write helpers return zero even when an ACK fails. The trial therefore places `0xff` sentinels in the two filter readback slots before the existing startup read loop. Read-only status page 117 returns schema `0xc1`, observation flags, ADC readback and DAC readback. Exact `0xc10f220a` confirms the expected cached observations. It does not prove chip identity, electrical timing or current register state. No live register-write command is exposed.

The Mac includes this observation in `codecStartup`; the phone includes it in Connection details. Physical trial tools require the matching observation before proceeding with preset restoration and timing checks. A failed read must stop the trial rather than be interpreted as successful configuration.

## Offline checks

- Actual startup call patch and stock I2C helper control flow, with simulated byte/ACK primitives; cold RAM filled with zero, `0xa5` and `0xff`, repeated startup, failed reads/writes and invalid call arguments.
- All existing DSP/driver object files except the main integration object are identical to the exact NAMLNK16 build. The new integration adds identity, startup and diagnostic handling. Vector table and stock audio IRQ remain unchanged.
- Seven-slot storage, duplicate saves, failed flash-driver writes, warm/cold starts, physical-button branch emulation, FX A/B, High / Low Cut, compact tuner and timing-fault mute tests against the exact candidate ELF.
- Fender and Marshall A2 Lite comparisons against 16, with NAM alone and NAM plus spring: identical software PCM and eight-sample protected output age. The converter is outside that PCM simulation, so this preserves the digital pipeline without measuring the intended analog-path change.
- Phone connection, capture transfer, live controls and compact-tuner tests; Mac widget/native-wire checks; a real browser connected to a simulated NAMLNK17 device.

Reports are in `evidence/namlnk17/`. No device API or host audio stream is used by the offline tests.

## Other latency paths investigated

### Bypassed effects

`probe_bypass_and_frames.py` executes initialized stock gate, digital delay and spring callbacks with synthetic input, then silence. It compares normal bypass processing against frozen state on wake. This is an isolated-callback experiment, not a listening test or worst-case sweep of every effect.

The digital-delay fixture retains a real tail after bypass. Sleeping after only 200 ms produces approximately `0.0713` internal floating-point peak on wake, versus around `1.44e-7` after continuously draining the fixture. A simple fixed timeout would resurrect old audio. Gate and spring behaved differently in the tested fixtures, so one rule for all effects is not justified.

No new tail-suspension policy is shipped in 17. Next work is to verify each effect's reset/drain behavior and compare a fade-to-dry, suspend and clean-wake policy across long-delay/high-feedback settings. A few quiet output blocks alone cannot prove that a delay buffer contains no later echo. Reducing retained work improves processing margin; it does not by itself remove the fixed audio pipeline delay.

### Four-frame processing

All eight tested effect stages overwrite output samples 5–8 when called with a tagged four-sample boundary. Their ABI has no frame-count argument. Cutting only DMA halves or changing the controller selection would therefore leave writes beyond the intended frame block. The stock IRQ counter, input/output conversion, dispatcher, effects, custom FX, tuner and protection also assume eight frames.

Four frames needs a separate driver/DSP prototype, with every block boundary audited and physical deadlines measured. It is not exposed as a working setting. At 48 kHz the theoretical saving is 4/48000 seconds, **0.083 ms per buffering stage shortened**, with twice the callback frequency. Eight samples remains the supported minimum.

## Pre-update physical check

A fresh NAMLNK16 USB read verified all seven saved records and FX A/B settings. Cached capture payloads match the fresh SHA-256 and CRC fields; they were not extracted from the device. The complete local restore plan passed validation. Three quiet timing cases completed with zero faults, and original live settings were restored with output muted. See [preflight results](../evidence/namlnk17/preflight.json). NAMLNK17 installation and converter readback remain pending.

## Build and physical test sequence

Use the existing NAMLNK16 flags plus `--adc-short-delay`. Run the exact-build startup, runtime, full-chain and sample-age suites. `stage_codec_latency_firmware.py` checks the stock package, source hashes and required reports before producing `NAMLNK17-converter-latency-test.bin`; it never accesses USB.

Before installation, read a fresh seven-preset backup in normal mode, with headphones unplugged and other controllers disconnected. This update clears the onboard bank. The official NUX updater and physical buttons perform the installation. After normal restart, check exact identity and cached ADC/DAC observations, restore the fresh bank, run the same silent timing cases, then verify power-off storage and color cycling. Finally compare the same capture, chain, eight-sample setting and headphone level. Stop if readback fails or audio is abnormal; retain the previous tested image for the official updater route.

No recovery guarantee or full bootloader backup is established by these offline results. The pre-update timing trial changed only volatile controls and restored them afterward. It did not write firmware or presets, open audio streams, or change system volume.
