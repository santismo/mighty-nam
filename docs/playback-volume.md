# Playback and master volume

Mac 0.4.1 is installed in Applications; controller 0.7.1 is deployed on the public controller Pages site. [Validation record](../evidence/playback-volume/validation.json).

Mac 0.4.1 (16) and phone controller 0.7.1 remove the manual Listen/Mute controls and startup-mute checkbox. Master volume is a live 0–100 stock patch-level control, saved per color by Save to plug. It does not change any Mac output device, system volume, or Teams audio. A successful capture transfer or tuner return resumes the verified capture; transfers still stop output while replacing model state, and processing faults remain guarded.

The command is stock MIDI CC73 / preset byte84. It passes the same bounded control plan and independent preset readback as effect parameters. No NAMLNK20 firmware change is needed. The firmware retains its stock volume smoothing, output protection and existing headphone knob.

Model downloads follow at most four HTTPS redirects, only for the model-download endpoint. Bearer authorization is removed permanently when leaving the API origin. Other API redirects remain rejected. Downloaded bytes must parse as the exact supported 48 kHz A2 Lite topology; incompatible files do not become active. A2 multi-size containers select their Lite submodel.

## Validation

- 85 Mac widget/behavior tests pass; one optional compiled-ARM test is skipped in this app-only suite.
- 22 account/download tests and 1,689 native wire assertions pass.
- 108 phone tests pass, including bounded volume, no implicit save, output preservation and guarded tuner return.
- Simulated browser: master37→25 applied live, output remained on, preset marked unsaved. The page shows only NAM and Reverb for that two-block fixture. This is not a real Bluetooth test.
- Physical NAMLNK20: volume37→32→37 confirmed by full preset readback; model CRC1854512385 unchanged, output on, zero faults, no preset saves or mute commands.
- At the user's request, all seven colors were seeded with the locally held Fender Super Reverb A2 Lite capture and NAM+Spring chain. Each save was independently read back and all colors recalled over USB, ending on Green, 8 samples, playback on and zero faults. No preset backup was made. A power-cycle/button check after this new seeding remains outstanding.
- The local Mac library and fallback capture were populated outside the repository. Manufacturer firmware, model weights and account credentials are not distributed here.

## USB audio remains separate

NAMLNK20 enumerates as a two-input/two-output USB audio device, but its replacement audio callback does not call the stock PCM exchange at 0xccec or the stock USB playback mix. This is a firmware-path omission, independent of the MIDI controller and master-volume controls. Logic duplex operation has not been repaired or verified by this app update. No host audio stream was opened and no firmware was flashed during these checks. NAM-specific input/output gain, tone controls and wet/dry mix also require a subsequent DSP/protocol implementation; master volume is not a substitute for those controls.
