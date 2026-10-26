"""Additional integration assertions, executed in test_extension's VM scope."""
# USB and BLE must return the same capability; read request never mutates audio.
for ch in [0,1]:assert m.page(126,ch)==(0,0x5354011d)
# Exercise standard FX and reverb as well as the stock amp; all synthetic PCM.
c=bytearray(config(1));c[16]=3;c[17]=1;c[18]=8
set_fx(bytes(c));d=preset([8],{8:4});d[84]=37;d[70:74]=bytes([20,20,50,0]);m.u.mem_write(m.preset,bytes(d));m.arm()
for n in range(1450):m.process(n,input_block(n))
assert not m.words()[4] and not m.diag()[3]
# Record with both amps, change a stock amp, retain recorded storage in playback.
assert m.loop_request(1,1)[0]==0;m.arm_loop('mpp_loop_before_tick')
for n in range(256):m.process(n,input_block(n))
assert m.loop_request(1,2)[0]==0;m.arm_loop('mpp_loop_before_tick')
assert m.loop_state(3)==3 and m.loop_state(0)>0
recorded=loops_hash()
def loop_tick(n):
 half=n%2;rx=0x20019000+128*half;tx=0x20019100+128*half;other=0x20019100+128*(1-half)
 before=bytes(m.u.mem_read(other,128));m.u.mem_write(rx,bytes(128));m.u.mem_write(tx,b'\x7f'*128);m.call(0xe19c,[rx,tx])
 assert m.u.mem_read(other,128)==before
 pcm=struct.unpack('<32i',m.u.mem_read(tx,128));assert pcm[0::4]==pcm[2::4] and pcm[1::4]==pcm[3::4]
 assert max(map(abs,pcm))<=234881024
 assert not m.words()[4] and not m.diag()[3] and not m.loop_state(8);m.guards()
 return any(pcm)
for amp in [26,1]:
 c[3]=amp;set_fx(bytes(c));assert loops_hash()==recorded
 assert sum(loop_tick(i) for i in range(1400))>1300
 assert loops_hash()==recorded
# Recall another capture while the loop plays; then the saved stock-amp preset.
for color in [1,0]:
 assert m.bank_request(3,color,nonce=510+color)[7]==0;m.service()
 assert sum(loop_tick(i) for i in range(1400))>1300
 assert loops_hash()==recorded
assert m.loop_request(1,4)[0]==0;m.arm_loop('mpp_loop_before_tick')
rows.append(dict(case='loop_playback_amp_switch_and_preset_recall',recorded_storage_unchanged=True,callbacks=5600,output_continued=True))
print('Loop playback / amp switching / preset recall PASS',flush=True)
