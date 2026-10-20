#!/usr/bin/env python3
"""Bounded static placement evidence from the exact saved V1.5.6 payload.
Reads files only. Pointer scans are evidence, not an exhaustive alias analysis.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from candidate_image import STOCK_SHA, require

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('payload', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
b = a.payload.read_bytes()
require(hashlib.sha256(b).hexdigest() == STOCK_SHA, 'Exact V1.5.6 payload required')
word = lambda off: struct.unpack_from('<I', b, off)[0]
state_start, state_end = 0x202e4000, 0x202e6000
refs = [{'offset': hex(i), 'value': hex(word(i))}
        for i in range(0, len(b)-3, 4) if state_start <= word(i) < state_end]
require(word(0x202fc) == 0x38000 and word(0x20300) == state_start,
        'Stock runtime zero-table entry changed')
require(not any(b[0x24000:0x28000]), 'Candidate code window no longer zero-filled')
require([int(r['offset'], 16) for r in refs] == [0x5470, 0x57a4, 0x20300],
        'Unexpected aligned state-window literals')
result = {
 'status': 'BOUNDED_STATIC_EVIDENCE_NOT_PHYSICAL_PLACEMENT_APPROVAL',
 'stock_sha256': STOCK_SHA,
 'code_window': {'start': '0x24000', 'end_exclusive': '0x28000',
                 'original_bytes_all_zero': True, 'loader_copies_window': None},
 'state_window': {'start': hex(state_start), 'end_exclusive': hex(state_end)},
 'stock_runtime_zero_entry': {'table_offset': '0x202fc', 'bytes': word(0x202fc),
                             'start': hex(word(0x20300)), 'end_exclusive': '0x2031c000'},
 'aligned_payload_words_into_state_window': refs,
 'nxp_reference_ram_bank': {
   'start': '0x202c0000', 'end_exclusive': '0x20340000',
   'source': 'https://raw.githubusercontent.com/nxp-mcuxpresso/legacy-mcux-sdk/main/devices/MIMXRT1176/gcc/MIMXRT1176xxxxx_cm7_ram.ld',
   'meaning': 'Reference linker memory bank, not proof of this unit configuration or memory ownership'},
 'traced_paths': [
   'Stock main e5f8 -> e4d2 -> tail 5778 AMP initialization; later 11984 SAI/DMA setup',
   'Stock main loop e68a -> 57c0 -> 56ea and 53e0 AMP control/background loading',
   '5308 -> 5488 memcpy writes at 202e4000; 5340 resets state at 2031b000',
   'Candidate redirects 5578 processing and 5778 initialization, returns immediately from 57c0'],
 'dynamic_cross_check': 'candidate-reboot-tests.json includes a real stock memcpy collision negative control',
 'limits': ['Aligned-word scan misses computed, unaligned, encoded and runtime-created pointers',
            'Traced paths do not prove all callers or interrupt/background ownership',
            'Only exact V1.5.6 is supported; installed 20220720 build differs',
            'No loader, MPU/cache, peripheral or physical RAM test'],
 'device_or_audio_access': False
}
a.output.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({'status': result['status'], 'aligned_references': len(refs)}))
