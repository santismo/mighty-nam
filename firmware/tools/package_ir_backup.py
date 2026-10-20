"""Validate a completed GET-only capture and save portable cabinet backups.
Does not contact the plug, import files, open audio streams or play WAVs.
"""
import argparse
import hashlib
import html
import json
import math
import re
import shutil
import struct
import zipfile
from pathlib import Path

def need(condition, message):
    if not condition:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def decode(data):
    need(len(data) % 3 == 0, 'Encoded length is not a multiple of three')
    result = bytearray()
    for i in range(0, len(data), 3):
        a, b, c = data[i:i+3]
        need(a <= 3 and b < 128 and c < 128, 'Invalid encoded word')
        result.extend(((a << 14) | (b << 7) | c).to_bytes(2, 'big'))
    return bytes(result)

def encode(data):
    need(len(data) % 2 == 0, 'Odd raw length')
    result = bytearray()
    for i in range(0,len(data),2):
        value = int.from_bytes(data[i:i+2], 'big')
        result.extend((value >> 14, (value >> 7) & 127, value & 127))
    return bytes(result)

def wav(data):
    # IEEE float, mono, 48 kHz. No rescaling/trimming/normalization.
    fmt = struct.pack('<HHIIHH',3,1,48000,192000,4,32)
    chunks = b'fmt '+struct.pack('<I',16)+fmt+b'fact'+struct.pack('<II',4,len(data)//4)+b'data'+struct.pack('<I',len(data))+data
    return b'RIFF'+struct.pack('<I',len(chunks)+4)+b'WAVE'+chunks

def package(capture, output):
    raw_capture = capture.read_bytes()
    rows = [json.loads(line) for line in raw_capture.splitlines() if line.strip()]
    need(rows[-1].get('status') == 'BACKUP_CAPTURE_COMPLETE','Capture did not finish')
    need(rows[-1]['audio_stream_opened'] is False and rows[-1]['flash_reset_or_set_sent'] is False,'Unexpected capture mode')
    messages = rows[:-1]
    need(len(messages) == rows[-1]['requests_sent'], 'Request count mismatch')
    catalogs = {p:{} for p in ['catalog','catalog_after']}
    chunks = {0:{},1:{}}
    settings = {p:{} for p in ['settings_before','settings_after']}
    versions = []
    for row in messages:
        need(row['matched'] is True,'Unmatched request')
        request, reply = [bytes.fromhex(row[k]) for k in ['request_hex','reply_hex']]
        kind, slot, offset, phase = [row[k] for k in ['kind','slot','offset','phase']]
        need(reply[:3] == b'\xf0\x43\x58' and reply[-1] == 247 and max(reply[1:-1]) < 128,'Bad response frame')
        if kind == 0:
            need(request == b'\xf0\x43\x58\0\xf7' and len(reply) == 45 and reply[36:44] == b'PLUGPRO\0','Bad identity')
            versions.append(reply[4:12].decode('ascii'))
            continue
        need(reply[3:6] == bytes([112,kind,2]),'Wrong response command/direction')
        if kind == 16:
            need(0 <= slot < 54 and 0 <= offset <= 2016 and offset % 32 == 0,'Out-of-range read')
            expected = b'\xf0\x43\x58\x70\x10\0'+encode(struct.pack('<HH',slot,offset))+b'\0\0\xf7'
            need(request == expected and len(reply) == 205,'Bad IR request/reply')
            body = decode(reply[6:-1])
            need(body[:4] == struct.pack('<HH',slot,offset) and len(body) == 132,'IR address mismatch')
            if phase == 'prime':
                need(slot == 53 and offset == 0,'Unexpected priming read')
            else:
                need(phase == 'ir' and row['pass'] in [0,1],'Unexpected IR phase')
                target = chunks[row['pass']]
                need((slot,offset) not in target,'Duplicate IR chunk')
                target[slot,offset] = body[4:]
        elif kind == 9:
            need(phase in catalogs and 0 <= slot < 54 and len(reply) == 62 and reply[6] == slot,'Bad metadata reply')
            need(request == bytes([240,67,88,112,9,2,slot,247]),'Bad metadata request')
            need(slot not in catalogs[phase],'Duplicate metadata')
            catalogs[phase][slot] = decode(reply[7:-1])
        else:
            need(phase in settings and kind in [11,12,20],'Unexpected command')
            expected = bytes([240,67,88,112,kind,2])+ (bytes([slot]) if kind == 11 else b'')+b'\xf7'
            need(request == expected,'Unexpected settings request')
            key = f'{kind:02x}-{slot}'
            need(key not in settings[phase],'Duplicate settings')
            settings[phase][key] = reply.hex()
    need(versions == ['20220720','20220720'],'Identity changed or missing')
    need(all(len(c)==3456 for c in chunks.values()),'Incomplete IR data')
    need(all(len(c)==54 for c in catalogs.values()),'Incomplete metadata')
    need(all(len(c)==9 for c in settings.values()),'Incomplete settings')
    need(chunks[0] == chunks[1], 'Second complete IR read differs')
    need(catalogs['catalog'] == catalogs['catalog_after'],'Metadata changed during backup')
    need(settings['settings_before'] == settings['settings_after'],'Preset/settings replies changed during backup')
    need(not output.exists(),'Output folder already exists; choose a new backup folder')
    output.mkdir(parents=True)
    (output/'raw').mkdir()
    (output/'wav').mkdir()
    (output/'usb-get-capture.jsonl').write_bytes(raw_capture)
    (output/'settings-sysex.json').write_text(json.dumps(settings['settings_before'],indent=2)+'\n')
    records = []
    for slot in range(54):
        data = b''.join(chunks[0][slot,offset] for offset in range(0,2048,32))
        metadata = catalogs['catalog'][slot]
        name = metadata[4:35].split(b'\0')[0].decode('ascii',errors='replace').strip()
        safe = re.sub(r'[^A-Za-z0-9_-]+','-',name).strip('-') or 'empty'
        filename = f'{slot:02d}-{safe}'
        raw_path = f'raw/{filename}.f32'
        (output/raw_path).write_bytes(data)
        (output/f'raw/{filename}.metadata').write_bytes(metadata)
        values = struct.unpack('<2048f',data)
        finite = all(math.isfinite(x) for x in values)
        # Names are descriptive, not proof of whether a slot contains an IR.
        wave_path = None
        if finite:
            wave_path = f'wav/{filename}.wav'
            wave = wav(data)
            need(wave[-8192:] == data and struct.unpack_from('<I',wave,4)[0]+8 == len(wave),'WAV container failure')
            (output/wave_path).write_bytes(wave)
        records.append(dict(slot_zero_based=slot,name=name,raw_file=raw_path,wav_file=wave_path,
            bytes=len(data),samples=2048,sha256=sha(data),metadata_hex=metadata.hex(),
            metadata_sha256=sha(metadata),all_samples_finite=finite,
            finite_peak=max(abs(x) for x in values) if finite else None,
            nonfinite_samples=sum(not math.isfinite(x) for x in values),
            all_bytes_ff=all(x==255 for x in data)))
    summary = dict(status='VERIFIED_TWO_PASS_CABINET_AND_SETTINGS_BACKUP',firmware_build='20220720',
        slots=54,samples_per_slot=2048,raw_bytes=54*8192,wav_files=sum(x['wav_file'] is not None for x in records),
        capture_requests=len(messages),capture_sha256=sha(raw_capture),
        two_complete_reads_identical=True,metadata_before_after_identical=True,settings_before_after_identical=True,
        seven_preset_replies_saved=True,current_preset_reply_saved=True,global_settings_reply_saved=True,
        full_firmware_backup=False,bootloader_backup=False,device_restore_tested=False,
        playback=False,flash_reset_or_set_sent=False,
        notes=['Each pass switches among all 54 valid slots, reloading the stock IR cache between passes.',
               'Exact 8192-byte data and 36-byte metadata are retained even for empty/non-finite slots.',
               'Finite samples additionally have mono 48 kHz IEEE-float WAV copies with identical sample bytes.',
               'WAV import on the destination firmware is untested. Raw settings replies are archival data, not a validated restore script.',
               'No software/bootloader/full-flash backup or failed-application recovery proof is implied.'],records=records)
    (output/'manifest.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    table=''.join(f'<tr><td>{r["slot_zero_based"]}</td><td>{html.escape(r["name"])}</td><td>'+ (f'<a href="{r["wav_file"]}">WAV</a>' if r['wav_file'] else 'Raw only: non-finite data')+f'</td><td><a href="{r["raw_file"]}">Exact bytes</a></td></tr>' for r in records)
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Mighty Plug Pro cabinet backup</title><style>body{font:17px/1.5 system-ui;max-width:950px;margin:40px auto;padding:0 22px;color:#172b3c;background:#f7fafc}h1{line-height:1.15}table{border-collapse:collapse;width:100%;background:white}td,th{padding:8px;border-bottom:1px solid #dce5eb;text-align:left}a{color:#005cb9}.box{background:#e5f3ed;padding:16px;border-radius:10px}</style><h1>Mighty Plug Pro backup</h1><p class="box">54 cabinet slots saved twice. Both reads match byte for byte. Presets, current preset, global settings and cabinet metadata also match before and after capture.</p><p>Captured from build <strong>20220720</strong>. No audio was played and no firmware, reset or SET command was sent.</p><p><strong>This is a cabinet/settings backup, not a firmware or bootloader backup.</strong> Restoring it has not been tested. Empty slots are preserved as raw data; non-finite sample data is not converted into a WAV.</p><p>The WAV files preserve all 2,048 float samples at 48 kHz, with no normalization. Use the compatible NUX editor's IR import workflow for WAV imports; importing to another firmware may convert or truncate them. The raw files and metadata preserve the original values. Saved settings replies must not be blindly replayed as write commands.</p><p><a href="manifest.json">Verification manifest</a> · <a href="settings-sysex.json">Saved settings replies</a> · <a href="usb-get-capture.jsonl">Complete USB request/reply record</a></p><table><thead><tr><th>Slot (0-based)</th><th>Device name</th><th>Portable copy</th><th>Raw backup</th></tr></thead><tbody>'''+table+'</tbody></table></html>'
    (output/'index.html').write_text(page)
    archive=output.with_suffix('.zip')
    need(not archive.exists(),'Archive already exists')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(output.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(output.parent))
    with zipfile.ZipFile(archive) as z:need(z.testzip() is None,'Archive CRC verification failed')
    return {k:summary[k] for k in ['status','slots','raw_bytes','wav_files','capture_requests','two_complete_reads_identical','settings_before_after_identical']}

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    print(json.dumps(package(a.capture,a.output),indent=2))
