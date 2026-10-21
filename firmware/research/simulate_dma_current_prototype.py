"""Finite-service FIFO/DMA model using the prototype's observed ARM store order.

The timing inputs are explicit hypotheses. Historical19 whole-IRQ measurements
are only publication-time proxies, not measurements of this candidate. Tests
intentionally include corrupt output and starvation; these are release blockers.
No device, audio API, updater or firmware image access.
"""
import argparse
from collections import deque
import hashlib
import heapq
import json
import math
from pathlib import Path

SUB = 16  # Resolution: one sixteenth of a 32-bit serial word, not a CPU cycle.


def simulate(stores, watermark=8, previous=False, publish_end=18, spread=1,
             irq_jitter=0, tx_stall=0, rx_stall=0, beat_ticks=0, rx_start=1,
             frames=400):
    fifo_tx, fifo_rx = deque(), deque()
    memory_tx, memory_rx = [None]*64, [None]*64
    cursor_tx=cursor_rx=0; busy_tx=busy_rx=False
    queue=[]; sequence=0; emitted=[]; irqs=[]; cpu_end=0
    underrun=overflow=overlap=0; previous_payload=[None]*32
    store_order=[s['offset']//4 for s in stores]
    assert sorted(store_order)==list(range(32))
    first,last=stores[0]['instruction'],stores[-1]['instruction']
    assert last>first

    def event(t, priority, kind, payload=None):
        nonlocal sequence
        sequence+=1; heapq.heappush(queue,(t,priority,sequence,kind,payload))

    def request_tx(now):
        nonlocal busy_tx
        if not busy_tx and len(fifo_tx)<=watermark:
            busy_tx=True; event(now+round(tx_stall*SUB),1,'tx',0)

    def request_rx(now):
        nonlocal busy_rx
        if not busy_rx and len(fifo_rx)>16:
            busy_rx=True; event(now+round(rx_stall*SUB),2,'rx',0)

    # Match the preceding idealized model's startup prefill. Initial values are
    # zero, excluded from the settled analysis; real startup phase is unknown.
    while len(fifo_tx)<=watermark:
        for _ in range(16):
            fifo_tx.append(memory_tx[cursor_tx]); cursor_tx=(cursor_tx+1)%64
    for word in range(1,frames*4+1): event(word*SUB,0,'clock',word)
    while queue:
        now,_,_,kind,payload=heapq.heappop(queue)
        if now>frames*4*SUB: break
        if kind=='clock':
            if fifo_tx: emitted.append((fifo_tx.popleft(),now//SUB))
            else:
                emitted.append((None,now//SUB))
                if now>128*SUB: underrun+=1
            request_tx(now)
            if payload>rx_start:
                fifo_rx.append(payload)
                if len(fifo_rx)>32: overflow+=1
            request_rx(now)
        elif kind=='tx':
            fifo_tx.append(memory_tx[cursor_tx]); cursor_tx=(cursor_tx+1)%64
            if len(fifo_tx)>32: overflow+=1
            if payload<15: event(now+beat_ticks,1,'tx',payload+1)
            else: busy_tx=False; request_tx(now)
        elif kind=='rx':
            assert fifo_rx, 'RX service outran available input'
            memory_rx[cursor_rx]=fifo_rx.popleft(); cursor_rx=(cursor_rx+1)%64
            if payload<15: event(now+beat_ticks,2,'rx',payload+1)
            else:
                busy_rx=False
                if cursor_rx%32==0:
                    half=(cursor_rx-32)%64; current=memory_rx[half:half+32]
                    data=previous_payload[:] if previous else current[:]
                    previous_payload=current[:]; irqs.append(now)
                    # Alternate the injected delay to expose variable-latency
                    # phase errors. A busy CPU cannot re-enter the same IRQ.
                    jitter=irq_jitter if len(irqs)%2 else 0
                    entry=max(now+round(jitter*SUB),cpu_end)
                    if entry>now+round(jitter*SUB): overlap+=1
                    end=entry+round(publish_end*SUB)
                    cpu_end=end
                    # Real callback clears the target half before processing.
                    for i in range(32): event(entry,3,'store',(half+i,None))
                    for s in stores:
                        position=(s['instruction']-first)/(last-first)
                        due=end-round((1-position)*spread*SUB)
                        assert due>=entry
                        i=s['offset']//4; event(due,3,'store',(half+i,data[i]))
                request_rx(now)
        else:
            i,value=payload; memory_tx[i]=value
    observed=[(label,t) for label,t in emitted if 192<t<frames*4-128]
    missing=sum(label is None for label,t in observed)
    valid=[(label,t) for label,t in observed if label is not None]
    ages=sorted(set(t-label for label,t in valid))
    discontinuities=sum(b!=a+1 for (a,_),(b,_) in zip(valid,valid[1:]))
    good=not(underrun or overflow or overlap or missing or discontinuities) and len(ages)==1
    return dict(safe_in_model=good,serial_label_age_words=ages,
                sequence_discontinuities=discontinuities,missing_output_words=missing,
                fifo_underruns=underrun,fifo_overflows=overflow,cpu_overlap_events=overlap,
                irq_period_subticks=sorted(set(b-a for a,b in zip(irqs,irqs[1:]))))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['arm_report','phase_report','report']: p.add_argument(name,type=Path)
    a=p.parse_args(); arm=json.loads(a.arm_report.read_text()); phase=json.loads(a.phase_report.read_text())
    assert arm['status']=='PASS_OFFLINE_DMA_CURRENT_PROTOTYPE'
    stores=arm['instruction_store_trace']['stores'][32:]
    # These values independently reproduce the previous idealized event model.
    old=simulate(stores,watermark=16,previous=True,publish_end=1,spread=0)
    changed=simulate(stores,publish_end=18,spread=0)
    unsafe_old=simulate(stores,watermark=16,publish_end=18,spread=0)
    assert old['safe_in_model'] and old['serial_label_age_words']==[95],old
    assert changed['safe_in_model'] and changed['serial_label_age_words']==[63],changed
    assert not unsafe_old['safe_in_model'],unsafe_old
    # Coincident first store/fetch is too late. 22-word deadline at this phase.
    safe=simulate(stores,publish_end=21,spread=0)
    equal=simulate(stores,publish_end=22,spread=0)
    assert safe['safe_in_model'] and not equal['safe_in_model']
    late=simulate(stores,publish_end=24,spread=1)
    starved=simulate(stores,tx_stall=10,beat_ticks=2)
    slow_rx=simulate(stores,rx_stall=24,beat_ticks=2)
    overloaded=simulate(stores,publish_end=34,spread=1)
    assert not late['safe_in_model'] and late['missing_output_words']>0
    assert not starved['safe_in_model'] and starved['fifo_underruns']>0
    assert not slow_rx['safe_in_model'] and slow_rx['fifo_overflows']>0
    assert not overloaded['safe_in_model'] and overloaded['cpu_overlap_events']>0
    screens=[]
    profiles=[('instantaneous',0,0,0),('small-service',2,1,1),
              ('larger-service',4,2,2),('near-empty-TX',8,2,2)]
    for case in phase['cases']:
        proxy=math.ceil(case['whole_irq_proxy_in_serial_word_times'])
        for name,tx,rx,beat in profiles:
            for jitter in (0,2,4,8):
                for spread in (1,2):
                    result=simulate(stores,publish_end=proxy,spread=spread,
                                    irq_jitter=jitter,tx_stall=tx,rx_stall=rx,beat_ticks=beat)
                    screens.append(dict(case=case['case'],service_profile=name,
                        whole_IRQ_proxy_words=proxy,extra_IRQ_delay_words=jitter,
                        TX_arbitration_delay_words=tx,RX_arbitration_delay_words=rx,
                        bus_beat_subticks=beat,publication_span_words=spread,result=result))
    phase_sweep=[dict(rx_start_words=s,result=simulate(stores,rx_start=s)) for s in range(16)]
    report=dict(status='PASS_OFFLINE_DMA_MODEL_INCLUDING_EXPECTED_FAILURES',
        candidate_elf_sha256=arm['elf_sha256'],
        inputs_sha256={k:hashlib.sha256(getattr(a,k).read_bytes()).hexdigest() for k in ['arm_report','phase_report']},
        word_rate_hz=192000,subticks_per_word=SUB,tx_watermark=8,rx_watermark=16,burst_words=16,
        baseline19=old,candidate_ideal=changed,current_block_without_retiming=unsafe_old,
        modeled_source_age_reduction_samples=8,modeled_reduction_ms=8/48,
        negative_controls=dict(exact_deadline=equal,late_publication=late,TX_starvation=starved,
                               RX_overflow=slow_rx,CPU_overload=overloaded),
        cases=screens,case_count=len(screens),passes=sum(r['result']['safe_in_model'] for r in screens),
        failures=sum(not r['result']['safe_in_model'] for r in screens),startup_phase_sweep=phase_sweep,
        device_access=False,host_audio_access=False,physical_latency_measured=False,ready_to_flash=False,
        limits=['Historical19 whole IRQ duration is a proxy for candidate publication completion, not a measured deadline.',
                'Store order is actual compiled ARM; store durations/visibility and all service delays are synthetic.',
                'RX and TX service use independently injected delays, not a cycle-accurate shared bus arbiter.',
                'No cache, peripheral synchronizer, interrupt-priority or electrical codec model.',
                'Modeled labels are serial words, not guitar-to-headphone analog latency.',
                'The current GPT guard is too late for some DMA races; expected failures block physical installation.'])
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],len(screens),'screens;',report['passes'],'pass;',report['failures'],'expected failures')


if __name__=='__main__': main()
