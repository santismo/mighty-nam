"""Exercise actual ARM output buffering and its ingress. No device or audio API."""
from pathlib import Path
import sys,struct,math,json,hashlib,time,argparse
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_link_listening import ListeningMachine,v,build,preset_fixture
from a2_storage import model_slot
p=argparse.ArgumentParser(description=__doc__)
for name in ['payload','elf','model','output']:p.add_argument(name,type=Path)
a=p.parse_args();start=time.monotonic();elf=a.elf;model=a.model
v.configure(a.payload,True,candidate_bundle=build(a.payload.read_bytes(),elf,'NAMLNK09'))
m=ListeningMachine(model);left=v.sym['mpp_link_output'];right=v.sym['_ZL11chain_right'];tx=0x20016900
baseline=m.words()[5:7];checks=0;render_samples=0;rows=[]
def selected():
 error,value=m.page(24);assert error==0 and value>>16==48000 and (value>>8)&255==1
 return value&255
def command(size):return bytes([0xf0,0x43,0x58,0x70,4,2,ord('N'),ord('B'),size,0xf7])
assert selected()==8
for size in [8,16,32,16,8]:
 m.arm();m.ingress([command(size)]);assert selected()==size and m.page(23)==(0,2)
 assert m.words()[5:7]==baseline
 m.arm();m.put(v.sym['mpp_listen_warm'],0)
 delay=size//8-1;queue=[]
 m.u.mem_write(tx-16,b'\x51'*16);m.u.mem_write(tx+128,b'\x52'*16)
 for block in range(140):
  l=[.5*math.sin((block*8+i)*.031) for i in range(8)]
  r=[.25*math.cos((block*8+i)*.079) for i in range(8)]
  m.floats(left,l);m.floats(right,r)
  # Read back float32 values; independently predict signed integer output.
  l=m.read(left);r=m.read(right);expected=[]
  for i in range(8):
   gain=min(block*8+i+1,1024)*2**18
   # ARM conversion multiplies with float32 rounding before truncation.
   a=int(struct.unpack('<f',struct.pack('<f',l[i]*gain))[0]);b=int(struct.unpack('<f',struct.pack('<f',r[i]*gain))[0])
   expected.extend([a,b,a,b])
  queue.append(expected);expected=queue.pop(0) if len(queue)>delay else [0]*32
  m.u.mem_write(tx,bytes(128));m.call(v.sym['mpp_listen_render'],[left,right,tx])
  assert list(struct.unpack('<32i',m.u.mem_read(tx,128)))==expected,(size,block)
  assert m.u.mem_read(tx-16,16)==b'\x51'*16 and m.u.mem_read(tx+128,16)==b'\x52'*16
  m.guards();render_samples+=8
 # Mute drops queued samples, even though their backing RAM is not cleared.
 m.arm(False);m.u.mem_write(tx,bytes(128));m.call(v.sym['mpp_listen_render'],[left,right,tx]);assert m.u.mem_read(tx,128)==bytes(128)
 rows.append(dict(samples=size,exact_PCM_blocks=140,additional_blocks=delay))
for value in range(128):
 if value in [8,16,32]:continue
 m.arm();before=m.page(23);m.ingress([command(value)])
 assert selected()==8 and m.page(23)==before;checks+=1
for channel in [0,1]:
 for body in [b'',b'\x10\x00',b'\x10\x10']:
  before=m.page(23);m.query(bytes.fromhex('f043587004024e42')+body+b'\xf7',channel)
  assert selected()==8 and m.page(23)==before;checks+=1
 m.put(0xe000ed04,16);m.query(command(32),channel);m.put(0xe000ed04,0)
 assert selected()==8;checks+=1
m.ingress([command(32)]);m.arm();m.upload(model_slot(model),901)
assert selected()==32 and m.page(23)==(0,2)
m.restart();assert selected()==8 and m.page(23)==(0,2) and m.words()[5:7]==[0,0]
m.upload(model_slot(model),902);m.ingress([command(32)]);m.arm();m.put(v.sym['mpp_listen_warm'],0)
for i in range(5):m.process(i)
m.timer_ticks=150;m.process(5,healthy=False)
assert m.page(23)==(0,2) and selected()==32
for i in range(6,9):assert m.process(i,healthy=False)==[0.]*16
report=dict(status='PASS_NAMLNK09_OUTPUT_BUFFER',elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
 cases=rows,renderer_samples=render_samples,negative_commands=checks,model_identity_unchanged=True,
 model_transfer_preserves_buffer_and_mutes=True,restart_restores_eight_and_mutes=True,
 fault_discards_queued_audio=True,sample_rate_hz=48000,processing_frames=8,
 lowest_matches_NAMLNK08=True,physical_device_access=False,host_audio_access=False,
 physical_deadline_proven=False,seconds=time.monotonic()-start)
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
