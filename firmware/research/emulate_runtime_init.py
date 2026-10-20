"""Offline CPU emulation of saved stock C runtime initialization only.
No peripheral mapping and no host/device IO callbacks. Firmware stays in VM memory.
"""
import json,struct,hashlib
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC,UC_PROT_ALL
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
import argparse
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('--version',choices=['1','3'],required=True);args=p.parse_args()
b=args.payload.read_bytes()
expected={'1':'a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990','3':'e971240a1e333003804cfd154e5ee053026254bbf09b11499e8b4968d3600752'}
if hashlib.sha256(b).hexdigest()!=expected[args.version]: raise ValueError('Unexamined payload')
entry=0x2025d if args.version=='1' else 0x22641
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
u.mem_map(0,0x100000);u.mem_write(0,b[:0x100000]);u.mem_protect(0,0x100000,UC_PROT_READ|UC_PROT_EXEC)
u.mem_map(0x20000000,0x400000);u.mem_write(0x20000000,bytes([0xa5])*0x400000)
u.reg_write(UC_ARM_REG_SP,0x20080000);u.reg_write(UC_ARM_REG_LR,0x40001)
u.emu_start(entry,0x40000,count=5000000)
assert u.reg_read(UC_ARM_REG_PC)==0x40000,hex(u.reg_read(UC_ARM_REG_PC))
ram=bytes(u.mem_read(0x20000000,0x40000))
print(json.dumps({'scope':'Emulated saved runtime initializer; no peripherals mapped or hardware access', 'stock_payload_sha256':hashlib.sha256(b).hexdigest(),'entry':hex(entry),'returned_to':'0x40000','codec_register_defaults_0_to_20':ram[0x284:0x299].hex(' '),'raw_ram_bytes_at_0x20009b20':ram[0x9b20:0x9b2c].hex(' '),'initialized_dtcm_sha256':hashlib.sha256(ram).hexdigest()},indent=2))
