#!/usr/bin/env python3
"""Bounded public-image search for ROM downloader entry. No live-device APIs."""
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import *
from capstone.arm import *
p=argparse.ArgumentParser();p.add_argument('payloads',nargs='+',type=Path);p.add_argument('--sdk',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
# Exact previously decoded public payloads; never accept a connected device.
known={'a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990','e971240a1e333003804cfd154e5ee053026254bbf09b11499e8b4968d3600752'}
targets={0x0020001c:'ROM tree pointer location A',0x0021001c:'ROM tree pointer location B',0xeb100000:'ROM downloader auto argument',0xeb110000:'ROM downloader USB argument',0xeb120000:'ROM downloader UART argument'}
cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB);cs.detail=True;cs.skipdata=True;reports=[]
for path in a.payloads:
 b=path.read_bytes();sha=hashlib.sha256(b).hexdigest();assert sha in known
 hits={}
 for value,name in targets.items():
  matches=[];pos=0;needle=struct.pack('<I',value)
  while (pos:=b.find(needle,pos))>=0:matches.append(hex(pos));pos+=1
  hits[hex(value)]={'meaning':name,'all_payload_unaligned_word_offsets':matches,'first_256KiB_offsets':[v for v in matches if int(v,16)<0x40000]}
 values={};constructed=[];rom_calls=[]
 for i in cs.disasm(b[0x400:0x40000],0x400):
  if not i.id:values.clear();continue
  ops=i.operands;dest=ops[0].reg if ops and ops[0].type==ARM_OP_REG else None;v=None
  if i.id in [ARM_INS_MOV,ARM_INS_MOVW] and len(ops)>1:
   if ops[1].type==ARM_OP_IMM:v=ops[1].imm&0xffffffff
   elif ops[1].type==ARM_OP_REG:v=values.get(ops[1].reg)
  elif i.id==ARM_INS_MOVT and len(ops)>1 and dest in values:v=(values[dest]&0xffff)|(ops[1].imm<<16)
  elif i.id==ARM_INS_LDR and len(ops)>1 and ops[1].type==ARM_OP_MEM and ops[1].mem.base==ARM_REG_PC:
   pos=((i.address+4)&~3)+ops[1].mem.disp
   if 0<=pos<len(b)-3:v=struct.unpack_from('<I',b,pos)[0]
  elif i.id in [ARM_INS_ADD,ARM_INS_SUB,ARM_INS_ORR] and len(ops)==3 and ops[1].type==ARM_OP_REG and ops[1].reg in values and ops[2].type==ARM_OP_IMM:
   src=values[ops[1].reg];imm=ops[2].imm
   v=((src+imm) if i.id==ARM_INS_ADD else (src-imm) if i.id==ARM_INS_SUB else (src|imm))&0xffffffff
  if i.group(CS_GRP_CALL) or i.group(CS_GRP_JUMP):
   for op in ops:
    target=op.imm if op.type==ARM_OP_IMM else values.get(op.reg) if op.type==ARM_OP_REG else None
    if target is not None and 0x00200000<=target<0x00240000:rom_calls.append({'pc':hex(i.address),'target':hex(target),'instruction':i.mnemonic+' '+i.op_str})
  _,written=i.regs_access()
  for reg in written:values.pop(reg,None)
  if dest is not None and v is not None:
   values[dest]=v
   if v in targets:constructed.append({'pc':hex(i.address),'value':hex(v),'meaning':targets[v],'instruction':i.mnemonic+' '+i.op_str})
  if i.group(CS_GRP_CALL) or i.group(CS_GRP_JUMP):values.clear()
 reports.append({'file':path.name,'sha256':sha,'bytes':len(b),'word_search':hits,'low_image_linear_scan':{'start':'0x400','end_exclusive':'0x40000','reconstructed_targets':constructed,'possible_rom_branches':rom_calls}})
sdk=a.sdk.read_text();assert '*(uint32_t *)0x0021001cU' in sdk and '*(uint32_t *)0x0020001cU' in sdk
assert sdk.index('void (*runBootloader)')<sdk.index('standard_version_t version;')
result={'status':'COMPLETE_BOUNDED_ROM_ENTRY_AUDIT','reports':reports,'sdk_sha256':hashlib.sha256(a.sdk.read_bytes()).hexdigest(),
 'primary_sources':{'sdk':'https://raw.githubusercontent.com/nxp-mcuxpresso/legacy-mcux-sdk/main/devices/MIMXRT1176/drivers/fsl_romapi.c','reference_manual_nxp_authored_mirror':'https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7139/IMXRT1170RM.pdf','nux_downloads':'https://nuxaudio.com/product/mightyplugpro/'},
 'documented_software_entry':{'argument':'0xeb110000','meaning':'Enter serial downloader selecting USB','api':'ROM_RunBootloader(&argument)','entry_tree':'SDK selects the pointer stored at 0x0021001c or 0x0020001c using the chip identification field; first tree member is runBootloader. Do not substitute a different RT-family API structure.','implemented_or_called':False},
 'engineering_implication':'A future working application could offer a software rescue entry before audio startup. This requires executing our code first, and cannot rescue a broken reset vector or establish initial USB RAM access on the untouched plug.',
 'match_review':'No auto/USB/UART argument word or reconstructed entry constant was found. Root-pointer word matches are mostly in later resources; the V3 low-image hit at 0xcb35 crosses instruction bytes (ADD at 0xcb34 and MOV at 0xcb36), not a pointer literal. Linear ROM-branch candidates include data-like regions and are not established reachable calls.',
 'physical_recovery_proven':False,'sealed_rom_entry_proven':False,'device_access':False,'playback':False,
 'limits':['Word searches and bounded linear constant reconstruction are not a control-flow proof; data may decode as instructions.','No negative result excludes computed calls, encoded code, other cores or the missing factory loader.','ROM availability is documented for the chip family; exact revision, security state, cleanup requirements and connector enumeration are untested.','No new public MP-3 loader/service binary or independently reachable recovery entry was established.']}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'payloads':[{'file':d['file'],'word_matches':sum(len(x['all_payload_unaligned_word_offsets']) for x in d['word_search'].values()),'constructed_targets':d['low_image_linear_scan']['reconstructed_targets'],'possible_rom_branches':d['low_image_linear_scan']['possible_rom_branches']} for d in reports],'sealed_rom_entry_proven':False}))
