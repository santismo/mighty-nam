# NAMLNK20 offline release evidence

Exact release ELF: `6cd51578d2ec623c9c44c5350bafaf564bead7b79a66b6b3ca83e881b01df8d6`.
Candidate: `c59c771251241aab0bdf441fd7ecaa45a5d298c3294686defb7ee88ca8d67046`.

These are offline results. No NAMLNK20 device installation, headphone listening, physical latency, recovery-mode check or USB recording test was performed. App 0.4.0 was installed without launching or connecting it. Controller 0.7.0 browser checks used local simulated BLE; real phone tests remain.

`arm.json` is the completed combined graph/PCM/transition/storage run. `startup.json` also contains three separately identified NAMDMP02 research cases; only its exact NAMLNK20 rows gate this release. `controller.json` binds the tested phone/Mac source files. Host DSP reports are retained from NAMLNK19 only where the source hashes remain identical and are checked by the package gate. `equivalence.json` compares the earlier offline graph prototype, whose allocated code differs only in the firmware identity. The metadata-only linker-hash fix rebuilds to the same exact tested ELF.

One initial cut-EQ test invocation mistakenly supplied NAM JSON where its fixture required a packed slot. The corrected packed-slot run passed, as recorded in `cut-arm.json`; no firmware modification was needed. Mac navigation tests found and fixed a PageStorage key collision when returning to search. Final Mac suite: 85 pass, one intentionally skipped optional external-ARM fixture. Final phone suite: 105 pass. Native wire suites: 1,677 stock, 85 FX and 921 tuner checks. The package gate rejected all eight invalid-evidence/source/package cases.

Captured NAM models, manufacturer payloads, app binaries and firmware containers are not in this repository. Generated packages remain local.
