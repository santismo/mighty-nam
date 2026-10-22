"""Build a LOCAL bank from app-exported presets using emulated firmware saves.
No connected device, MIDI or audio. Never commit the export, bank or captures.
"""
import argparse,base64,hashlib,json,struct,zlib
from pathlib import Path
from test_usb_nam import UsbMachine,v,preset_fixture
from preset_image import build,BANK,BANK_END

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['payload','elf','library_export','bank_output','review_output']:p.add_argument(name,type=Path)
 a=p.parse_args();data=json.loads(a.library_export.read_text())
 assert data['schema']=='mighty-nam-local-preset-export-1' and len(data['presets'])==7
 bundle=build(a.payload.read_bytes(),a.elf);assert bundle[2]['identity']=='NAMLNK22'
 v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=a.elf
 m=UsbMachine();m.service();rows=[]
 for color,row in enumerate(data['presets']):
  assert row['color']==color
  model=base64.b64decode(row['model']['slot'],validate=True)
  assert len(model)==8192 and hashlib.sha256(model).hexdigest()==row['model']['sha256']
  m.upload(model,100+color)
  fx=bytearray(preset_fixture([],{}))
  for index,value in row['effects'].items():fx[int(index)]=value
  fx[3]=(fx[3]&63)|(0 if row['nam_enabled'] else 64)
  fx[90:99]=bytes(row['order']);m.u.mem_write(m.preset,bytes(fx))
  assert m.ng(row['nam_tone'])[13]==0 and m.nv(row['usb_record_gain'])[13]==0
  at=v.SP-512;m.u.mem_write(at,bytes(row['fx']));m.call(v.sym['mpp_fx_set'],[at])
  fx=bytes(m.u.mem_read(m.preset,128));name=row['name'].encode('utf8')
  assert 0<len(name)<=63 and all(b>=32 and b!=127 for b in name)
  body=struct.pack('<4I',zlib.crc32(model),zlib.crc32(fx),1,8)+hashlib.sha256(model).digest()+name.ljust(64,b'\0')
  assert m.bank_request(2,color,body,nonce=200+color)[7]==0
  rows.append(dict(slot=color,name=row['name'],model_crc=zlib.crc32(model),model_sha256=hashlib.sha256(model).hexdigest(),effects=list(fx),extra_fx=row['fx'],play_on_boot=True,buffer=8))
  print('Seeded local Mac color',color+1,flush=True)
 flash=bytes(m.u.mem_read(BANK,BANK_END-BANK));cold=UsbMachine(flash,0xa5);cold.service()
 for color in [0,5,2,6,1,4,3,0]:
  cold.call(0xb38a,[color]);cold.service();expected=rows[color]
  assert cold.words()[5]==expected['model_crc'] and bytes(cold.u.mem_read(cold.preset,128))==bytes(expected['effects'])
  at=v.SP-512;cold.call(v.sym['mpp_fx_get'],[at]);assert bytes(cold.u.mem_read(at,32))==bytes(expected['extra_fx'])
  assert cold.words()[4]==0
 a.bank_output.write_bytes(flash)
 report=dict(status='PASS_OFFLINE_MAC_PRESET_BANK',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),export_sha256=hashlib.sha256(a.library_export.read_bytes()).hexdigest(),bank_sha256=hashlib.sha256(flash).hexdigest(),presets=rows,cold_boot_and_nonadjacent_recalls=True,device_access=False,host_audio_access=False)
 a.review_output.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
