# NAMLNK17 physical trial helpers

Build with `python3 tools/namlnk17-trial/build.py OUTPUT_DIRECTORY`. Compilation performs no USB operation. The four binaries mirror the established 16 restore, timing, restart and compact-tuner checks using production MIDI. They do not flash firmware or play Mac audio.

Restore and restart checks require exact NAMLNK17 identity and cached converter startup status `0xc10f220a`. The timing tool also accepts NAMLNK16 for the pre-update baseline; NAMLNK17 timing stops before changing effects or the buffer if readback is unverified. Use a fresh seven-preset restore plan collected in normal mode before installation. Model traces and private backup data stay outside Git. Read the [converter trial](../../docs/converter-latency-trial.md) for the installation and validation sequence.

Do not run the physical tools while the user is listening. First confirm headphones are unplugged, USB remains connected and other controllers are disconnected. The restore tool writes onboard presets, checks every record and leaves output muted. Saved startup-output flags remain enabled, so keep headphones unplugged during physical restart and color cycling.
