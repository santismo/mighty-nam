"""Exact ARM stereo-routing regression, using synthetic memory PCM only."""
from pathlib import Path
import argparse
import sys, json, struct, math, hashlib

parser=argparse.ArgumentParser(description=__doc__)
for name in ['work','stock_payload','baseline_elf','starter_bank','starter_report','output']:
 parser.add_argument(name,type=Path)
a=parser.parse_args()
HERE=a.work.resolve()
sys.path[:0]=[str(HERE/'generated/research'),str(HERE/'generated/tools')]
from test_usb_nam import UsbMachine,v,preset_fixture
from preset_image import build,BANK,BANK_END,FLASH
sha=lambda x:hashlib.sha256(x).hexdigest()
stock_path=a.stock_payload
stock=stock_path.read_bytes()
bank=a.starter_bank.read_bytes()
presets=json.loads(a.starter_report.read_text())['presets']
assert len(presets)==3

class MediaMachine(UsbMachine):
 def media(self,index,left=None,right=None,guitar=None,mic=None):
  zero=[0.]*8
  channels=[left or zero,right or zero,mic or zero,guitar or zero]
  values=[int(channels[ch][i]*2**31) for i in range(8) for ch in range(4)]
  assert all(-2**31<=n<2**31 for n in values)
  half=index%2;rx=0x20019000+128*half;tx=0x20019100+128*half
  other=0x20019100+128*(1-half)
  sentinel=bytes(self.u.mem_read(other,128))
  self.u.mem_write(rx,struct.pack('<32i',*values));self.u.mem_write(tx,b'\x7f'*128)
  self.call(0xe19c,[rx,tx])
  assert bytes(self.u.mem_read(other,128))==sentinel
  words=struct.unpack('<32i',self.u.mem_read(tx,128))
  assert words[0::4]==words[2::4] and words[1::4]==words[3::4]
  assert all(abs(n)<=1879048192 for n in words)
  self.run(0x666a,limit=3000000)
  self.guards();assert self.words()[4]==0 and self.words()[9]==1
  return [n*2**-31 for n in words[0::4]+words[1::4]]

def configure(elf):
 payload,symbols,plan=build(stock,elf)
 payload=bytearray(payload);payload[BANK-FLASH:BANK_END-FLASH]=bank
 payload=bytes(payload);plan['candidate_sha256']=sha(payload)
 v.configure(stock_path,True,candidate_bundle=(payload,symbols,plan));v.elf_path=elf
 return payload,symbols,plan

def guitar_test(m):
 output=[];summary=[]
 for color in [0,1,2]:
  assert m.bank_request(3,color,nonce=1800+color)[7]==0;m.service()
  assert m.words()[5]==presets[color]['model_crc']
  samples=[]
  for i in range(1600):
   signal=[.08*math.sin((i*8+j)*.071)+.023*math.sin((i*8+j)*.193) for j in range(8)]
   y=m.process(i,signal)
   if i>=1400:samples+=y
  assert max(map(abs,samples))>1e-7 and m.words()[4]==0
  output.append(samples)
  summary.append(dict(color=color,model_crc=m.words()[5],peak=max(map(abs,samples)),faults=0,callbacks=1600))
  print('Saved guitar chain PASS',color,flush=True)
 return output,summary

def empty_chain(m):
 p=preset_fixture([]);p[3]=65
 m.u.mem_write(m.preset,bytes(p))
 at=v.SP-512;m.call(v.sym['mpp_fx_get'],[at]);fx=bytearray(m.u.mem_read(at,32));fx[1]=fx[17]=0
 m.u.mem_write(at,bytes(fx));m.call(v.sym['mpp_fx_set'],[at])
 for i in range(1350):m.process(i,[0.]*8)
 assert m.get(v.sym['mpp_listen_warm'])==0

base_elf=a.baseline_elf
configure(base_elf)
m=MediaMachine();m.service()
baseline,old_summary=guitar_test(m)
empty_chain(m)
old_music=[]
for i in range(8):old_music+=m.media(i,[.2]*8,[-.1]*8)
assert old_music==[0.]*len(old_music),'Expected NAMLNK23 missing stereo-input regression'
print('Reproduced old firmware: stereo RX music discarded without USB',flush=True)

elf=HERE/'build/nam-link-offline.elf'
payload,symbols,plan=configure(elf)
m=MediaMachine();m.service()
actual,summary=guitar_test(m)
assert actual==baseline,'Guitar-only output changed'
print('All three guitar chains remain sample-exact',flush=True)
empty_chain(m)
media_cases=[]
# Actual callback and DMA, independent stereo lanes and non-USB standalone use.
for label,left,right,mic in [
 ('left only',[.2]*8,[0.]*8,None),
 ('right only',[0.]*8,[-.15]*8,None),
 ('center music',[.12]*8,[.12]*8,None),
 ('opposite polarity',[.12]*8,[-.12]*8,None),
 ('microphone excluded',[0.]*8,[0.]*8,[.3]*8),
]:
 for i in range(4):y=m.media(i,left,right,mic=mic)
 gain=m.read(0x200006f8)[0]
 expected=[x*gain for x in left+right]
 error=max(abs(a-b) for a,b in zip(y,expected))
 assert error<2e-7,(label,error,gain,y)
 assert m.read(0x200183a0)+m.read(0x200183c0)==[0.]*16,'Music entered guitar USB record feed'
 media_cases.append(dict(case=label,peak=max(map(abs,y)),headphone_gain=gain,peak_error=error))
print('Stereo/mono/opposite-polarity and no-microphone routing PASS',flush=True)
assert media_cases[0]['peak']>1e-5

# Buffer output remains ordered and preserves stereo at 8/16/32 samples.
buffers=[]
for buffer in [8,16,32]:
 m.ingress([bytes([240,67,88,112,4,2,78,66,buffer,247])],1)
 for i in range(1350):m.media(i)
 gain=m.read(0x200006f8)[0];timeline=[]
 for i in range(12):
  l=[.01*(i+1)]*8;r=[-.015*(i+1)]*8
  y=m.media(i,l,r);timeline.append((l+r,y))
 delay=buffer//8
 for i in range(delay,12):
  expected=[x*gain for x in timeline[i-delay][0]]
  assert max(abs(a-b) for a,b in zip(timeline[i][1],expected))<2e-7
 buffers.append(dict(samples=buffer,total_callback_blocks=delay,ordered_stereo=True))
print('8/16/32 stereo output staging PASS',flush=True)
m.ingress([bytes([240,67,88,112,4,2,78,66,8,247])],1)
for i in range(1350):m.media(i)

# Sinusoids through actual callback must retain stereo/sample waveform.
frequency_cases=[]
for hz in [80,440,1000,6000,12000,18000]:
 prev=None;peak_error=0
 for i in range(60):
  l=[.15*math.sin((i*8+j)*2*math.pi*hz/48000) for j in range(8)]
  r=[.12*math.cos((i*8+j)*2*math.pi*hz/48000) for j in range(8)]
  y=m.media(i,l,r);gain=m.read(0x200006f8)[0]
  if prev is not None:peak_error=max(peak_error,max(abs(a-b*gain) for a,b in zip(y,prev)))
  prev=l+r
 assert peak_error<2e-7,(hz,peak_error)
 frequency_cases.append(dict(hz=hz,peak_error=peak_error))
print('Full-band synthetic music waveform PASS',flush=True)

# USB PCM return may coexist; music must never enter the guitar recording feed.
m.initialize_usb()
for i in range(200):
 m.host([0.]*8,[0.]*8);m.media(i,[.08]*8,[-.06]*8)
assert m.read(0x200183a0)+m.read(0x200183c0)==[0.]*16
assert any(m.media(201,[.08]*8,[-.06]*8))
print('Bluetooth with USB initialized and record-loopback isolation PASS',flush=True)

# Direct renderer extremities: valid full-scale sum and corrupt/nonfinite input
# stay bounded; explicit disabled output still produces no DMA samples.
m.put(symbols['mpp_listen_warm'],0)
at=0x20018800;tx=0x20019100
m.floats(at,[.875]*8);m.floats(at+32,[-.875]*8)
m.floats(symbols['mpp_bluetooth_output'],[2.]*8+[-2.]*8)
m.call(symbols['mpp_listen_render'],[at,at+32,tx])
q=list(struct.unpack('<32i',m.u.mem_read(tx,128)))
assert q[::4]==[1879048192]*8 and q[1::4]==[-1879048192]*8
m.floats(symbols['mpp_bluetooth_output'],[float('nan')]*16)
m.call(symbols['mpp_listen_render'],[at,at+32,tx]);assert bytes(m.u.mem_read(tx,128))==bytes(128)
m.arm(False);m.u.mem_write(tx,bytes(128));m.call(symbols['mpp_listen_render'],[at,at+32,tx])
assert bytes(m.u.mem_read(tx,128))==bytes(128)
print('Final summing ceiling, nonfinite and disabled-output checks PASS',flush=True)

boots=[]
for fill in [0,0xa5,0xff]:
 n=MediaMachine(fill=fill);n.service()
 assert bytes(n.u.mem_read(BANK,BANK_END-BANK))==bank
 assert n.get(symbols['mpp_listen_enabled'])==1
 assert n.read(symbols['mpp_bluetooth_output'])==[0.]*8
 for color in [1,2,0]:assert n.button()==color and n.words()[5]==presets[color]['model_crc']
 n.restart();n.service();assert n.words()[5]==presets[0]['model_crc']
 assert n.get(symbols['mpp_listen_enabled'])==1
 boots.append(fill)
 print('Starter bank cold/warm/buttons PASS',fill,flush=True)
report=dict(status='PASS_NAMLNK23_R2_BLUETOOTH_OFFLINE',identity='NAMLNK23',revision='r2-bluetooth',
 elf_sha256=sha(elf.read_bytes()),candidate_payload_sha256=sha(payload),
 bank_sha256=sha(bank),baseline_music_discard_reproduced=True,guitar_samples_exact=True,
 guitar_chains=summary,media_cases=media_cases,buffer_cases=buffers,frequency_cases=frequency_cases,
 record_feed_excludes_music=True,usb_initialized_stereo_music=True,nonfinite_and_sum_ceiling=True,
 cold_warm_RAM_fills=boots,device_access=False,host_audio_access=False,
 limitations=['RX PCM is synthetic; this test does not measure physical Bluetooth transport, analog gain or listening.',
 'The emulated timer is synthetic; real processing deadlines require a later hardware check.',
 'Bluetooth uses a flat stereo path; the stock Bluetooth EQ/vocal-cancel feature is not applied.',
 'Headphone gain follows the stock smoother once per eight-sample block; guitar smoothing is unchanged.'])
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(report['status'],flush=True)
