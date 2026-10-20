#!/usr/bin/env python3
"""Compare public Plug Pro containers with nux-effects evidence. Files only.

Does not import nux-effects tools or any USB, HID, serial or audio package.
No hardware action is available. Format similarity is NOT loader equivalence.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

def sha(data):
    return hashlib.sha256(data).hexdigest()

def inspect(path):
    data = path.read_bytes()
    if not data.startswith(b'NUX DFU'):
        raise ValueError('Not a NUX container')
    candidates = []
    for offset in range(0, min(1024, len(data) - 12), 4):
        if data[offset:offset+4] == b'BINA':
            size, start = struct.unpack_from('<II', data, offset+4)
            if start > len(data) or size > len(data)-start or size % 540:
                raise ValueError('Invalid BINA bounds')
            candidates.append(data[start:start+size])
    if len(candidates) != 1:
        raise ValueError('Expected one BINA section')
    bina = candidates[0]
    records = [bina[i:i+540] for i in range(0, len(bina), 540)]
    if len(records) < 2 or records[0][2:4] != b'\x00\x01':
        raise ValueError('Missing setup record')
    setup = records[0][28:]
    product = bytes(x ^ 255 for x in setup[:8]).decode('ascii')
    version = bytes(x ^ 255 for x in setup[8:16]).decode('ascii')
    declared = struct.unpack_from('>I', setup, 24)[0]
    for index, record in enumerate(records[1:]):
        marker = 0xffffffff if index == len(records)-2 else index
        if record[2:4] != b'\x00\x04' or struct.unpack_from('>I', record, 12)[0] != marker:
            raise ValueError('Unexpected operation or page marker')
    payload = b''.join(r[28:] for r in records[1:])
    if declared != len(payload):
        raise ValueError('Declared length does not match pages')
    return dict(file=path.name, container_sha256=sha(data), product=product,
        version_field=version, record_size=540, record_header_size=28,
        page_size=512, data_records=len(records)-1,
        declared_bytes=declared, payload_sha256=sha(payload),
        first_vector_sp=hex(struct.unpack_from('<I', payload)[0]),
        first_vector_reset=hex(struct.unpack_from('<I', payload,4)[0]),
        absolute_flash_destination_encoded_in_examined_page_index=False,
        interpretation='Sequential indices are visible; actual device address calculation and erase bounds require the Plug Pro loader.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nux-effects', type=Path, required=True)
    parser.add_argument('--containers', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    references = ['DFU_PROTOCOL.md','docs/hardware/ROM_SDP_RECOVERY.md',
        'docs/hardware/NOR_PROGRAM_FIFO_DEFECT.md','docs/protocol/OPEN_RECOVERY_PROTOCOL.md',
        'firmware/bootloader/src/recovery_protocol.c','firmware/bootloader/src/boot_journal.c']
    source_hashes = {p:sha((args.nux_effects/p).read_bytes()) for p in references}
    # Assertions pin the claims to specific available evidence, not guessed hardware.
    dfu = (args.nux_effects/'DFU_PROTOCOL.md').read_text()
    defect = (args.nux_effects/'docs/hardware/NOR_PROGRAM_FIFO_DEFECT.md').read_text()
    rom = (args.nux_effects/'docs/hardware/ROM_SDP_RECOVERY.md').read_text()
    assert '0x60000 + running_offset' in dfu and '540-byte' in dfu
    assert '1fc9:0130' in rom and 'CH341A' in rom
    assert '2026-07-31' in defect and '2026-08-01' in defect
    report = {
        'mode':'OFFLINE_FILES_ONLY', 'source_commit':'28b7c3ab05a9e980530950c7c784b062ebf96cd3',
        'source_hashes':source_hashes, 'public_plug_pro_containers':[inspect(p) for p in args.containers],
        'shared_evidence':['9527:c157 is shared across products, so it cannot establish loader compatibility.',
            '540-byte records, 28-byte headers, 512-byte pages, setup op 1 and data op 4 are shared.',
            'The public Plug Pro files use PLUGXDFU, not Core Deluxe COREDLX.',
            'Sequential page indices do not reveal the target loader\'s hard-coded flash base or erase policy.'],
        'core_deluxe_specific':{'mcu':'RT1051','rom_usb_id':'1fc9:0130','xip_base':'0x60000000',
            'loader_program_offset':'0x60000','version_sector':'0x5e000','factory_copy_limit':'0x1e000',
            'evidence_basis':'Author reports disassembly of full private flash dump and physical tests.'},
        'plug_pro':{'mcu_working_identification':'RT1176','rt1170_rom_usb_id_from_NXP':'1fc9:013d',
            'xip_base_working_inference':'0x30000000','loader_program_offset_verified':False,
            'loader_survives_custom_application_verified':False,'sealed_rom_entry_verified':False},
        'new_receiver_design_use':['Bounded packets and arithmetic; explicit capabilities.',
            'Checksums, session/offset checks and idempotent retries.',
            'Separate staging bank; previous RAM bank survives rejected or interrupted transfers.',
            'No arbitrary-address writes, erase command, reboot command or hardware transport.'],
        'recovery_lessons':['nux-effects documents success acknowledgements despite corrupt programmed flash; readback is a separate requirement.',
            'Its later ROM-backed implementation passed bounded A/B tests; full-chip open recovery remains separately gated in that revision.',
            'Its deliberate ROM entry erases a boot region; that is not an acceptable read-only way to investigate this sealed Plug Pro.',
            'Trial-boot rollback is useful for our future bootloader but cannot be retroactively assumed in the unknown stock loader.'],
        'needed_for_sealed_usb_recovery_proof':['Plug Pro loader code or vendor statement proving protected boot region and erase bounds.',
            'Proof that blue-mode entry remains reachable before an invalid or non-starting app.',
            'A restoration path for this exact installed build; public app files alone do not contain that proof.'],
        'usb_recovery_proven':False,'custom_firmware_loadable':False,'device_access':False,'playback':False,
    }
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'status':'COMPARISON_COMPLETE_RECOVERY_UNPROVEN','containers':len(report['public_plug_pro_containers'])}))

if __name__ == '__main__':
    main()
