# Build and test

## Mac controller

Reference toolchain: Flutter **3.27.4**, Dart **3.6.2**, Xcode Command Line Tools and CocoaPods. The app declares macOS 10.15 minimum; not every macOS release or Apple-silicon machine has been verified.

```sh
cd app
flutter pub get
flutter test test/nam
(cd packages/nam_link && dart pub get && dart test)
flutter analyze lib/nam lib/main.dart test/nam
flutter build macos --release --dart-define-from-file=config/tone3000.json
```

The ordinary app suite skips one optional file-based ARM interoperability case unless `NAM_PRESET_INTEROP` is set. That is intentional. For independent distribution, register your own TONE3000 publishable application ID and redirect `mighty-nam://oauth/callback`. See `app/config/README.txt`. The release's public ID is not an account credential; sign-in tokens belong in Keychain.

## Portable checks — no plug or audio devices

CMake 3.20+, a C++20 compiler, and Python 3 are required. The preset-bank test uses address and undefined-behavior sanitizers on supported compilers.

```sh
python3 scripts/check_publication.py
python3 scripts/check_site.py
cmake -S firmware -B build/host -DCMAKE_BUILD_TYPE=Debug
cmake --build build/host -j 2
ctest --test-dir build/host --output-on-failure
```

These run CPU/memory tests and do not play sound or change audio settings. The firmware test fixtures are upstream examples; passing them does not validate a commercial capture or device deadlines.

## Local firmware builder

End users can use the [browser builder](https://santismo.github.io/mighty-nam/builder.html) or offline ZIP without a compiler. [Maintainer reproduction, provenance and tests](docs/local-builder.md) cover its source-derived patch recipe and exact file checks. Builder 0.3.0 targets NAMLNK23 and the exact public V3.0.5 Original file. It includes three MIT-licensed RiffSmith starters, whose source hashes and emulated bank are validated by the exporter. Mac 0.5.4 and phone 0.8.3 support the result. Installation uses the official NUX updater. Run `node --test scripts/test_firmware_builder.cjs`; set `MIGHTY_NAM_STOCK_FILE` to your local exact stock file to enable the complete assembly and corruption tests.

The current V3 build and test commands are in [local-builder.md](docs/local-builder.md#reproduce-offline). The examples below use an older stock base and are historical.

## Historical NAMLNK10 build example

This is a developer path, not a one-click consumer installer. `target/link/` is the current hybrid path. `target/standalone/` and `target/hardware/` are earlier independent-backend research.

The reference ARM build uses Apple clang and Zig 0.13.0. Builds on another compiler may differ; existing exact-hash evidence will then reject packaging.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r firmware/research/requirements.txt
python3 firmware/tools/build_link_firmware.py build/link10 \
  --stock-chain --m7-conv --fast-bypass --m7-dense --prime-state \
  --irq-timing --listening --early-output --output-buffer --preset-bank
```

Obtain the original **MP3 V1.5.6 Original(VT)** firmware from [NUX](https://nuxaudio.com/product/mightyplugpro/). As checked 22 October 2026, the public page lists V3.0.5 instead; request the exact older version from NUX support or use an existing lawful copy. See [stock-file instructions](docs/local-builder.md#obtain-the-input). The exact package expected by this experiment has SHA-256:

```text
95c704b6026cb26aceaae179039e994c261a93610b0c578f50634b39f4393dd6
```

Do not substitute a similarly named newer file. If the official package is unavailable, this exact experiment cannot be packaged from another version. Keep the file locally in ignored `private/`. Then, only with an unchanged reference build matching the recorded evidence:

```sh
python3 firmware/tools/stage_preset_firmware.py \
  'private/MP3_V1.5.6_Original(VT).bin' \
  build/link10/nam-link-offline.elf evidence/namlnk10 build/candidate
```

This checks the stock package, ELF-bound results, memory placement, image headers, and an empty initial preset bank, then writes a local candidate. It does **not** flash, reset, discover devices, or play audio. Expected candidate SHA-256:

```text
02f161c703568c59b096239e7de818511c80ba74848f6ba04b87b99897faf172
```

Recorded evidence is not fresh verification. Modified source needs new checks, including `research/test_preset_runtime.py`, `test_preset_storage_contract.py`, and controller/native interoperability tests. Some historical tools need local stock payloads, prior reports, and separately licensed model inputs. They are retained as research tools, not an automatic fully reproducible hardware certification pipeline.

Install only as an experimental hardware trial with the official NUX updater. [Device instructions and recovery limits](https://github.com/santismo/mighty-nam/blob/main/docs/guide.html). Installing or reinstalling this candidate empties the onboard bank. No full bootloader backup exists.

## Mac installer

Build in a neutral temporary path, strip local/debug symbols, then sign ad hoc and package. This keeps local account paths and personal certificates out of the download:

```sh
python3 scripts/build_public_macos.py --flutter flutter \
  --config app/config/tone3000.json --output build/public/mighty-nam.app
python3 scripts/package_macos.py \
  'build/public/mighty-nam.app' build/releases
```

This produces a read-only DMG containing the app, an Applications shortcut, installation help, and notices. It verifies the existing signature and generates a SHA-256 manifest. Developer ID signing and notarization are separate release steps; the public preview is ad-hoc signed and unnotarized. The packaging gate rejects personal signing certificates.

## Website

`docs/` is a dependency-free static site published at https://santismo.github.io/mighty-nam/. Both source repositories are public. No analytics, cookies, fonts, or scripts from third-party CDNs. Serve it locally with:

```sh
python3 -m http.server 8765 --directory docs
```

Edit the HTML/CSS/JS, then run `python3 scripts/check_site.py`. Gallery images render the actual controllers with simulated connections and explicitly licensed RiffSmith presets. They do not claim hardware validation of the depicted effect combinations. The local builder and its tests are documented in [local-builder.md](docs/local-builder.md).

## NAMLNK20 active-chain candidate

This NAMLNK20 reference uses the same feature flags through NAMLNK19 plus `--active-chain` (not `--active-chain-prototype` or either DMA prototype). See [trial behavior and limits](docs/active-chain-trial.md) and [exact evidence](evidence/namlnk20/README.md).

```sh
python3 firmware/tools/build_link_firmware.py build/link20 \
  --stock-chain --m7-conv --fast-bypass --m7-dense --prime-state \
  --irq-timing --listening --early-output --output-buffer --preset-bank \
  --performance --tuner --fx-blocks --cut-eq --responsive-controls \
  --nam-pointer --adc-short-delay --global-buffer --driver-timing --active-chain
python3 firmware/tools/stage_active_chain_firmware.py \
  'private/MP3_V1.5.6_Original(VT).bin' build/link20 evidence/namlnk20 build/candidate20 \
  --controller-dir ../mighty-nam-controller
```

The source checkout and exact build must match the evidence, or the gate rejects packaging. Current reports are reference evidence, not permission to skip fresh tests after changes. The package contains empty preset/settings storage and requires a backup and restore only if preserving existing presets; a clean start needs neither. Packaging does not contact the plug. USB recording compatibility is a required next-release check, not a result established by these offline tests.

## Current controller signing

Public previews must be ad-hoc signed, including nested code, with no personal developer certificate. Keep bundle ID `org.namplug.controller` and the Keychain service unchanged for data compatibility. Changing signing identity can require a new Keychain approval or sign-in; do not disable Keychain protection. A private development build may retain its existing signing identity, but must not be uploaded as a public download. The preview is not notarized.

The historical NAMLNK21 candidate and exact offline evidence are documented in [USB audio and NAM controls](docs/usb-audio-nam-controls.md). It adds `--usb-nam-controls` to the NAMLNK20 build flags. Use `stage_usb_nam_firmware.py` and fresh `test_usb_nam.py` / storage reports bound to the resulting ELF.

The historical NAMLNK22 source and validation are in [pitch quality](docs/pitch-quality-trial.md). It adds the pitch quality path to the NAMLNK21 configuration. Do not publish locally assembled hybrid images or personal preset banks.
