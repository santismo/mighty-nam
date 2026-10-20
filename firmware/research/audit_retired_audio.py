"""Bounded incoming-reference audit of the replaced V1.5.6 audio callback.
No device access. Exact payload, recursive control flow, broad linear branch/
literal scan and aligned pointer scan. Computed references are not proven.
"""
import hashlib,struct
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_GRP_CALL,CS_GRP_JUMP
from capstone.arm import *
from audit_reclaimed_code import STOCK_SHA,need

ENTRY,LOW,HIGH=0x14bfc,0x14c04,0x14f08
def audit(b):
 need(hashlib.sha256(b).hexdigest()==STOCK_SHA,'Exact V1.5.6 required')
 cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB);cs.detail=True
 todo=[ENTRY];seen={};literals=set();calls=set()
 while todo:
  pc=todo.pop()
  if pc in seen:continue
  need(ENTRY<=pc<HIGH,'Audio callback flow escapes selected extent')
  i=next(cs.disasm(b[pc:pc+4],pc,count=1),None)
  need(i is not None,'Undecodable callback instruction');seen[pc]=i
  imm=[o.imm for o in i.operands if o.type==ARM_OP_IMM]
  call=i.group(CS_GRP_CALL);jump=i.group(CS_GRP_JUMP)
  returns=(i.id==ARM_INS_BX and i.operands[0].reg==ARM_REG_LR) or (
   i.id in [ARM_INS_POP,ARM_INS_LDM] and any(o.type==ARM_OP_REG and o.reg==ARM_REG_PC for o in i.operands))
  for o in i.operands:
   if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC:
    target=((pc+4)&~3)+o.mem.disp;literals.add(target)
    need(not LOW<=target<HIGH,'Callback has an embedded data pool')
  if call:
   need(bool(imm),'Indirect audio callback call needs separate audit')
   calls.add(imm[-1]);need(not LOW<=imm[-1]<HIGH,'Internal callback subroutine')
  if jump and not call and not returns:
   need(bool(imm),'Computed callback branch needs separate audit')
   todo.append(imm[-1])
  if returns or (jump and not call and i.id not in [ARM_INS_CBZ,ARM_INS_CBNZ] and i.cc==ARM_CC_AL):continue
  todo.append(pc+i.size)
 need(max(seen)==HIGH-4,'Expected callback terminal POP at 0x14f04')
 cs.skipdata=True
 for i in cs.disasm(b[0x400:0x202a8],0x400):
  if not i.id or ENTRY<=i.address<HIGH:continue
  if i.group(CS_GRP_CALL) or i.group(CS_GRP_JUMP):
   need(not any(o.type==ARM_OP_IMM and LOW<=o.imm<HIGH for o in i.operands),
        f'External branch into retired audio body: {i.address:#x}')
  for o in i.operands:
   if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC:
    need(not LOW<=((i.address+4)&~3)+o.mem.disp<HIGH,'External literal read into retired audio')
 for off in range(0,len(b)-3,4):
  if LOW<=off<HIGH:continue
  value=struct.unpack_from('<I',b,off)[0]
  need(not LOW<=value<HIGH,f'External aligned address into retired audio at {off:#x}')
 return dict(status='PASS_BOUNDED_RETIRED_AUDIO_BODY_AUDIT',stock_sha256=STOCK_SHA,
  start=hex(LOW),end_exclusive=hex(HIGH),bytes=HIGH-LOW,
  region_sha256=hashlib.sha256(b[LOW:HIGH]).hexdigest(),reachable_instructions=len(seen),
  shared_literals_preserved=[hex(x) for x in sorted(literals)],
  direct_calls=[hex(x) for x in sorted(calls)],
  retirement_dependency='0x14bfc must redirect to mpp_probe_audio before this body is replaced',
  limits=['No exhaustive computed-reference proof','No physical timing or recovery proof'])
