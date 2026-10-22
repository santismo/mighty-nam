# mighty-nam

NAM A2 Lite on the NUX Mighty Plug Pro, with a Mac editor and a phone controller. By **santismo**.

[Mac installer](https://github.com/santismo/mighty-nam/releases/tag/v0.5.2-preview.1) · [Phone controller](https://santismo.github.io/mighty-nam-controller/) · [User guide](https://santismo.github.io/mighty-nam/) · [Development](DEVELOPMENT.md) · [Roadmap](ROADMAP.md)

This repository contains the firmware experiments, Mac app, protocols and test evidence. The separate [mighty-nam-controller repository](https://github.com/santismo/mighty-nam-controller) is public and hosts the phone page.

## Current version

| Component | Status |
| --- | --- |
| Mac 0.5.2 | Universal ad-hoc-signed preview. TONE3000 picker stays open while loading captures; seven colored presets; live effects; tuner; master and recording gain; NAM input/output, bass/middle/treble and mix. NAMLNK22 support. Not notarized. |
| Phone 0.8.2 | Public Bluefy/Web Bluetooth controller with live editing, capture browsing/transfers, favorites, tuner, direct preset selection, FX A/B and global buffering. |
| NAMLNK22 | **Staged, not installed.** Improved monophonic pitch, USB audio routing repair, NAM controls and Auto Wah changes. Offline checks pass; hardware pitch timing/listening and Logic duplex checks remain. [Trial](docs/pitch-quality-trial.md). |
| Hardware baseline | NAMLNK20 was installed on the development unit. Earlier builds demonstrated NAM listening, seven-color storage after restart, and phone live controls. These observations do not certify every new effect or timing combination. |

## What you can do

- Load compatible **48 kHz A2 Lite** captures. An A2 container is accepted only when its Lite component validates; full A2 is not supported.
- Add, move, change, bypass or remove blocks. Bypass keeps the tile/settings; removed or bypassed processors do not run in the active chain.
- Use stock gate, compressor, drive, cabinet, EQ, modulation, delay and reverb, plus **FX A** and **FX B** with Pitch, Auto Wah, Chorus, Flanger, Phaser, Tremolo and Vibrato. Pitch is −12 to +12 semitones; High / Low Cut has independent cutoffs.
- Save a capture and effects into each of seven colors. Recall any color in either controller or cycle occupied slots using PRESET.
- Set a global **8 / 16 / 32-sample** output buffer on NAMLNK18+. This is output staging, not measured end-to-end latency or extra processing capacity.
- Browse TONE3000, make the selected compatible capture active after confirmed transfer, and keep favorites. Full amp-and-cab captures bypass the separate cabinet block.

**Powered by [TONE3000](https://www.tone3000.com).** Captures belong to their creators. The integration uses user-authenticated requests; source repositories and Mac installers contain no catalog captures.

## Use it

On Mac, install the preview into Applications and connect the plug over a data-capable USB cable in normal mode. The installer does not flash firmware. On iPhone, open the [controller](https://santismo.github.io/mighty-nam-controller/) in Bluefy and tap Connect. Use one controller at a time. Controls apply live; **Save to plug** makes preset edits survive power-off. The buffer is saved globally on compatible firmware.

Firmware installation is a separate, experimental step using an exact locally built image and the official NUX updater. The current local NAMLNK22 image was assembled with the owner's seven Mac-saved presets; it is not a redistributable factory bank. Updates replace onboard storage unless a specific build says otherwise. There is no complete bootloader backup or guarantee of recovery from arbitrary firmware damage.

## Source, licenses and privacy

[MIT © 2026 santismo](LICENSE) applies to original project code. Retained third-party licenses still apply: see [notices](THIRD_PARTY_NOTICES.md). NUX firmware, bootloader, hardware design and creator captures are not licensed by this project. The current firmware is a stock-based hybrid, not a fully open replacement operating system or open hardware.

[Legal and distribution notes](LEGAL.md) explain license scope, external service terms and remaining review items. [Privacy](PRIVACY.md) describes local presets, credentials and direct service connections. No claim of manufacturer endorsement, legal clearance or guaranteed hardware recovery is made.

| Folder | Contents |
| --- | --- |
| `app/` | Flutter Mac editor and native CoreMIDI/TONE3000 integration |
| `firmware/` | Original DSP, hooks, local image tools and upstream notices |
| `spec/` | Protocols and persistence formats |
| `evidence/` | Build-specific offline and physical results |
| `docs/` | Guide source; public GitHub Pages guide |
| `tools/`, `scripts/`, `examples/` | Validation, packaging and extension examples |

Historical results stay scoped to their original build. See the [latest trial](docs/pitch-quality-trial.md), [USB/NAM changes](docs/usb-audio-nam-controls.md), and [latency investigation](docs/driver-phase-investigation.md). The standalone looper remains planned.
