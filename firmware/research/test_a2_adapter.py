#!/usr/bin/env python3
"""ARM adapter failures, in-place ABI and scoped guard negative control. Silent."""
import argparse,json,math,struct
from pathlib import Path
import candidate_vm as v
from a2_stock_vm import A2Machine
from a2_oracle import library,Engine
p=argparse.ArgumentParser();p.add_argument('payload');p.add_argument('library');p.add_argument('model',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();v.configure(a.payload,True);lib=library(a.library);m=A2Machine(lib,a.model);m.phase='adapter'
def run(xs,preset=None,control=1):
 if preset is not None:m.put(0x20005ad0,preset)
 m.u.mem_write(m.preset+3,bytes([control]));m.floats(0x20025000,xs);m.floats(0x20025100,[-x for x in xs])
 for reg,val in zip(v.R,[0x20025000,0x20025100,0x20025000,0x20025100]):m.u.reg_write(reg,val)
 m.run(m.a2_symbols['mpp_a2_process']);m.a2_guards();return m.read(0x20025000)+m.read(0x20025100)
x=[i*.02 for i in range(8)];ref=Engine(lib,a.model);y=run(x);error=max(abs(v-w) for v,w in zip(y,ref.run(x)*2));assert error<2e-5
assert run(x,control=0x41)==list(struct.unpack('<16f',struct.pack('<16f',*(x+[-v for v in x]))))
for p in [0,0x1fffffff,0x2003ff81,0xffffffff]:assert run(x,preset=p)==[0.]*16
m.put(0x20005ad0,m.preset)
for invalid in [float('nan'),float('inf'),-float('inf')]:assert run([invalid]+x[1:])==[0.]*16
# After finite-input fault, state is reset to the same zero-history model.
ref=Engine(lib,a.model);assert max(abs(a-b) for a,b in zip(run(x),ref.run(x)*2))<2e-5
# Scoped write guard must catch an executed foreign stock memory copy.
for reg,val in zip(v.R[:3],[m.a2_lo,0x30040000,16]):m.u.reg_write(reg,val)
try:m.run(0x5488)
except v.Collision as e:negative=str(e)
else:raise AssertionError('A2 guard missed a foreign write')
r=dict(status='PASS',silent=True,device_access=False,in_place_abi_max_error=error,bypass_stereo_exact=True,invalid_preset_cases=4,nonfinite_input_cases=3,post_fault_reset=True,negative_write_guard=negative,expected_negative_write=m.a2_violations)
a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
