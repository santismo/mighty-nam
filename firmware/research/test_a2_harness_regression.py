#!/usr/bin/env python3
"""Ensure new optional A2 hooks preserve default LSTM stock-chain behavior."""
import sys,json,math
from pathlib import Path
import candidate_vm as v
from stock_chain_vm import StockChainMachine
v.configure(sys.argv[1],True);results=[]
for fast,observe in [(False,True),(True,True),(True,False)]:
 m=StockChainMachine(fast=fast,observe_blocks=observe);m.set_preset([1,2,4,6,7,8,9]);ys=[]
 for b in range(24):ys+=m.block([.16*math.sin((b*8+i)*.071)+.04*math.sin((b*8+i)*.213) for i in range(8)])
 results.append(ys)
assert results[0]==results[1]==results[2]
Path(sys.argv[2]).write_text(json.dumps(dict(status='PASS',blocks_per_mode=24,bit_identical=True,modes=['every instruction','basic blocks','boundaries only'],device_or_audio_access=False),indent=2)+'\n');print('Instrumentation regression PASS')
