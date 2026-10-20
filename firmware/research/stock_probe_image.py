"""Compose a version-pinned diagnostic candidate in memory, never upload it."""
import hashlib,struct
from candidate_image import build_candidate,require

def build(stock,elf):
 candidate,symbols,plan=build_candidate(stock,elf,profile='reclaimed')
 out=bytearray(candidate)
 def jump(name):
  target=symbols[name];require(target&1 and 0x1a0a4<=target<0x1b488,'Invalid probe entry')
  return bytes.fromhex('dff800f0')+struct.pack('<I',target)
 for address,expected,replacement,reason in [
  (0x14bfc,bytes.fromhex('2de9fe4f05460e46'),jump('mpp_probe_audio'),'Replace whole audio callback with exact-buffer zero writer'),
  (0xac8a,bytes.fromhex('38b58cb014462d216846'),bytes.fromhex('00bf')+jump('mpp_probe_version'),'Aligned trampoline identifies probe through standard version query'),
  (0x1f397,struct.pack('<I',0xa1d3),struct.pack('<I',symbols['mpp_probe_query']),'Bind formerly default command 4 read-side handler')]:
  require(stock[address:address+len(expected)]==expected,'Unexpected diagnostic patch bytes')
  require(len(expected)==len(replacement),'Patch size changed')
  out[address:address+len(replacement)]=replacement
  plan['patches'].append({'offset':hex(address),'original':expected.hex(),'replacement':replacement.hex(),'reason':reason})
 plan['patches'][0]['reason']='Retire old AMP processing with zero output'
 plan['patches'][1]['reason']='Capture diagnostic state before stock audio setup'
 require(out[:0x400]==stock[:0x400],'Vectors changed')
 require(out[0x202a8:]==stock[0x202a8:],'Reset/runtime/resource bytes changed')
 # NAMPB001 did not export a separate identity symbol; preserve its metadata
 # when rebuilding the historical ELF for the physical-failure regression.
 identity='NAMPB001'
 if 'mpp_probe_identity' in symbols:
  start=symbols['mpp_probe_identity'];require(0x1a0a4<=start<=0x1b480,'Identity outside code window')
  identity=bytes(out[start:start+8]).decode('ascii')
  require(identity=='NAMPB002','Unknown probe identity')
 plan.update(mode='SILENT_STOCK_BRIDGE_IN_MEMORY_ONLY',candidate_sha256=hashlib.sha256(out).hexdigest(),
  changed_byte_count=sum(x!=y for x,y in zip(stock,out)),nam_included=False,
  standard_version_marker=identity,private_command=4,query_has_arbitrary_addresses=False,
  audio_callback_outputs_zero=True,initialization_snapshot_stage='Stock AMP initialization after SystemInit, before audio setup',
  actual_loader_entry_state_observed=False,stock_usb_startup_dependencies=True)
 return bytes(out),symbols,plan
