#!/usr/bin/env python3
"""Build the licensed public bank using emulated NAMLNK23 saves. No device/audio.

Inputs are the three pinned, creator-licensed RiffSmith files, never a user
library. Compare real firmware cold boot, recalls and processing before export.
"""
import argparse, base64, hashlib, json, math, struct, sys, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(data): return hashlib.sha256(data).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['work', 'payload', 'reference_library', 'output']:
        p.add_argument(name, type=Path)
    a = p.parse_args()
    sys.path[:0] = [str(a.work/'generated/research'), str(a.work/'generated/tools')]
    from test_usb_nam import UsbMachine, v, preset_fixture, input_block
    from preset_image import build, BANK, BANK_END
    from a2_storage import model_slot
    from a2_model import extract
    from a2_oracle import Engine, library
    elf = a.work/'build/nam-link-offline.elf'
    bundle = build(a.payload.read_bytes(), elf)
    assert bundle[2]['identity'] == 'NAMLNK23'
    v.configure(a.payload, True, candidate_bundle=bundle); v.elf_path = elf
    source = ROOT/'firmware/models/riffsmith'
    provenance = json.loads((source/'provenance.json').read_text())
    names = ['RiffSmith Clean', 'RiffSmith Bass Clean', 'RiffSmith Distorted']
    m = UsbMachine(); m.service(); rows = []; records = []
    for color, entry in enumerate(provenance['models']):
        path = source/entry['file']; raw = path.read_bytes()
        assert sha(raw) == entry['sha256'], 'Starter source changed'
        model = model_slot(path); m.upload(model, 700+color)
        # Clean routing with only NAM running; all three captures include cab.
        effects = bytearray(preset_fixture()); effects[84] = 37
        m.u.mem_write(m.preset, bytes(effects))
        assert m.ng([48,12,12,12,100,48])[13] == 0
        assert m.nv(48)[13] == 0
        extra = bytes([1,0,2,12,100,30,50,0,50,50,0,0,0,0,0,0,
                       2,0,3,12,100,30,50,0,50,50,0,0,0,0,0,0])
        at = v.SP-512; m.u.mem_write(at, extra); m.call(v.sym['mpp_fx_set'], [at])
        effects = bytes(m.u.mem_read(m.preset,128))
        name = names[color].encode()
        body = struct.pack('<4I',zlib.crc32(model),zlib.crc32(effects),1,8)
        body += hashlib.sha256(model).digest()+name.ljust(64,b'\0')
        assert m.bank_request(2,color,body,nonce=800+color)[7] == 0
        metadata = dict(name=names[color], creator='Matt Hartman / RiffSmith',
                        license='MIT', source_url=entry['url'],
                        license_url=provenance['upstream']+'/blob/'+provenance['revision']+'/LICENSE',
                        source_sha256=sha(raw), nam_metadata=json.loads(raw)['metadata'],
                        topology='a2-lite-fixed-v1', sample_rate=48000,
                        tone_metadata=dict(gear='amp-cab'), bundled_starter=True)
        records.append(dict(slot=base64.b64encode(model).decode(), sha256=sha(model),metadata=metadata))
        rows.append(dict(color=color,name=names[color],model_crc=zlib.crc32(model),
                         model_sha256=sha(model),source_sha256=sha(raw),effects=list(effects),extra_fx=list(extra)))
        print('Saved public starter',color+1,flush=True)
    bank = bytes(m.u.mem_read(BANK,BANK_END-BANK))
    assert len(bank) == 0x1c000 and bank[3*16384:] == b'\xff'*(4*16384)
    cold = UsbMachine(bank,0xa5); cold.service()
    assert cold.words()[5] == rows[0]['model_crc']
    for color in [1,2,0,1,2,0]:
        assert cold.button() == color
        assert cold.words()[5] == rows[color]['model_crc']
        assert bytes(cold.u.mem_read(cold.preset,128)) == bytes(rows[color]['effects'])
    a.output.mkdir(parents=True,exist_ok=True)
    tests=[]
    for color,entry in enumerate(provenance['models']):
        assert cold.bank_request(3,color,nonce=900+color)[7] == 0
        cold.service()
        lite = a.output/(Path(entry['file']).stem+'-lite.nam')
        lite.write_text(json.dumps(extract(json.loads((source/entry['file']).read_text())))+'\n')
        cold.boundary_oracle = Engine(library(str(a.reference_library)),lite)
        cold.max_boundary_error=0.; peak=0
        for i in range(1600):
            y=cold.process(i,input_block(i)); assert all(math.isfinite(x) for x in y)
            peak=max(peak,max(map(abs,y)))
        assert peak>1e-7 and peak<1 and cold.words()[4]==0, (color,peak,cold.words(),cold.page(23))
        assert cold.max_boundary_error<2e-5
        tests.append(dict(color=color,callbacks=1600,peak=peak,reference_error=cold.max_boundary_error,faults=0))
        cold.boundary_oracle=None
        print('Processed public starter',color+1,flush=True)
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'starter-bank.bin').write_bytes(bank)
    report=dict(status='PASS_OFFLINE_PUBLIC_STARTERS',elf_sha256=sha(elf.read_bytes()),
                bank_sha256=sha(bank),presets=rows,callbacks=tests,cold_boot=True,
                button_cycles_three=True,remaining_four_empty=True,device_access=False,host_audio_access=False,
                physical_listening_verified=False,physical_timing_verified=False,
                provenance_sha256=sha((source/'provenance.json').read_bytes()))
    (a.output/'starter-bank.json').write_text(json.dumps(report,indent=2)+'\n')
    assets=ROOT/'app/assets/starter-captures.json'
    assets.write_text(json.dumps(dict(schema='mighty-nam-starter-captures-1',models=records),indent=2)+'\n')
    print(report['status'],flush=True)

if __name__ == '__main__': main()
