#!/usr/bin/env python3
"""Exact saved-image timer audit. Files and emulated MMIO only."""
import argparse,struct,json,hashlib
from pathlib import Path
from capstone import *
from capstone.arm import *
from unicorn import *
from unicorn.arm_const import *
p=argparse.ArgumentParser();p.add_argument('payload');p.add_argument('--output',required=True);a=p.parse_args()
b=Path(a.payload).read_bytes();sha=hashlib.sha256(b).hexdigest();assert sha=='a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990'
cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB);cs.detail=True;cs.skipdata=True
bases={f'GPT{i+1}':0x400ec000+i*0x4000 for i in range(6)}
# Real GPT register span is 0x28 bytes. Wider searches find floating constants.
ranges={**{k:(v,v+0x28) for k,v in bases.items()},'GPT2_clock_root':(0x40cc0780,0x40cc0800),'GPT2_clock_gate':(0x40cc6820,0x40cc6840)}
scans={}
for name,(lo,hi) in ranges.items():
 hits=[{'offset':hex(o),'value':hex(struct.unpack_from('<I',b,o)[0])} for o in range(0,0x2356c-3) if lo<=struct.unpack_from('<I',b,o)[0]<hi]
 scans[name]={'start':hex(lo),'end_exclusive':hex(hi),'unaligned_low_image_word_matches':hits}
# Bounded straight-line constant reconstruction: literal LDR, MOV/MOVW/MOVT,
# immediate arithmetic. Never claim exhaustive computed-pointer resolution.
values={};constructed=[]
for i in cs.disasm(b[0x400:0x2356c],0x400):
 if not i.id:values.clear();continue
 ops=i.operands;value=None;dest=ops[0].reg if ops and ops[0].type==ARM_OP_REG else None
 if i.id in [ARM_INS_MOV,ARM_INS_MOVW] and len(ops)>1 and ops[1].type==ARM_OP_IMM:value=ops[1].imm & 0xffffffff
 elif i.id==ARM_INS_MOVT and len(ops)>1 and dest in values:value=(values[dest]&0xffff)|(ops[1].imm<<16)
 elif i.id==ARM_INS_LDR and len(ops)>1 and ops[1].type==ARM_OP_MEM and ops[1].mem.base==ARM_REG_PC:
  pos=((i.address+4)&~3)+ops[1].mem.disp
  if 0<=pos<len(b)-3:value=struct.unpack_from('<I',b,pos)[0]
 elif i.id in [ARM_INS_ADD,ARM_INS_SUB] and len(ops)==3 and ops[1].type==ARM_OP_REG and ops[1].reg in values and ops[2].type==ARM_OP_IMM:
  value=(values[ops[1].reg]+(ops[2].imm if i.id==ARM_INS_ADD else -ops[2].imm))&0xffffffff
 _,written=i.regs_access()
 for reg in written:values.pop(reg,None)
 if dest is not None and value is not None:
  values[dest]=value
  for name,(lo,hi) in ranges.items():
   if lo<=value<hi:constructed.append({'pc':hex(i.address),'value':hex(value),'range':name,'instruction':i.mnemonic+' '+i.op_str})
 if i.group(CS_GRP_CALL) or i.group(CS_GRP_JUMP):values.clear()
vectors=[]
for i in range(6):
 off=(16+119+i)*4;target=struct.unpack_from('<I',b,off)[0];vectors.append({'timer':f'GPT{i+1}','vector_offset':hex(off),'handler':hex(target)})
assert vectors[0]['handler']=='0x11595' and all(x['handler']=='0x207fd' for x in vectors[1:])
assert scans['GPT2']['unaligned_low_image_word_matches']==[]
assert not [x for x in constructed if x['range']=='GPT2']

STOP=0x3fffc;u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A15)
u.mem_map(0,0x40000);u.mem_write(0,b[:0x2356c]);u.mem_map(0x20000000,0x40000)
for addr in [0x400ec000,0x40cc6000,0x40c60000,0xe000e000]:u.mem_map(addr,0x1000)
u.reg_write(UC_ARM_REG_C1_C0_2,0xf00000);u.reg_write(UC_ARM_REG_FPEXC,0x40000000)
def put(addr,v):u.mem_write(addr,struct.pack('<I',v))
def get(addr):return struct.unpack('<I',u.mem_read(addr,4))[0]
def run(pc,end=STOP):
 u.reg_write(UC_ARM_REG_SP,0x20035f00);u.reg_write(UC_ARM_REG_LR,STOP|1);u.emu_start(pc|1,end,count=100000);assert u.reg_read(UC_ARM_REG_PC)==end
# Clock-query stub, NOT a measured clock; GPT reset completion is virtual.
u.mem_write(0x8ae8,bytes.fromhex('00487047')+struct.pack('<I',24000000))
def reset_complete(uc,access,addr,size,value,user):
 if get(0x400ec000)&0x8000:put(0x400ec000,get(0x400ec000)&~0x8000)
u.hook_add(UC_HOOK_MEM_READ,reset_complete,begin=0x400ec000,end=0x400ec003)
run(0x11620);active={'cr':hex(get(0x400ec000)),'pr':get(0x400ec004),'ocr1':get(0x400ec010),'ir':get(0x400ec00c)}
put(0x2000e488,6);run(0x115c2);inactive={'cr':hex(get(0x400ec000)),'pr':get(0x400ec004),'ocr1':get(0x400ec010),'ir':get(0x400ec00c)}
assert active=={'cr':'0x47','pr':23,'ocr1':100000,'ir':1};assert inactive==dict(active,cr='0x46')
rows=[];peak=0
for count in [0,83,166,200,500,1000,50]:
 run(0x11662);assert get(0x400ec000)==0x47
 put(0x400ec024,count);u.reg_write(UC_ARM_REG_R4,0x2000969c);run(0x14eca,0x14f04)
 ratio,maximum=struct.unpack('<ff',u.mem_read(0x2000969c,8));display=u.mem_read(0x200096a4,1)[0]
 expected=struct.unpack('<f',struct.pack('<f',count/166))[0];peak=max(peak,expected)
 assert ratio==expected and maximum==peak and get(0x2000e490)==count and get(0x400ec000)==0x46
 rows.append({'synthetic_gpt_ticks':count,'stored_ratio':ratio,'stored_peak':maximum,'display_byte':display})
assert rows[4]['display_byte']<100 and rows[4]['stored_ratio']>3
out={'status':'PASS_BOUNDED_OFFLINE_TIMER_AUDIT','device_access':False,'playback':False,'payload_sha256':sha,'vectors':vectors,'scans':scans,'constant_reconstruction_matches':constructed,
 'stock_GPT1':{'base':'0x400ec000','start':'0x11662','stop_read':'0x11670','init_active':'0x11620','init_stopped':'0x115c2','active_config':active,'stopped_config':inactive,'counter_raw_ram':'0x2000e490','current_ratio_ram':'0x2000969c','peak_ratio_ram':'0x200096a0','percentage_byte_ram':'0x200096a4','callback_start_call':'0x14c04','callback_stop_call':'0x14eca','synthetic_meter_cases':rows,'clock_query_stub_hz':24000000,'physical_clock_measured':False,'formula':'ratio = float(CNT)/166.0f; byte is low 8 bits of int(ratio*100), clamped only after low-byte comparison. Values above 255 percent can wrap. Use raw count/float peak, not byte, for stress evidence.','coverage_limit':'Most main audio callback; excludes earlier/later IRQ work, entry latency and final callback bookkeeping. GPT1 is reset-on-enable, not free-running.'},
 'preferred_unused_candidate':{'name':'GPT2','confidence':'No direct register literal, reconstructed simple constant or installed nondefault IRQ handler found in bounded public low-image audit. Candidate unused, not a whole-device proof.','base':'0x400f0000','counter':'0x400f0024','candidate_control':'0x741','meaning':'EN + FRR + CLKSRC=5 (oscillator) + EN_24M; prescalers zero, IRQs off. No timer configuration executed on hardware.','clock_gate':'0x40cc6820','clock_root':'0x40cc0780','needed_before_use':['Confirm loader/other-core ownership and exact installed build','Verify oscillator routing and gate/root state','Bounded reset/setup and observed advancing counter','Calibration and DMA release timing']},
 'limits':['Unaligned low-image word scan plus straight-line reconstruction is not exhaustive alias or indirect-call analysis.','Resource overlay code and other-core/loader timer ownership are not fully audited.','Static default IRQ handler does not prove a polled timer is unused.','Unicorn timer values and reset completion are synthetic, not wall-clock/cycle measurements.']}
Path(a.output).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':out['status'],'preferred_candidate':'GPT2','stock_meter_cases':len(rows),'wrapped_percentage_example':rows[4]}))
