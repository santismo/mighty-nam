"""Fixed model-slot format and bounded stock ownership audit. Files/memory only."""
import hashlib,json,struct,zlib,sys
from pathlib import Path
from candidate_image import STOCK_SHA,require
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from a2_model import extract
FLASH_BASE=0x30040000
SLOT_ADDRESS=0x30384000
SLOT_OFFSET=SLOT_ADDRESS-FLASH_BASE
SLOT_SIZE=8192
HEADER_SIZE=32
WEIGHTS=1871
BYTES=WEIGHTS*4
MAGIC=0x3241504d

def model_slot(path):
 j=extract(json.loads(Path(path).read_text()));data=struct.pack('<1871f',*j['weights']);crc=zlib.crc32(data)
 header=struct.pack('<8I',MAGIC,1,48000,WEIGHTS,BYTES,crc,1,0)
 return header+data+b'\xff'*(SLOT_SIZE-HEADER_SIZE-len(data))
def audit(stock):
 require(hashlib.sha256(stock).hexdigest()==STOCK_SHA,'Exact stock payload required')
 descriptors=[struct.unpack_from('<8I',stock,0x18428+32*i) for i in range(30)]
 owners=[i for i,d in enumerate(descriptors) if d[1] and d[3]<SLOT_ADDRESS+SLOT_SIZE and d[3]+d[1]>SLOT_ADDRESS]
 require(owners==[12],'Model slot ownership changed')
 d=descriptors[12];require(d[3]<=SLOT_ADDRESS and SLOT_ADDRESS+SLOT_SIZE<=d[3]+d[1],'Slot outside retired AMP data')
 refs=[{'offset':hex(i),'value':hex(struct.unpack_from('<I',stock,i)[0])} for i in range(0,len(stock)-3,4) if SLOT_ADDRESS<=struct.unpack_from('<I',stock,i)[0]<SLOT_ADDRESS+SLOT_SIZE]
 require(not refs,'Unclassified pointer into proposed model slot')
 overlays=json.loads((Path(__file__).resolve().parents[1]/'artifacts/reclaimed-overlay-audit.json').read_text())['overlays']
 require(all(not(int(o['saved_source_address'],16)<SLOT_ADDRESS+SLOT_SIZE and int(o['saved_source_address'],16)+o['bytes']>SLOT_ADDRESS) for o in overlays),'Slot overlaps effect overlay')
 ram_refs=[(i,struct.unpack_from('<I',stock,i)[0]) for i in range(0,0x2356c,4) if 0x202e4000<=struct.unpack_from('<I',stock,i)[0]<0x202f9000]
 require([x[0] for x in ram_refs]==[0x5470,0x57a4,0xf9c4,0x1f530,0x1fc84,0x20300],'Expanded RAM reference set changed')
 require(stock[0xf9c4:0xf9c8]==bytes.fromhex('80f82e20'),'Expected STRB instruction encoding')
 for off in [0x1f530,0x1fc84]:require(stock[off:off+4]==b') / ','Expected assertion-string bytes')
 return {'status':'BOUNDED_STORAGE_AUDIT_PASS','stock_sha256':STOCK_SHA,'slot_address':hex(SLOT_ADDRESS),'payload_offset':hex(SLOT_OFFSET),'slot_bytes':SLOT_SIZE,'slot_original_sha256':hashlib.sha256(stock[SLOT_OFFSET:SLOT_OFFSET+SLOT_SIZE]).hexdigest(),'amp_descriptor_owners':owners,'owner_source':hex(d[3]),'owner_bytes':d[1],'direct_aligned_references_into_slot':refs,'effect_overlays_excluded':len(overlays),'expanded_ram_refs':[{'offset':hex(i),'value':hex(v),'classification':('original AMP RAM literal' if i in [0x5470,0x57a4] else 'stock runtime zero table' if i==0x20300 else 'instruction encoding, not a pointer' if i==0xf9c4 else 'assertion text, not a pointer')} for i,v in ram_refs],'limits':['Aligned scans and descriptor ranges cannot exclude computed or encoded aliases','Retirement depends on all three AMP-entry patches','Only exact V1.5.6; installed build differs','Flash base is inferred; no physical loader/device tested']}
