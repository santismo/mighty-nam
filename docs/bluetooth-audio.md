# Bluetooth playback — NAMLNK23 r2

Local builder **0.3.1** incorporates the stereo phone-playback fix. It still requires
NUX **MP3_OR_V3.0.5.bin**, generates the image locally and uses the official NUX
updater. Firmware identity stays **NAMLNK23**. Mac **0.5.4** and phone **0.8.3** use
the unchanged controller protocol.

The custom callback previously consumed the guitar input without forwarding the
separate phone-music PCM lanes. The correction reads those stereo lanes and adds
them after guitar effects, under the stock headphone-volume control. Phone music
does not enter NAM, the guitar effects or the USB guitar-recording feed. The
Bluetooth path is flat stereo; stock vocal cancellation and Bluetooth EQ are not
included. This change does not reduce the Bluetooth transport's inherent delay.

The owner reports that Bluetooth playback works on the development unit with the
personal r2 image. That is a listening report from one unit, not a fresh device
measurement or certification of every controller/phone combination.

## Offline evidence

[Reports](../evidence/bluetooth-r2/) bind the tested code to ELF SHA-256
`1cf2b1a8146879c2e2d25aab22de3e144ab24ba82e6d20cb5bbdce2d45bf32f7`.
Tests execute the ARM instructions with synthetic PCM and modeled peripherals:

- Reproduce the missing phone-audio path in the previous NAMLNK23 build.
- Compare guitar-only output before/after the change, sample for sample.
- Check independent stereo, opposite-polarity signals, 80 Hz–18 kHz waveforms,
  headphone gain and 8/16/32-sample output ordering.
- Check that music stays out of the USB guitar feed, including with USB initialized.
- Check nonfinite samples, output limits, cold/warm initialization and preset cycling.
- Rebuild the three licensed public starters and verify their NAM reference output.

The public starter variant has not been listened to on hardware. Real Bluetooth
transport, analog gain, sustained deadlines and Logic duplex still need hardware
coverage. The earlier owner report used personal captures, which are not published.

## Reproduce

Use the setup and stage checks in [local-builder.md](local-builder.md). Build the
candidate with `--bluetooth-audio`; build the prior baseline without that flag.
After generating the public starter bank, run:

```sh
python scripts/test_bluetooth_audio.py BUILD_DIRECTORY STOCK_PAYLOAD \
  BASELINE_ELF STARTER_BANK STARTER_REPORT bluetooth.json
```

This regression uses emulated memory only. It neither connects to a plug nor opens
an audio device. The public builder emits only project code, hooks and the licensed
RiffSmith bank; it does not download or redistribute the stock NUX container.

The [DaisySP wah](wah-prototype.md) and [looper controls](looper-research.md) are
separate offline prototypes and are **not included in builder 0.3.1**.
