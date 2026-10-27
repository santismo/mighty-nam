# NAMLNK29 revision 2 — seven presets, NAM only

The only firmware change from the pre-stock-amp NAMLNK29 is CPU cache-line invalidation after successful preset/settings erase and program operations. The existing bounded FlexSPI reset remains. The live audio path, NAM working-data placement, 48 kHz rate and output staging are unchanged. No NAMLNK30 stock-amp code is included.

The stale CPU-read fixture reproduces save error 3 on slot four with original NAMLNK29. The revised compiled image passes 21 saves/overwrites over seven slots, alternating USB/BLE framing, arbitrary recall, restart/button cycling and failed-write preservation. This is a modeled cache failure, **not proof of the hardware cause or a successful physical repair**.

The public builder starts all seven colors with three MIT RiffSmith A2 Lite captures repeated in order. Each color runs 1,600 compiled ARM callbacks against the independent NAM reference (11,200 total), with cold/warm startup and cycling. Code packaging rejects incomplete or stale test reports. Original NAMLNK28 and NAMLNK23 r2 output hashes remain unchanged.

The actual browser UI and extracted offline ZIP both build the independently staged output with seven presets and no external requests. Current builder tests: 29 passed, 2 skipped optional alternate-stock inputs. Older builders: 21 passed each, 7 skipped version-specific or optional-input cases. Updated screenshots render current Mac 0.6.1 / phone 0.11.4 interfaces with simulated connections and licensed examples.

Native ASan/UBSan and compiled ARM checks cover audio/USB/Bluetooth routing, looper layers, preset changes, startup and saved settings. Native full-duration coverage is 2,700,000 eight-frame callbacks and 86 NAM changes. These do not measure target-cycle deadlines or establish peripheral/RAM safety on hardware. No device access, flashing, auto-mute or host audio operations occurred.

Public downloads contain owned compiled changes, generated hooks and licensed captures only. Full combined firmware and personal presets remain local. Controller commands remain compatible with Mac 0.6.1 and phone 0.11.4. Physical seven-slot save/power-off validation of this revision is still pending.
