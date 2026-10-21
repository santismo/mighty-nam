"""Execute stock audio setup, then explore a separate FIFO/DMA event model.

The peripheral model is a hypothesis, not cycle-accurate hardware emulation.
Serial words are atomic, DMA bursts instantaneous, RX/TX synchronous, and
startup TX FIFOs immediately prefilled. Real arbitration, FIFO synchronizers,
interrupt entry/preemption and converter group delay are not modeled.
No physical device, host audio, update image or firmware edits.
"""
import argparse, hashlib, json, struct
from collections import deque
from pathlib import Path
from test_codec_startup import Startup
from preset_image import build


def simulate(burst, rx_watermark, tx_watermark, publish_words, previous_block=True, frames=400, rx_start_words=0):
    """A label identifies its source *serial word*, not an analog sample."""
    assert 32 % burst == 0 and 0 <= rx_watermark < 32 and 0 <= tx_watermark < 32
    assert burst <= rx_watermark + 1 and burst <= 32 - tx_watermark
    rx_fifo, tx_fifo = deque(), deque()
    rx_memory, tx_memory = [None]*64, [None]*64
    rx_cursor = tx_cursor = 0
    last_block = [None]*32; scheduled = []; emitted = []; deadlines = []
    overflow = underrun = 0
    # There is no stall before a burst in this idealized model.
    def fill_tx(now):
        nonlocal tx_cursor, overflow
        while len(tx_fifo) <= tx_watermark:
            assert len(tx_fifo)+burst <= 32
            for _ in range(burst):
                tx_fifo.append(tx_memory[tx_cursor]);tx_cursor=(tx_cursor+1)%64
    fill_tx(0)
    irq_times = []
    for tick in range(1,frames*4+1):
        # Publication is conservatively after a coincident DMA read.
        if tx_fifo:
            label = tx_fifo.popleft()
            if label is not None:emitted.append((label,tick))
        else:underrun += 1
        fill_tx(tick)
        if tick > rx_start_words:rx_fifo.append(tick)
        if len(rx_fifo)>32:overflow += 1
        while len(rx_fifo)>rx_watermark:
            for _ in range(burst):
                rx_memory[rx_cursor]=rx_fifo.popleft();rx_cursor=(rx_cursor+1)%64
            if rx_cursor % 32 == 0:
                half = (rx_cursor//32-1)%2; current=rx_memory[half*32:half*32+32]
                irq_times.append(tick)
                payload=list(last_block if previous_block else current);last_block=list(current)
                scheduled.append((tick+publish_words,half,payload,tick))
                # Count serial-word consumption until TX next reads the first
                # word of the half. FIFO depth determines this deadline.
                distance=(half*32-tx_cursor)%64
                wait=max(0,len(tx_fifo)-tx_watermark)+distance
                deadlines.append(wait)
        pending=[]
        for due,half,payload,irq in scheduled:
            if due<=tick:
                # A late publish can partially update a half already fetched.
                tx_memory[half*32:half*32+32]=payload
            else:pending.append((due,half,payload,irq))
        scheduled=pending
    observed=[(label,t) for label,t in emitted if label>128 and t<frames*4-128]
    ages=sorted(set(t-label for label,t in observed))
    sequence=[label for label,_ in observed]
    discontinuities=sum(b!=a+1 for a,b in zip(sequence,sequence[1:]))
    margin=min(deadlines)-publish_words
    return dict(burst_words=burst,rx_watermark=rx_watermark,tx_watermark=tx_watermark,
        rx_start_delay_words=rx_start_words,
        publication='previous protected block' if previous_block else 'current completed block',
        publication_after_irq_us=round(publish_words/192000*1e6,3),
        minimum_first_word_deadline_us=round(min(deadlines)/192000*1e6,3),
        nominal_publication_margin_us=round(margin/192000*1e6,3),
        modeled_label_age_words=ages,modeled_label_age_ms=[round(x/192,6) for x in ages],
        sequence_discontinuities=discontinuities,fifo_underruns=underrun,fifo_overflows=overflow,
        irq_period_words=sorted(set(b-a for a,b in zip(irq_times,irq_times[1:]))))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['payload','elf','report']:p.add_argument(name,type=Path)
    a=p.parse_args();stock=a.payload.read_bytes();bundle=build(stock,a.elf)
    m=Startup(*bundle);_,raw=m.audio_setup()
    descriptors=[dict(zip(('source','source_step','attributes','burst_bytes','source_last',
        'destination','destination_step','iterations','next','control','initial_iterations'),
        struct.unpack('<IhHIiIhHIHH',raw[i:i+32]))) for i in range(0,128,32)]
    assert all(x['burst_bytes']==64 and x['iterations']==2 for x in descriptors)
    read=lambda at:struct.unpack('<I',m.u.mem_read(at,4))[0]
    txw,rxw=read(0x4040400c),read(0x4040408c)
    assert txw==rxw==16
    assert ((read(0x40404018)>>16)&31)+1==4
    assert ((read(0x4040401c)>>16)&31)+1==32
    assert [x['control'] for x in descriptors]==[0x12,0x12,0x10,0x10]
    rows=[]
    for burst,rx,tx in [(16,16,16),(16,15,0),(8,7,8),(4,3,4),(4,3,0),(1,0,0)]:
        for previous in (True,False):
            for elapsed in ([1] if previous else [1,16,24,28,30,32,36]):
                rows.append(simulate(burst,rx,tx,elapsed,previous))
    stable=[x for x in rows if x['publication']=='previous protected block']
    assert all(x['irq_period_words']==[32] and x['sequence_discontinuities']==0 for x in stable)
    assert all(x['modeled_label_age_words']==[96] for x in stable)
    # A fast but unsafe post-DSP publish produces mixed/stale blocks in this
    # independent event model once its actual TX-fetch deadline is exceeded.
    negative=next(x for x in rows if x['burst_words']==16 and x['tx_watermark']==16 and
        x['publication']=='current completed block' and x['publication_after_irq_us']==156.25)
    assert negative['sequence_discontinuities']>0
    phases=[simulate(16,16,16,1,rx_start_words=phase) for phase in (0,1,4,8,16,24,31)]
    assert len({tuple(x['modeled_label_age_words']) for x in phases})>1
    result=dict(status='PASS_OFFLINE_AUDIO_SCHEDULING_AUDIT',
        elf_sha256=hashlib.sha256(a.elf.read_bytes()).hexdigest(),
        stock_sha256=hashlib.sha256(stock).hexdigest(),
        actual_setup=dict(serial_words_per_frame=4,bits_per_word=32,
          tx_fifo_watermark=txw,rx_fifo_watermark=rxw,descriptors=descriptors,
          frames_per_burst=4,frames_per_interrupt=8),event_model_cases=rows,
        unknown_start_phase_cases=phases,
        findings=['Eight-frame DSP remains fixed when only FIFO watermarks/burst sizes change.',
          'In this synchronous model, reducing FIFO depth alone changes refill margin but not label latency.',
          'Removing the protected block can save eight frames only if output is ready before every TX fetch.',
          'Current direct-after-DSP output misses that deadline in longer synthetic processing cases.',
          'Unknown RX/TX startup phase changes the predicted delay; a physical phase snapshot is required.'],
        source_manual='NXP IMXRT1170RM Rev 5, 58.3.6.1, pp.3476-3477: TX <= watermark; RX > watermark.',
        device_access=False,host_audio_access=False,physical_latency_measured=False,
        limits=['The modeled 0.5 ms serial-label age is NOT measured guitar-to-headphone latency.',
          'Excludes codec/filter delay, channel-slot phase, bus service time, preemption and real start phase.',
          'Synthetic execution times are swept inputs, not measured Cortex-M7 cycles; >= one IRQ period cannot be sustainable.',
          'TX watermark zero is an idealized bound with no FIFO reserve at request time, not a recommended setting.',
          'No production driver change or installable image is created.'])
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
    print(json.dumps(stable,indent=2))


if __name__=='__main__':main()
