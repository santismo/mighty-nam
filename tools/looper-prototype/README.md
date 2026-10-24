# Looper prototypes

The latest source-only preview is [NAMLNK29 independent lanes and preset-save fixes](takes/README.md). It adds reusable overdub lanes and one-edit undo within the existing RAM pool.

See [controls, compressed transport, tests and RAM findings](../../docs/looper-research.md).
Nothing here is integrated into NAMLNK24 or the public builder. The separate
[NAMLNK25 hardware-test sources](hardware/README.md) add startup integration and
local diagnostic-image staging. Offline tests never access devices or play audio;
the explicitly invoked MIDI client is reserved for a later physical trial.

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

## Candidate device RAM and interruptible preset loads

The newer RAM-only overlay moves storage into two candidate device-address ranges
and keeps the mixer running while actual preset loading is preempted by audio IRQs.
It is **not an installable firmware**. Stock MPU/startup and bounded CPU ownership
checks do not prove physical DMA ownership, cache coherency or real-time timing.

- `layout.hpp`, `test_segments.cpp`: fixed split storage, exact byte parity and bounds.
- `audit_layout.py`: 80 stock loader cases, heavy chains, guarded memory/helper spans and negative controls.
- `audit_memory_contract.py`: actual stock MPU/C-runtime routines with modeled registers; initialization ordering and apparent-pointer classification.
- `continuity.cpp`, `continuity.ld`, `build_continuity.py`: AHB reads, independent loop mixer and pause path, write rejection, exact baseline ELF pin. No flash load address or boot copy.
- `test_continuity.py`: actual ARM IRQ interleaving during recalls, stock preset-button path, separate interrupt stack, native playback/recording parity, failed save/recall and full-store split/wrap.

```sh
research-python tools/looper-prototype/run_continuity.py \
  /path/to/v3-work /path/to/stock-payload.bin /tmp/mighty-loop-continuity \
  --signal-python python3.12
```

The dependencies and pinned NAMLNK24 baseline are the same as above. This separate
runner regenerates its fixtures from the three licensed repository captures, runs
the sanitizer/oracle checks, builds only a local RAM ELF, and writes JSON evidence.
The ELF requires the baseline in the emulator and cannot be passed to the normal
image builder. The research backend rejects **all** preset flash writes; production
firmware and the public builder are unchanged.
