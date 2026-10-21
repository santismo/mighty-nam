# Active-chain offline runner

Run with the lab Python environment containing Unicorn, capstone, pyelftools and
ziglang. Clang must support the Cortex-M7 cross target and native sanitizers.

```sh
python run_offline.py STOCK_PAYLOAD A2_LITE_CAPTURE REFERENCE_LIBRARY OUTPUT_DIRECTORY
```

The stock payload must match the project's exact V1.5.6 hash. The capture and the
existing independent A2 reference library remain local inputs; do not commit
them. The runner builds a byte-checked NAMLNK19 baseline and a `NAMACP01` ELF,
runs the sanitized planner test and the compiled ARM comparisons. It produces
logs and JSON only, apart from local build binaries. No updater container,
USB/MIDI access, app launch, host playback or device output commands occur.

See [the design and limitations](../../docs/active-chain-prototype.md).
