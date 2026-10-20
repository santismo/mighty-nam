#!/usr/bin/env python3
"""Bounded saved-image audit. No USB, audio, updater or device APIs."""
import argparse, hashlib, json, struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
ap=argparse.ArgumentParser();ap.add_argument('payload');ap.add_argument('--output',required=True);a=ap.parse_args()
p=Path(a.payload).read_bytes();sha=hashlib.sha256(p).hexdigest()
assert sha=='a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990'
STOP=0x3fffc;DWT=0xe0001000

def vm():
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7);u.mem_map(0,0x40000);u.mem_write(0,p[:0x2356c]);u.mem_map(0x20000000,0x40000);u.mem_map(0xe0000000,0x10000)
 return u

def run(u,pc):
 u.reg_write(UC_ARM_REG_SP,0x20035f00);u.reg_write(UC_ARM_REG_LR,STOP|1);
 try:u.emu_start(pc|1,STOP,count=100000)
 except Exception as e:raise RuntimeError(hex(u.reg_read(UC_ARM_REG_PC))) from e
 assert u.reg_read(UC_ARM_REG_PC)==STOP

def word(u,addr):return struct.unpack('<I',u.mem_read(addr,4))[0]

# Execute the actual delay with a deliberately synthetic advancing DWT register.
delays=[]
for initial in [12345678,0xfffffff0]:
 u=vm();u.mem_write(DWT+4,struct.pack('<I',initial));writes=[];selectors=[];reads=[]
 def read(uc,access,addr,size,value,user):
  v=(word(uc,DWT+4)+100)&0xffffffff;uc.mem_write(DWT+4,struct.pack('<I',v));reads.append(v)
 def write(uc,access,addr,size,value,user):writes.append({'pc':hex(uc.reg_read(UC_ARM_REG_PC)),'value':value})
 def code(uc,pc,size,user):
  if pc==0x8ae8:
   selectors.append(uc.reg_read(UC_ARM_REG_R0));uc.reg_write(UC_ARM_REG_R0,600000000);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_MEM_READ,read,begin=DWT+4,end=DWT+7)
 u.hook_add(UC_HOOK_MEM_WRITE,write,begin=DWT+4,end=DWT+7)
 u.hook_add(UC_HOOK_CODE,code);u.reg_write(UC_ARM_REG_R0,1);run(u,0xbe34)
 assert writes==[{'pc':'0xbe48','value':0}] and selectors==[29] and reads[0]==100
 delays.append({'initial_counter':initial,'counter_writes':writes,'clock_selector':selectors,'counter_read_count':len(reads),'returned':True})

# Execute stock registration, then dispatch every legal byte ID in both directions.
u=vm();run(u,0xac1e)
records=[]
for offset in range(0x1f384,0x1f384+128*9,9):
 c,h0,h1=struct.unpack_from('<BII',p,offset)
 assert bytes(u.mem_read(0x200141c4+c*9,9))==p[offset:offset+9]
 records.append({'id':c,'id_hex':hex(c),'record':hex(offset),'direction_0':hex(h0&~1),'direction_1':hex(h1&~1),'both_default':h0==h1==0xa1d3})
 if c==127:break
handlers={0xa1d2}|{int(r[k],16) for r in records for k in ['direction_0','direction_1']}
selected=[]
def stop_handler(uc,pc,size,user):
 if pc in handlers:selected.append(pc);uc.reg_write(UC_ARM_REG_PC,STOP)
u.hook_add(UC_HOOK_CODE,stop_handler)
dispatches=[]
for privacy in [0x70,0x20]:
 for cmd in range(128):
  for direction in [0,1]:
   msg=bytes([0xf0,0x43,0x58,privacy,cmd,direction,0,0,0,0,0xf7]);u.mem_write(0x20030000,msg)
   for reg,val in [(UC_ARM_REG_R0,0x20030000),(UC_ARM_REG_R1,len(msg)),(UC_ARM_REG_R2,0)]:u.reg_write(reg,val)
   before=len(selected);run(u,0xae24);assert len(selected)==before+1
   expected=word(u,0x200141c4+cmd*9+1+direction*4)&~1
   assert selected[-1]==expected
   dispatches.append({'privacy':privacy,'id':cmd,'direction':direction,'handler':hex(expected)})
# Confirm default response metadata without executing the transport.
v=vm();response=[]
def reply(uc,pc,size,user):
 if pc==0xa18a:
  response.append({'id':uc.reg_read(UC_ARM_REG_R0),'direction':uc.reg_read(UC_ARM_REG_R1),'length':uc.reg_read(UC_ARM_REG_R3),'data_hex':bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R2),8)).hex()})
  uc.reg_write(UC_ARM_REG_PC,STOP)
v.hook_add(UC_HOOK_CODE,reply);v.reg_write(UC_ARM_REG_R2,0);run(v,0xa1d2)
assert response==[{'id':127,'direction':2,'length':8,'data_hex':'0000000000000000'}]
# The separate privacy-0x40 path invokes a persistent-write routine before reply.
# Intercept its calls in simulated memory; never execute flash controller code.
w=vm();persistent=[]
def persistent_call(uc,pc,size,user):
 if pc in [0xbfa4,0xc0b0]:
  persistent.append({'entry':hex(pc),'args':[hex(uc.reg_read(reg)) for reg in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]][:1 if pc==0xbfa4 else 3]})
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
w.hook_add(UC_HOOK_CODE,persistent_call);run(w,0xba50)
assert persistent==[{'entry':'0xbfa4','args':['0x3003d000']},{'entry':'0xbfa4','args':['0x3003e000']},{'entry':'0xc0b0','args':['0x20004284','0x3003df00','0x200']}]
q=vm();route=[]
def route_stop(uc,pc,size,user):
 if pc==0xad9e:route.append(hex(pc));uc.reg_write(UC_ARM_REG_PC,STOP)
q.hook_add(UC_HOOK_CODE,route_stop);q.mem_write(0x20030000,bytes([0xf0,0x43,0x58,0x40,0x7f,0,0xf7]))
q.reg_write(UC_ARM_REG_R0,0x20030000);q.reg_write(UC_ARM_REG_R1,7);q.reg_write(UC_ARM_REG_R2,0);run(q,0xae24);assert route==['0xad9e']
# Exercise both DMA-buffer selections in the real IRQ body, with the actual
# processing callback intercepted. These are virtual DMA registers, not hardware.
irq_cases=[]
for next_tcd in [0x20016aa0,0x20016ac0]:
 t=vm();t.mem_map(0x40070000,0x2000);t.mem_write(0x40071018,struct.pack('<I',next_tcd))
 t.mem_write(0x200147c8,struct.pack('<I',100));calls=[];acks=[]
 t.mem_write(0x150fc,bytes.fromhex("04207047"));t.mem_write(0x14bfc,bytes.fromhex("7047"))
 def irq_call(uc,pc,size,user):
  if pc==0x14bfc:calls.append([hex(uc.reg_read(UC_ARM_REG_R0)),hex(uc.reg_read(UC_ARM_REG_R1))])
 def ack(uc,access,addr,size,value,user):acks.append(value)
 t.hook_add(UC_HOOK_CODE,irq_call,begin=0x14bfc,end=0x14bfc)
 run(t,0x11d94)
 offset=0 if next_tcd==0x20016aa0 else 0x80
 assert calls==[[hex(0x20016800+offset),hex(0x20016900+offset)]] and t.mem_read(0x4007001f,1)==bytes([16]) and word(t,0x200147c8)==108,(calls,list(t.mem_read(0x4007001f,1)),word(t,0x200147c8),hex(next_tcd))
 irq_cases.append({'virtual_next_tcd':hex(next_tcd),'callback_args':calls,'final_dma_ack_channel':t.mem_read(0x4007001f,1)[0],'sample_counter_before':100,'sample_counter_after':108,'callback_stubbed':True,'status_helper_stubbed':True})
cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
def disasm(lo,hi):return [{'pc':hex(i.address),'instruction':i.mnemonic+' '+i.op_str} for i in cs.disasm(p[lo:hi],lo)]
result={'status':'PASS_OFFLINE_ONLY','device_access':False,'audio_playback':False,'payload_sha256':sha,
 'delay':{'entry':'0xbe34','dwt_cyccnt_reset_pc':'0xbe48','cases':delays,'synthetic_clock_hz':600000000,'clock_not_measured':True,'disassembly':disasm(0xbe34,0xbe80)},
 'command_registry':{'initializer':'0xac1e','source_table':'0x1f384','ram_table':'0x200141c4','records':records,'tested_dispatches':len(dispatches),'dispatches':dispatches,'default_response':response,
 'finding':'Private 0x70 and R&D 0x20 use the same table. CPU RUN 0x05 and legacy-looking IDs 102/104/105 all dispatch to the default response in this exact public firmware; generic app constants do not establish a backup, DFU or timing command. Handlers were intercepted before execution.',
 'special_command_0x75':'Write handler compares subcommands 0x30, 0x32, 0x44. 0x32 follows factory-reset/preset paths. No physical command sent; do not probe these as recovery commands.'},
 'audio_boundary':{'vector_trampoline':'0x205a4','interrupt_entry':'0x11d94','block_callback':'0x14bfc','effects_outer':'0xe934','dispatcher':'0x122d0','interrupt_return':'0x11dd6','virtual_irq_cases':irq_cases,'block_frames':8,'nominal_rate_hz':48000,'nominal_period_us':8/48000*1e6,'disassembly':disasm(0x11d94,0x11dd8),'limitation':'Prior profiles do not encompass the full 0x14bfc callback or DMA interrupt, exception entry/exit, preemption or physical DMA.'},
 'privacy_0x40_path':{'parser':'0xae24','handler':'0xad9e','persistent_routine':'0xba50','calls_intercepted_in_emulator':persistent,'finding':'The separate 0x40 header route calls the flash erase/program wrappers at fixed addresses below the inferred application base before replying. Not a generic flash-read or RAM-execute command. These may be configuration sectors; contents and loader ownership remain unknown. Do not try as a read-only discovery command.','wrapper_evidence':'0xbfa4 strips address high nibble and submits flash command; 0xc0b0 loops over 256-byte program calls to 0xc034. Flash wrappers were intercepted, not run.'},
 'rom_api_literal_scan':{'range_end_exclusive':'0x2356c','pointers':{hex(x):[hex(i) for i in range(0x2356c-3) if p[i:i+4]==struct.pack('<I',x)] for x in [0x0020001c,0x0021001c]},'limitation':'Absent exact literals cannot rule out computed addresses or an indirect ROM entry path.'},
 'limits':['No bootloader bytes recovered.','Firmware map is public V1.5.6, not the installed 20220720 build.','Emulated clock and branch tests do not prove hardware timing or USB recovery.']}
for x in dispatches:
 if x['id'] in [5,102,104,105]:assert x['handler']=='0xa1d2'
Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'delay_cases':len(delays),'registered_records':len(records),'dispatches':len(dispatches),'default_reply':response,'output':a.output}))
