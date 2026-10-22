"""NAMLNK21 compiled ARM duplex/controls regression. No physical I/O.
USB enumeration, endpoint completion and frame counter are modeled. The stock
PCM ring readers/writers, conversion, class gain/mute and limiter execute.
"""
import argparse,struct,json,math,zlib,hashlib
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_PC,UC_ARM_REG_LR
from test_active_chain import ActiveMachine,v,preset_fixture,input_block
from preset_image import build,BANK,BANK_END
from a2_oracle import Engine,library
from a2_storage import model_slot
class UsbMachine(ActiveMachine):
 def initialize_usb(self):
  self.run(0xcc7c) # Actual stock class-volume initialization.
  # Enumeration publishes this pointer; peripheral setup itself is not emulated.
  self.put(0x2000b01c,0x2000dac8);self.put(0x2000dac8+0x9c,48)
  self.u.mem_write(0x2000dac8+0xa0,struct.pack('<H',0x1800));self.u.mem_write(0x2000dac8+0xb8,b'\1')
  def frame(u,pc,size,unused):
   self.put(u.reg_read(UC_ARM_REG_R1),1);u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
  self.u.hook_add(UC_HOOK_CODE,frame,begin=0x13964,end=0x13964)
 def host(self,l,r):
  self.u.mem_write(0x2000dac8+0x54,b'\1\0\1')
  self.put(0x2000dac8+0x58,0);self.put(0x2000dac8+0x5c,512);self.put(0x2000dac8+0x60,0)
  self.u.mem_write(0x2000b028,struct.pack('<16i',*[q for i in range(8) for q in [int(l[i]*2**31),int(r[i]*2**31)]]))
 def nv(self,value=None,channel=0,crc=None):
  active=self.page(25)[1]&255;model=self.words()[5] if crc is None else crc
  q=[240,67,88,112,4,2,78,86,1,int(value is not None),127 if active==255 else active,14,2]
  if value is not None:q += [0]+[(model>>(7*i))&127 for i in range(5)]+[value]
  q += [247];rows=self.ingress([bytes(q)],channel);assert len(rows)==1 and rows[0][1]==channel
  r=rows[0][0];assert len(r)==17 and r[9]==(q[9]|64);return r
 def ng(self,config=None,channel=0,crc=None,slot=None):
  active=self.page(25)[1]&255;slot=active if slot is None else slot
  model=self.words()[5] if crc is None else crc
  q=[240,67,88,112,4,2,78,71,1,int(config is not None),127 if slot==255 else slot,13,2]
  if config is not None:q += [0]+[(model>>(7*i))&127 for i in range(5)]+config
  q+=[247];rows=self.ingress([bytes(q)],channel)
  assert len(rows)==1 and rows[0][1]==channel
  r=rows[0][0];assert len(r)==22 and r[9]==(q[9]|64) and r[10:13]==bytes(q[10:13]);return r

def main():
 p=argparse.ArgumentParser()
 for n in ['payload','elf','model','library','output']:p.add_argument(n,type=Path)
 p.add_argument('--seed-bank',type=Path);p.add_argument('--pitch-prototype',action='store_true');p.add_argument('--pitch-release',action='store_true');a=p.parse_args();bundle=build(a.payload.read_bytes(),a.elf,allow_pitch_prototype=a.pitch_prototype);assert bundle[2]['identity']==('NAMPIT01' if a.pitch_prototype else 'NAMLNK22' if a.pitch_release else 'NAMLNK21')
 v.configure(a.payload,True,candidate_bundle=bundle);v.elf_path=a.elf
 m=UsbMachine(boundary_oracle=Engine(library(str(a.library)),a.model));m.service();m.upload(model_slot(a.model),101);m.initialize_usb()
 # Execute both original stock PCM ring paths, retaining stereo separation.
 left=[.01*(i+1) for i in range(8)];right=[-.015*(i+1) for i in range(8)]
 m.host(left,right);m.floats(0x20015a10,left);m.floats(0x20015a30,right);m.run(0xccec)
 assert max(abs(x-y) for x,y in zip(m.read(0x20015b10)+m.read(0x20015b30),left+right))<1e-7
 pcm=struct.unpack('<16i',m.u.mem_read(0x2000d0c8,64));assert max(abs(pcm[2*i]*2**-31-left[i]) for i in range(8))<1e-7 and max(abs(pcm[2*i+1]*2**-31-right[i]) for i in range(8))<1e-7
 # Class mute is applied independently to each direction by retained stock code.
 m.host(left,right);m.u.mem_write(0x2000a144+12,b'\1');m.u.mem_write(0x2000a144+15,b'\1');m.run(0xccec)
 assert m.read(0x20015b10)+m.read(0x20015b30)==[0.]*16 and m.u.mem_read(0x2000d0c8,64)==bytes(64)
 m.run(0xcc7c)
 # Entire bridge executes the real stock playback gain/limiter after PCM input.
 for _ in range(128):m.host(left,right);m.call(v.sym['mpp_usb_begin'],[1])
 assert any(abs(x)>1e-5 for x in m.read(0x20015b10)) and any(abs(x)>1e-5 for x in m.read(0x20015b30))
 m.u.mem_write(0x2000dac8+0x54,b'\0\0\1')
 # Real callback, neutral NAM against independent reference, NAM + spring.
 settings=bytearray(preset_fixture([8],{8:4}));settings[84]=37;settings[70:74]=bytes([20,20,50,0]);m.u.mem_write(m.preset,bytes(settings));m.arm()
 peak=0
 for i in range(1450):
  y=m.process(i,input_block(i));peak=max(peak,max(map(abs,y)))
  if i%500==0:print('callback block',i,flush=True)
 assert peak>1e-6 and m.words()[4]==0 and m.stats()[2]==2
 assert any(m.u.mem_read(0x2000d0c8,0x600)), 'No guitar recorded to USB ring'
 assert m.max_boundary_error<2e-5
 # Bridge mix is wet-record-before-return; original USB playback gain remains.
 addr=0x20016000;m.floats(addr,left);m.floats(addr+32,right);m.floats(0x20015b10,[.03]*8);m.floats(0x20015b30,[-.02]*8)
 m.call(v.sym['mpp_usb_finish'],[addr,addr+32]);assert max(abs(x-y*.625) for x,y in zip(m.read(0x20015a10)+m.read(0x20015a30),left+right))<1e-7
 assert max(abs(x-(y+.048)) for x,y in zip(m.read(addr),left))<1e-7
 assert max(abs(x-(y-.032)) for x,y in zip(m.read(addr+32),right))<1e-7
 # Both MIDI transports execute actual NG handler. Knobs do not trigger settling.
 assert list(m.ng()[15:21])==[48,12,12,12,100,48]
 before=bytes(m.u.mem_read(m.preset,128));controls=[54,18,8,14,75,42];modelcrc=m.words()[5]
 for channel in [0,1]:
  r=m.ng(controls,channel);assert r[13]==0 and list(r[15:21])==controls
  assert m.ng(controls,channel,crc=modelcrc^1)[13]==2
  assert m.ng([127,12,12,12,100,48],channel)[13]==2
 assert m.words()[5]==modelcrc and m.get(v.sym['mpp_listen_warm'])==0
 after=bytes(m.u.mem_read(m.preset,128));assert all(before[i]==after[i] for i in range(128) if not 27<=i<=34)
 # Independent USB record gain never changes headphone samples or host return.
 assert m.nv()[15]==48
 for transport in [0,1]:
  assert m.nv(60,transport)[13]==0
  assert m.nv(60,transport,crc=modelcrc^1)[13]==2
  assert m.nv(127,transport)[13]==2
 for _ in range(250):
  m.floats(addr,left);m.floats(addr+32,right);m.call(v.sym['mpp_usb_finish'],[addr,addr+32])
 assert max(abs(x-y*.625*10**(.3)) for x,y in zip(m.read(0x20015a10)+m.read(0x20015a30),left+right))<2e-6
 assert max(abs(x-(y+.048)) for x,y in zip(m.read(addr),left))<1e-7
 m.nv(96)
 for _ in range(250):
  m.floats(addr,[.9]*8);m.floats(addr+32,[-.9]*8);m.call(v.sym['mpp_usb_finish'],[addr,addr+32])
 assert m.read(0x20015a10)==[.875]*8 and m.read(0x20015a30)==[-.875]*8
 m.nv(48)
 m.boundary_oracle=None
 for i in range(1450,1650):m.process(i,input_block(i));assert m.get(v.sym['mpp_listen_warm'])==0
 # Removed NAM has no callback and ignores all its tone/gain settings.
 count=m.amp_calls;m.u.mem_write(m.preset+3,b'\x41');m.process(1650);m.process(1651);assert m.amp_calls==count
 m.u.mem_write(m.preset,bytes(settings));m.ng([48,12,12,12,100,48]);
 slot=model_slot(a.model);saved=[]
 for color in range(7):
  assert m.nv(48+color)[13]==0
  desired=[48+color,12,12,12,100,48];assert m.ng(desired)[13]==0
  fx=bytes(m.u.mem_read(m.preset,128));body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(fx),1,8)+hashlib.sha256(slot).digest()+b'Fender A2 Lite'.ljust(64,b'\0')
  assert m.bank_request(2,color,body,channel=color%2,nonce=100+color)[7]==0;saved.append(fx)
  print('saved control preset',color+1,flush=True)
 flash=bytes(m.u.mem_read(BANK,BANK_END-BANK));m.restart();m.service();assert bytes(m.u.mem_read(m.preset,128))==saved[0]
 for i in [1,2,3,4,5,6,0]:assert m.button()==i and bytes(m.u.mem_read(m.preset,128))==saved[i]
 cold=UsbMachine(flash,0xa5);cold.service();assert bytes(cold.u.mem_read(cold.preset,128))==saved[0]
 # Cold boot before USB enumeration must be safe and must clear stale return.
 cold.process(0);assert cold.read(0x20015b10)+cold.read(0x20015b30)==[0.]*16
 if a.seed_bank:
  # Optional private factory bank uses neutral controls in every color. No model bytes in reports.
  for color in range(7):
   m.call(0xb38a,[color]);m.service();m.ng([48,12,12,12,100,48]);m.nv(48);fx=bytes(m.u.mem_read(m.preset,128));body=struct.pack('<4I',zlib.crc32(slot),zlib.crc32(fx),1,8)+hashlib.sha256(slot).digest()+b'Fender A2 Lite'.ljust(64,b'\0');assert m.bank_request(2,color,body,nonce=200+color)[7]==0
  a.seed_bank.write_bytes(bytes(m.u.mem_read(BANK,BANK_END-BANK)))
 report=dict(status='PASS_OFFLINE_'+bundle[2]['identity'],elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),compiled_callback_blocks=1652,neutral_NAM_reference_peak_error=m.max_boundary_error,stereo_USB_PCM_ring_roundtrip=True,class_mutes_verified=True,wet_record_excludes_host_return=True,USB_record_gain_guarded_and_persistent=True,USB_record_gain_headphone_independent=True,NAM_controls_both_transports=True,seven_presets_cold_warm_button=True,removed_NAM_no_callback=True,device_access=False,host_audio_access=False,limitations=['USB enumeration/endpoint completion/frame counter modeled','Real-time physical deadlines and Logic duplex pending installation'])
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
if __name__=='__main__':main()
