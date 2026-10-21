# NAMLNK20 — active signal chain trial

NAMLNK20 executes only the effects present in the signal chain. With NAM and reverb selected, it runs two effect processors. Phone controller 0.7.0 and Mac app 0.4.0 show those two blocks, with controls below the selection and an **Add block** menu. The block symbol or selected-block Remove action removes the effect from processing. Adding it restores its settings. Reordering, seven-color saves, capture loading, global 8/16/32 output buffering and tuning retain the existing protocol.

The nine stock categories and two custom FX slots remain available. Removing an effect does not reclaim its static memory. Removing delay or reverb stops its tail; adding it again resets history. Older firmware keeps the full bypass-based UI. Existing saved presets become active-only chains when restored on NAMLNK20.

The Mac TONE3000 browser keeps search results alongside capture details on wide windows, exposes the official picker at the top, shows the current capture, and provides an explicit **Load on plug** action. Compatible downloaded captures become active only through the existing validated transfer/readback workflow; multiple local favorites remain supported. Browse-only cabinet IRs are not advertised as transferable NAM captures.

## Offline evidence and limits

The exact NAMLNK20 ARM build passes active graph execution/PCM comparisons, all seven custom FX modes, insertion/removal/reordering, saved membership, cold/warm startup, two NAM reference models, preset storage, button branches, global buffer persistence, High / Low Cut response and compact tuner protocol checks. The planner covers 450,560 membership/order combinations under address and undefined-behavior sanitizers. Controller tests use simulated devices, never the connected plug.

NAM + spring executes 53,259 emulator instructions versus 56,435 on NAMLNK19 (5.63% fewer), with identical tested settled PCM. This measures work, **not physical latency**. The 48 kHz sample rate, eight-frame DSP block, converter settings and previous-block output schedule remain unchanged. The separate guarded DMA experiment is excluded. Optional one-shot DMA snapshots and per-effect profiling are omitted for space; whole-IRQ timing and graph status pages 118–123 remain.

No NAMLNK20 physical timing, listening, USB recording or phone-transfer result is claimed yet. Tests cover bounded settings, not every possible effect combination. USB recording compatibility with Logic Pro is the next explicit regression requirement in the roadmap.

## Prepared update

The local file is `NAMLNK20-active-chain-test.bin`. It is an experimental candidate, not an installed or general-use release. The package gate verifies exact ELF/report hashes, current source/header/linker hashes, the stock container, record headers, vectors, IRQ placement and empty bank/settings ranges.

Updating clears the onboard preset bank and global settings. Back up and restore only if keeping the existing presets; otherwise start with empty slots and save new presets after installation. The current user has chosen to discard the old presets, so this trial will not make a backup. No installation, mute, audio-device access or playback is performed by preparation. Empty-bank startup is muted; restored saved presets retain their playback intent. Do not interpret this as automatic muting during development.

The physical trial should verify identity, save/read back new presets (or restore a bank if retained), select a two-block NAM + reverb chain in both controllers, check whole-IRQ timing and faults, exercise add/remove/reorder, then check button cycling and restart persistence. Listening and recovery checks remain separate physical steps. Keep the current NAMLNK19 installation until that trial is requested.
