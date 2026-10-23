#!/usr/bin/env python3
"""Export NAMLNK27/28 owned code/patches plus licensed starters. Never stock bytes."""
import argparse,base64,hashlib,importlib.util,json,sys,tempfile,zipfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
def need(ok,msg):
 if not ok:raise ValueError(msg)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['baseline','work','stock','starters','output']:p.add_argument(name,type=Path)
 a=p.parse_args()
 sys.path[:0]=[str(ROOT/'tools/looper-prototype/hardware'),str(a.baseline/'generated/research'),str(a.baseline/'generated/tools'),str(ROOT/'scripts')]
 from starter_bank import validate_bank
 from nux_container_lab import Container
 from stage import stage
 from image import build
 bank=(a.starters/'starter-bank.bin').read_bytes();r=json.loads((a.starters/'starter-bank.json').read_text());validate_bank(bank,r)
 manifest=json.loads((a.work/'build/build.json').read_text());identity=manifest['identity']
 need(identity in ['NAMLNK27','NAMLNK28'] and r['identity']==identity and r['elf_sha256']==manifest['sha256'],'Public bank must be tested on exact firmware')
 original=Container(a.stock.read_bytes())
 with tempfile.TemporaryDirectory() as t:
  checked=stage(a.baseline,a.work,a.stock,a.starters/'starter-bank.bin',a.starters/'starter-bank.json',Path(t))
  candidate=(Path(t)/checked['file']).read_bytes()
 payload,_,plan=build(original.payload,a.baseline/'build/nam-link-offline.elf',a.work/'build/loop-startup-test.elf',identity)
 need(sha(payload)==r['candidate_payload_sha256'],'Public starter test mismatch')
 final=Container(candidate).payload;operations=[];covered=[]
 def operation(kind,name,offset,content,**extra):
  need(not any(offset<b and offset+len(content)>lo for lo,b in covered),'Overlapping recipe operations')
  covered.append((offset,offset+len(content)))
  operations.append(dict(kind=kind,id=name,offset=offset,length=len(content),before_sha256=sha(original.payload[offset:offset+len(content)]),sha256=sha(content),**extra))
 patches={int(x['offset'],16):bytes.fromhex(x['replacement']) for x in plan['patches']}
 patches.update({int(x['offset'],16):bytes.fromhex(x['replacement']) for x in plan['loop_patches']})
 for file,overlay in [(a.baseline/'build/nam-link-offline.elf',False),(a.work/'build/loop-startup-test.elf',True)]:
  with file.open('rb') as f:
   for section in ELFFile(f).iter_sections():
    if not section['sh_flags']&2 or not section['sh_size'] or section['sh_type']=='SHT_NOBITS':continue
    name=section.name
    need(name in ({'.loop_startup','.text'} if overlay else {'.text','.retired_audio','.ARM.exidx','.banktext'}),'Unexpected ELF section')
    offset=0x360000 if overlay and name=='.text' else 0x366000 if name=='.banktext' else section['sh_addr']
    data=bytearray(section.data())
    for at,replacement in patches.items():
     if offset<=at<offset+len(data):
      need(at+len(replacement)<=offset+len(data),'Hook crosses code section')
      data[at-offset:at-offset+len(replacement)]=replacement
    need(bytes(data)==final[offset:offset+len(data)],'Export differs from owned ELF plus generated patches')
    operation('code','.looptext' if overlay and name=='.text' else name,offset,bytes(data),data=base64.b64encode(data).decode())
 for at,data in patches.items():
  if any(lo<=at and at+len(data)<=hi for lo,hi in covered):continue
  need(len(data)<=10,'Unexpected hook size');need(final[at:at+len(data)]==data,'Unexpected final hook')
  operation('hook',f'hook-{at:x}',at,data,data=base64.b64encode(data).decode())
 operation('preset-bank','licensed-starters',0x344000,bank,data=base64.b64encode(bank).decode())
 operation('fill','empty-global-settings',0x364000,b'\xff'*8192,value=255)
 reconstructed=bytearray(original.payload)
 for op in operations:
  data=bytes([op['value']])*op['length'] if op['kind']=='fill' else base64.b64decode(op['data'])
  reconstructed[op['offset']:op['offset']+op['length']]=data
 need(original.rebuild_same_length(bytes(reconstructed))==candidate,'Recipe not equal to independently gated image')
 notices={'mighty-nam':ROOT/'LICENSE','Neural Amp Modeler':ROOT/'firmware/target/a2/UPSTREAM-LICENSE','RiffSmith captures':ROOT/'firmware/models/riffsmith/LICENSE','DaisySP AutoWah':ROOT/'firmware/target/link/DAISY-LICENSE'}
 recipe=dict(schema='mighty-nam-local-builder-1',builder_version='0.5.0' if identity=='NAMLNK28' else '0.4.0',identity=identity,target='NUX-MP3',firmware_revision='looper-preview',presets='riffsmith-mit-3',captures_included=True,starter_presets=r['presets'],starter_bank_sha256=sha(bank),input=dict(name='MP3_OR_V3.0.5.bin',bytes=len(original.data),sha256=sha(original.data),payload_sha256=sha(original.payload)),output=dict(name=f'mighty-nam-{identity}-experimental.bin',bytes=len(candidate),sha256=sha(candidate),payload_sha256=sha(final)),elf_sha256=manifest['sha256'],baseline_elf_sha256=manifest['baseline_sha256'],evidence=checked['evidence'],licenses=list(notices),license_notices={name:path.read_text() for name,path in notices.items()},physical_validation='Public starter variant offline only; looper hardware tests cover earlier variants.',operations=operations)
 target=ROOT/'docs/looper-builder';target.mkdir(exist_ok=True)
 text='/* Original linked code, generated hooks and MIT RiffSmith starters. No stock firmware. */\nglobalThis.MightyNamRecipe = '+json.dumps(recipe,indent=2)+';\n'
 (target/'recipe.js').write_text(text)
 audit=dict(schema='mighty-nam-builder-provenance-1',identity=identity,recipe_sha256=sha(text.encode()),elf_sha256=manifest['sha256'],input_sha256=sha(original.data),output_sha256=sha(candidate),output_payload_sha256=sha(final),operations=len(operations),code_bytes=sum(op['length'] for op in operations if op['kind']=='code'),stock_original_bytes_exported=False,private_or_tone3000_captures_exported=False,starter_bank_sha256=sha(bank),output_matches_independent_stager=True,device_access=False,flashed=False)
 (target/'provenance.json').write_text(json.dumps(audit,indent=2)+'\n')
 a.output.mkdir(parents=True,exist_ok=True);(a.output/recipe['output']['name']).write_bytes(candidate)
 (a.output/'export.json').write_text(json.dumps(audit,indent=2)+'\n')
 print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
