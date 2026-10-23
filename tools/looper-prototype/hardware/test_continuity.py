"""Actual compiled preset/IRQ paths with cooperative preemption; OFFLINE ONLY.

Suspends foreground ARM at instruction boundaries, runs the real software IRQ
on a lower stack, restores registers, then resumes. This is NOT M7 cycle timing
or hardware exception/cache/FlexSPI emulation. No device/audio access.
"""
import argparse,ctypes,hashlib,json,struct,sys,zlib
from pathlib import Path
from collections import Counter
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_PROT_ALL
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR
p=argparse.ArgumentParser(description=__doc__)
for n in ['baseline','payload','fixtures','output']:p.add_argument(n,type=Path)
a=p.parse_args()
from harness import setup
Base,v,symbols,preset_fixture,input_block,model_slot=setup(a.baseline,a.payload,a.output)
baseline=a.baseline/'build/nam-link-offline.elf';overlay=a.output/'build/loop-startup-test.elf'
functions=[]
for file in [baseline,overlay]:
    with file.open('rb') as f:
        e=ELFFile(f)
        functions += [(s.name,s['st_value']&~1,(s['st_value']&~1)+s['st_size']) for s in e.get_section_by_name('.symtab').iter_symbols() if s['st_info']['type']=='STT_FUNC']
class Machine(Base):
    def __init__(self):
        self.preempt=False;self.in_irq=False;self.due=False;self.instructions=0;self.period=11003;self.irq_phases=Counter();self.masked=0
        self.interleaved=0;self.masked_sites=Counter();self.masked_run=0;self.masked_max=0;super().__init__()
    def schedule(self,u,pc,n,user):
        if not self.preempt or self.in_irq:return
        self.instructions+=1
        if self.primask:
            self.masked+=1;self.masked_run+=1;self.masked_max=max(self.masked_max,self.masked_run)
            self.masked_sites[hex(pc)]+=1
        else:self.masked_run=0
        if self.instructions%self.period==0 and not self.primask:
            self.due=True;u.emu_stop()
    def run(self,pc,end=v.STOP,limit=6000000):
        if not self.preempt or self.in_irq:return super().run(pc,end,limit)
        self.last_pc=None;self.u.reg_write(UC_ARM_REG_SP,v.SP);self.u.reg_write(UC_ARM_REG_LR,v.STOP|1)
        start=pc|1;remaining=max(limit,40000000);before=self.instructions
        while True:
            self.due=False;hook=self.u.hook_add(UC_HOOK_CODE,self.schedule)
            try:self.u.emu_start(start,end,count=remaining)
            finally:self.u.hook_del(hook)
            where=self.u.reg_read(UC_ARM_REG_PC)
            if not self.due:
                assert where==end,('foreground instruction budget',hex(where));return
            assert self.instructions-before<remaining,'preemption budget exhausted'
            context=self.u.context_save();sp=self.u.reg_read(UC_ARM_REG_SP);old_sp=v.SP
            # Model exception separation explicitly. Never reset IRQ SP to the
            # foreground frame base: that would overwrite the suspended call.
            assert 0x20030000<sp<=old_sp
            stack=bytes(self.u.mem_read(sp,old_sp-sp));mask=self.primask
            label=next((name for name,lo,hi in functions if lo<=where<hi),hex(where));self.irq_phases[label]+=1
            self.in_irq=True;v.SP=sp-256
            try:process_loop();self.interleaved+=1
            finally:v.SP=old_sp;self.in_irq=False
            assert bytes(self.u.mem_read(sp,old_sp-sp))==stack,'IRQ overwrote foreground stack'
            assert self.primask==mask==0
            self.u.context_restore(context);self.last_pc=None;start=where|1
m=Machine();m.service();m.initialize_usb();models=sorted((a.fixtures/'models').glob('*-lite.nam'));assert len(models)==3
saved=[]
for color,model in enumerate(models):
    slot=model_slot(model);m.upload(slot,900+color)
    data=bytearray(preset_fixture([8] if color else [],{8:4}));data[84]=37;data[70:74]=bytes([20,20,50,0]);m.u.mem_write(m.preset,bytes(data))
    body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(data),1,8)+hashlib.sha256(slot).digest()+f'Loop test {color}'.encode().ljust(64,b'\0')
    assert m.bank_request(2,color,body,nonce=950+color)[7]==0;saved.append((slot,bytes(data),body))
m.arm()
for i in range(1320):m.process(i,input_block(i))
print('Seeded three emulated public presets; NAM + spring warmed',flush=True)
first,n,second,other=0x202a0020,270336,0x2031c020,100980
guarded=[(first,n),(second,other),(0x20314020,0x3fc0),(0x20318020,0x1fc0)]
def access(u,kind,addr,size,val,user):
    assert 0x20314020<=u.reg_read(UC_ARM_REG_PC)<0x20318000,('Foreign owner in loop RAM',hex(u.reg_read(UC_ARM_REG_PC)),hex(addr))
for lo,size in guarded:m.u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,access,begin=lo,end=lo+size-1)
def arm(name,*args):
    if name=='mpp_loop_fixture':
        obj=m.get(symbols['_ZN12_GLOBAL__N_15audioE']);controls=m.get(symbols['_ZN12_GLOBAL__N_18controlsE'])
        assert m.loop_state(7)==720
        m.put(obj+20,args[0]);m.put(controls+12,args[0]*2);m.u.mem_write(controls,bytes([0,3]))
        m.u.mem_write(symbols['_ZN12_GLOBAL__N_17touchedE'],b'\1')
        m.u.mem_write(symbols['_ZN12_GLOBAL__N_114headphone_gainE'],bytes(m.u.mem_read(0x200006f8,4)))
        return
    if name=='mpp_loop_fixture_block':
        obj=m.get(symbols['_ZN12_GLOBAL__N_15audioE'])
        m.put(obj+24,args[0]);m.u.mem_write(obj+36,bytes(8));m.put(obj+56,0);m.u.mem_write(obj+316,bytes(256));return
    if name=='mpp_loop_command':
        assert m.loop_request(1,[1,2,3,4][args[0]])[0]==0
        m.arm_loop('mpp_loop_before_tick');return
    return m.arm_loop(name,*args)
def state(key):return arm('mpp_loop_state',key)
def guards():
    expected=struct.pack('<8I',*[0x6c705200+i for i in range(8)])
    for lo,size in guarded:
        assert m.u.mem_read(lo-32,32)==expected and m.u.mem_read(lo+size,32)==expected,(hex(lo),'guard damaged')
    assert m.diag()[3]==0,m.diag()
    m.guards()
fixture=(a.fixtures/'record24.blocks').read_bytes();assert len(fixture)==n+other
m.u.mem_write(first,fixture[:n]);m.u.mem_write(second,fixture[n:]);arm('mpp_loop_fixture',720000)
native=ctypes.CDLL(str((a.output/'loop-native.dylib').resolve()));U=ctypes.c_uint;P=ctypes.c_void_p;F=ctypes.c_float
for name,args in [('lp_init',[P,U,U,U]),('lp_command',[U]),('lp_fixture_play',[U]),('lp_fixture_block',[U]),('lp_state',[U]),('lp_process8',[P,P,P,U])]:
    fn=getattr(native,name);fn.argtypes=args;fn.restype=U if name=='lp_state' else None
host=(ctypes.c_uint8*len(fixture)).from_buffer_copy(fixture);native.lp_init(host,len(fixture),24000,720000);native.lp_fixture_play(720000)
counter=0;parity_error=0.;paused_irqs=0;nonzero_paused_irqs=0;pcm_peak=0;guitar_active_irqs=0;pcm_error=0;pcm_checked=0
zero=(F*8)();expected=(F*16)()
def process_loop():
    global counter,parity_error,paused_irqs,nonzero_paused_irqs,pcm_peak,guitar_active_irqs,pcm_error,pcm_checked
    # IRQ doesn't invoke foreground stock effect-load service while suspended.
    # Live processing resumes only after the complete foreground recall returns.
    index=counter;counter+=1;half=index%2;rx=0x20019000+128*half;tx=0x20019100+128*half
    untouched=0x20019100+128*(1-half);before=bytes(m.u.mem_read(untouched,128))
    xs=input_block(index);m.u.mem_write(rx,struct.pack('<32i',*[q for x in xs for q in [0,0,0,int(x*2**31)]]))
    m.u.mem_write(tx,b'\x7f'*128)
    running=m.words()[9];warm=m.get(v.sym['mpp_listen_warm'])
    gain=struct.unpack('<f',m.u.mem_read(symbols['_ZN12_GLOBAL__N_114headphone_gainE'],4))[0]
    settings=m.get(0x20014970);volume=m.u.mem_read(settings+0x16,1)[0];volume=50 if volume>100 else volume
    muted=m.u.mem_read(settings+0x10,1)[0]
    level=struct.unpack('<f',m.u.mem_read(0x200006f8+4*(4+volume),4))[0]
    master=struct.unpack('<f',m.u.mem_read(0x200006f8+4*105,4))[0]
    target=0 if muted else F(level*master).value
    m.call(0xe19c,[rx,tx])
    assert bytes(m.u.mem_read(untouched,128))==before,'Other DMA half overwritten'
    native.lp_process8(zero,zero,expected,0)
    bus=m.read(symbols['_ZN12_GLOBAL__N_13busE']);error=max(abs(x-y) for x,y in zip(bus,expected[:8]));parity_error=max(parity_error,error)
    assert error<2e-6,('loop discontinuity',index,error)
    words=struct.unpack('<32i',m.u.mem_read(tx,128));assert words[0::4]==words[2::4] and words[1::4]==words[3::4]
    assert max(map(abs,words))<=int(float.fromhex('0x1.cp30'));pcm_peak=max(pcm_peak,max(map(abs,words)))
    if not running:
        smoothing=F(.999).value;step=F(target*F(1-smoothing).value).value
        for j in range(8):
            gain=F(step+F(gain*smoothing).value).value
            wanted=int(F(F(bus[j]*gain).value*2**28).value)
            error=max(abs(words[4*j+k]-wanted) for k in range(4));pcm_error=max(pcm_error,error)
            assert error<=2,('Loop PCM publication mismatch while guitar paused',index,j,error)
        pcm_checked+=1
    if not running or warm:
        paused_irqs+=1
        if max(map(abs,bus))>1e-4:
            assert any(words),'Loop was silenced during preset loading/settling';nonzero_paused_irqs+=1
    else:guitar_active_irqs+=1
    assert m.words()[4]==0
    guards()
def check_store():
    assert bytes(m.u.mem_read(first,n))+bytes(m.u.mem_read(second,other))==fixture
    assert state(1)==native.lp_state(1) and state(2)==native.lp_state(5) and not state(8)
for _ in range(80):process_loop()
queued=bytes(m.u.mem_read(0x20019100,256));position=state(2)
arm('mpp_loop_bank_pause')
assert bytes(m.u.mem_read(0x20019100,256))==queued and state(2)==position
m.call(v.sym['mpp_bank_resume'],[1])
recalls=[];flash_before=len(m.flash_operations)
for index,color in enumerate([0,1,2,0]):
    m.period=[11003,17011,7001,13007][index];before=m.interleaved;masked=m.masked
    m.preempt=True
    try:
        assert m.bank_request(3,color,nonce=1000+index)[7]==0;m.service()
    finally:m.preempt=False
    assert m.interleaved>before,('No IRQ interleaving',m.interleaved,before)
    assert m.masked==masked,('Masked recall instructions',m.masked-masked,dict(m.masked_sites))
    assert m.words()[5]==zlib.crc32(saved[color][0]);assert bytes(m.u.mem_read(m.preset,128))==saved[color][1]
    for _ in range(1320):process_loop();m.run(0x666a,limit=3000000)
    check_store();recalls.append(dict(color=color,interleaved_irqs=m.interleaved-before,IRQs_masked=False))
    print('Preset recall',color,'with',m.interleaved-before,'interleaved real IRQs PASS',flush=True)
# Physical-button handler queues a recall; deferred service is also preemptible.
m.preempt=True;before=m.interleaved
try:selected=m.button()
finally:m.preempt=False
assert selected==1 and m.interleaved>before
for _ in range(1320):process_loop();m.run(0x666a,limit=3000000)
check_store();print('Stock preset-button path preserves loop PASS',flush=True)
# A real save request would need erase/program. The research backend must
# reject it, while still allowing IRQs through its preceding validation/read.
body=saved[1][2][:48]+b'Changed name forces write'.ljust(64,b'\0')
before_save_masked=m.masked
m.preempt=True
try:rejected_save=m.bank_request(2,1,body,nonce=1199)
finally:m.preempt=False
assert rejected_save[7]!=0 and state(6)>0
save_masked=m.masked-before_save_masked
assert 0<save_masked<=32 and m.masked==save_masked
assert len(m.flash_operations)==flash_before
for _ in range(32):process_loop()
# Cross the noncontiguous storage boundary and final partial-block wrap.
for position in [524032,719872]:
    arm('mpp_loop_fixture_block',position);native.lp_fixture_block(position)
    for _ in range(180):process_loop()
    check_store()
# Failed/empty recall and flash writes must not damage or stall the loop.
m.preempt=True
try:empty=m.bank_request(3,6,nonce=1200)
finally:m.preempt=False
assert empty[7]!=0
for _ in range(32):process_loop()
assert not arm('mpp_loop_read',0,0x303a6000,0x20030000,16)
assert not arm('mpp_loop_no_erase',0,0x30384000)
assert not arm('mpp_loop_no_program',0,0x30384000,0x20030000,256)
assert len(m.flash_operations)==flash_before;check_store()
assert m.irq_phases['mpp_loop_read']>0 and paused_irqs>0 and nonzero_paused_irqs>0
assert any('crc' in name.lower() for name in m.irq_phases),m.irq_phases
report=dict(status='PASS_OFFLINE_STARTUP_PRESET_LOOP',candidate_payload_sha256=v.plan['candidate_sha256'],startup_copy_used=True,baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
    overlay_sha256=hashlib.sha256(overlay.read_bytes()).hexdigest(),store_sha256=hashlib.sha256(fixture).hexdigest(),
    storage_bytes=n+other,recorded_samples=720000,recorded_rate=24000,live_rate=48000,callback_frames=8,
    callbacks=counter,interleaved_IRQs=m.interleaved,interrupt_phases=dict(m.irq_phases),masked_foreground_instructions=m.masked,
    recalls=recalls,recall_masked_instructions=0,rejected_save_masked_instructions=save_masked,stock_preset_button_selected=selected,paused_guitar_irqs=paused_irqs,nonzero_loop_paused_irqs=nonzero_paused_irqs,
    guitar_active_irqs=guitar_active_irqs,max_native_loop_sample_error=parity_error,peak_output_PCM=pcm_peak,
    paused_guitar_DMA_blocks_checked=pcm_checked,max_paused_guitar_PCM_error=pcm_error,
    AHB_read_calls=state(4),AHB_read_bytes=state(5),blocked_flash_writes=state(6),loop_state_bytes=state(7),
    guards_intact=True,recording_unchanged=True,flash_mutations_after_overlay=0,device_access=False,audio_device_opened=False,
    pause_preserves_queued_DMA=True,real_preset_save_rejected=True,
    limitations=['Cooperative instruction-boundary preemption, not Cortex-M7 exception/bus/deadline emulation.',
    'Hardware OCRAM ownership, MPU/cache permissions, AHB stalls and physical performance remain unproven.',
    'Flash writes rejected while a loop exists; normal idle saving supported. No overdub or power persistence.',
    'Real startup copy is installed; physical looper button mapping is not installed.'])
# Exercise real hook recording, not just a preloaded playback fixture. Feed
# the native oracle exactly the previous raw/post-FX block cached by the hook.
assert m.bank_request(3,0,nonce=1300)[7]==0
for _ in range(1320):process_loop();m.run(0x666a,limit=3000000)
arm('mpp_loop_init');native.lp_init(host,len(fixture),24000,720000)
arm('mpp_loop_command',0);native.lp_command(0)
for i in range(120):
    raw=(F*8)(*m.read(symbols['_ZN12_GLOBAL__N_112recorded_rawE']))
    guitar=(F*8)(*m.read(symbols['_ZN12_GLOBAL__N_115recorded_guitarE']))
    ready=m.u.mem_read(symbols['_ZN12_GLOBAL__N_112guitar_readyE'],1)[0]
    native.lp_process8(raw,guitar,expected,ready)
    half=i%2;rx=0x20019000+128*half;tx=0x20019100+128*half
    xs=[0.]*8 if i<16 else input_block(i)
    m.u.mem_write(rx,struct.pack('<32i',*[q for x in xs for q in [0,0,0,int(x*2**31)]]))
    m.call(0xe19c,[rx,tx]);m.run(0x666a,limit=3000000)
    assert state(0)==native.lp_state(0) and not state(8);guards()
assert state(0)>256 and state(3)==2
assert bytes(m.u.mem_read(first,n))+bytes(m.u.mem_read(second,other))==bytes(host)
recorded_samples=state(0);arm('mpp_loop_command',1);native.lp_command(1)
assert state(3)==3
for _ in range(80):process_loop()
assert state(1)==native.lp_state(1) and state(2)==native.lp_state(5)
assert bytes(m.u.mem_read(first,n))+bytes(m.u.mem_read(second,other))==bytes(host)
report['actual_recording_hook']=dict(callbacks=120,recorded_samples=recorded_samples,encoded_bytes_match_native=True,
    threshold_waiting_callbacks=16,closed_loop_playback_callbacks=80,guards_intact=True)
# Stop rewinds immediately even though inactive loops skip audio DSP. Resuming
# must start at the beginning, not at the old paused cursor.
arm('mpp_loop_command',3);native.lp_command(3);native.lp_process8(zero,zero,expected,0)
assert state(3)==5 and state(1)==0
native.lp_command(2);native.lp_command(1);arm('mpp_loop_command',1)
for _ in range(10):process_loop()
assert state(1)==40
# Clear is refused while playing; it is explicit and permitted after stopping.
assert m.loop_request(1,5)[0]==0;m.arm_loop('mpp_loop_before_tick');assert m.diag()[14]==2 and state(0)==recorded_samples
arm('mpp_loop_command',3);assert m.loop_request(1,5)[0]==0;m.arm_loop('mpp_loop_before_tick')
assert m.diag()[14]==0 and state(0)==state(3)==0
report['stop_resume_clear_controls']=True
report['timing_buckets_exercised']={'recording':m.diag()[23], 'playing':m.diag()[24], 'inactive':m.diag()[25]}
assert all(report['timing_buckets_exercised'].values())
from preset_image import build
try:build(a.payload.read_bytes(),overlay)
except (TypeError,ValueError,KeyError):report['normal_image_builder_rejects_overlay']=True
else:raise AssertionError('Diagnostic ELF unexpectedly accepted by ordinary image builder')
(a.output/'continuity-test.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
