# Third-party notices

Original mighty-nam code and documentation: MIT, Copyright (c) 2026 santismo. The root license does not replace third-party licenses or grant rights to NUX firmware or downloaded captures.

| Component | Source / license | Retained notice |
| --- | --- | --- |
| Mightier Amp adaptation and effect definitions | [tuntorius/mightier_amp](https://github.com/tuntorius/mightier_amp), MIT, Dian Iliev | `app/LICENSE.md`, `app/PROVENANCE.json`, source notices |
| NeuralAmpModelerCore | [sdatkinson/NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore), MIT, Steven Atkinson | `firmware/third_party/nam/LICENSE`, `firmware/target/a2/UPSTREAM-LICENSE` |
| DaisySP AutoWah (NAMLNK24 experimental candidate) | [daisyaudio/DaisySP](https://github.com/daisyaudio/DaisySP), MIT, Electrosmith and Soundpipe contributors | `firmware/target/link/DAISY-LICENSE` and `tools/auto-wah-prototype/DAISY-LICENSE`; pinned upstream files; compiled only with `MPP_DAISY_WAH`, not into builder 0.3.1 |
| Eigen | [Eigen](https://gitlab.com/libeigen/eigen), primarily MPL-2.0, with file-level alternatives | `firmware/third_party/eigen/COPYING.*` and source headers |
| nlohmann/json | [nlohmann/json](https://github.com/nlohmann/json), MIT | Notice in `firmware/third_party/json/json.hpp` |
| musl math | [musl](https://git.musl-libc.org/cgit/musl/), mixed permissive source notices | `firmware/third_party/musl-math/COPYRIGHT` and individual source headers |
| RiffSmith Clean, Bass Clean and Distorted captures | [hartmamt/riffsmith](https://github.com/hartmamt/riffsmith), MIT, Matt Hartman | `firmware/models/riffsmith/LICENSE`, pinned `provenance.json`, app `RIFFSMITH-LICENSE`, kit `RIFFSMITH-LICENSE` |
| TONE3000 official logos | [Official brand kit](https://www.tone3000.com/api), service/trademark terms; not MIT | `app/assets/brand/NOTICE.txt`, `docs/assets/brand/NOTICE.txt` |
| Flutter and packages | SDK/package-specific licenses | Flutter's in-app Licenses view; package revisions in `app/pubspec.lock` |

Exact firmware dependency revisions are in `firmware/third_party/versions.json`. Upstream NAM example fixtures in `firmware/models/` retain the upstream MIT attribution; they exist for correctness tests, not as a musical preset collection.

[nux-effects](https://github.com/opensensor/nux-effects) and the [TONE3000 plugin](https://github.com/tone-3000/tone3000-plugin) were design/research references. Their source was not copied into this adaptation. API services and captures are governed by their respective terms and licenses.

The Mac release includes Flutter's license registry. The disk image additionally includes this notice and the project MIT license. Original stock NUX code is not included in the repository or Mac installer. Locally generated firmware containers include user-supplied proprietary stock bytes and should not be re-uploaded here.

Distribution scope: the current free TONE3000 integration is described in [LEGAL.md](LEGAL.md). Keep creator attribution/license metadata with requested captures. MIT covers original code, not catalog access or redistribution of models. The public Mac preview is ad-hoc signed and not notarized; no personal developer certificate is included. For binaries containing MPL-covered Eigen code, make the corresponding covered source available as required by its license.

The local firmware builder ZIP includes the original-code MIT license and
`NAM-LICENSE` for its compiled A2 Lite implementation. Its generated recipe
contains original/NAM-derived ELF sections and generated hook replacements;
it does not embed the NUX file or an Eigen/musl runtime. See
[recipe provenance](docs/builder/provenance.json) and [builder details](docs/local-builder.md).

The three RiffSmith captures were downloaded directly from their creator's MIT-licensed repository, not through the TONE3000 catalog API. The recipe includes their A2 Lite weights and preset records. The Mac app includes the same model slots for identity recognition and preserves existing user libraries. Creator copyright and permission text accompany every distribution. Full upstream files are retained unchanged with pinned hashes; only the Lite component runs on the device. These alternatives are not claimed to reproduce the private captures' sound.
