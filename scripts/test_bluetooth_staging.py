"""Reject incomplete Bluetooth release evidence; temporary copies, no device I/O."""
import argparse, hashlib, json, shutil, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'firmware/tools'))
from stage_public_v3 import stage

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['stock','work','reports','output']: parser.add_argument(name,type=Path)
    a=parser.parse_args();rows=[]
    cases=['failed','stale','missing','routing','buffers','waveforms','wrong stock']
    for label in cases:
        with tempfile.TemporaryDirectory(prefix='mighty-nam-bt-gate-') as tmp:
            tmp=Path(tmp)
            shutil.copytree(a.work/'build',tmp/'build')
            shutil.copytree(a.work/'generated',tmp/'generated',symlinks=True)
            (tmp/'reports').mkdir()
            for name in ['arm','storage','runtime','chain','bluetooth']:
                shutil.copy2(a.reports/(name+'.json'),tmp/'reports'/(name+'.json'))
            report=tmp/'reports/bluetooth.json';d=json.loads(report.read_text())
            expected='Missing/stale/failed Bluetooth evidence';stock=a.stock
            if label=='failed':d['status']='FAIL'
            elif label=='stale':d['elf_sha256']='0'*64
            elif label=='routing':d['record_feed_excludes_music']=False;expected='Bluetooth acceptance'
            elif label=='buffers':d['buffer_cases']=d['buffer_cases'][:1];expected='Incomplete stereo regression'
            elif label=='waveforms':d['frequency_cases']=[];expected='Incomplete stereo regression'
            elif label=='wrong stock':stock=tmp/'wrong.bin';stock.write_bytes(b'unsupported');expected='Exact public'
            report.write_text(json.dumps(d))
            if label=='missing':report.unlink()
            try: stage(stock,tmp/'build',tmp/'reports',tmp/'rejected')
            except FileNotFoundError as e:
                assert label=='missing' and Path(e.filename).name=='bluetooth.json'
            except ValueError as e:
                assert expected in str(e),(label,str(e))
            else: raise AssertionError('Accepted invalid '+label)
            assert not (tmp/'rejected').exists()
            rows.append(label)
    result=dict(status='PASS_BLUETOOTH_STAGING_REJECTIONS',rejected=rows,
        elf_sha256=hashlib.sha256((a.work/'build/nam-link-offline.elf').read_bytes()).hexdigest(),
        device_access=False,host_audio_access=False)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],len(rows))
if __name__=='__main__':main()
