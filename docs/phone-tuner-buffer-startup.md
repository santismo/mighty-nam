# Controller 0.6.1 — tuner, output buffer and standalone startup

The phone controller now starts tuner readings automatically. It keeps one capture/read in flight, uses 512 samples for clear guitar notes and extends to 1024 or 2048 for low or uncertain notes. It preserves nonce, generation, count and CRC checks. Closing or hiding the page stops polling after the current reply; no automatic retry occurs after an error. Tuning and saving still mute plug output. These operations never access host audio or a microphone.

The main editor exposes **Play when powered on**, defaulted on for explicit saves. It separately displays the actual saved startup flag. Older trial presets were saved with flag 0, and ordinary edits previously preserved that flag without offering a way to change it. Save each existing color once with this checked to enable standalone output. This preserves its capture, effects, FX A/B and buffer. Merely connecting the page does not rewrite presets or enable output.

The buffer control shows the last confirmed device setting and the color's saved setting separately. The existing 8/16/32 command path already verified readback; no buffer protocol defect was reproduced. A rejected or ignored write does not report success. Changing buffers remains live and muted; Save persists the selected value. Connection reports now retain the current firmware, buffer, model CRC, fault state, effects and FX settings above the rolling packet log. Active delay-based FX receive a contextual note.

## Evidence and remaining uncertainty

- 70 Node tests pass, including sequential automatic polling, cancellation, errors, guitar-string accuracy and detuning, a shorter capture, low-note fallback, buffer round-trips, ignored-buffer rejection, startup flags and capture preservation.
- The exact installed NAMLNK14 ELF (`8f63f2a9191ca0f6d8e06d211515d38f1760cf728ba35e4e141005b16589523d`) passed stock Bluetooth-channel ingress and sample-exact output rendering at 32, 16 and 8. Eight adds zero extra output blocks.
- With modeled persistent flash, the real preset runtime enabled saved standalone output on cold and warm startup and retained buffer 8. Save itself remained muted.
- The real dry-input capture produced exactly the expected 2048 samples. All 162 paged Bluetooth response frames reassembled and decoded with the production JavaScript parser. Short, medium and full snapshots detected synthetic A2 within one cent.
- Output rendering, NAM processing and effect-profiler object files match the previously working NAMLNK12 build byte-for-byte. Existing NAMLNK14 regression evidence also records bit-identical bypass PCM against NAMLNK13. No audio-path or bypass change was made in this release.
- In-app browser checks using a simulated device verified automatic A2 display, closing while reading and regained controls, and saving an existing muted preset as startup-output-on. A 390 × 844 mobile-layout fixture also displayed automatic A2 without horizontal overflow; its mock disabled pacing to avoid background-browser timer throttling. Production pacing was retained in the in-app browser check. These are browser/protocol tests, not a physical Bluefy run.

The user's reported extra listening latency is still unresolved. The supplied 0.6.0 report contains saved-bank reads after live settings scrolled out, so it cannot identify the active buffer/effects at the time. New reports retain that information. No physical plug was visible over USB this turn. No firmware was flashed, no physical presets were rewritten and no audio was played. Mac/Teams volume was untouched. A physical phone tuner check, current-chain report and listening comparison remain needed; offline execution cannot establish real-time deadlines or acoustic latency.

No firmware update is needed for these controller fixes on NAMLNK14. The production page is https://santismo.github.io/nam-plug-controller/?v=0.6.1 .
