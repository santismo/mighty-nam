"""Decode NAMLNK19 raw diagnostic words. Pure offline arithmetic; no device I/O."""
import argparse,json
from pathlib import Path
FIELDS=['epoch_before','ctrl_before','cycles_before','rx_next_before','tx_next_before',
 'rx_destination_before','tx_source_before','rx_doff_citer_before','tx_doff_citer_before',
 'tx_fifo','rx_fifo','tx_status','rx_status','rx_next_after','tx_next_after',
 'rx_destination_after','tx_source_after','rx_doff_citer_after','tx_doff_citer_after',
 'cycles_after','ctrl_after','epoch_after','irq_sequence','published_tx_half']
def phase(words):
 if len(words)!=24:raise ValueError('Expected 24 words per phase')
 d=dict(zip(FIELDS,words));d['counter_valid']=(d['ctrl_before']&1)!=0 and d['ctrl_before']==d['ctrl_after'] and d['epoch_before']==d['epoch_after'] and 0<(d['cycles_after']-d['cycles_before'])&0xffffffff<0x80000000
 d['read_span_cycles']=(d['cycles_after']-d['cycles_before'])&0xffffffff
 d['dma_changed_during_reads']=any(d[k+'_before']!=d[k+'_after'] for k in ['rx_next','tx_next','rx_destination','tx_source','rx_doff_citer','tx_doff_citer'])
 for side in ['rx','tx']:
  word=d[side+'_fifo'];d[side+'_fifo_occupancy'] = ((word>>16)-(word&63))&63
  d[side+'_fifo_occupancy_valid']=d[side+'_fifo_occupancy']<=32
  d[side+'_fifo_error']=bool(d[side+'_status']&(1<<18))
  d[side+'_sync_error']=bool(d[side+'_status']&(1<<19))
 return d

def decode(words):
 if len(words)!=48 or any(type(x)!=int or x<0 or x>0xffffffff for x in words):raise ValueError('Expected 48 uint32 words')
 a,b=phase(words[:24]),phase(words[24:]);span=(b['cycles_after']-a['cycles_before'])&0xffffffff
 valid=a['counter_valid'] and b['counter_valid'] and a['epoch_after']==b['epoch_before'] and a['ctrl_after']==b['ctrl_before'] and a['irq_sequence']==b['irq_sequence'] and 0<span<0x80000000
 return dict(schema='nam-driver-timing-1',entry=a,publication=b,counter_span_valid=valid,entry_to_publication_cycles=span if valid else None,
  physical_deadline_proven=False,limits=['Non-atomic time-bracketed observations; DMA may advance between reads.',
  'Cycle counts include the diagnostic overhead and are not calibrated to milliseconds.',
  'A stable pair of cursors cannot exclude an ABA/wrap race; repeat observations and inspect phase.',
  'Does not measure converter or analog headphone latency.'])
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);a=p.parse_args();data=json.loads(a.input.read_text());
 if isinstance(data,dict):
  if data.get('status')!='DIAGNOSTIC_READ_COMPLETE':raise ValueError('Collector did not complete')
  data=data['words']
 print(json.dumps(decode(data),indent=2))
