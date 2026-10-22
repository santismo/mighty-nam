# NAMLNK23: public V3.0.5 Original port

The original port campaign below was offline and did not access the plug or
audio devices. Subsequent NAMLNK23 installation, private-preset transfer/recall
and user-confirmed guitar output are recorded separately in
[controller evidence](../controllers-0.5.3/summary.json).

Accepted public NUX input: `MP3_OR_V3.0.5.bin`, 15,009,655 bytes.
SHA-256: `39fa7057865f95e4c52c48544cd8284f4da606d3ac29e985e9b8938a3237467e`.
Original image, not ChopTones. See [input and reproduction instructions](../../docs/local-builder.md).

ELF SHA-256: `55c60715a5e9b9042d6ae2693f583d88dda709fee1859cf1ad42bce8d867f7fb`.
Original empty-bank container SHA-256: `27f99a123b94e152c33f45985b6daf4dac34c0361ea89978280c083ea20e7fdb`.
No container, stock code or capture weights are included here.

| Evidence | Scope |
| --- | --- |
| `arm.json` | 1,652 compiled callbacks; USB PCM, distinct record gain, NAM controls, seven colors, cold/warm/button recall |
| `runtime.json` | 8,182 callbacks; six representative chains including V3 Phi Delay; 64 stock type switches; bypass skips processing; global 8/16/32 settings after restart; actual stock MIDI assembly |
| `chain.json` | 2,501 callbacks; dual pitch, NAM and Spring; zero bypassed pitch calls |
| `storage.json` | V3 MPU and flash wrapper instructions; modeled controller completion, bounds and error propagation |
| `staging-tests.json` | Eight invalid build/provenance/evidence/input cases rejected before output |
| `builder.json` | 22 builder checks, exact browser download, wrong actual stock variants rejected |
| `controllers.json` | Historical Mac/phone recognition and protocol checks before publication |

The reference NAM comparison had zero observed peak difference for this test
fixture. That is not an accuracy claim for every possible capture. The effect
loader sweep checks switching and guards, not long audio-quality renders of all
64 choices. The storage report retains its historical test-name label; its
stock/ELF hashes identify this V3 port.

Peripheral responses, USB completion, flash behavior and timing counters are
modeled. Hardware bootloader acceptance/recovery, cache behavior, actual audio
deadlines, analog latency, listening quality and Logic duplex need a controlled
physical trial. Nothing here proves the factory bootloader will survive an
arbitrary bad image. NAMLNK23 retains the prior scheduling; no new latency
reduction is claimed.

## Public builder 0.3.0

The current builder includes three MIT-licensed RiffSmith A2 Lite starters,
independently obtained from the creator's repository. `public-starters.json`
records 4,800 compiled callbacks, cold boot, six button-handler transitions,
and erased remaining slots. `public-starter-reference.json` compares each
model over 48,000 samples against the independent NAM reference.
`public-builder-browser.json` verifies actual local browser downloads in
HTTP localhost and file modes; no external/upload requests or audio/device
access occurred. The public starter bank has not been flashed or listened to.

The browser recipe contains original compiled changes, generated hooks and
licensed model data. NUX stock bytes are supplied locally by each user. No
complete hybrid firmware image is distributed. See
[recipe provenance](../../docs/builder/provenance.json),
[starter licenses](../../firmware/models/riffsmith/provenance.json) and
[installation guide](../../docs/builder.html).
