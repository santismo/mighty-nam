# mighty-nam: rights and distribution

Reviewed 22 October 2026. This records project boundaries and release practices, not a legal opinion or manufacturer approval.

## Original code

Original contributions are **MIT © 2026 santismo**. The MIT license permits commercial use of that code; it does not grant rights to external services, trademarks, captures, hardware designs or proprietary firmware. Do not replace upstream copyrights with the project's copyright.

## Third-party material

Retain the applicable notices when distributing source or binaries. Mightier Amp's MIT attribution is preserved. The firmware repository also retains NeuralAmpModelerCore, Eigen, nlohmann/json and musl notices. Eigen has file-level terms including MPL-2.0; if distributing binaries containing covered code, supply the required corresponding covered source and notices. The MIT label does not relicense those files. See [Mozilla's MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/) and the actual vendored licenses.

No NUX stock binary, bootloader, manufacturer DSP, or downloaded catalog capture is distributed in these source repositories or Mac installers. Locally assembled hybrid firmware contains proprietary stock bytes and can contain the owner's captures. Keep those files local unless separately authorized by the relevant rights holders. Device ownership alone is not a redistribution license. Do not advertise the hardware or whole stock-based image as MIT-licensed or fully open hardware.

## TONE3000

**Powered by [TONE3000](https://www.tone3000.com).** API access and creator content have separate terms from NAM's open-source inference code.

The free release uses authenticated Select/Load picker flows and bounded account/discovery lists. Full search stays in the official picker. Downloads are requested by each user, with creator/license metadata retained; there is no shared catalog or bundled capture collection. Public client IDs identify the integration; secret keys and account tokens must not ship in source or installers.

Charging for a TONE3000-enabled product, linking it to a paid product or upsell, or changing these access patterns requires reviewing the current service terms and obtaining any required agreement before launch. Review the [API terms](https://www.tone3000.com/api/terms), [design requirements](https://www.tone3000.com/api#design-requirements), and [service terms](https://www.tone3000.com/terms). The project does not claim TONE3000 sign-off. Creator licenses and API restrictions are not waived by this repository's MIT license.

## Names and safety

NUX, Mighty Plug Pro, Neural Amp Modeler, TONE3000, Apple, Logic Pro and Bluefy identify interoperability targets and third-party products. Their owners retain their marks. This project is independent; references do not imply endorsement or an official partnership.

Experimental firmware can fail, erase presets or require recovery that has not been demonstrated for every failure. Test evidence is build-specific. The MIT warranty disclaimer applies; no guarantee of recoverability, latency, audio quality or compatibility is offered.
