#!/usr/bin/env python3
"""Bounded static audit of retired AMP code in exact stock V1.5.6.
Recursive decoding avoids treating each function's literal pool as code. This
is not whole-program proof: computed transfers and encoded pointers remain.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_GRP_CALL, CS_GRP_JUMP
from capstone.arm import *

STOCK_SHA='a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990'
LOW,HIGH=0x1a0a4,0x1b488
MODELS={9:(0x1a8fd,0x1a785),10:(0x1b2dd,0x1b14d),12:(0x1a22d,0x1a0a5),
        13:(0x1afa1,0x1ae11),18:(0x1a5b5,0x1a415),22:(0x1ac69,0x1aad1)}
def need(ok,message):
 if not ok:raise ValueError(message)
def audit(b):
 need(hashlib.sha256(b).hexdigest()==STOCK_SHA,'Exact V1.5.6 required for reclaimed-code audit')
 cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB);cs.detail=True
 roots=sorted(v&~1 for pair in MODELS.values() for v in pair)
 functions=[];previous_code=set();previous_literals=set()
 for root,end in zip([0x19eb8]+roots,roots+[HIGH]):
  seen={};todo=[root];calls=[];literals=[]
  while todo:
   pc=todo.pop()
   if pc in seen:continue
   need(root<=pc<end,'Control flow crosses selected function boundary: '+hex(pc))
   i=next(cs.disasm(b[pc:pc+4],pc,count=1),None);need(i is not None,'Invalid instruction')
   seen[pc]=i;ops=i.operands;imm=[o.imm for o in ops if o.type==ARM_OP_IMM]
   call=i.group(CS_GRP_CALL);jump=i.group(CS_GRP_JUMP)
   returns=(i.id==ARM_INS_BX and ops[0].reg==ARM_REG_LR) or (i.id in [ARM_INS_POP,ARM_INS_LDM] and any(o.type==ARM_OP_REG and o.reg==ARM_REG_PC for o in ops))
   for o in ops:
    if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC:
     addr=((pc+4)&~3)+o.mem.disp;literals.append(addr)
   if call:
    need(bool(imm),'Indirect call in selected function needs review')
    calls.append(imm[-1]);need(not LOW<=imm[-1]<HIGH,'Unexpected call into reclaimed span')
   if jump and not call and not returns:
    need(bool(imm),'Indirect jump needs review')
    target=imm[-1]
    if root<=target<end:todo.append(target)
    else:
     need(i.id==ARM_INS_B and i.cc==ARM_CC_AL,'Conditional branch escapes function')
     calls.append(target);need(not LOW<=target<HIGH,'Unexpected tail call into reclaimed span')
   if returns or (jump and not call and i.id not in [ARM_INS_CBZ,ARM_INS_CBNZ] and i.cc==ARM_CC_AL):continue
   todo.append(pc+i.size)
  if root==0x19eb8:
   previous_code=set(seen);previous_literals=set(literals)
  else:functions.append({'entry':hex(root),'next_function':hex(end),'reachable_instructions':len(seen),
   'last_reachable_instruction':hex(max(seen)),'direct_call_or_tail_targets':[hex(x) for x in sorted(set(calls))]})
 # Broad linear scan generates false branches from data; retain and classify
 # them, rather than silently treating the entire file as executable code.
 cs.skipdata=True;branch_candidates=[];literal_reads=[]
 for i in cs.disasm(b[0x400:0x202a8],0x400):
  if not i.id or LOW<=i.address<HIGH:continue
  if i.group(CS_GRP_CALL) or i.group(CS_GRP_JUMP):
   for o in i.operands:
    if o.type==ARM_OP_IMM and LOW<=o.imm<HIGH:
     branch_candidates.append({'source':hex(i.address),'target':hex(o.imm),
       'classification':'preceding function literal pool; not reachable instructions'})
     need(i.address not in previous_code and (i.address&~3) in previous_literals,'Unclassified incoming branch')
  for o in i.operands:
   if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC:
    target=((i.address+4)&~3)+o.mem.disp
    if LOW<=target<HIGH:literal_reads.append(hex(i.address))
 need(not literal_reads,'External PC-relative data access into reclaimed span')
 raw_refs=[];expected={}
 for model,pair in MODELS.items():
  for field,value in zip([6,7],pair):expected[0x18428+model*32+field*4]=value
 for off in range(0,len(b)-3,4):
  if LOW<=off<HIGH:continue
  value=struct.unpack_from('<I',b,off)[0]
  if LOW<=value<HIGH and value&1:
   need(expected.get(off)==value,'Unclassified aligned Thumb pointer into reclaimed span')
   raw_refs.append({'offset':hex(off),'value':hex(value)})
 need(len(raw_refs)==12,'Expected twelve AMP descriptor callbacks')
 return {'status':'BOUNDED_RECLAIMED_AMP_CODE_AUDIT_PASS','stock_sha256':STOCK_SHA,
  'region':{'start':hex(LOW),'end_exclusive':hex(HIGH),'capacity_bytes':HIGH-LOW,
    'original_region_sha256':hashlib.sha256(b[LOW:HIGH]).hexdigest()},
  'retired_amp_model_ids':sorted(MODELS),'functions':functions,
  'external_linear_branch_candidates':branch_candidates,'external_pc_relative_data_reads':literal_reads,
  'external_aligned_thumb_pointers':raw_refs,
  'retirement_dependency':'5578 and 5778 redirected; 57c0 returns before old background loader. Descriptor targets remain stock but those consumers must remain unreachable.',
  'offset_example':{'literal':'0x1aa84 = 0x1a864','use':'0x1a88a loads it; 0x1a890 uses [r4,r0], where r4 is amp data base, not a code pointer'},
  'limits':['Linear decoding and aligned-word scans are bounded heuristics, not exhaustive computed-reference proof',
   'No whole-program indirect-call, interrupt or encoded-pointer proof',
   'Static audit does not establish physical loader acceptance, MPU/cache behavior or USB recovery'],
  'device_or_audio_access':False}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 result=audit(a.payload.read_bytes());a.output.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'status':result['status'],'capacity_bytes':HIGH-LOW,'retired_amp_models':len(MODELS)}))
