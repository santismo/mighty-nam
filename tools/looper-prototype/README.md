# Looper prototypes

See [controls, compressed transport, tests and RAM findings](../../docs/looper-research.md).
Nothing here is integrated into NAMLNK24 or the public builder. There is no device access or audio playback.

- `test.cpp`: gestures and color selection.
- `test_audio.cpp`: initial PCM prototype across simulated guitar reloads.
- `test_compressed.cpp`: full 30-second IMA recordings at 48/24 kHz, live A2 Lite at 48 kHz/eight frames, 60-second playback and model changes, sanitizers and bounds checks.
- `check_compression.py`: independent CPython codec oracle and filter/quality measurements.
- `test_compressed_arm.py`: bounded actual ARM NAM/stock reverb and four preset recalls, native parity, full-length storage boundary/wrap checks. Loop code/storage use artificial emulator addresses, never a physical RAM allocation.
- `ram_audit.py`: bounded runtime CPU ownership observations and static initialization/literal leads. Unobserved space is not proven free.

Run from the repository root with a prepared V3 NAMLNK24 research directory (`generated/research`, `generated/tools`, `build/nam-link-offline.elf`) and its exact decoded stock payload. The runner extracts only the three pinned MIT RiffSmith A2 Lite models already in this repository; it never reads a personal capture library.

```sh
research-python tools/looper-prototype/run_offline.py \
  /path/to/v3-work /path/to/stock-payload.bin /tmp/mighty-loop30 \
  --signal-python python3.12
```

Replace `/path/to/v3-work` above with the single path to the prepared research directory (quote paths containing spaces). `research-python` means the Python environment with Unicorn, Capstone, pyelftools and ziglang; `--signal-python` needs Python 3.12 with numpy and stdlib `audioop`. Clang++ must support native macOS and `arm-none-eabi` builds. The native parity library is macOS-specific. This runner creates local data/test executables and JSON only, not an installable firmware container.

The work directory contains raw numeric test fixtures, not files intended for listening. The public reports omit those fixtures and all stock/firmware binaries. The 30-second result proves component behavior with supplied memory; physical RAM ownership, flash-read scheduling, button hooks and hardware deadlines remain unresolved.
