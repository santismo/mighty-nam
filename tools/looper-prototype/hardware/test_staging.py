"""Negative staging gates plus local-only packaging. Never invokes a device."""
import argparse,hashlib,json,shutil,tempfile
from pathlib import Path
from stage import stage
p=argparse.ArgumentParser(description=__doc__)
for name in ['baseline','work','stock','bank','bank_report','output']:p.add_argument(name,type=Path)
a=p.parse_args();rejected=[]
identity=json.loads((a.work/'build/build.json').read_text())['identity']
extended=identity in ['NAMLNK26','NAMLNK27']
cases=[
    ('missing startup','startup.json',None),
    ('stale ELF','audio.json',lambda r:r.update(elf_sha256='0'*64)),
    ('changed payload','startup.json',lambda r:r.update(candidate_payload_sha256='0'*64)),
    ('guitar changed','audio.json',lambda r:r['cases'][0].update(output_exact=False)),
    ('loop discontinuity','continuity-test.json',lambda r:r.update(max_native_loop_sample_error=.1)),
    ('missing fault coverage','startup.json',lambda r:r.update(negative_controls=[])),
]
if extended:cases += [
    ('missing overdub recall','continuity-test.json',lambda r:r.update(overdub_preset_recalls=[])),
    ('unbounded button lock','continuity-test.json',lambda r:r.update(max_masked_instruction_run=100)),
    ('stale buttons','buttons.json',lambda r:r.update(elf_sha256='0'*64)),
    ('missing full duration','offline/full-duration.json',lambda r:r.update(callbacks=1)),
]
if identity=='NAMLNK27':cases += [
    ('missing meter','layers-arm.json',lambda r:r.update(live_meter_in_compact_status=False)),
    ('missing short tap','buttons.json',lambda r:r.update(phone_arm_physical_short_tap_finish=False)),
    ('missing quality','offline/quality.json',None),
    ('quality regression','offline/quality.json',lambda r:r.update(snr_db=16)),
]
for label,file,edit in cases:
    with tempfile.TemporaryDirectory(prefix='mighty-loop-stage-') as tmp:
        test=Path(tmp);(test/'build').mkdir()
        files=['build/build.json','build/loop-startup-test.elf','startup.json','audio.json','continuity-test.json']
        if extended:files+=['layers-arm.json','buttons.json','offline/layers.json','offline/full-duration.json','offline/source-hashes.json']
        if identity=='NAMLNK27':files+=['offline/quality.json']
        for name in files:
            (test/name).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(a.work/name,test/name)
        if edit:
            report=json.loads((test/file).read_text());edit(report);(test/file).write_text(json.dumps(report))
        else:(test/file).unlink()
        output=test/'forbidden'
        try:stage(a.baseline,test,a.stock,a.bank,a.bank_report,output)
        except (FileNotFoundError,ValueError):assert not output.exists();rejected.append(label)
        else:raise AssertionError('Invalid report accepted: '+label)
result=stage(a.baseline,a.work,a.stock,a.bank,a.bank_report,a.output)
report=dict(status='PASS_OFFLINE_LOOP_STAGING_GATES',identity=identity,elf_sha256=result['elf_sha256'],
    rejected_cases=rejected,container_bytes=result['bytes'],container_headers_preserved=True,
    vector_table_and_C_startup_preserved=True,local_bank_unchanged=True,device_access=False,host_audio_access=False,flashed=False)
(a.work/'staging.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','file','sha256','flashed']},indent=2))
