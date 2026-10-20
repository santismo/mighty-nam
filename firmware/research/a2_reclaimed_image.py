"""Compose exact-stock A2 candidate IN MEMORY ONLY. No image writer or USB."""
import hashlib
from pathlib import Path
from candidate_image import build_candidate,require
from a2_storage import audit,model_slot,SLOT_OFFSET,SLOT_SIZE

def build(stock,elf,model):
 storage=audit(stock);candidate,sym,plan=build_candidate(stock,Path(elf),profile='a2-reclaimed')
 out=bytearray(candidate);slot=model_slot(model);out[SLOT_OFFSET:SLOT_OFFSET+SLOT_SIZE]=slot
 require(len(out)==len(stock),'Payload length changed')
 require(out[0x2356c:SLOT_OFFSET]==stock[0x2356c:SLOT_OFFSET] and out[SLOT_OFFSET+SLOT_SIZE:]==stock[SLOT_OFFSET+SLOT_SIZE:],'Unplanned resource changes')
 plan.update(candidate_sha256=hashlib.sha256(out).hexdigest(),changed_byte_count=sum(a!=b for a,b in zip(stock,out)),model_storage=storage,model_slot_sha256=hashlib.sha256(slot).hexdigest(),model_source_sha256=hashlib.sha256(Path(model).read_bytes()).hexdigest(),original_bytes_above_occupied_low_image_preserved=False,only_high_image_change='Retired AMP12 8 KiB data slot',flash_source_in_vm='The complete candidate payload mapped read-only at inferred 0x30040000 before stock startup',no_ram_only_installation='Boot uses original redirected stock AMP initialization to CRC-check/read weights from the candidate resource image; no host model injection after boot')
 return bytes(out),sym,plan
