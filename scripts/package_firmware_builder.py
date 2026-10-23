#!/usr/bin/env python3
"""Export original compiled sections + hook replacements, never a stock binary/diff.

Maintainer tool: all existing NAMLNK23 staging gates must pass first. This creates
a recipe and an offline browser kit. No USB, audio, uploads or flashing.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'firmware/tools'), str(ROOT / 'firmware/research')]
from elftools.elf.elffile import ELFFile
from nux_container_lab import Container


def sha(data):
    return hashlib.sha256(data).hexdigest()


def need(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock_file', type=Path)
    parser.add_argument('build_dir', type=Path)
    parser.add_argument('reports_dir', type=Path)
    parser.add_argument('output_dir', type=Path, help='Ignored/local directory for the downloadable ZIP')
    parser.add_argument('--starter-bank', type=Path, required=True)
    parser.add_argument('--starter-report', type=Path, required=True)
    args = parser.parse_args()
    meta = json.loads((args.build_dir/'build.json').read_text())
    need('-DMPP_BLUETOOTH_AUDIO' in meta['compiler_flags'] and
         meta.get('revision') == 'r2-bluetooth-audio' and not meta.get('research_only'),
         'Builder 0.3.1 requires the production Bluetooth r2 build, not a research prototype')
    bank = args.starter_bank.read_bytes()
    starters = json.loads(args.starter_report.read_text())
    from starter_bank import validate_bank
    validate_bank(bank, starters)
    with tempfile.TemporaryDirectory(prefix='mighty-nam-builder-') as temp:
        subprocess.run([sys.executable, str(ROOT/'firmware/tools/stage_public_v3.py'),
                        str(args.stock_file.resolve()), str(args.build_dir.resolve()),
                        str(args.reports_dir.resolve()), temp], check=True)
        staged = Path(temp)
        review = json.loads((staged/'NAMLNK23-review.json').read_text())
        candidate = (staged/'NAMLNK23-public-v3-test.bin').read_bytes()
    need(review['identity'] == 'NAMLNK23' and not review['factory_presets'] and
         review['source_bank_sha256'] is None, 'Expected the audited unseeded NAMLNK23 baseline')
    need('bluetooth' in review['evidence'], 'Bluetooth release evidence required')
    stock = args.stock_file.read_bytes()
    original = Container(stock)
    baseline_sha = sha(candidate)
    seeded = bytearray(Container(candidate).payload)
    seeded[0x344000:0x360000] = bank
    candidate = original.rebuild_same_length(bytes(seeded))
    plan = review['candidate_plan']
    operations = []

    def operation(kind, name, offset, content, **extra):
        operations.append(dict(kind=kind, id=name, offset=offset, length=len(content),
                               before_sha256=sha(original.payload[offset:offset+len(content)]),
                               sha256=sha(content), **extra))

    # Only allocatable, file-backed sections from our own ELF. No unmodified
    # stock ranges, debug paths, generic binary-diff literals or model banks.
    with (args.build_dir/'nam-link-offline.elf').open('rb') as stream:
        elf = ELFFile(stream)
        for section in elf.iter_sections():
            if not section['sh_flags'] & 2 or not section['sh_size'] or section['sh_type'] == 'SHT_NOBITS':
                continue
            need(section.name in {'.text', '.retired_audio', '.ARM.exidx', '.banktext'}, 'Unexpected section')
            data = section.data()
            offset = 0x366000 if section.name == '.banktext' else section['sh_addr']
            operation('code', section.name, offset, data, data=base64.b64encode(data).decode('ascii'))
    for patch in plan['patches']:
        replacement = bytes.fromhex(patch['replacement'])
        need(len(replacement) <= 10, 'Unexpected hook payload')
        offset = int(patch['offset'], 16)
        operation('hook', 'hook-'+format(offset,'x'), offset, replacement,
                  data=base64.b64encode(replacement).decode('ascii'))
    operation('preset-bank', 'licensed-starters', 0x344000, bank, data=base64.b64encode(bank).decode('ascii'))
    for name, start, end in [('empty-global-settings',0x364000,0x366000)]:
        operation('fill', name, start, b'\xff'*(end-start), value=255)
    # Independently reconstruct only from these operations, and require the
    # existing fully audited image builder's exact result.
    rebuilt = bytearray(original.payload)
    for op in operations:
        data = bytes([op['value']])*op['length'] if op['kind']=='fill' else base64.b64decode(op['data'])
        rebuilt[op['offset']:op['offset']+op['length']] = data
    need(original.rebuild_same_length(bytes(rebuilt)) == candidate, 'Recipe differs from validated image builder')
    need(rebuilt[0x344000:0x360000] == bank, 'Starter bank mismatch')
    need(meta['elf_sha256'] == starters['elf_sha256'], 'Starter tests used a different firmware')
    recipe = dict(schema='mighty-nam-local-builder-1', builder_version='0.3.1', firmware_revision='r2-bluetooth-audio', identity='NAMLNK23',
                  target='NUX-MP3', presets='riffsmith-mit-3', captures_included=True, starter_presets=starters['presets'], starter_bank_sha256=sha(bank),
                  input=dict(name='MP3_OR_V3.0.5.bin', bytes=len(stock), sha256=sha(stock),
                             payload_sha256=sha(original.payload)),
                  output=dict(name='mighty-nam-NAMLNK23-r2-experimental.bin', bytes=len(candidate),
                              sha256=sha(candidate), payload_sha256=sha(bytes(rebuilt))),
                  elf_sha256=meta['elf_sha256'], sources=meta['sources'], headers=meta['headers'],
                  linker_sha256=meta['linker_sha256'], evidence=review['evidence'],
                  licenses=['MIT © 2026 santismo', 'NAM MIT © 2023 Steven Atkinson', 'RiffSmith MIT © 2026 Matt Hartman'],
                  license_notices={name:path.read_text() for name,path in {
                      'mighty-nam':ROOT/'LICENSE', 'Neural Amp Modeler':ROOT/'firmware/target/a2/UPSTREAM-LICENSE',
                      'RiffSmith captures':ROOT/'firmware/models/riffsmith/LICENSE'}.items()},
                  physical_validation='starter variant offline only; core has limited device validation', operations=operations)
    recipe_path = ROOT/'docs/builder/recipe.js'
    recipe_path.write_text('/* Generated by scripts/package_firmware_builder.py. See LICENSE, NAM-LICENSE and RIFFSMITH-LICENSE. */\n'
                          + 'globalThis.MightyNamRecipe = '+json.dumps(recipe, indent=2)+';\n')
    public_audit = dict(schema='mighty-nam-builder-provenance-1', identity='NAMLNK23',
                        recipe_sha256=sha(recipe_path.read_bytes()), elf_sha256=meta['elf_sha256'],
                        input_sha256=sha(stock), output_sha256=sha(candidate),
                        output_payload_sha256=sha(bytes(rebuilt)),
                        emitted_code_bytes=sum(op['length'] for op in operations if op['kind']=='code'),
                        emitted_hook_bytes=sum(op['length'] for op in operations if op['kind']=='hook'),
                        operations=len(operations),
                        payload_origin='File-backed allocated sections from original linked ELF; generated hook replacements; constant erase fills; three explicitly MIT-licensed RiffSmith A2 Lite model records.',
                        stock_headers_or_unchanged_ranges_exported=False, stock_original_bytes_exported=False,
                        preset_bank_exported=True, capture_weights_exported=True,
                        capture_source='firmware/models/riffsmith/provenance.json', capture_license='MIT',
                        private_or_tone3000_captures_exported=False, starter_bank_sha256=sha(bank),
                        source_gate='Existing stage_public_v3.py source/evidence/placement checks',
                        output_matches_stager_plus_validated_starters=True, unseeded_stager_sha256=baseline_sha, no_device_access=True,
                        legal_clearance_claimed=False, physical_validation='starter variant offline only; core has limited device validation')
    (ROOT/'docs/builder/provenance.json').write_text(json.dumps(public_audit, indent=2)+'\n')
    # Curated allowlist only. Never zip a workspace, ELF or staged directory.
    files = {
        'builder.html': ROOT/'docs/builder.html',
        'assets/style.css': ROOT/'docs/assets/style.css',
        'assets/guitar.svg': ROOT/'docs/assets/guitar.svg',
        'LICENSE': ROOT/'LICENSE', 'NAM-LICENSE': ROOT/'firmware/target/a2/UPSTREAM-LICENSE',
        'RIFFSMITH-LICENSE': ROOT/'firmware/models/riffsmith/LICENSE',
        'THIRD_PARTY_NOTICES.md': ROOT/'THIRD_PARTY_NOTICES.md',
        'LEGAL.md': ROOT/'LEGAL.md', 'PRIVACY.md': ROOT/'PRIVACY.md',
        'README.txt': ROOT/'docs/builder/OFFLINE.txt',
    }
    for name in ['core.js','ui.js','recipe.js','style.css','provenance.json']:
        files['builder/'+name] = ROOT/'docs/builder'/name
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir/'mighty-nam-NAMLNK23-r2-experimental.bin').write_bytes(candidate)
    output = args.output_dir/'mighty-nam-local-builder-0.3.1.zip'
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            # Fixed metadata makes the archive reproducible and excludes local paths.
            info = zipfile.ZipInfo('mighty-nam-local-builder/'+name, (2026,10,22,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    (args.output_dir/'SHA256SUMS.txt').write_text(sha(output.read_bytes())+'  '+output.name+'\n')
    print(json.dumps(public_audit, indent=2))


if __name__ == '__main__':
    main()
