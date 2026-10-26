"""Export original overlay instructions and user-input copy recipes, not NUX bytes."""
from integration import *
sys.path[:0]=[str(BASE/"generated/research"),str(BASE/"generated/tools")]
import base64
from seven_defaults import populate
sys.path.insert(0,str(ROOT/'firmware/tools'))
from nux_container_lab import Container
repo=ROOT
digest=lambda b:hashlib.sha256(b).hexdigest()
b64=lambda b:base64.b64encode(b).decode()
old=json.JSONDecoder().raw_decode((repo/'docs/builder-v29/recipe.js').read_text().split('globalThis.MightyNamRecipe = ',1)[1])[0]
original=Container(STOCK_FILE.read_bytes())
body,s,plan=extension(original.payload,BASE/'build/nam-link-offline.elf',LOOP/'build/loop-startup-test.elf')
body=bytearray(body);bank=base64.b64decode(next(o['data'] for o in old['operations'] if o['kind']=='preset-bank'))
bank=populate(bank)
body[0x344000:0x360000]=bank;body[0x364000:0x366000]=bytes([255])*8192
ops=[];covered=[]
def operation(kind,id,at,content,**extra):
 assert not any(at<end and at+len(content)>lo for lo,end in covered),(id,'overlap')
 covered.append((at,at+len(content)))
 op=dict(kind=kind,id=id,offset=at,length=len(content),before_sha256=digest(original.payload[at:at+len(content)]),sha256=digest(content),**extra)
 ops.append(op)
for o in old['operations']:
 at,n=o['offset'],o['length'];data=bytes(body[at:at+n]);kwargs={'value':255} if o['kind']=='fill' else {'data':b64(data)}
 operation(o['kind'],o['id'],at,data,**kwargs)
for row in plan['elf_regions']:
 if row['name'] not in ['.extra_boot','.master_zero','.stockamptext']:continue
 at=int(row.get('load_address',row['start']),16);at=at-0x30040000 if at>=0x30040000 else at
 data=bytes(body[at:at+row['bytes']]);operation('code',row['name'],at,data,data=b64(data))
at=0x65d8;data=bytes(body[at:at+4]);operation('hook','hook-65d8',at,data,data=b64(data))
operation('stock-copy','amp-12-resource',0xb00000,bytes(body[0xb00000:0xb2c428]),source=0x340000)
for row in json.loads((HERE/'wrappers/manifest.json').read_text()):
 at=0xb40000+(row['amp']-1)*0x800;data=bytes(body[at:at+row['bytes']]);segments=[];cursor=0
 for fragment in sorted(row['original_fragments'],key=lambda x:x['offset']):
  lo,n,src=fragment['offset'],fragment['length'],fragment['source'];assert lo>=cursor
  if lo>cursor:segments.append(dict(offset=cursor,length=lo-cursor,data=b64(data[cursor:lo])))
  assert data[lo:lo+n]==original.payload[src:src+n]
  segments.append(dict(offset=lo,length=n,source=src));cursor=lo+n
 if cursor<len(data):segments.append(dict(offset=cursor,length=len(data)-cursor,data=b64(data[cursor:])))
 operation('stock-wrapper',f'amp-wrapper-{row["amp"]}',at,data,segments=segments)
for amp,offsets in {4:[0x84,0x8e0c],22:[0x236c4,0x2c3ec]}.items():
 source=struct.unpack_from('<I',original.payload,0x1ab60+32*amp+12)[0]-0x30040000
 for off in offsets:operation('amp-zero',f'amp-zero-{source+off:x}',source+off,bytes(4))
at=0xb50000;data=bytes(body[at:at+29*24]);operation('code','.amp-metadata',at,data,data=b64(data))
rebuilt=bytearray(original.payload)
for op in ops:
 if op['kind']=='stock-copy':data=original.payload[op['source']:op['source']+op['length']]
 elif op['kind']=='stock-wrapper':
  data=bytearray()
  for p in op['segments']:
   assert p['offset']==len(data)
   data+=original.payload[p['source']:p['source']+p['length']] if 'source' in p else base64.b64decode(p['data'])
 elif op['kind']=='amp-zero':data=bytes(4)
 elif op['kind']=='fill':data=bytes([255])*op['length']
 else:data=base64.b64decode(op['data'])
 assert len(data)==op['length'] and digest(data)==op['sha256'];rebuilt[op['offset']:op['offset']+len(data)]=data
assert rebuilt==body
candidate=original.rebuild_same_length(bytes(body))
r=copy.deepcopy(old);r.update(builder_version='0.7.1',identity='NAMLNK30',firmware_revision='stock-amps-r2',elf_sha256=sha(HERE/'build/extra.elf'),operations=ops,physical_validation='Exact NAMLNK30 build tested offline; hardware trial pending.',evidence={'stock_amp_dsp_cases':87,'real_time_deadlines_verified':False})
r['starter_presets'] += [{**r['starter_presets'][0], 'color':color} for color in range(3,7)]
r['starter_bank_sha256']=digest(bank)
r['output']=dict(name='mighty-nam-NAMLNK30-r2-experimental.bin',bytes=len(candidate),sha256=digest(candidate),payload_sha256=digest(body))
text='/* Original code, relocation instructions, input-copy descriptions and MIT starters. No stock firmware bytes. */\nglobalThis.MightyNamRecipe = '+json.dumps(r,indent=2)+';\n(globalThis.MightyNamRecipes ??= {})[globalThis.MightyNamRecipe.identity] = globalThis.MightyNamRecipe;\n'
(repo/'docs/looper-builder/recipe.js').write_text(text)
audit=dict(schema='mighty-nam-builder-provenance-1',identity='NAMLNK30',recipe_sha256=digest(text.encode()),elf_sha256=r['elf_sha256'],input_sha256=digest(original.data),output_sha256=digest(candidate),output_payload_sha256=digest(body),operations=len(ops),code_bytes=sum(o['length'] for o in ops if o['kind']=='code'),stock_original_bytes_exported=False,private_or_tone3000_captures_exported=False,starter_bank_sha256=digest(bank),output_matches_independent_stager=True,device_access=False,flashed=False)
(repo/'docs/looper-builder/provenance.json').write_text(json.dumps(audit,indent=2)+'\n')
out=HERE/'staged';out.mkdir(exist_ok=True)
(out/r['output']['name']).write_bytes(candidate)
(out/'build-report.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(audit))
print('amp_zero_allowlist',[(hex(o['offset']),o['length']) for o in ops if o['kind']=='amp-zero'])
