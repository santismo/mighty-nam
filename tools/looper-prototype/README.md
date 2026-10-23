# Looper prototypes

See [controls, PCM transport, tests and memory findings](../../docs/looper-research.md).
`test.cpp` checks gestures; `test_audio.cpp` checks recording and playback across simulated guitar-preset reloads. Both run with ASan/UBSan and no audio I/O. Storage is caller-owned host memory; neither prototype is integrated into NAMLNK24.
