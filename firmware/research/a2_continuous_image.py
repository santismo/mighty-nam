"""Compose the silent A2 screen in emulator memory; no uploader or file writer."""
import hashlib,struct
from a2_reclaimed_image import build as build_a2
from candidate_image import require

def build(stock,elf,model):
 candidate,symbols,plan=build_a2(stock,elf,model);out=bytearray(candidate)
 def jump(name):
  target=symbols[name];require(target&1 and 0x1a0a4<=target<0x1b488,'Bad Thumb continuous entry')
  return bytes.fromhex('dff800f0')+struct.pack('<I',target)
 for addr,expected,new,reason in [
  (0x14bfc,bytes.fromhex('2de9fe4f05460e46'),jump('mpp_probe_audio'),'Silent callback with bounded continuous A2 processing'),
  (0xac8a,bytes.fromhex('38b58cb014462d216846'),bytes.fromhex('00bf')+jump('mpp_probe_version'),'Identify continuous through standard query'),
  (0x1f397,struct.pack('<I',0xa1d3),struct.pack('<I',symbols['mpp_probe_query']),'Fixed read-only continuous status pages')]:
  require(stock[addr:addr+len(expected)]==expected and len(new)==len(expected),'Patch bytes changed')
  out[addr:addr+len(new)]=new;plan['patches'].append(dict(offset=hex(addr),original=expected.hex(),replacement=new.hex(),reason=reason))
 start=symbols['mpp_probe_identity'];require(out[start:start+8]==b'NAMA2C01','Wrong continuous identity')
 require(out[:0x400]==stock[:0x400],'Vectors modified')
 plan.update(mode='SILENT_CONTINUOUS_A2_IN_MEMORY_ONLY',candidate_sha256=hashlib.sha256(out).hexdigest(),
  changed_byte_count=sum(a!=b for a,b in zip(stock,out)),nam_included=True,standard_version_marker='NAMA2C01',
  batches=60000,frames_per_batch=8,batch_spacing_callbacks=1,minimum_initial_callbacks=6000,
  output_samples_zero=True,model_output_sent_to_dma=False,timing_source='Read-only DWT model spans and stock GPT1 start/stop body spans',
  timing_is_calibrated=False,deadline_or_underrun_proof=False,physical_device_access=False)
 return bytes(out),symbols,plan
