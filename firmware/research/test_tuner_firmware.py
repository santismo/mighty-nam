"""Execute tuner packets through stock ingress and compare unchanged stock DSP.
Synthetic counter/USB boundaries only; no physical device or audio streams.
"""
import argparse,hashlib,json,math,struct,zlib
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR
from test_preset_runtime import PresetMachine,build,v,preset_fixture
from test_link_firmware import unpack
class TunerMachine(PresetMachine):
 def code(self,u,pc,size,unused):
  if self.phase=='probe' and pc==0xae80 and u.reg_read(UC_ARM_REG_R1)==330:
   address=u.reg_read(UC_ARM_REG_R0);self.messages.append((bytes(u.mem_read(address,330)),u.reg_read(UC_ARM_REG_R2)))
   u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  super().code(u,pc,size,unused)
 def tuner(self,op,page=0,nonce=301,channel=0):
  request=bytes([0xf0,0x43,0x58,0x70,4,2,78,85,1,op,page,nonce&127,nonce>>7,0xf7])
  result=self.ingress([request],channel=channel,start=2045)
  if not result:return None
  assert len(result)==1 and result[0][1]==channel
  wire=result[0][0];assert wire[:9]==request[:9] and len(wire)==330 and wire[-1]==247
  raw=unpack(wire[9:-1]);assert len(raw)==280
  assert struct.unpack_from('<I',raw,276)[0]==zlib.crc32(raw[:276])
  assert raw[:7]==struct.pack('<IBBB',0x31554e4d,1,op|128,page)
  assert struct.unpack_from('<I',raw,8)[0]==nonce and struct.unpack_from('<H',raw,16)[0]==12000
  return raw

def main():
 p=argparse.ArgumentParser();p.add_argument('payload',type=Path);p.add_argument('elf',type=Path);p.add_argument('model',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 bundle=build(a.payload.read_bytes(),a.elf);assert bundle[2]['identity']=='NAMLNK12'
 v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=a.elf
 m=TunerMachine(path=a.model);ref=TunerMachine(path=a.model)
 assert m.tuner(2)[7]==1
 for op,page,nonce in [(3,0,1),(1,1,1),(2,16,1),(2,0,0)]:assert m.tuner(op,page,nonce) is None
 m.put(0xe000ed04,16);assert m.tuner(1) is None;m.put(0xe000ed04,0)
 m.arm();assert m.tuner(1)[7]==3;m.arm(False)
 for machine in [m,ref]:machine.arm(False);machine.u.mem_write(machine.preset,bytes(preset_fixture([1,2,4,5,6,7,8,9])))
 started=m.tuner(1);assert started[7]==0;generation=struct.unpack_from('<I',started,12)[0]
 expected=[]
 for block in range(1024):
  samples=[.45*math.sin(2*math.pi*110*(block*8+i)/48000)+.2*math.sin(2*math.pi*220*(block*8+i)/48000) for i in range(8)]
  assert m.process(block,samples)==ref.process(block,samples)
  assert bytes(m.u.mem_read(v.sym['mpp_link_output'],32))==bytes(ref.u.mem_read(v.sym['mpp_link_output'],32))
  ints=[int(x*2**31)>>16 for x in samples]
  expected += [sum(ints[i:i+4])>>2 for i in [0,4]]
  if block in [0,200,1022]:assert m.tuner(2)[7]==1
 actual=[]
 for page in range(16):
  raw=m.tuner(2,page,nonce=350+page,channel=page%2);assert raw[7]==0
  assert struct.unpack_from('<I',raw,12)[0]==generation and struct.unpack_from('<H',raw,18)[0]==2048
  actual.extend(struct.unpack_from('<128h',raw,20))
 assert actual==expected
 # Completed buffer is frozen, even while the audio chain continues.
 first=m.tuner(2,0)
 for i in range(16):m.process(1024+i)
 assert m.tuner(2,0)==first
 m.tuner(0);assert m.tuner(2)[7]==1
 m.tuner(1);m.process(1050);m.arm();m.process(1051);assert m.tuner(2)[7]==1
 m.arm(False);m.tuner(1);m.restart();assert m.tuner(2)[7]==1
 # Capture can work without any loaded NAM model and still never arm output.
 m.service();assert not m.words()[9];assert m.tuner(1)[7]==0
 for i in range(1024):m.process(i,healthy=False)
 assert m.tuner(2)[7]==0 and not m.get(v.sym['mpp_listen_enabled'])
 assert not m.flash_operations and not ref.flash_operations
 report=dict(status='PASS_NAMLNK12_TUNER_ARM',elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),captured_samples=2048,actual_stock_ingress=True,both_usb_channels=True,exact_dry_input_decimation=True,full_chain_blocks_identical=1024,starts_muted_only=True,auto_stop_and_snapshot_frozen=True,invalid_and_irq_requests_ignored=True,warm_restart_clears=True,works_without_model=True,no_flash_writes=True,device_access=False,audio_access=False)
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
if __name__=='__main__':main()
