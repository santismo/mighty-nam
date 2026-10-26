from integration import *
import json,math
sys.path.insert(0,str(ROOT/'scripts'))
M,v,s,preset,input_block,model_slot=setup(True)
from a2_model import extract
from a2_oracle import Engine,library
r=json.JSONDecoder().raw_decode((ROOT/'docs/builder-v29/recipe.js').read_text().split('globalThis.MightyNamRecipe = ',1)[1])[0]
import base64
bank=base64.b64decode(next(o['data'] for o in r['operations'] if o['kind']=='preset-bank'))
m=M(bank,fill=0xa5);m.service();m.initialize_usb();m.arm();rows=[]
assert m.get(v.sym['mpp_listen_enabled'])==1
for color in [1,2,0]:assert m.button()==color
assert m.page(126)==(0,0x5354011d)
for color,name in enumerate(['clean','bass-clean','distorted']):
 assert m.bank_request(3,color,nonce=1000+color)[7]==0;m.service()
 file=HERE/f'public-{name}-lite.nam';file.write_text(json.dumps(extract(json.loads((ROOT/f'firmware/models/riffsmith/riffsmith-{name}.nam').read_text()))))
 m.boundary_oracle=Engine(library(str(Path(__import__('os').environ['MIGHTY_NAM_REFERENCE']))),file);m.max_boundary_error=0.;peak=0
 for n in range(1600):
  out=m.process(n,input_block(n));assert all(map(math.isfinite,out));peak=max(peak,*map(abs,out))
 assert 0<peak<1 and not m.words()[4] and not m.diag()[3] and m.max_boundary_error<2e-5,(color,peak,m.words(),m.diag(),m.max_boundary_error)
 rows.append(dict(color=color,callbacks=1600,peak=peak,reference_error=m.max_boundary_error));m.boundary_oracle=None
 print(rows[-1],flush=True)
(HERE/'starter-tests.json').write_text(json.dumps(dict(status='PASS_NAMLNK30_PUBLIC_STARTERS',rows=rows,amp_extension_sha256=sha(HERE/'build/extra.elf'),startup_playback=True,button_cycle=True,hardware_tested=False),indent=2)+'\n')
