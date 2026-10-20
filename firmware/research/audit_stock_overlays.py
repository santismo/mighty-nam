#!/usr/bin/env python3
"""Audit stock executable overlays observed in the bounded reload test.
Reads saved files; scans cannot exclude computed or encoded references.
"""
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_GRP_CALL,CS_GRP_JUMP
from capstone.arm import ARM_OP_IMM,ARM_OP_MEM,ARM_REG_PC
from candidate_image import STOCK_SHA,require
p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('background_results',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
b=a.payload.read_bytes();require(hashlib.sha256(b).hexdigest()==STOCK_SHA,'Exact V1.5.6 required')
j=json.loads(a.background_results.read_text());require(j['status']=='PASS_BOUNDED_STOCK_BACKGROUND_RAM_TESTS','Successful observed-loader results required')
blocks=sorted({(int(x['destination'],16),int(x['source'],16),x['bytes']) for x in j['memory_activity'] if x['source'] and 0x24000<=int(x['destination'],16)<0x40000})
cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB);cs.detail=True;cs.skipdata=True;hits=[];records=[]
for dest,src,size in blocks:
 offset=src-0x30040000;require(0<=offset<offset+size<=len(b),'Overlay outside saved payload')
 data=b[offset:offset+size]
 for i in cs.disasm(data,dest):
  if not i.id:continue
  if i.group(CS_GRP_JUMP) or i.group(CS_GRP_CALL):
   for o in i.operands:
    if o.type==ARM_OP_IMM and 0x1a0a4<=o.imm<0x1b488:hits.append({'kind':'branch','source':hex(src+i.address-dest),'target':hex(o.imm)})
  for o in i.operands:
   if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC:
    target=((i.address+4)&~3)+o.mem.disp
    if 0x1a0a4<=target<0x1b488:hits.append({'kind':'pc_literal','source':hex(src+i.address-dest),'target':hex(target)})
 for off in range(0,len(data)-3,4):
  value=struct.unpack_from('<I',data,off)[0]
  if (0x1a0a4<=value<0x1b488 and value&1) or 0x202e4000<=value<0x202e6000:
   hits.append({'kind':'aligned_word','source':hex(src+off),'target':hex(value)})
 records.append({'runtime_destination':hex(dest),'saved_source_address':hex(src),'payload_offset':hex(offset),'bytes':size,'sha256':hashlib.sha256(data).hexdigest()})
require(len(blocks)==40,'Observed overlay coverage changed; review before approving scan')
require(not hits,'Potential reference into retired AMP space requires review')
result={'status':'PASS_BOUNDED_STOCK_OVERLAY_REFERENCE_SCAN','stock_sha256':STOCK_SHA,'overlay_variants':len(blocks),'references_into_reclaimed_code_or_reserved_state':hits,'overlays':records,
 'limits':['Only forty overlays exercised by the saved reload test','Linear disassembly and aligned-word scanning do not establish a complete call/data graph','Computed addresses, compressed pointers and indirect calls are not excluded','Overlay DSP functions were not run by this audit'],
 'device_or_audio_access':False}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'overlay_variants':len(blocks),'potential_references':len(hits)}))
