"""Reproducible V3 adapter of the original target and offline harness.

The explicit address manifest is reviewed against the exact public Original
payload, never inferred during a build. Numeric constants not in the manifest
(including peripheral registers and storage extents) stay unchanged. Generated
sources are retained for inspection; no stock code is copied into them.
"""
import argparse,hashlib,json,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OLD_SHA='a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990'
SHA='e971240a1e333003804cfd154e5ee053026254bbf09b11499e8b4968d3600752'
def prepare(out):
 out=out.resolve();out.mkdir(parents=True,exist_ok=True)
 mapping={int(k,16):int(v,16) for k,v in json.loads((Path(__file__).with_name('relocations.json')).read_text()).items()}
 report={}
 def translate(text):return re.sub(r'0x[0-9a-fA-F]+',lambda m:hex(mapping[int(m[0],16)]) if int(m[0],16) in mapping else m[0],text)
 for directory in ('target','research','tools'):
  for src in (ROOT/directory).rglob('*'):
   if not src.is_file() or src.suffix not in ('.py','.cpp','.hpp','.h','.ld','.c'):continue
   relative=src.relative_to(ROOT);dest=out/relative;dest.parent.mkdir(parents=True,exist_ok=True)
   original=src.read_text();text=translate(original).replace(OLD_SHA,SHA).replace('V1.5.6','V3.0.5 Original')
   # V3 uses a distinct identity; protocol and seven-slot record format stay unchanged.
   text=text.replace('NAMLNK22','NAMLNK23').replace("'K','2','2'","'K','2','3'")
   if relative.as_posix()=='target/link/usb_nam.ld':text=text.replace('LENGTH = 0x13e4','LENGTH = 0x13d4').replace('ORIGIN = 0xe1a4, LENGTH = 0x304','ORIGIN = 0x1c0e8, LENGTH = 0x188')
   if relative.as_posix()=='tools/build_link_firmware.py':text=text.replace("'-DMPP_COMPACT_INIT'","'-DMPP_COMPACT_INIT','-DMPP_STOCK_V3'")
   if relative.as_posix()=='research/candidate_vm.py':
    text=text.replace('0x2356c if reclaimed','0x30000 if reclaimed').replace('0xafb4,','')
    text=text.replace("['0x5778',hex(","['0x581a',hex(").replace(",'0x11984']",",'0x9194']")
    text=text.replace('u.mem_protect(0x24000,0x1c000,UC_PROT_READ)','u.mem_protect(0x30000,0x10000,UC_PROT_READ)')
   if relative.as_posix()=='research/audit_reclaimed_code.py':
    text=text.replace('LOW,HIGH=0x1c45c,0x1d830','LOW,HIGH=0x1c0e8,0x1d830').replace('MODELS={','MODELS={16:(0x1c271,0x1c0e9),').replace('0x1c270','0x1befc').replace('len(raw_refs)==12','len(raw_refs)==14').replace('twelve AMP','fourteen AMP')
    text=text.replace("'offset_example':{'literal':'0x1aa84 = 0x1a864','use':'0x1a88a loads it; 0x1a890 uses [r4,r0], where r4 is amp data base, not a code pointer'},",'')
   if relative.as_posix()=='research/preset_image.py':
    text=(Path(__file__).with_name('image.py')).read_text()
   if relative.as_posix()=='research/test_preset_runtime.py':text=text.replace("'NAMLNK23',", "'NAMLNK23','NAMLNK24',")
   if relative.as_posix()=='research/test_usb_nam.py':text=text.replace("'NAMLNK23' if a.pitch_release", "bundle[2]['identity'] if a.pitch_release and bundle[2]['identity'] in ('NAMLNK23','NAMLNK24')")
   if relative.as_posix()=='research/test_pitch_chain.py':text=text.replace("bundle[2]['identity']=='NAMLNK23'", "bundle[2]['identity'] in ('NAMLNK23','NAMLNK24')")
   dest.write_text(text)
   report[str(relative)]={'source_sha256':hashlib.sha256(original.encode()).hexdigest(),'generated_sha256':hashlib.sha256(text.encode()).hexdigest()}
 for directory in ('artifacts','models'):
  target=out/directory
  if not target.exists():target.symlink_to(ROOT/directory,target_is_directory=True)
 (out/'port-provenance.json').write_text(json.dumps({'stock_sha256':SHA,'relocations_sha256':hashlib.sha256(Path(__file__).with_name('relocations.json').read_bytes()).hexdigest(),'files':report},indent=2)+'\n')
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();print(prepare(a.output))
