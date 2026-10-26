#!/usr/bin/env python3
"""Package the checked public recipe and browser builder; never a firmware image."""
import argparse, hashlib, json, re, zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
docs = root / 'docs'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('output', type=Path)
a = p.parse_args()
source = (docs / 'looper-builder/recipe.js').read_text()
recipe = json.JSONDecoder().raw_decode(source.split('globalThis.MightyNamRecipe = ', 1)[1])[0]
audit = json.loads((docs / 'looper-builder/provenance.json').read_text())
assert hashlib.sha256(source.encode()).hexdigest() == audit['recipe_sha256']
assert not audit['stock_original_bytes_exported'] and not audit['private_or_tone3000_captures_exported']
assert recipe['identity'] == 'NAMLNK30' and recipe['presets'] == 'riffsmith-mit-3'
version = recipe['builder_version']
assert re.fullmatch(r'\d+\.\d+\.\d+', version)
files = {name: docs / name for name in [
    'builder/core.js', 'builder/ui.js', 'builder/style.css',
    'looper-builder/recipe.js', 'looper-builder/provenance.json',
    'builder/recipe.js', 'builder/provenance.json', 'builder-v28/recipe.js', 'builder-v28/provenance.json', 'builder-v29/recipe.js', 'builder-v29/provenance.json',
    'assets/style.css', 'assets/brand/mighty-nam.svg', 'assets/brand/mighty-nam-icon.png']}
for folder,identity in [('builder','NAMLNK23'),('builder-v28','NAMLNK28'),('builder-v29','NAMLNK29')]:
    text = (docs / folder / 'recipe.js').read_text()
    previous = json.JSONDecoder().raw_decode(text.split('globalThis.MightyNamRecipe = ',1)[1])[0]
    provenance = json.loads((docs / folder / 'provenance.json').read_text())
    assert previous['identity'] == identity and previous['presets'] == 'riffsmith-mit-3'
    assert hashlib.sha256(text.encode()).hexdigest() == provenance['recipe_sha256']
    assert previous['output']['sha256'] == provenance['output_sha256']
    assert not provenance['stock_original_bytes_exported']
    assert not provenance.get('private_or_tone3000_captures_exported',False)
for name in ['LICENSE', 'LEGAL.md', 'THIRD_PARTY_NOTICES.md', 'PRIVACY.md']:
    files[name] = root / name
for name, path in [('NAM-LICENSE', 'firmware/target/a2/UPSTREAM-LICENSE'),
                   ('RIFFSMITH-LICENSE', 'firmware/models/riffsmith/LICENSE'),
                   ('DAISY-LICENSE', 'firmware/target/link/DAISY-LICENSE')]:
    files[name] = root / path
entries = {name: path.read_bytes() for name, path in files.items()}
html = (docs / 'looper-builder.html').read_text()
html = re.sub(r'href="((?:index|guide|phone|status|development|builder|builder-v23|looper-builder)\.html(?:#[^"]*)?)"',
              r'href="https://santismo.github.io/mighty-nam/\1"', html)
entries['builder.html'] = html.encode()
entries['README.txt'] = f'''mighty-nam local builder {version} — NAMLNK30 / NAMLNK29 / NAMLNK28 / NAMLNK23 r2

Open builder.html in a modern desktop browser. Supply your own exact
MP3_OR_V3.0.5.bin from NUX. It stays local; no compiler or plug connection needed.
Save the generated image and report, then install with the official NUX updater.
Guide: https://santismo.github.io/mighty-nam/guide.html

This archive contains original compiled changes and three MIT-licensed
RiffSmith captures, not a NUX or combined firmware image. Keep generated images
local. Installation replaces onboard presets and global settings. Green Clean,
Orange Bass Clean and Red Distorted are supplied; colors 4–7 start as copies of Green on NAMLNK30 r2. Earlier builds retain four empty colors.

NAMLNK30 revision 2 fixes Bluetooth Amp discovery and adds flash-readback cache invalidation.
The hardware storage failure still needs verification. NAMLNK30 adds all 29 stock amp choices through Add block > Amp alongside NAM. Only
one stock amp can run at once. Stock code is copied from your supplied NUX
file during local assembly. No stock bytes are bundled.

NAMLNK29/30 include Daisy-derived Auto Wah, the 30-second looper (optional
lower-bandwidth 60 seconds), up to three independent overdub lanes, one-edit undo/redo, input meter,
seven-slot preset saving fix and button gestures. Shorter loops leave more lane
space: a full 30/60-second base leaves no overdub space. To re-edit with three
lanes and undo, keep the base slightly under 6 seconds (30 s mode) or 12 seconds
(60 s mode). Lane controls are on the phone; Mac supports transport/settings.
Threshold, level and duration apply live. Clear the retained loop, then choose
Save looper settings to persist them. Defaults: -50 dB threshold, 100% level.
Loops themselves are lost on power-off. Mac 0.7.0+ and phone 0.11.1+ supported.

The version menu also offers NAMLNK29 (without stock amps), NAMLNK28 (merged overdubs, no lanes/undo)
and NAMLNK23 r2 (NAM/effects, no looper or Daisy-derived Auto Wah).
Older builds use the same exact NUX input and licensed presets. Downgrading
also erases saved presets/settings. The phone supports NAMLNK12–30 and only
enables commands for the connected version. Unsupported newer commands stay off.
The gestures below describe NAMLNK28/29/30; NAMLNK23 has no looper gestures.

Outside Looper: tap PRESET next occupied color; hold PRESET previous once.
In Looper: tap PRESET arm/finish/pause/resume; hold toggles overdub on a loop.
Tap PRESET then press and hold within 300 ms to clear. Hold duration: 800 ms.
Double POWER enters when no loop exists; otherwise stops/exits. Single POWER
switches preset/looper controls while retaining a loop. POWER hold shuts down.

No automatic flashing, muting or host audio. Exact public build tested offline;
hardware trial remains pending. No recovery guarantee. Read included notices.
'''.encode()
a.output.mkdir(parents=True, exist_ok=True)
out = a.output / f'mighty-nam-local-builder-{version}.zip'
with zipfile.ZipFile(out, 'w') as archive:
    for name, data in sorted(entries.items()):
        info = zipfile.ZipInfo('mighty-nam-local-builder/' + name, (2026, 10, 24, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, data)
digest = hashlib.sha256(out.read_bytes()).hexdigest()
(a.output / 'SHA256SUMS.txt').write_text(f'{digest}  {out.name}\n')
print(json.dumps({'file': out.name, 'sha256': digest, 'files': len(entries), 'combined_firmware_included': False}))
