# Evidence and its limits

Recorded NAMLNK10 results bind to ELF SHA-256 `7b92cb19fd515067c65034e27cf8c7b4364e4a5100a05b8fde0f36946e7151c9`.
These are original lab records, not fresh execution by your checkout or hardware guarantees.

- 252 portable bank cases, including torn writes, corruption fallback, and sanitizer checks.
- ARM emulator: seven recalls, stock PRESET branch and wrap/empty skipping, three cold patterns and three warm restarts.
- Two locally licensed A2 Lite captures matched the reference through 1,300 blocks each. These captures are not redistributed; reproducing those exact comparisons requires the original inputs.
- Stock flash wrapper/MPU behavior modeled; real flash endurance, cache behavior, button LEDs, timing, and NAMLNK10 recovery remain unverified.
- 50 app tests, 34 shared protocol tests, 1,557 native wire checks, plus Dart/Swift/ARM request/reply interoperability.

The included baseline09 reports support unchanged DSP/output object comparisons. They are not newly executed NAMLNK10 long-run tests. Historical physical listening on NAMLNK08 succeeded with a Fender capture and selected spring reverb/delay combinations; this is a single-unit observation, not a full-effects certification.

For new source changes, regenerate the relevant results. The packaging gate rejects an ELF whose digest differs from these reports. Do not edit result hashes merely to force packaging.
