from integration import *
import struct,zlib,hashlib,json,time
start=time.monotonic();M,v,s,preset,input_block,model_slot=setup(True)
m=M(TEST_BANK.read_bytes());m.service();m.initialize_usb();m.arm();rows=[]
scratch=0x20025000
c=bytes([8,1,0,1,100,50,50,50,50,50,0,0,0,0,0,0,2,0,3,12,100,30,50,0,50,50,0,0,0,0,0,0])
m.u.mem_write(scratch,c);m.call(v.sym['mpp_fx_set'],[scratch]);assert m.u.reg_read(v.R[0])==1;m.service()
print('Stock config initialized',flush=True)
# Bad/duplicate types are rejected without replacing the live configuration.
m.call(v.sym['mpp_fx_get'],[scratch]);good=bytes(m.u.mem_read(scratch,32))
for bad in [0,30,127]:
 c=bytearray(good);c[3]=bad;m.u.mem_write(scratch,bytes(c));m.call(v.sym['mpp_fx_set'],[scratch]);assert m.u.reg_read(v.R[0])==0
c=bytearray(good);c[16]=8;c[19]=26;m.u.mem_write(scratch,bytes(c));m.call(v.sym['mpp_fx_set'],[scratch]);assert m.u.reg_read(v.R[0])==0
m.call(v.sym['mpp_fx_get'],[scratch]);assert m.u.mem_read(scratch,32)==good

# Save/reload through real bank code, while all flash lives only in emulator RAM.
m.call(v.sym['mpp_bank_model'],[]);address=m.u.reg_read(v.R[0]);
# Slot extent comes from the existing receiver/storage schema, not a guessed size.
from a2_storage import SLOT_SIZE
capture=bytes(m.u.mem_read(address,SLOT_SIZE));settings=bytes(m.u.mem_read(m.preset,128))
body=struct.pack('<4I',zlib.crc32(capture),zlib.crc32(settings),1,8)+hashlib.sha256(capture).digest()+b'Stock amp'.ljust(64,b'\0')
assert m.bank_request(2,0,body)[7]==0
m.restart();m.service();m.call(v.sym['mpp_fx_get'],[scratch]);assert m.u.mem_read(scratch,32)==good
assert m.page(126)==(0,0x5354011d) and not m.diag()[3]
rows.append(dict(case='stored_stock_block',persisted_after_restart=True,unsupported_models_rejected=True))

(HERE/'persistence-tests.json').write_text(json.dumps(dict(status='PASS_NAMLNK30_STOCK_PERSISTENCE',sha256=sha(HERE/'build/extra.elf'),rows=rows,seconds=time.monotonic()-start),indent=2)+'\n')
print('Invalid configs, store and restart PASS',flush=True)
