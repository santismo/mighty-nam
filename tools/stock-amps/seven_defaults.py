"""Populate empty colors from a supplied bank without changing existing records."""
import struct,zlib

def populate(bank):
    if len(bank)!=7*16384:raise ValueError('Unexpected bank size')
    out=bytearray(bank);records=[]
    for color in range(7):
        candidates=[]
        for copy in range(2):
            at=color*16384+copy*8192;r=bank[at:at+8192]
            if struct.unpack_from('<III',r)==(0x3142504e,1,color) and struct.unpack_from('<I',r,8188)[0]==0x454e4f44 and struct.unpack_from('<I',r,8184)[0]==zlib.crc32(r[:8184]):
                candidates.append(r)
        records.append(max(candidates,key=lambda r:struct.unpack_from('<I',r,12)[0]) if candidates else None)
    source=next((r for r in records if r is not None),None)
    if source is None:raise ValueError('No valid source preset')
    for color,record in enumerate(records):
        if record is not None:continue
        new=bytearray(source);struct.pack_into('<II',new,8,color,1)
        struct.pack_into('<I',new,8184,zlib.crc32(new[:8184]))
        out[color*16384:color*16384+8192]=new
    return bytes(out)
