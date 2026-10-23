# mighty-nam: rights and distribution

Reviewed 23 October 2026. This records project boundaries and release practices, not a legal opinion or manufacturer approval.

## Original code

Original contributions are **MIT © 2026 santismo**. The MIT license permits commercial use of that code; it does not grant rights to external services, trademarks, captures, hardware designs or proprietary firmware. Do not replace upstream copyrights with the project's copyright.

## Third-party material

Retain the applicable notices when distributing source or binaries. Mightier Amp's MIT attribution is preserved. The firmware repository also retains NeuralAmpModelerCore, Eigen, nlohmann/json and musl notices. Eigen has file-level terms including MPL-2.0; if distributing binaries containing covered code, supply the required corresponding covered source and notices. The MIT label does not relicense those files. See [Mozilla's MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/) and the actual vendored licenses.

No NUX stock binary, bootloader, manufacturer DSP, or downloaded catalog capture is distributed in these source repositories or Mac installers. Locally assembled hybrid firmware contains proprietary stock bytes and can contain the owner's captures. Keep those files local unless separately authorized by the relevant rights holders. Device ownership alone is not a redistribution license. Do not advertise the hardware or whole stock-based image as MIT-licensed or fully open hardware.

## TONE3000

**Powered by [TONE3000](https://www.tone3000.com).** API access and creator content have separate terms from NAM's open-source inference code.

The free release uses authenticated Select/Load picker flows and bounded account/discovery lists. Full search stays in the official picker. Downloads are requested by each user, with creator/license metadata retained; there is no shared catalog or bundled TONE3000 capture collection. The three public RiffSmith starters are obtained directly from their creator’s MIT-licensed GitHub repository, independently of the TONE3000 API. Public client IDs identify the integration; secret keys and account tokens must not ship in source or installers.

Charging for a TONE3000-enabled product, linking it to a paid product or upsell, or changing these access patterns requires reviewing the current service terms and obtaining any required agreement before launch. Review the [API terms](https://www.tone3000.com/api/terms), [design requirements](https://www.tone3000.com/api#design-requirements), and [service terms](https://www.tone3000.com/terms). The project does not claim TONE3000 sign-off. Creator licenses and API restrictions are not waived by this repository's MIT license.

## Names and safety

NUX, Mighty Plug Pro, Neural Amp Modeler, TONE3000, Apple, Logic Pro and Bluefy identify interoperability targets and third-party products. Their owners retain their marks. This project is independent; references do not imply endorsement or an official partnership.

Experimental firmware can fail, erase presets or require recovery that has not been demonstrated for every failure. Test evidence is build-specific. The MIT warranty disclaimer applies; no guarantee of recoverability, latency, audio quality or compatibility is offered.

## Experimental local builder distribution

The browser/offline builder distributes original compiled changes, generated
hooks, constant erase fills, checksum metadata and three MIT-licensed RiffSmith starter records. It does not distribute a
NUX stock or combined firmware image, an updater, private presets or TONE3000
catalog captures. Its exporter starts from our linked ELF and the existing validation
gates, rather than a generic diff that might include stock ranges. The user's
exact stock file is supplied locally and is not uploaded. Generated hybrid
images remain local unless separately authorized for redistribution.

Original contributions remain MIT © 2026 santismo. The offline kit retains
Steven Atkinson's NAM MIT license, Matt Hartman's RiffSmith MIT license and project notices. NUX and other third-party
rights are not granted by the project. Local assembly reduces direct stock
redistribution; it is not a finding that modification or any circumvention is
legally permitted in every jurisdiction. Public availability does not make
firmware public domain. A disclaimer or user action cannot supply missing rights.

The current NAMLNK28 builder output is experimental. The exact NAMLNK28 starter-bank variant has offline validation; earlier NAM/looper versions have limited device validation. Complete hardware validation of this release remains outstanding.
They replace onboard presets/settings and may cause unexpected audio or leave
a device unusable. No compatibility or recovery guarantee is provided. Software
is provided without warranty to the extent permitted by applicable law; the
actual MIT and dependency licenses remain authoritative for covered code.
See the [builder and distribution boundary](docs/local-builder.md).

## Public starter captures

RiffSmith Clean, RiffSmith Bass Clean and RiffSmith Distorted are distributed under **MIT, Copyright (c) 2026 Matt Hartman**. The creator explicitly includes these captures in that license. Pinned sources, checksums and the permission statement are in [provenance](firmware/models/riffsmith/provenance.json); the [complete license](firmware/models/riffsmith/LICENSE) accompanies the source, builder kit and Mac app. The builder uses their unchanged A2 Lite weights. No permission is inferred merely from a model being free to download. The maintainer's three private catalog captures are not public defaults.
