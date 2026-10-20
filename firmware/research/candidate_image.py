"""Construct a candidate application IN MEMORY for offline emulation only.
No CLI, image-file writer, NUX packager, updater or USB code is provided here.
The gap profile assumes the missing loader loads padding; the reclaimed profile
uses stock AMP code space. Neither proves physical loader acceptance or recovery.
"""
import hashlib,struct
from elftools.elf.elffile import ELFFile
STOCK_SHA='a8a064a5b0e308b9cf193ebdf23d352ddff092d88db71531729ca1864a86d990'
def require(ok,msg):
    if not ok:raise ValueError(msg)
def build_candidate(stock,elf_path,profile='gap'):
    require(hashlib.sha256(stock).hexdigest()==STOCK_SHA,'Exact V1.5.6 payload required')
    require(profile in ['gap','reclaimed','a2-reclaimed','a2-listening'],'Unknown placement profile')
    code_low,code_high=(0x24000,0x28000) if profile=='gap' else (0x1a0a4,0x1b488)
    if profile in ['reclaimed','a2-reclaimed','a2-listening']:
        from audit_reclaimed_code import audit
        audit(stock)
    audio_audit=None
    if profile=='a2-listening':
        from audit_retired_audio import audit as audit_audio
        audio_audit=audit_audio(stock)
    out=bytearray(stock);changes=[];regions=[];occupied=[]
    with elf_path.open('rb') as f:
        e=ELFFile(f);require(e['e_machine']=='EM_ARM' and e['e_type']=='ET_EXEC','Expected linked ARM ELF')
        syms=list(e.get_section_by_name('.symtab').iter_symbols())
        require(not [s.name for s in syms if s.name and s['st_shndx']=='SHN_UNDEF'],'Unresolved ELF symbols')
        symbols={s.name:s['st_value'] for s in syms}
        for s in e.iter_sections():
            if not s['sh_flags']&2 or not s['sh_size']:continue
            start,end=s['sh_addr'],s['sh_addr']+s['sh_size']
            regions.append({'name':s.name,'start':hex(start),'end_exclusive':hex(end),'bytes':s['sh_size']})
            if s['sh_type']=='SHT_NOBITS':
                require(0x202e4000<=start<end<=(0x2031c000 if profile in ['a2-reclaimed','a2-listening'] else 0x202e6000),'State outside retired-amp candidate window')
                continue
            require(code_low<=start<end<=code_high or
                (profile=='a2-listening' and s.name in ['.retired_audio','.ARM.exidx'] and 0x14c04<=start<end<=0x14f08),
                'Code/data outside selected candidate window')
            if profile=='gap':require(not any(stock[start:end]),'Candidate gap contains stock bytes')
            require(not any(start<y and end>x for x,y in occupied),'Overlapping allocated sections')
            occupied.append((start,end))
            out[start:end]=s.data()
        for name in ['mpp_stock_amp_process','mpp_stock_amp_init']:
            require(name in symbols and symbols[name]&1 and code_low<=symbols[name]<code_high,'Missing/invalid Thumb entry')
    def jump(symbol):return bytes.fromhex('dff800f0')+struct.pack('<I',symbols[symbol])
    for addr,expected,new,why in [
        (0x5578,'2de9fe4f80469246',jump('mpp_stock_amp_process'),'Redirect existing AMP callback; stock dispatch tables stay untouched'),
        (0x5778,'80b501200c490870',jump('mpp_stock_amp_init'),'Replace old AMP initialization with NAM reset before stock audio starts'),
        (0x57c0,'80b5',bytes.fromhex('7047'),'Retire old AMP background loader entry without changing main-loop callsite')]:
        old=bytes.fromhex(expected);require(stock[addr:addr+len(old)]==old,'Unexpected original patch-site bytes')
        require(len(old)==len(new),'Patch length changed')
        out[addr:addr+len(new)]=new
        changes.append({'offset':hex(addr),'original':old.hex(),'replacement':new.hex(),'reason':why})
    if profile=='a2-listening':
        addr=0x14bfc;old=bytes.fromhex('2de9fe4f05460e46')
        require(stock[addr:addr+8]==old,'Audio retirement entry mismatch')
        require(code_low<=symbols['mpp_probe_audio']<code_high and symbols['mpp_probe_audio']&1,'Invalid audio entry')
        new=jump('mpp_probe_audio');out[addr:addr+8]=new
        changes.append(dict(offset=hex(addr),original=old.hex(),replacement=new.hex(),
            reason='Redirect audio entry before reusing its audited retired body'))
    require(len(out)==len(stock),'Payload size changed')
    require(out[:0x400]==stock[:0x400],'Vector table changed')
    plan={'mode':'IN_MEMORY_CANDIDATE_FOR_OFFLINE_EMULATOR_ONLY','placement_profile':profile,'stock_sha256':STOCK_SHA,
        'candidate_sha256':hashlib.sha256(out).hexdigest(),'elf_sha256':hashlib.sha256(elf_path.read_bytes()).hexdigest(),
        'patches':changes,'elf_regions':regions,'original_vector_table_preserved':True,
        'payload_length_preserved':True,'changed_byte_count':sum(x!=y for x,y in zip(stock,out)),
        'device_loadable_proven':False,'loader_copy_extent_known':False,'flash_container_written':False,
        'requires_loading_original_zero_padding':profile=='gap',
        'original_bytes_above_occupied_low_image_preserved':out[0x2356c:]==stock[0x2356c:],
        'stock_dispatch_source_pointer_unchanged':'0x20000554 = 0x5579 after each stock runtime initialization',
        'no_ram_only_installation':'All redirections are application-byte edits in the VM input; reset repeats stock initialization and the redirected AMP init'}
    if audio_audit:plan['retired_audio_audit']=audio_audit
    return bytes(out),symbols,plan
