#!/usr/bin/env python3
"""Negative controls for reclaimed resource reads and explicit init after junk RAM."""
import argparse,json,math
from pathlib import Path
import candidate_vm as v
from a2_reclaimed_vm import configure,A2ReclaimedMachine
from a2_oracle import library,Engine
from a2_storage import SLOT_ADDRESS,SLOT_SIZE
p=argparse.ArgumentParser();p.add_argument('payload',type=Path);p.add_argument('library');p.add_argument('model',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();lib=library(a.library);configure(a.payload,a.model)
m=A2ReclaimedMachine(lib,a.model);m.phase='explicit-init-test';flash=bytes(m.u.mem_read(SLOT_ADDRESS,SLOT_SIZE))
m.u.mem_write(v.state_start,b'\xa5'*(v.state_end-v.state_start));reads=m.model_reads
# Call the image's patched AMP initializer directly, skipping the stock zero table.
m.run(0x5778);assert m.get(v.sym['mpp_hybrid_ready'])==1 and m.get(v.sym['mpp_a2_load_status'])==0
assert m.model_reads>reads
x=[.15*math.sin(i*.13) for i in range(8)];m.floats(0x20025000,x);m.floats(0x20025040,[-q for q in x]);m.u.mem_write(m.preset+3,b'\x01')
for reg,val in zip(v.R,[0x20025000,0x20025040,0x20025080,0x200250c0]):m.u.reg_write(reg,val)
m.run(0x5578);y=m.read(0x20025080);ref=Engine(lib,a.model);err=max(abs(a-b) for a,b in zip(y,ref.run(x)));assert err<2e-5
assert flash==bytes(m.u.mem_read(SLOT_ADDRESS,SLOT_SIZE))
# A real stock memcpy reading model data must be rejected by the scoped reader.
for reg,val in zip(v.R[:3],[0x20025000,SLOT_ADDRESS,16]):m.u.reg_write(reg,val)
try:m.run(0x5488)
except v.Collision as e:negative=str(e)
else:raise AssertionError('Model storage read guard failed')
r=dict(status='PASS',device_access=False,audio_playback=False,explicit_amp_init_without_zero_table=True,max_numerical_error=err,flash_unchanged=True,foreign_stock_read_rejected=negative,expected_negative_access=m.model_access_violations)
a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
