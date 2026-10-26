# Reuse only the isolated CPU fixture setup, not its normal test loop.
from pathlib import Path
exec(Path(__file__).with_name('test_stock_unit.py').read_text().split('rows=[]')[0])
m=new_candidate();config=bytes([8,1,2,1,100,50,50,50,50,50,0,0,0,0,0,0,2,0,3,12,100,30,50,0,50,50,0,0,0,0,0,0])
state=symbols(HERE/'build/extra.elf')['_ZN12_GLOBAL__N_15stateE']
m.u.mem_write(0x20025000,config);m.call(s['mpp_fx_set'],[0x20025000]);assert m.u.reg_read(UC_ARM_REG_R0)==1
original=bytes(m.u.mem_read(0x30b80000,1));m.u.mem_write(0x30b80000,bytes([original[0]^1]));m.call(s['mpp_extra_service'])
assert struct.unpack('<I',m.u.mem_read(state+16,4))[0]==0
x=np.array([.01,-.02,.03,-.04,.05,-.06,.07,-.08],dtype=np.float32).tobytes()
m.u.mem_write(0x20025000,x);m.u.mem_write(0x20025020,x);m.call(s['mpp_extra_process'],[0,0x20025000,0x20025020]);assert bytes(m.u.mem_read(0x20025000,32))==x
m.u.mem_write(0x30b80000,original);m.call(s['mpp_extra_service']);assert struct.unpack('<I',m.u.mem_read(state+16,4))[0]==1
(HERE/'fallback-tests.json').write_text(json.dumps(dict(status='PASS_COPY_CHECKSUM_FALLBACK',corrupt_copy_never_executed=True,dry_path_preserved=True,recovered_after_valid_copy=True,extra_sha256=sha(HERE/'build/extra.elf')),indent=2)+'\n')
print('Copy checksum / dry fallback / valid retry PASS')
