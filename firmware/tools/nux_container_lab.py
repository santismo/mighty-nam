#!/usr/bin/env python3
"""Offline NUX MP-3 package round-trip + HID framing audit. NO device I/O.
Only reads files and prints JSON. Does not create firmware or transmit anything.
The original per-record headers are preserved: their integrity semantics and
on-device destination are not established. This is NOT a firmware signer.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Container:
    def __init__(self, data):
        self.data = data
        need(len(data) >= 956 and data[:7] == b'NUX DFU', 'Not a NUX container')
        need(data[7] in (0, 2), 'Unexamined format variant')
        need(struct.unpack_from('<I', data, 8)[0] == len(data), 'Container length mismatch')
        need(data[20:276].split(b'\0')[0] == b'MIGHTY PLUG PRO DFU', 'Not the MP-3 product')
        tags = ('TEXT', 'BINA') if data[7] == 0 else ('TEXT', 'BINA', 'EXTR')
        self.sections = {}
        for i, tag in enumerate(tags):
            pos = 0x224 + 12*i
            need(data[pos:pos+4] == tag.encode(), 'Unexpected section directory')
            size, offset = struct.unpack_from('<II', data, pos+4)
            need(offset >= 956 and size > 0 and offset+size <= len(data), 'Section outside container')
            self.sections[tag] = {'offset': offset, 'size': size}
        ordered = sorted(self.sections.values(), key=lambda x: x['offset'])
        need(all(a['offset']+a['size'] <= b['offset'] for a,b in zip(ordered,ordered[1:])), 'Overlapping sections')
        section = self.sections['BINA']
        stream = data[section['offset']:section['offset']+section['size']]
        need(len(stream) >= 1080 and len(stream)%540 == 0, 'Invalid record stream')
        self.records = [stream[i:i+540] for i in range(0,len(stream),540)]
        setup = self.records[0]
        need(setup[2:4] == b'\0\1', 'Setup opcode missing')
        need(bytes(x^255 for x in setup[28:36]) == b'PLUGXDFU', 'Unexpected setup identity')
        self.version = bytes(x^255 for x in setup[36:44]).decode('ascii')
        self.payload = b''.join(r[28:] for r in self.records[1:])
        need(struct.unpack_from('>I',setup,52)[0] == len(self.payload), 'Payload size mismatch')
        for i,r in enumerate(self.records[1:]):
            need(r[2:4] == b'\0\4', 'Unexpected page opcode')
            expected = 0xffffffff if i == len(self.records)-2 else i
            need(struct.unpack_from('>I',r,12)[0] == expected, 'Page sequence mismatch')

    def rebuild_same_length(self, payload):
        """In-memory template reassembly, NOT validated custom-image packaging."""
        need(len(payload) == len(self.payload), 'Only original-length payloads supported')
        section = self.sections['BINA']
        stream = self.records[0] + b''.join(r[:28]+payload[i*512:(i+1)*512] for i,r in enumerate(self.records[1:]))
        return self.data[:section['offset']]+stream+self.data[section['offset']+section['size']:]

    def audit(self):
        rebuilt = self.rebuild_same_length(self.payload)
        need(rebuilt == self.data, 'Byte-for-byte container round-trip failed')
        digest = hashlib.sha256()
        # Host upload function splits each 540-byte record into nine 60-byte
        # chunks, each preceded by [0x01, fragment_index, 0, 0].
        # This verifies framing only, not acknowledgments, retries or writes.
        for record in self.records:
            packets = [bytes((1,i,0,0))+record[i*60:(i+1)*60] for i in range(9)]
            need(all(len(p)==64 for p in packets), 'HID report size mismatch')
            need(b''.join(p[4:] for p in packets)==record, 'HID reassembly failed')
            for packet in packets:
                digest.update(packet)
        return {
            'mode':'OFFLINE_ONLY_NO_USB', 'format_byte':self.data[7],
            'container_sha256':sha(self.data), 'payload_sha256':sha(self.payload),
            'sections':self.sections, 'setup_version':self.version,
            'payload_bytes':len(self.payload), 'records':len(self.records),
            'host_hid_reports':len(self.records)*9,
            'host_report_stream_sha256':digest.hexdigest(),
            'byte_exact_container_roundtrip':True, 'all_host_fragments_reassemble':True,
            'usb_transmitted':False, 'custom_image_acceptance_proven':False,
            'bootloader_destination_proven':False, 'recovery_after_bad_application_proven':False,
            'restore_candidate':'Original stock package, conditional on intact/reachable blue-mode loader',
            'not_established':['Meaning of all opaque header fields', 'Loader write/erase boundaries',
                'Signature/checksum policy on modified payload', 'Loader entry independent of application',
                'Reset pin wiring and physical ROM recovery access']
        }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('firmware',type=Path,nargs='+')
    args=p.parse_args()
    try:
        print(json.dumps({str(path):Container(path.read_bytes()).audit() for path in args.firmware},indent=2))
    except (OSError, ValueError, UnicodeError, struct.error) as error:
        p.exit(1,f'Audit failed: {error}\n')

if __name__=='__main__':
    main()
