# NAMLNK27 offline evidence

The latest looper source fixes the short physical tap case, carries the overdub
encoder state between rewritten blocks and adds storage headroom. A live raw-input
peak is returned in one compact status packet for a threshold slider meter.

The exact build, startup, audio/media, preset continuity, layer, button, native
and staging reports are bound to the same ELF hash. The old image fails the added
12 ms stock-scanner tap case; the new image passes. Quality metrics use numerical
signals and do not replace a listening test. All checks in this set are offline.

Mac 0.5.8 and phone 0.8.7 expose the controls. The simulator screenshot is UI
verification, not a real Bluetooth connection or hardware measurement. No device
was accessed, muted or flashed. No audio stream was opened. Public firmware
building remains at NAMLNK23 r2. Personal captures and complete generated images
are excluded from this repository.
