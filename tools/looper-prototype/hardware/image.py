"""Compose the exact NAMLNK25 diagnostic image in memory. No updater I/O."""
import copy, hashlib, struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from build_test import BASELINE_SHA

FLASH=0x30040000
sha=lambda b:hashlib.sha256(b).hexdigest()

def build(stock, baseline, overlay, identity='NAMLNK25'):
    if identity not in ['NAMLNK25','NAMLNK26','NAMLNK27','NAMLNK28','NAMLNK29']:raise ValueError('Unsupported looper identity')
    from preset_image import build as base_build
    if sha(baseline.read_bytes())!=BASELINE_SHA:raise ValueError('Unsupported baseline')
    original,base,plan=base_build(stock,baseline)
    out=bytearray(original); plan=copy.deepcopy(plan); symbols=dict(base)
    with overlay.open('rb') as f:
        e=ELFFile(f); entries=list(e.get_section_by_name('.symtab').iter_symbols())
        new={s.name:s['st_value'] for s in entries if s.name}
        assert not [s.name for s in entries if s.name and s['st_shndx']=='SHN_UNDEF']
        rows=[];allowed=[]
        for s in e.iter_sections():
            if not s['sh_flags']&2 or not s['sh_size']:continue
            lo=s['sh_addr'];hi=lo+s['sh_size'];name=s.name
            if name=='.loop_startup':assert 0x1d760<=lo<hi<=0x1d830;at=lo
            elif name=='.text':assert lo==0x20314020 and hi<=0x20317fe0;at=0x303a0000-FLASH
            elif name=='.bss':assert lo==0x20318020 and hi<=0x20319fe0 and s['sh_type']=='SHT_NOBITS';at=None
            else:raise ValueError('Unexpected diagnostic section '+name)
            if at is not None:
                assert all(not(max(at,int(r.get('load_address',r['start']),16)-(FLASH if 'load_address' in r else 0))<
                    min(at+s['sh_size'],int(r.get('load_address',r['start']),16)-(FLASH if 'load_address' in r else 0)+r['bytes']))
                    for r in plan['elf_regions'] if r['name']!='.bss'),'Section overlap'
                out[at:at+s['sh_size']]=s.data();allowed.append((at,at+s['sh_size']))
            row=dict(name=name,start=hex(lo),end_exclusive=hex(hi),bytes=s['sh_size'])
            if name=='.text':row['load_address']='0x303a0000';row['name']='.looptext'
            rows.append(row)
    assert set(r['name'] for r in rows)=={'.loop_startup','.looptext','.bss'}
    assert new['__loop_code_load']==0x303a0000
    patches=[]
    def patch(at,data,reason):
        before=bytes(out[at:at+len(data)]);out[at:at+len(data)]=data;allowed.append((at,at+len(data)))
        patches.append(dict(offset=hex(at),original=before.hex(),replacement=data.hex(),reason=reason))
    def jump(at,name):
        target=new[name];assert target&1
        patch(at,(b'\x00\xbf' if at%4 else b'')+bytes.fromhex('dff800f0')+struct.pack('<I',target),name)
    for at,name in [(0x581a,'mpp_loop_startup'),(0xe19c,'mpp_loop_probe_audio'),(0x5868,'mpp_loop_service')]:jump(at,name)
    if identity in ['NAMLNK26','NAMLNK27','NAMLNK28','NAMLNK29']:
        for at,name in [(0xa05e,'mpp_loop_buttons'),(0x60ec,'mpp_loop_color')]:jump(at,name)
    patch(0x21243,struct.pack('<I',new['mpp_loop_query']),'Looper diagnostic command; standard commands delegate')
    patch(0x229b0,struct.pack('<I',new['mpp_loop_irq']),'Whole IRQ cycle observation')
    for old,target in [('_ZN12_GLOBAL__N_14readEPvjPhj','mpp_loop_read'),
        ('_ZN12_GLOBAL__N_15eraseEPvj','mpp_loop_erase'),('_ZN12_GLOBAL__N_17programEPvjPKhj','mpp_loop_program'),
        ('mpp_bank_pause','mpp_loop_bank_pause')]:
        address=base[old]&~1;assert 0x2030f000<=address<0x20314000
        jump(0x303a6000-FLASH+address-0x2030f000,target)
    if identity in ['NAMLNK28','NAMLNK29']:
        for prefix,target in [('_ZN3mpp8settings11BufferStore4load','mpp_loop_store_load'),('_ZN3mpp8settings11BufferStore4save','mpp_loop_store_buffer')]:
            names=[k for k in base if k.startswith(prefix)]
            assert len(names)==1,(prefix,names)
            address=base[names[0]]&~1
            assert 0x2030f000<=address<0x20314000
            jump(0x303a6000-FLASH+address-0x2030f000,target)
    identity_at=0x303a6000-FLASH+base['mpp_probe_identity']-0x2030f000
    assert out[identity_at:identity_at+8]==b'NAMLNK24';patch(identity_at,identity.encode(),'Diagnostic firmware identity')
    symbols.update({k:v for k,v in new.items() if k not in symbols or k.startswith(("mpp_loop_","__loop_"))})
    # The emulator's startup trace uses this name for the stock entry's target.
    symbols['mpp_stock_amp_init']=new['mpp_loop_startup']
    assert out[:0x400]==stock[:0x400] and out[0x22618:0x229ac]==stock[0x22618:0x229ac]
    assert out[0x344000:0x360000]==original[0x344000:0x360000]
    assert out[0x364000:0x366000]==original[0x364000:0x366000]
    assert len(out)==len(stock)
    assert all(any(a<=i<b for a,b in allowed) for i,(x,y) in enumerate(zip(original,out)) if x!=y)
    plan.update(identity=identity,mode='LOOPER_RAM_TIMING_TEST_ONLY',baseline_elf_sha256=BASELINE_SHA,
        elf_sha256=sha(overlay.read_bytes()),candidate_sha256=sha(out),elf_regions=plan['elf_regions']+rows,
        loop_patches=patches,loop_changed_spans=allowed,startup_copy_implemented=True,
        physical_button_looper_hooks=identity in ['NAMLNK26','NAMLNK27','NAMLNK28','NAMLNK29'],physical_RAM_safe_proven=False)
    return bytes(out),symbols,plan
