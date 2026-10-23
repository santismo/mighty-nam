"""Boot the exact staged local container in the CPU harness; no physical I/O."""
import argparse,hashlib,json,sys
from pathlib import Path
from harness import setup
p=argparse.ArgumentParser(description=__doc__)
for n in ['baseline','payload','work','staged']:p.add_argument(n,type=Path)
a=p.parse_args();M,v,s,*_=setup(a.baseline,a.payload,a.work)
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'firmware/tools'))
from nux_container_lab import Container
report=json.loads((a.staged/'verification.json').read_text());file=a.staged/report['file']
assert hashlib.sha256(file.read_bytes()).hexdigest()==report['sha256']
payload=Container(file.read_bytes()).payload
assert hashlib.sha256(payload).hexdigest()==report['payload_sha256']
assert payload[:0x344000]==v.candidate[:0x344000] and payload[0x360000:]==v.candidate[0x360000:]
v.candidate=payload;v.plan['candidate_sha256']=report['payload_sha256']
m=M(fill=0xff);m.service();colors=[]
rows=report['presets'];assert len(rows)==3
for index,color in enumerate([0,1,2,0]):
    if index:assert m.button()==color
    assert m.words()[5]==rows[color]['model_crc'] and m.get(v.sym['mpp_listen_enabled'])==1 and not m.diag()[3]
    colors.append(color)
assert not m.flash_operations and m.loop_state(3)==0
result=dict(status='PASS_EXACT_LOCAL_LOOP_CONTAINER_BOOT',container_sha256=report['sha256'],elf_sha256=report['elf_sha256'],
    payload_sha256=report['payload_sha256'],bank_sha256=report['bank_sha256'],colors=colors,capture_CRCs_verified=True,
    normal_output_enabled=True,looper_inactive=True,flash_writes=0,device_access=False,host_audio_access=False)
(a.staged/'container-boot.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],flush=True)
