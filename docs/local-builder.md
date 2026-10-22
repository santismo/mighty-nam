# Local firmware builder

Builder **0.3.0** creates experimental **NAMLNK23** from the publicly downloadable **NUX V3.0.5 Original** file. The public starter variant has offline validation; NAMLNK23 core has limited physical validation documented on the [Status page](status.html). These packaging tests do not access a device or play audio.

## Obtain the input

Use the official [Mighty Plug Pro downloads](https://nuxaudio.com/product/mightyplugpro/), Support → Firmwares → V3.0.5 for macOS. Extract `MP3_OR_V3.0.5.bin`. The package also contains a ChopTones (`CT`) variant; that is not supported. The ZIP can be extracted on other computers.

Exact accepted container:

- Size: 15,009,655 bytes.
- SHA-256: `39fa7057865f95e4c52c48544cd8284f4da606d3ac29e985e9b8938a3237467e`.
- Decoded payload: 14,229,504 bytes.
- Payload SHA-256: `e971240a1e333003804cfd154e5ee053026254bbf09b11499e8b4968d3600752`.
- Format 2, setup `PLUGXDFU20240812`, TEXT/BINA/EXTR sections.

The builder rejects other files before applying changes. V1.5.6 Original(VT) is no longer required or accepted. Do not rename an unsupported file to bypass validation.

## What is distributed

The recipe contains allocated code sections compiled from original project sources, generated branch/pointer replacements, erase-fill instructions, checksums, and three RiffSmith preset records. The creator explicitly licenses these captures under MIT; pinned sources and notices are in `firmware/models/riffsmith`. It contains no original stock sections, opaque stock headers, generic binary-diff literals, firmware container, private presets or TONE3000 catalog captures. The combined firmware is assembled in the user's browser from their supplied file. It remains a hybrid containing NUX code and is not wholly MIT licensed.

The page has no upload endpoint, device API, audio API or analytics. Its CSP disallows connections and forms. Inputs are copied before asynchronous work; generation never overwrites the input file. Exact before/after hashes, allowed patch locations, overlap checks, unchanged vectors, preserved record headers, and an independently staged output hash gate the download.

The offline kit includes all browser build scripts. Browser file-mode support varies; if access is blocked, use the HTTPS builder or a local web server. Do not disable browser security. No compiler is required by an end user.

## V3 port

`firmware/ports/v3/relocations.json` is an explicit address adapter, not a runtime pattern finder. `prepare.py` retains inspectable generated sources and hashes of both source and generated forms. The shared legacy source is compiled with `MPP_STOCK_V3`, which handles V3's F7-inclusive SysEx length. The stock audio/USB/preset addresses were remapped; peripheral register addresses, 48 kHz rate, eight-frame processing, and existing prior-block output scheduling remain unchanged.

The retired AMP region `0x1c0e8..0x1d830` contains the new low code. Copied code lives at `0x2030f000` and is loaded from retired AMP storage `0x303a6000`. Seven preset slots remain at `0x30384000..0x303a0000`; global settings remain at `0x303a4000..0x303a6000`. The replaced stock audio callback body is preserved. Bounded incoming-reference audits cover seven retired AMP models. One apparent flash pointer is compressed C-initializer data; executing the original decompressor reproduces the initialized DTCM hash and yields no pointer into the reclaimed storage.

These are bounded static and CPU checks, not exhaustive indirect-reference or hardware proofs. Stock initialization, effects, MIDI assembly, button selection, USB PCM conversion and flash wrapper instructions execute in the emulator. Physical peripherals, flash completion, USB enumeration and timing counters are modeled.

## Reproduce offline

Use Python with Unicorn 2.1.4, Capstone 5, pyelftools and ziglang 0.13, plus Apple clang. No connected plug is required. Keep user stock files, captures and generated firmware outside the repository.

```sh
python firmware/tools/build_public_v3.py /path/to/local-build
```

Decode the user-supplied container with `firmware/tools/nux_container_lab.py`'s `Container(...).payload`. With an independently built NAM reference library and your own compatible A2 Lite capture, run:

```sh
python /path/to/local-build/generated/research/test_usb_nam.py PAYLOAD ELF MODEL REFERENCE_LIBRARY /path/to/local-build/arm.json --pitch-release
python /path/to/local-build/generated/research/test_preset_storage_contract.py PAYLOAD ELF --output /path/to/local-build/storage.json
python firmware/ports/v3/test_runtime.py /path/to/local-build/generated PAYLOAD ELF MODEL REFERENCE_LIBRARY /path/to/local-build/runtime.json
python /path/to/local-build/generated/research/test_pitch_chain.py PAYLOAD ELF MODEL REFERENCE_LIBRARY /path/to/local-build/chain.json
python firmware/ports/v3/test_staging.py STOCK_BIN /path/to/local-build /path/to/local-build/staging-tests.json
python firmware/tools/stage_public_v3.py STOCK_BIN /path/to/local-build/build /path/to/local-build /path/to/local-staged
python scripts/build_starter_presets.py /path/to/local-build PAYLOAD REFERENCE_LIBRARY /path/to/local-starters
python scripts/package_firmware_builder.py STOCK_BIN /path/to/local-build/build /path/to/local-build /path/to/local-kit --starter-bank /path/to/local-starters/starter-bank.bin --starter-report /path/to/local-starters/starter-bank.json
MIGHTY_NAM_STOCK_FILE=STOCK_BIN node --test scripts/test_firmware_builder.cjs
```

`ELF` is `/path/to/local-build/build/nam-link-offline.elf`. Staging fails on stale source, generated source, linker, ELF or test report hashes. The kit exporter independently reconstructs the staged baseline plus a strictly validated public starter bank using only allowed operations and requires byte equality. Source hashes, model-slot CRCs, record commits/padding, emulator reports and all three source licenses are checked. The three populated colors run NAM only; remaining colors are erased. The ZIP uses a curated file allowlist and fixed metadata.

## Controller compatibility

NAMLNK23 capability allowlists and protocol fixtures are updated in both controller sources. Unknown future identities remain rejected. Mac 0.5.4 and phone 0.8.3 support NAMLNK23. Mac Settings opens official download, local build and manual installation resources. Exact starter model identities resolve to bundled names and metadata without replacing private captures.

## Installation status

Nothing is automatically installed. Flashing is a separate, explicitly chosen operation. Installation replaces all seven onboard NAM slots and global settings. Green, Orange and Red contain RiffSmith Clean, Bass Clean and Distorted; four slots remain empty. Each uses the 48 kHz A2 Lite component with its included cabinet. Save any additional captures to a color after installation. Saved playback intent and global buffer settings are retained on subsequent power cycles.

NAMLNK23 has been installed on the development unit with private presets and confirmed guitar output. The new public starter bank has not been physically tested. An intact reachable updater is required to restore stock; full bootloader backup and recovery from arbitrary damage are not established. Local building reduces bundled third-party material but does not establish legal clearance or grant redistribution rights. See [LEGAL.md](../LEGAL.md) and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
