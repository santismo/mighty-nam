# Current-block DMA experiment

Offline-only NAMDMP01 prototype based on NAMLNK19. This is not an update release.
The normal image builder rejects its identity unless a research caller supplies
`allow_dma_prototype=True`; release packagers do not supply that opt-in.

Run from a Python environment with the existing lab dependencies (Unicorn,
capstone, pyelftools, ziglang), with clang++ on PATH:

```sh
python tools/dma-current-prototype/run_offline.py \
  /private/path/MP3_V1.5.6.payload \
  /private/path/first-a2-lite.nam \
  /private/path/second-a2-lite.nam \
  /private/path/dma-prototype-results
```

The first model must be the established Fender fixture and the second the
Marshall Lite fixture to reproduce the recorded evidence. Only hashes of these
private inputs appear in the reports. No stock payload or model is distributed.

The runner rebuilds NAMLNK19, builds the experiment, executes real ARM DSP and stock
startup in the CPU harness, checks diagnostics, and runs the FIFO/service model.
It produces ELF/object files and JSON/logs, never an updater `.bin`. It does not
load MIDI, USB, audio playback, device-volume, or app-control tools.

Passing the suite includes detecting deliberately bad DMA timing. It does not
make this prototype ready for installation. Actual bus timing, publication
margin, cache/store visibility and startup phase remain unverified.
