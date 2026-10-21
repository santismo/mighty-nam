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
- Includes experimental seven-color onboard presets: capture, effects, order, settings, name, and output buffer per color.
- Exposes 8 / 16 / 32-sample output staging at 48 kHz in the new firmware. This does not change the processing block or increase CPU capacity.

## Current state — read before updating

| Component | State |
| --- | --- |
| Mac controller 0.3.2 | Handles large CoreMIDI replies and enables Listen for verified onboard captures even without a Mac-library copy. Universal build; Apple-silicon execution is not separately verified. |
| Mac controller 0.3.4 / NAMLNK12 | App and firmware installed locally; seven presets restored and switched successfully; quiet tuner transport passed. Adds a chromatic USB tuner and includes the NAMLNK11 preparation/profiling work. No measured latency reduction claimed. See [trial notes](docs/tuner-performance-trial.md). |
| NAMLNK08 | Live NAM guitar listening and selected delay/reverb combinations worked on the development unit. |
| NAMLNK10 | Physically installed. Seven captures/effects presets saved, recalled, and checked after a user power cycle. Buffer settings 8/16/32 recalled correctly. |
| Seven presets | All seven saved records matched after restart; the user confirmed seven-color button cycling. Tested combinations had zero processing faults. This does not establish flash endurance, every effect combination, or NAMLNK10 recovery. |
| Looper / phone control | Next goals, not shipping features. iPhone is the first phone target. |

This is an experimental, stock-based hybrid. Our source is open; NUX's firmware, bootloader, and proprietary DSP are not ours to license and are not distributed here. This does not make the physical hardware open source. Bring your own exact stock firmware for local firmware construction.

The local 0.3.4 app includes preset-reply and onboard-listening fixes plus the NAMLNK12 tuner; the hosted 0.3.0 installer is older. The older release asset has not been replaced. See [physical preset results](evidence/10-physical-persistence-summary.json). TONE3000 integration terms review remains outstanding; private repository access does not resolve that review.

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

NAMLNK13 is an **offline-tested experimental candidate** adding two movable FX blocks and short Bluetooth reply pages. It has not been installed or validated on hardware. See [trial notes](docs/dual-fx-trial.md). The public [controller 0.4.0](https://santismo.github.io/nam-plug-controller/?v=0.4.0) supports it and retains NAMLNK12 fallback behavior.
