# NAM Plug

**Neural Amp Modeler on a NUX Mighty Plug Pro. An open controller, firmware experiments, and a documented path from guitar to headphones.**

By [santismo](https://github.com/santismo). Original project code is MIT licensed; upstream notices are retained.

[Guide source](docs/guide.html) · [Mac installer](https://github.com/santismo/nam-plug/releases/tag/v0.3.0-preview.1) · [Roadmap](ROADMAP.md) · [Build from source](DEVELOPMENT.md)

The repository is private and GitHub Pages is disabled. The guide source remains available here.

## What it does

- Runs compatible **48 kHz NAM A2 Lite** captures on the plug.
- Provides a Mac editor with a movable signal chain, block bypass, and controls below the selected block.
- Browses TONE3000 after sign-in; selecting a compatible capture makes it the active NAM capture. Favorites stay in your Mac library.
- Retains the stock gate, compressor, drive, cabinet, EQ, modulation, delay, and reverb. Full amp-and-cab captures automatically bypass the separate cabinet block.
- Adds a chromatic tuner in the Mac app with NAMLNK12, using dry-input snapshots over USB MIDI. Quiet transport checks passed; real-guitar tuning checks remain.
- Includes experimental seven-color onboard presets: capture, effects, order, settings, and name per color; NAMLNK18 makes output buffering global.
- Exposes 8 / 16 / 32-sample output staging at 48 kHz in the new firmware. This does not change the processing block or increase CPU capacity.

## Current state — read before updating

| Component | State |
| --- | --- |
| NAMLNK18 / Mac 0.3.10 / phone 0.6.5 | Global persistent buffer and playback-preserving edits; earlier NAM hot-code/table placement restored. Offline checks passed; firmware not installed or physically measured. See [global buffer trial](docs/global-buffer-trial.md). |
| NAMLNK17 / Mac 0.3.9 / phone 0.6.4 | Installed; converter startup readback, seven restored presets, restart/color cycling and fault-free eight-sample checks verified. CPU snapshots were about 5–6% higher than the immediate 16 baseline; cause remains under investigation. Approximate 0.292 ms converter saving is predicted, not measured. See [converter trial](docs/converter-latency-trial.md). |
| NAMLNK16 / Mac 0.3.8 / phone 0.6.3 | Installed and verified over USB. All seven fresh-backed-up presets restored and checked after power-off; user confirmed color cycling. Quiet matched-chain runs used 4.0–4.6% fewer median IRQ cycles than 15. Mac app installed and phone controller live. Fixed audio path unchanged; no measured guitar-to-headphone latency reduction claimed. See [NAM processing trial](docs/nam-performance-trial.md). |
| NAMLNK15 / Mac 0.3.7 / phone 0.6.2 | Installed on the development plug. Seven presets restored and independently checked after power-off; the user confirmed seven-color button cycling. Live FX controls and compact quiet USB tuner checks passed. Physical listening latency and Bluefy tuner cadence remain unmeasured. See [responsive controls](docs/responsive-controls-trial.md). |
| NAMLNK14 / Mac 0.3.6 / phone 0.6.0 | Installed locally. High / Low Cut has independent live sliders; muted USB control, full-chain and fresh preset save/recall checks passed. The user confirmed the cut EQ works. Broader listening and post-save restart checks remain. See [EQ trial notes](docs/high-low-cut-trial.md). |
| Mac controller 0.3.2 | Handles large CoreMIDI replies and enables Listen for verified onboard captures even without a Mac-library copy. Universal build; Apple-silicon execution is not separately verified. |
| Mac controller 0.3.4 / NAMLNK12 | App and firmware installed locally; seven presets restored and switched successfully; quiet tuner transport passed. Adds a chromatic USB tuner and includes the NAMLNK11 preparation/profiling work. No measured latency reduction claimed. See [trial notes](docs/tuner-performance-trial.md). |
| NAMLNK08 | Live NAM guitar listening and selected delay/reverb combinations worked on the development unit. |
| NAMLNK10 | Physically installed. Seven captures/effects presets saved, recalled, and checked after a user power cycle. Buffer settings 8/16/32 recalled correctly. |
| Seven presets | All seven saved records matched after restart; the user confirmed seven-color button cycling. Tested combinations had zero processing faults. This does not establish flash endurance, every effect combination, or NAMLNK10 recovery. |
| Phone controller | GitHub Pages / Bluefy 0.6.0 adds TONE3000 selection, local favorites, A2 Lite Bluetooth transfers and saving new captures to seven colors. Real browser, simulated BLE and exact ARM checks passed; user deferred the physical phone transfer. The looper remains a later goal. |

This is an experimental, stock-based hybrid. Our source is open; NUX's firmware, bootloader, and proprietary DSP are not ours to license and are not distributed here. This does not make the physical hardware open source. Bring your own exact stock firmware for local firmware construction.

The local 0.3.10 app includes FX A/B, High / Low Cut and explicit NAMLNK15/16/17/18 support, plus the prior preset, listening and tuner features; the hosted 0.3.0 installer is older. The older release asset has not been replaced. See [physical preset results](evidence/10-physical-persistence-summary.json). The phone 0.6.0 integration follows the official free picker/bounded-feed workflow; separate Mac-app and distribution terms review remains outstanding. Private repository access does not resolve that review.

## Install the Mac app

1. Download `NAM-Plug-0.3.0-macOS.dmg` from the preview release.
2. Open it and drag **NAM Plug** to **Applications**.
3. Launch NAM Plug. This preview is ad-hoc signed, not Apple notarized; see [installation help](docs/guide.html#install).
4. Connect the Mighty Plug Pro by a data-capable USB cable in normal mode. The app requires a compatible custom firmware for NAM control; installing the Mac app alone does not install that firmware.

The app installer does not flash the device or change system audio. Start hardware checks with headphones unplugged, then use the plug's headphones at low volume for listening.

## Firmware and captures

There is no bundled NUX image and no one-click flasher. The exact NAMLNK10 candidate can be built locally from original project source, recorded validation evidence, and the exact user-supplied stock package. [Developer steps](DEVELOPMENT.md#firmware-candidate) preserve the existing checks; the official NUX updater performs the actual update.

The bootloader has not been fully backed up. Restore with stock firmware depends on the updater remaining reachable. NAMLNK10 has not yet demonstrated recovery. Reinstalling this candidate clears its onboard preset bank; keep captures and presets in the Mac library.

TONE3000 captures have their own creator licenses. Your account/session, personal library, and downloaded captures are never part of this repository. The included `.nam` files are upstream test fixtures, not a playable capture bundle.

## Repository map

| Path | Contents |
| --- | --- |
| `app/` | Flutter Mac controller, TONE3000 client, native CoreMIDI bridge, tests |
| `firmware/target/` | A2 Lite processing, device hooks, startup/audio prototypes, onboard bank |
| `firmware/research/` | Reverse-engineering tools and bounded ARM emulation tests |
| `firmware/tools/` | Local builds, container inspection, and checked candidate packaging |
| `spec/` | Wire formats, control mappings, persistence formats |
| `evidence/` | Recorded test results; distinguishes simulation from physical results |
| `docs/` | GitHub Pages site; plain HTML, CSS, and JavaScript |
| `scripts/` | Offline checks, site validation, reproducible installer packaging |
| `tools/`, `examples/` | Release-file verifier, historical hardware trials, custom-effect examples |

## License and credits

[MIT © 2026 santismo](LICENSE) covers original NAM Plug contributions. [Third-party notices](THIRD_PARTY_NOTICES.md) preserve Mightier Amp, NeuralAmpModelerCore, Eigen, nlohmann/json, musl, and dependency licenses. NUX, Neural Amp Modeler, and TONE3000 identify interoperability targets; this is an independent project.

NAMLNK13 is **installed for an experimental trial**, adding two movable FX blocks and short Bluetooth reply pages. Initial muted USB runs passed, and the user confirmed Bluefy reaches Ready with both FX blocks visible. Listening quality, calibrated deadlines and phone save/tuner checks remain outstanding. See [trial notes](docs/dual-fx-trial.md). The public [controller 0.4.1](https://santismo.github.io/nam-plug-controller/?v=0.4.1) adds a second enable/bypass control in the selected-block header and retains NAMLNK12 fallback behavior. This historical controller has been superseded by 0.6.0; see the current trial notes below.

NAMLNK14 adds **High / Low Cut** to the movable EQ block, with independent Off settings, live controls and saved cutoffs. Matching controllers: Mac 0.3.6 and [phone 0.5.0](https://santismo.github.io/nam-plug-controller/?v=0.5.0). It is installed on the development plug; bounded muted USB controls and preset save/recall passed. See [EQ trial notes](docs/high-low-cut-trial.md).

The public [phone controller 0.6.0](https://santismo.github.io/nam-plug-controller/?v=0.6.0) now browses TONE3000, extracts A2 Lite, loads captures through the existing NAMLNK14 Bluetooth protocol and saves captures/FX to chosen colors. All 63 tests passed and real sign-in/download worked. The user will test the physical Bluefy transfer later; see [phone trial notes](docs/phone-tone3000-trial.md).

Phone controller 0.6.1 adds automatic tuning, confirmed/saved buffer values and standalone startup-output defaults. See [phone fixes and validation](docs/phone-tuner-buffer-startup.md). No NAMLNK14 firmware update is required; the reported physical latency difference remains under investigation.

Mac 0.3.7, phone 0.6.2 and the installed NAMLNK15 trial address extra-block editing, the single-saved-color pause, idle FX work and tuner transport overhead. Seven restored presets survived a physical restart, and the user confirmed button cycling through every color. Standalone playback was observed on at startup; the final USB check explicitly muted current output. See [scope, evidence and physical limitations](docs/responsive-controls-trial.md).

The [minimal-chain investigation](docs/latency-workload.md) compares NAMLNK10/12/15, measures retained work after bypassing effects, and tests an isolated NAM optimization. It reduces simulated instruction events by 3.79% for NAM alone and 3.33% with Spring, with identical tested output. A separate converter-filter option has a datasheet-predicted 0.292 ms benefit. NAMLNK16 subsequently shipped the NAM processing optimization and was verified on the plug. The separate [NAMLNK17 converter trial](docs/converter-latency-trial.md) is installed with verified startup readback and preset persistence; neither result establishes measured guitar-to-headphone latency.
