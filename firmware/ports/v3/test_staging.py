"""Exercise packaging rejection paths without devices or changing real artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from stage_public_v3 import stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock_file', type=Path)
    parser.add_argument('work', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    work = args.work.resolve()
    cases = [
        ('identity', 'Public V3 build required'),
        ('ELF', 'ELF mismatch'),
        ('port provenance', 'Incomplete port provenance'),
        ('generated source', 'Generated source changed'),
        ('linker', 'Linker mismatch'),
        ('failed evidence', 'Missing/stale/failed runtime evidence'),
        ('stale evidence', 'Missing/stale/failed arm evidence'),
        ('wrong stock', 'Exact public'),
    ]
    passed = []
    for label, error in cases:
        with tempfile.TemporaryDirectory(prefix='mighty-nam-stage-test-') as temp:
            temp = Path(temp)
            build = temp / 'build'
            shutil.copytree(work / 'build', build)
            generated = temp / 'generated'
            shutil.copytree(work / 'generated', generated, symlinks=True)
            reports = temp / 'reports'
            reports.mkdir()
            for name in ['arm', 'storage', 'runtime', 'chain']:
                shutil.copyfile(work / (name + '.json'), reports / (name + '.json'))
            meta = json.loads((build / 'build.json').read_text())
            stock = args.stock_file
            if label == 'identity':
                meta['identity'] = 'NAMLNK22'
            elif label == 'ELF':
                with (build / 'nam-link-offline.elf').open('ab') as stream:
                    stream.write(b'changed')
            elif label == 'port provenance':
                meta['port_sources'] = {}
            elif label == 'generated source':
                with (generated / 'target/link/stock_chain_firmware.cpp').open('a') as stream:
                    stream.write('\n// changed after compilation\n')
            elif label == 'linker':
                meta['linker_sha256'] = '0' * 64
            elif label in ('failed evidence', 'stale evidence'):
                report = reports / ('runtime.json' if label == 'failed evidence' else 'arm.json')
                data = json.loads(report.read_text())
                data['status' if label == 'failed evidence' else 'elf_sha256'] = 'invalid'
                report.write_text(json.dumps(data))
            elif label == 'wrong stock':
                stock = temp / 'wrong.bin'
                stock.write_bytes(b'not the supported stock')
            (build / 'build.json').write_text(json.dumps(meta))
            try:
                stage(stock, build, reports, temp / 'rejected')
            except ValueError as failure:
                assert error in str(failure), (label, str(failure))
                assert not (temp / 'rejected').exists()
                passed.append(label)
            else:
                raise AssertionError('Staging accepted ' + label)
    result = dict(status='PASS_OFFLINE_NAMLNK23_STAGING_GATES',
                  elf_sha256=hashlib.sha256((work / 'build/nam-link-offline.elf').read_bytes()).hexdigest(),
                  rejected_cases=passed, device_access=False, host_audio_access=False)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'], len(passed), 'rejected cases')


if __name__ == '__main__':
    main()
