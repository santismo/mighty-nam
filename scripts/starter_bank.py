"""Strict public-bank gate: only the pinned, MIT-licensed RiffSmith inputs."""
import hashlib, json, struct, sys, zlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'firmware/tools'))
from a2_storage import model_slot

def validate_bank(bank, report):
    def require(ok, message):
        if not ok: raise ValueError(message)
    sha = lambda data: hashlib.sha256(data).hexdigest()
    source = ROOT/'firmware/models/riffsmith'
    provenance = json.loads((source/'provenance.json').read_text())
    require(report['status']=='PASS_OFFLINE_PUBLIC_STARTERS' and
            report['cold_boot'] and (report.get('button_cycles_all') or report['button_cycles_three']), 'Starter emulation has not passed')
    require(report['provenance_sha256']==sha((source/'provenance.json').read_bytes()), 'Stale starter provenance')
    require(len(bank)==114688 and sha(bank)==report['bank_sha256'], 'Starter bank checksum mismatch')
    count=len(report['presets'])
    require(count in (3,7) and len(report['callbacks'])==count, 'Expected three or seven starter tests')
    require(bank[count*16384:]==b'\xff'*(114688-count*16384), 'Unexpected additional presets')
    for i in range(count):
        entry=provenance['models'][i%3]
        raw = (source/entry['file']).read_bytes()
        require(sha(raw)==entry['sha256'], 'Licensed source changed')
        model = model_slot(source/entry['file'])
        row = report['presets'][i]; test = report['callbacks'][i]
        require(row['color']==test['color']==i and test['callbacks']>=1600 and
                test['faults']==0 and test['reference_error']<2e-5 and
                1e-7<test['peak']<1, 'Starter audio check failed')
        expected = bytearray(b'\xff'*8192)
        struct.pack_into('<8I',expected,0,0x3142504e,1,i,1,zlib.crc32(model),1,8,0)
        expected[32:64] = hashlib.sha256(model).digest()
        expected[64:128] = row['name'].encode().ljust(64,b'\0')
        expected[128:256] = bytes(row['effects'])
        expected[256:7772] = model[:7516]
        struct.pack_into('<I',expected,7808,0x33315846)
        expected[7812:7844] = bytes(row['extra_fx'])
        struct.pack_into('<II',expected,8184,zlib.crc32(expected[:8184]),0x454e4f44)
        require(bank[i*16384:i*16384+8192]==expected and
                bank[i*16384+8192:(i+1)*16384]==b'\xff'*8192, 'Unexpected starter record bytes')
        require(row['model_sha256']==sha(model) and row['source_sha256']==sha(raw), 'Unexpected model attribution')
    return True
