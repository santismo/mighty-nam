#!/usr/bin/env python3
"""Inspect saved host-updater disassembly only. Never opens a USB device."""
import argparse,hashlib,json,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('disassembly',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
text=a.disassembly.read_text();calls=[];function='';functions={}
for line in text.splitlines():
 if re.match(r'^[_A-Za-z].*:$',line):function=line[:-1];functions.setdefault(function,[])
 if not re.match(r'^[0-9a-f]{16}\s',line):continue
 functions.setdefault(function,[]).append(line)
 if re.search(r'\bbl\b',line) and any(x in line for x in ['_hid_read','_IOHIDDeviceGetReport','_IOHIDDeviceSetReport']):
  calls.append(dict(function=function,address=line.split()[0],disassembly=line))
writer='__ZN16HID_Write_Thread3runEv';scanner='__ZN20MainContentComponent10scanDeviceEv'
reads=[c for c in calls if '_hid_read_timeout' in c['disassembly']]
writes=[c for c in calls if '_IOHIDDeviceSetReport' in c['disassembly']]
assert len(reads)==2 and {c['function'] for c in reads}=={writer,scanner}
wr=[c for c in reads if c['function']==writer];ww=[c for c in writes if c['function']==writer]
assert len(ww)==45 and int(wr[0]['address'],16)<min(int(c['address'],16) for c in ww)
assert '_IOHIDDeviceGetReport' not in text
r=dict(status='PASS_BOUNDED_STATIC_HOST_AUDIT',device_access=False,updater_executed=False,source_file=a.disassembly.name,source_sha256=hashlib.sha256(a.disassembly.read_bytes()).hexdigest(),read_calls=reads,set_report_calls_by_function={f:sum(c['function']==f for c in writes) for f in [writer,scanner]},get_report_references=0,interpretation=[
 'The upload routine contains one direct hid_read_timeout call in its pre-upload input-drain loop (0x1000029ec..0x100002a08); the subsequent 45 direct SetReport call sites implement file transfer.',
 'The other direct hid_read_timeout call belongs to discovery: a zeroed 64-byte output report begins with 0x56 and the reply is parsed as a string for the UI.',
 'No direct post-upload flash readback or full-backup command was identified in these host paths. Transfer completion is not an independently checked restoration.',
 'This is a bounded direct-call/static audit. It cannot prove there are no undocumented device commands, indirect paths, encoded loader, or service tools; it does not reveal device erase protection or recovery entry.'
 ],physical_usb_recovery_proven=False)
a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k] for k in ['status','set_report_calls_by_function','get_report_references']}))
