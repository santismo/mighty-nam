"""Extend the established CPU harness for the new startup area; no physical I/O."""
import hashlib,struct,sys,json,os
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE,UC_HOOK_MEM_READ,UC_PROT_ALL
from unicorn.arm_const import UC_ARM_REG_PC
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS

def setup(baseline,payload,output,reference=False,identity=None):
    identity=identity or json.loads((output/'build/build.json').read_text())['identity']
    assert identity in ['NAMLNK25','NAMLNK26','NAMLNK27','NAMLNK28','NAMLNK29','NAMLNK30']
    schema={'NAMLNK25':1,'NAMLNK26':2,'NAMLNK27':3,'NAMLNK28':4,'NAMLNK29':5,'NAMLNK30':5}[identity]
    # Identity allowlists only; no weakened state/transport/write assertions.
    path=output/'harness'/str(os.getpid());path.mkdir(parents=True,exist_ok=True)
    original=(baseline/'generated/research/test_preset_runtime.py').read_text()
    changed=original.replace("'NAMLNK24',",f"'NAMLNK24','{identity}',")
    assert changed.count(f"'{identity}'")==3
    if identity in ['NAMLNK28','NAMLNK29','NAMLNK30']:
        with (output/'build/loop-startup-test.elf').open('rb') as f:
            entries=ELFFile(f).get_section_by_name('.symtab').iter_symbols()
            scratch=[(x['st_value'],x['st_value']+x['st_size']) for x in entries if x.name in ['_ZN12_GLOBAL__N_11aE','_ZN12_GLOBAL__N_11bE']]
        assert len(scratch)==2 and all(hi-lo==256 and 0x20318020<=lo<hi<=0x20319fe0 for lo,hi in scratch)
        old='n in (4,256) and v.state_start<=r0 and r0+n<=v.state_end'
        assert changed.count(old)==1
        changed=changed.replace(old,f'n in (4,256) and ((v.state_start<=r0 and r0+n<=v.state_end) or any(lo<=r0 and r0+n<=hi for lo,hi in {scratch!r}))')
    (path/'test_preset_runtime.py').write_text(changed)
    chain=(baseline/'generated/research/test_link_stock_chain.py').read_text()
    assert chain.count('  self.u.mem_map(0x20240000,0x80000)')==1
    chain=chain.replace('  self.u.mem_map(0x20240000,0x80000)', '  if not getattr(self,"loop_first_mapped",False):self.u.mem_map(0x20240000,0x80000)')
    (path/'test_link_stock_chain.py').write_text(chain)
    sys.path[:0]=[str(path),str(baseline/'generated/research'),str(baseline/'generated/tools')]
    from test_usb_nam import UsbMachine,v,preset_fixture,input_block,model_slot
    from image import build
    from preset_image import build as original_build
    base=baseline/'build/nam-link-offline.elf';overlay=output/'build/loop-startup-test.elf'
    v.configure(payload,True,candidate_bundle=original_build(payload.read_bytes(),base) if reference else build(payload.read_bytes(),base,overlay,identity));v.elf_path=base
    with overlay.open('rb') as f:
        e=ELFFile(f);symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols() if s.name}
        functions=[(s['st_value']&~1,s['st_size']) for s in e.get_section_by_name('.symtab').iter_symbols() if s['st_info']['type']=='STT_FUNC']
    class Machine(UsbMachine):
        def cycle_read(self,u,access,address,size,value,user):
            assert address==0xe0001004, 'Timer fixture dispatched outside DWT'
            return super().cycle_read(u,access,address,size,value,user)
        def __init__(self,*args,**kwargs):
            self.loop_boot_count=0;self.loop_boot_events=[];self.inject=None
            super().__init__(*args,**kwargs)
            if reference:return
            self.flexspi_resets=0
            if identity in ['NAMLNK29','NAMLNK30']:
                # Peripheral self-clearing SWRESET bit; timing is not modeled.
                def reset(u,kind,address,size,value,unused):
                    if u.mem_read(address,1)[0]&1:
                        self.flexspi_resets+=1;u.mem_write(address,bytes(4))
                self.u.hook_add(UC_HOOK_MEM_READ,reset,begin=0x400cc000,end=0x400cc003)
            decoder=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);decoder.skipdata=True
            for address,length in functions:
                for ins in decoder.disasm(bytes(self.u.mem_read(address,length)),address):
                    if ins.mnemonic in ('mrs','msr') and 'primask' in ins.op_str or ins.mnemonic in ('cpsid','cpsie'):
                        self.mclass_ops[ins.address]=(ins.mnemonic,ins.op_str,ins.size)
                        self.u.hook_add(UC_HOOK_CODE,self.code,begin=ins.address,end=ins.address)
        def boot(self,*args,**kwargs):
            if not reference:
                if not getattr(self,'loop_first_mapped',False):
                    self.u.mem_map(0x20240000,0x80000);self.loop_first_mapped=True
                self.u.mem_protect(0x20314000,0x4000,UC_PROT_ALL)
            super().boot(*args,**kwargs)
            if not reference:
                self.loop_boot_count+=1
                assert self.diag()[:7]==[0x4c4f5031,schema,2,0,0,371316,2],self.diag()
                assert self.loop_state(3)==0
        def code(self,u,pc,n,user):
            if not reference and self.phase=='boot':
                if pc in [symbols['mpp_loop_boot']&~1,0x9194]:self.loop_boot_events.append(hex(pc))
                if pc==0x9194:assert self.diag()[2]==2,'Audio setup preceded loop startup'
            return super().code(u,pc,n,user)
        def arm_loop(self,name,*args):
            self.call(symbols[name],list(args));return self.u.reg_read(v.R[0])
        def button(self):
            if identity=='NAMLNK25':return super().button()
            # Exact scanner and patched dispatcher; synthetic elapsed time is
            # only for gesture debounce, never evidence of physical deadlines.
            for down,count in [(False,40),(True,80),(False,80)]:
                for _ in range(count):
                    self.put(0x40c60000,0xffffffff & ~(128 if down else 0))
                    self.put(0x40c5c000,0xffffffff);self.put(0x40c68000,0xffffffff)
                    self.run(0x9dd4);self.run(0xa05e)
                    at=v.sym['mpp_link']+12;self.put(at,(self.get(at)+6)&0xffffffff)
                    self.arm_loop('mpp_loop_buttons_tick')
            self.service()
            return self.u.mem_read(self.get(0x20014970)+2,1)[0]
        def diag(self):return list(struct.unpack('<40I',self.u.mem_read(symbols['mpp_loop_diag'],160)))
        def loop_state(self,key):return self.arm_loop('mpp_loop_state',key)
        def loop_request(self,op=0,arg=0,channel=0,nonce=73):
            message=bytes([240,67,88,112,4,2,78,79,1,op,arg,nonce&127,nonce>>7,247])
            rows=self.ingress([message],channel);assert len(rows)==1 and rows[0][1]==channel,rows
            reply=rows[0][0];assert len(reply)==55 and reply[:9]==message[:9] and reply[9]==op|64 and reply[10:13]==message[10:13]
            values=[sum(reply[14+5*i+j]<<(7*j) for j in range(5)) for i in range(8)]
            return reply[13],values
        def loop_report(self,channel=0):
            values=[]
            for arg in range(5):
                error,words=self.loop_request(0,arg,channel);assert not error;values+=words
            return values
    return Machine,v,symbols,preset_fixture,input_block,model_slot
