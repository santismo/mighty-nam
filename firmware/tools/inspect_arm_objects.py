#!/usr/bin/env python3
"""Minimal ELF32 ARM object audit (no loading or execution)."""
import json
import struct
import sys
from pathlib import Path
reports={}
for filename in sys.argv[1:]:
    b=Path(filename).read_bytes()
    assert b[:7]==b'\x7fELF\x01\x01\x01'
    typ,machine=struct.unpack_from('<HH',b,16);assert typ==1 and machine==40
    offset=struct.unpack_from('<I',b,32)[0]
    size,num,names_idx=struct.unpack_from('<HHH',b,46)
    sh=[struct.unpack_from('<10I',b,offset+i*size) for i in range(num)]
    names=b[sh[names_idx][4]:sh[names_idx][4]+sh[names_idx][5]]
    def name(table,pos):return table[pos:].split(b'\0',1)[0].decode()
    sections=[{'name':name(names,s[0]),'type':s[1],'bytes':s[5]} for s in sh if s[2]&2]
    undefined=[]
    for s in sh:
        if s[1]!=2:continue
        strings=sh[s[6]];strings=b[strings[4]:strings[4]+strings[5]]
        for p in range(s[4],s[4]+s[5],s[9]):
            n,v,z,info,other,idx=struct.unpack_from('<IIIBBH',b,p)
            if n and idx==0:undefined.append(name(strings,n))
    reports[Path(filename).name]={'format':'ELF32 ARM relocatable, not executable firmware','allocated_sections':sections,
        'static_zero_initialized_bytes':sum(s['bytes'] for s in sections if s['type']==8),'unresolved_symbols':undefined,
        'has_static_initializers':any(s['name'].startswith('.init_array') for s in sections)}
print(json.dumps(reports,indent=2))
